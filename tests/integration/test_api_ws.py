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
from datetime import UTC

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

    def __init__(self, app, path: str, query_string: bytes = b""):
        self._app = app
        self._scope = {
            "type": "websocket",
            "path": path,
            "raw_path": path.encode(),
            "headers": [],
            "query_string": query_string,
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
        self._task = asyncio.ensure_future(self._app(self._scope, self._receive, self._send))
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
            except (TimeoutError, _WSClosed):
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


async def _seed_campaign_and_job(session, *, status: str = "queued") -> tuple[str, str, uuid.UUID]:
    """Insert a minimal campaign + job.

    Returns ``(campaign_id, job_id, owner_id)`` where ``owner_id`` is the
    campaign's ``created_by`` (the user authorized to stream the job).
    """
    creator_id = uuid.uuid4()

    from datetime import datetime

    from src.db.models import User

    user = User(
        id=creator_id,
        email=f"ws-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.unused",
        display_name="WS Tester",
        role="editor",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
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

    return str(campaign.id), str(job.id), creator_id


def _owner_token(owner_id: uuid.UUID, role: str = "editor") -> str:
    """Mint an access token for the job's owner."""
    from src.api.dependencies import create_access_token

    return create_access_token(str(owner_id), role)


def _ws_query(token: str) -> bytes:
    """Build a ``?token=...`` query string for the WS handshake scope."""
    return f"token={token}".encode()


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


async def test_ws_streams_real_progress_then_closes_on_terminal(real_db_session, monkeypatch):
    """The socket emits INCREASING real progress and a terminal ``completed``.

    Drives the job row through 25 -> 60 -> 100/completed and asserts the client
    sees those exact real fields (not a fake heartbeat), in increasing order,
    followed by a terminal ``completed`` message, after which the socket CLOSES.

    DETERMINISM (P6-T1 flake fix): the previous version started a background
    ``_advance()`` task that mutated the row on a fixed ``asyncio.sleep(0.6)``
    cadence, RACING the server's 0.5s poll loop — occasionally a transition
    landed between two polls and a frame was missed/merged, flaking the run.
    This version instead:

      * shrinks the server poll interval to ~10ms via ``WS_POLL_INTERVAL_SECONDS``
        (read at connection time by ``src.api.routes.ws``), and
      * drives each transition IN LOCKSTEP with the received frames: it reads
        the next CHANGED frame, then applies the next transition, then reads the
        next changed frame, etc.

    Because the endpoint emits ONLY on a changed ``(progress, stage, status)``
    signature, advancing strictly after observing the prior frame guarantees we
    see every distinct state exactly once, in order — no wall-clock race.
    """
    # Drive the server poll loop fast so each transition is observed promptly,
    # then synchronize on the emitted frames (below) for determinism.
    monkeypatch.setenv("WS_POLL_INTERVAL_SECONDS", "0.01")

    session = real_db_session
    campaign_id, job_id, owner_id = await _seed_campaign_and_job(session, status="queued")

    from src.db.repositories import JobRepository

    repo = JobRepository(session)
    app = _make_app(session)
    token = _owner_token(owner_id)

    received: list[dict] = []

    async def _read_next_changed(ws, after_progress: int) -> dict:
        """Return the next frame whose progress advanced past *after_progress*.

        The fast poll loop can re-emit the current state at most once before our
        transition commits; skip any frame that has not advanced so we
        deterministically land on the NEXT distinct state.
        """
        while True:
            msg = await ws.receive_json(timeout=10)
            received.append(msg)
            if msg["progress_percent"] > after_progress:
                return msg

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id), query_string=_ws_query(token)) as ws:
        # 1) Initial real frame: queued at 0.
        first = await ws.receive_json(timeout=10)
        received.append(first)
        assert first["progress_percent"] == 0 and first["status"] == "queued"

        # 2) Advance to 25/validating, then read the frame that reflects it.
        await repo.update_progress(uuid.UUID(job_id), 25, "validating")
        await session.commit()
        frame_25 = await _read_next_changed(ws, after_progress=0)
        assert frame_25["progress_percent"] == 25
        assert frame_25["current_stage"] == "validating"

        # 3) Advance to 60/generating, then read the frame that reflects it.
        await repo.update_progress(uuid.UUID(job_id), 60, "generating")
        await session.commit()
        frame_60 = await _read_next_changed(ws, after_progress=25)
        assert frame_60["progress_percent"] == 60
        assert frame_60["current_stage"] == "generating"

        # 4) Complete -> terminal frame at 100/completed, then the server closes.
        await repo.complete(uuid.UUID(job_id), result={"ok": True})
        await session.commit()
        terminal_frame = await _read_next_changed(ws, after_progress=60)
        assert terminal_frame["status"] == "completed"
        await ws.expect_close(timeout=5)

    # --- assertions --------------------------------------------------------
    # Every message carries REAL job fields, never a bare heartbeat.
    assert received, "no messages received"
    assert all(m["type"] in {"progress"} for m in received), received
    assert all(m["job_id"] == job_id for m in received)
    assert not any(m.get("type") == "heartbeat" for m in received), "heartbeat-only loop still present"

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
    campaign_id, job_id, owner_id = await _seed_campaign_and_job(session, status="queued")

    from src.db.repositories import JobRepository

    repo = JobRepository(session)
    await repo.fail(uuid.UUID(job_id), "boom", "trace")
    await session.commit()

    app = _make_app(session)
    token = _owner_token(owner_id)

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id), query_string=_ws_query(token)) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "progress"
        assert msg["status"] == "failed"
        assert msg["job_id"] == job_id
        await ws.expect_close(timeout=5)

    assert ws.closed is True


