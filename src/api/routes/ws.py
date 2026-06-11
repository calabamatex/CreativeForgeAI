"""WebSocket endpoint for real-time generation progress.

Approach (P3-T4): **bounded DB polling**.

The worker (``src.jobs.tasks.process_campaign_job``) already writes real
progress to the ``jobs`` row on every transition: ``update_progress`` sets
``progress_percent`` / ``current_stage`` / ``status="running"``, and the
terminal ``complete`` / ``fail`` / ``cancel`` calls set the terminal
``status``. So the source of truth for "what is this job doing right now" is
the DB row, and no extra worker plumbing (Redis pub/sub, a publish call on
every progress update) is needed.

This endpoint therefore POLLS the job row on a fixed short interval and emits a
JSON message carrying the REAL fields (``progress_percent``, ``current_stage``,
``status``) **only when the observed state changes**, plus one final terminal
message (``status`` in :data:`TERMINAL_STATES`) before it CLOSES the socket. No
infinite heartbeat-only loop remains.

Loop-termination / backpressure guards (so it can NEVER loop forever):

* :data:`POLL_INTERVAL_SECONDS` — how often we re-read the row (0.5s).
* :data:`MAX_POLL_ITERATIONS` — a hard cap on the number of polls. Even if the
  worker dies and the job never reaches a terminal state, the socket is closed
  with a ``timeout`` message after ``MAX_POLL_ITERATIONS * POLL_INTERVAL``
  seconds (default 600 polls * 0.5s = 5 minutes) instead of hanging forever.
* Terminal state — as soon as ``status`` is terminal we emit it once and break.

Edge cases:

* Unknown / nonexistent ``job_id`` (or a non-UUID id) → send a terminal
  ``{"type": "error", "status": "not_found", ...}`` message and close. Never
  hang.
* Job already terminal at connect → emit the terminal state once and close.
* Client disconnect → caught via ``WebSocketDisconnect`` and logged; the loop
  exits cleanly.

The message field names match what the frontend ``useWebSocket.ts`` reads
(``type`` / ``job_id`` / ``status`` / ``progress_percent`` / ``current_stage``);
the frontend itself is out of scope here (Phase 5).
"""

import asyncio
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.dependencies import get_db
from src.db.repositories import JobRepository

logger = structlog.get_logger(__name__)

router = APIRouter()

# Terminal job states: once a job reaches one of these we emit it and close.
TERMINAL_STATES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})

# Poll the job row every 0.5s. Small enough to feel real-time, large enough not
# to hammer the DB.
POLL_INTERVAL_SECONDS: float = 0.5

# Hard cap on poll iterations so the loop can NEVER run forever (backpressure /
# safety guard). 600 * 0.5s = 5 minutes of wall-clock before we force-close a
# job that never reaches a terminal state.
MAX_POLL_ITERATIONS: int = 600


def _progress_payload(job_id: str, job) -> dict:
    """Build the progress message for a job row (real fields only)."""
    return {
        "type": "progress",
        "job_id": job_id,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "current_stage": job.current_stage,
    }


@router.websocket("/ws/generation/{job_id}")
async def generation_progress(
    websocket: WebSocket,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Stream REAL generation progress for ``job_id`` until it terminates.

    Polls the ``jobs`` row on :data:`POLL_INTERVAL_SECONDS` and forwards each
    observed change in ``(progress_percent, current_stage, status)``, then sends
    the terminal status and closes. See the module docstring for the full
    contract and guards.
    """
    await websocket.accept()
    logger.info("ws.connected", job_id=job_id)

    # Validate the job id up front: a non-UUID can never match a row, so treat
    # it like an unknown job (terminal error + close) rather than letting the
    # query raise.
    try:
        job_uuid = uuid.UUID(job_id)
    except (ValueError, AttributeError):
        await websocket.send_json(
            {
                "type": "error",
                "job_id": job_id,
                "status": "not_found",
                "message": "Invalid or unknown job id",
            }
        )
        await websocket.close()
        logger.info("ws.closed.invalid_job_id", job_id=job_id)
        return

    job_repo = JobRepository(db)
    last_signature: tuple | None = None

    try:
        for _ in range(MAX_POLL_ITERATIONS):
            # Drop any identity-map cache so a row mutated by the worker (in
            # another session / transaction) is re-read fresh every poll.
            db.expire_all()
            job = await job_repo.get_by_id(job_uuid)

            if job is None:
                # Unknown job id (or it disappeared): terminal error + close.
                await websocket.send_json(
                    {
                        "type": "error",
                        "job_id": job_id,
                        "status": "not_found",
                        "message": "Job not found",
                    }
                )
                await websocket.close()
                logger.info("ws.closed.not_found", job_id=job_id)
                return

            signature = (job.progress_percent, job.current_stage, job.status)
            if signature != last_signature:
                await websocket.send_json(_progress_payload(job_id, job))
                last_signature = signature

            if job.status in TERMINAL_STATES:
                # Terminal: we've already emitted this state above; close.
                await websocket.close()
                logger.info(
                    "ws.closed.terminal", job_id=job_id, status=job.status
                )
                return

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        # Exhausted the poll budget without reaching a terminal state: force a
        # clean close rather than hanging the client forever.
        await websocket.send_json(
            {
                "type": "timeout",
                "job_id": job_id,
                "status": "timeout",
                "message": "Progress stream timed out before the job terminated",
            }
        )
        await websocket.close()
        logger.warning("ws.closed.timeout", job_id=job_id)
    except WebSocketDisconnect:
        logger.info("ws.disconnected", job_id=job_id)
