"""Integration test for the real-progress WebSocket (P3-T4).

Asserts that ``/ws/generation/{job_id}`` streams the ACTUAL job state
(``progress_percent`` / ``current_stage`` / ``status``) by polling the real
``jobs`` row, emits a terminal message, and then CLOSES — i.e. no infinite
heartbeat-only loop remains.

Why an in-loop ASGI WebSocket driver instead of Starlette's ``TestClient``:
the real-DB harness gives us an ``AsyncSession`` bound to a per-test event loop
inside an outer transaction/savepoint (see ``conftest.real_db_session``).
``TestClient.websocket_connect`` runs the app on a *separate* portal/loop, which
cannot share that session. So we speak the ASGI ``websocket`` protocol to the
app directly on the test's own event loop via :class:`_ASGIWebSocketClient`,
and drive the job-state changes from the same loop. Everything stays on one
loop, sharing the isolated session, fully deterministic.

No paid calls, no external services: pure DB-row mutations drive the stream.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.api.dependencies import check_rate_limit, get_db
from src.db.models import Campaign, Job

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

WS_PATH_TEMPLATE = "/ws/generation/{job_id}"


# ---------------------------------------------------------------------------
# Minimal in-loop ASGI WebSocket client
# ---------------------------------------------------------------------------


class _ASGIWebSocketClient:
    """Drive an ASGI app's ``websocket`` endpoint on the current event loop.

    Implements just enough of the ASGI websocket protocol to: connect, receive
    JSON text frames, and observe the server-side close. The app coroutine runs
    as a background task; ``send``/``receive`` queues bridge the two sides.
    """

    def __init__(self, app, path: str):
        self._app = app
        self._scope = {
            "type": "websocket",
            "path": path,
            "raw_path": path.encode(),
            "headers": [],
            "query_string": b"",
            "subprotocols": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "ws",
        }
        # Messages from app -> client (accept / text / close).
        self._from_app: asyncio.Queue = asyncio.Queue()
        # Messages from client -> app (connect / disconnect).
        self._to_app: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self.closed = False
        self.close_code: int | None = None

    async def _receive(self):
        return await self._to_app.get()

    async def _send(self, message):
        await self._from_app.put(message)

    async def __aenter__(self):
        # Kick off the handshake: client requests connect.
        await self._to_app.put({"type": "websocket.connect"})
        self._task = asyncio.ensure_future(
            self._app(self._scope, self._receive, self._send)
        )
        # Expect the server to accept.
        msg = await asyncio.wait_for(self._from_app.get(), timeout=5)
        assert msg["type"] == "websocket.accept", msg
        return self

    async def receive_json(self, timeout: float = 5.0):
        """Return the next text frame as JSON, or raise on close/timeout."""
        import json

        msg = await asyncio.wait_for(self._from_app.get(), timeout=timeout)
        if msg["type"] == "websocket.close":
            self.closed = True
            self.close_code = msg.get("code", 1000)
            raise _WSClosed(self.close_code)
        assert msg["type"] == "websocket.send", msg
        return json.loads(msg["text"])

    async def expect_close(self, timeout: float = 5.0):
        """Assert the next frame is a server close."""
        msg = await asyncio.wait_for(self._from_app.get(), timeout=timeout)
        assert msg["type"] == "websocket.close", f"expected close, got {msg}"
        self.closed = True
        self.close_code = msg.get("code", 1000)

    async def __aexit__(self, exc_type, exc, tb):
        # Tell the app the client went away, then let the task finish.
        await self._to_app.put({"type": "websocket.disconnect", "code": 1000})
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, _WSClosed):
                self._task.cancel()
        return False


class _WSClosed(Exception):
    """Raised by the client when the server closes the socket."""

    def __init__(self, code: int):
        self.code = code
        super().__init__(f"websocket closed (code={code})")


# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------


async def _seed_campaign_and_job(session, *, status: str = "queued") -> tuple[str, str]:
    """Insert a minimal campaign + job; return ``(campaign_id, job_id)`` strs."""
    creator_id = uuid.uuid4()

    from src.db.models import User
    from datetime import datetime, timezone

    user = User(
        id=creator_id,
        email=f"ws-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.unused",
        display_name="WS Tester",
        role="editor",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()

    campaign = Campaign(
        id=uuid.uuid4(),
        campaign_id=f"WS-{uuid.uuid4().hex[:8]}",
        campaign_name="WS Progress Campaign",
        brand_name="TechStyle",
        status="processing",
        image_backend="firefly",
        brief={"headline": "x"},
        target_locales=["en-US"],
        aspect_ratios=["1:1"],
        created_by=creator_id,
    )
    session.add(campaign)
    await session.flush()

    job = Job(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        status=status,
        progress_percent=0,
    )
    session.add(job)
    await session.flush()

    return str(campaign.id), str(job.id)


def _make_app(real_db_session):
    """Build the app with ``get_db`` overridden to the isolated test session."""
    from src.api.main import create_app

    app = create_app()

    async def _override_db():
        yield real_db_session

    async def _no_rate_limit():
        pass

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[check_rate_limit] = _no_rate_limit
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_ws_streams_real_progress_then_closes_on_terminal(real_db_session):
    """The socket emits INCREASING real progress and a terminal ``completed``.

    Drives the job row through 25 -> 60 -> 100/completed from the same loop and
    asserts the client sees those exact real fields (not a fake heartbeat), in
    increasing order, followed by a terminal ``completed`` message, after which
    the socket CLOSES.
    """
    session = real_db_session
    campaign_id, job_id = await _seed_campaign_and_job(session, status="queued")

    from src.db.repositories import JobRepository

    repo = JobRepository(session)
    app = _make_app(session)

    received: list[dict] = []

    async def _advance():
        """Step the job through real progress states with small gaps."""
        # Let the WS connect + emit the initial (queued, 0) frame.
        await asyncio.sleep(0.6)
        await repo.update_progress(uuid.UUID(job_id), 25, "validating")
        await session.commit()
        await asyncio.sleep(0.6)
        await repo.update_progress(uuid.UUID(job_id), 60, "generating")
        await session.commit()
        await asyncio.sleep(0.6)
        await repo.complete(uuid.UUID(job_id), result={"ok": True})
        await session.commit()

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id)) as ws:
        advancer = asyncio.ensure_future(_advance())
        try:
            while True:
                msg = await ws.receive_json(timeout=10)
                received.append(msg)
                if msg.get("status") in {"completed", "failed", "cancelled"}:
                    # After a terminal progress frame the server must close.
                    await ws.expect_close(timeout=5)
                    break
        finally:
            await advancer

    # --- assertions --------------------------------------------------------
    # Every message carries REAL job fields, never a bare heartbeat.
    assert received, "no messages received"
    assert all(m["type"] in {"progress"} for m in received), received
    assert all(m["job_id"] == job_id for m in received)
    assert not any(m.get("type") == "heartbeat" for m in received), (
        "heartbeat-only loop still present"
    )

    # Progress is non-decreasing and includes the real intermediate values.
    progresses = [m["progress_percent"] for m in received]
    assert progresses == sorted(progresses), f"progress not monotonic: {progresses}"
    assert 25 in progresses and 60 in progresses, progresses

    # Real stage names came through.
    stages = [m.get("current_stage") for m in received]
    assert "validating" in stages and "generating" in stages, stages

    # Terminal message: completed at 100, and the socket is now closed.
    terminal = received[-1]
    assert terminal["status"] == "completed"
    assert terminal["progress_percent"] == 100
    assert ws.closed is True


async def test_ws_already_terminal_sends_state_once_and_closes(real_db_session):
    """A job already ``failed`` at connect → one terminal frame, then close."""
    session = real_db_session
    campaign_id, job_id = await _seed_campaign_and_job(session, status="queued")

    from src.db.repositories import JobRepository

    repo = JobRepository(session)
    await repo.fail(uuid.UUID(job_id), "boom", "trace")
    await session.commit()

    app = _make_app(session)

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id)) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "progress"
        assert msg["status"] == "failed"
        assert msg["job_id"] == job_id
        await ws.expect_close(timeout=5)

    assert ws.closed is True


async def test_ws_unknown_job_sends_error_and_closes(real_db_session):
    """A nonexistent job id → terminal error frame, then close (no hang)."""
    session = real_db_session
    app = _make_app(session)
    missing_job_id = str(uuid.uuid4())

    async with _ASGIWebSocketClient(
        app, WS_PATH_TEMPLATE.format(job_id=missing_job_id)
    ) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "error"
        assert msg["status"] == "not_found"
        assert msg["job_id"] == missing_job_id
        await ws.expect_close(timeout=5)

    assert ws.closed is True
