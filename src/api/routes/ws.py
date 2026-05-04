"""WebSocket endpoint for real-time generation progress."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/generation/{job_id}")
async def generation_progress(websocket: WebSocket, job_id: str):
    """Stream real-time generation progress for a job."""
    await websocket.accept()
    logger.info("ws.connected", job_id=job_id)

    try:
        while True:
            # In production, subscribe to Redis pub/sub for job updates.
            # For now, send heartbeat to keep connection alive.
            await websocket.send_json({
                "type": "heartbeat",
                "job_id": job_id,
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("ws.disconnected", job_id=job_id)