async def test_ws_unknown_job_sends_error_and_closes(real_db_session):
    """A nonexistent job id → terminal error frame, then close (no hang)."""
    session = real_db_session
    # Seed a real user so the handshake authenticates; then connect to a job id
    # that does not exist so the post-auth lookup yields not_found.
    _c, _j, owner_id = await _seed_campaign_and_job(session, status="queued")
    app = _make_app(session)
    token = _owner_token(owner_id)
    missing_job_id = str(uuid.uuid4())

    async with _ASGIWebSocketClient(
        app, WS_PATH_TEMPLATE.format(job_id=missing_job_id), query_string=_ws_query(token)
    ) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "error"
        assert msg["status"] == "not_found"
        assert msg["job_id"] == missing_job_id
        await ws.expect_close(timeout=5)

    assert ws.closed is True


# ---------------------------------------------------------------------------
# WebSocket authentication + authorization  (P4-T1)
# ---------------------------------------------------------------------------


async def test_ws_rejects_missing_token(real_db_session):
    """No ``?token=`` and no cookie → unauthorized error + close 4401."""
    session = real_db_session
    _c, job_id, _owner = await _seed_campaign_and_job(session, status="queued")
    app = _make_app(session)

    from src.api.routes.ws import WS_CLOSE_UNAUTHENTICATED

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id)) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "error"
        assert msg["status"] == "unauthorized"
        await ws.expect_close(timeout=5)

    assert ws.closed is True
    assert ws.close_code == WS_CLOSE_UNAUTHENTICATED


async def test_ws_rejects_invalid_token(real_db_session):
    """A malformed/garbage token → unauthorized + close 4401 (no streaming)."""
    session = real_db_session
    _c, job_id, _owner = await _seed_campaign_and_job(session, status="queued")
    app = _make_app(session)

    from src.api.routes.ws import WS_CLOSE_UNAUTHENTICATED

    async with _ASGIWebSocketClient(
        app,
        WS_PATH_TEMPLATE.format(job_id=job_id),
        query_string=_ws_query("definitely.not.a.valid.jwt"),
    ) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "error"
        assert msg["status"] == "unauthorized"
        await ws.expect_close(timeout=5)

    assert ws.closed is True
    assert ws.close_code == WS_CLOSE_UNAUTHENTICATED


async def test_ws_rejects_revoked_token(real_db_session):
    """A revoked (denylisted) token → unauthorized + close 4401."""
    session = real_db_session
    _c, job_id, owner_id = await _seed_campaign_and_job(session, status="queued")
    app = _make_app(session)
    token = _owner_token(owner_id)

    # Revoke the token by denylisting its jti (as /auth/logout would).
    from jose import jwt as _jwt
    from src.cache import get_cache

    jti = _jwt.get_unverified_claims(token)["jti"]
    await get_cache().connect()
    await get_cache().denylist_jti(jti, 300)

    from src.api.routes.ws import WS_CLOSE_UNAUTHENTICATED

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id), query_string=_ws_query(token)) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "error"
        assert msg["status"] == "unauthorized"
        await ws.expect_close(timeout=5)

    assert ws.closed is True
    assert ws.close_code == WS_CLOSE_UNAUTHENTICATED


async def test_ws_owner_can_stream(real_db_session):
    """A valid token for a job you OWN streams the terminal state and closes."""
    session = real_db_session
    _c, job_id, owner_id = await _seed_campaign_and_job(session, status="queued")

    from src.db.repositories import JobRepository

    repo = JobRepository(session)
    await repo.complete(uuid.UUID(job_id), result={"ok": True})
    await session.commit()

    app = _make_app(session)
    token = _owner_token(owner_id)

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id), query_string=_ws_query(token)) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "progress"
        assert msg["status"] == "completed"
        assert msg["job_id"] == job_id
        await ws.expect_close(timeout=5)

    assert ws.closed is True


async def test_ws_rejects_non_owner(real_db_session):
    """A valid token for a DIFFERENT user → forbidden + close 4403 (no stream)."""
    session = real_db_session
    _c, job_id, _owner_id = await _seed_campaign_and_job(session, status="queued")

    # Seed a SECOND, unrelated user and authenticate as them.
    from datetime import datetime

    from src.db.models import User

    other_id = uuid.uuid4()
    other = User(
        id=other_id,
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.unused",
        display_name="Other User",
        role="editor",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(other)
    await session.flush()

    app = _make_app(session)
    token = _owner_token(other_id)

    from src.api.routes.ws import WS_CLOSE_FORBIDDEN

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id), query_string=_ws_query(token)) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "error"
        assert msg["status"] == "forbidden"
        await ws.expect_close(timeout=5)

    assert ws.closed is True
    assert ws.close_code == WS_CLOSE_FORBIDDEN


async def test_ws_admin_can_stream_any_job(real_db_session):
    """An admin token streams a job owned by someone else (admin override)."""
    session = real_db_session
    _c, job_id, _owner_id = await _seed_campaign_and_job(session, status="queued")

    from datetime import datetime

    from src.db.models import User

    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id,
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.unused",
        display_name="Admin User",
        role="admin",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(admin)
    await session.flush()

    from src.db.repositories import JobRepository

    await JobRepository(session).complete(uuid.UUID(job_id), result={"ok": True})
    await session.commit()

    app = _make_app(session)
    token = _owner_token(admin_id, role="admin")

    async with _ASGIWebSocketClient(app, WS_PATH_TEMPLATE.format(job_id=job_id), query_string=_ws_query(token)) as ws:
        msg = await ws.receive_json(timeout=5)
        assert msg["type"] == "progress"
        assert msg["status"] == "completed"
        await ws.expect_close(timeout=5)

    assert ws.closed is True
