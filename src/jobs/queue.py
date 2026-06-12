"""ARQ Redis pool accessor for enqueuing background jobs from the API.

The API process needs a (write-only) handle to the same Redis that the ARQ
worker (:mod:`src.jobs.worker`) consumes from. This module builds that pool
from the ``REDIS_URL`` environment variable -- the SAME DSN the worker uses --
so producer and consumer always agree on the broker.

Kept intentionally tiny: one function to open the pool, one to close it. The
FastAPI lifespan (:mod:`src.api.main`) owns the lifecycle and stores the pool on
``app.state.arq_pool``; the ``get_arq_pool`` dependency hands it to routes.
"""

from __future__ import annotations

import os

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

# Same default + env var as src.jobs.worker so producer/consumer match.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _redis_settings() -> RedisSettings:
    """Build :class:`RedisSettings` from ``REDIS_URL`` (read at call time)."""
    return RedisSettings.from_dsn(os.getenv("REDIS_URL", REDIS_URL))


async def create_arq_pool() -> ArqRedis:
    """Open and return an ARQ Redis pool for enqueuing jobs."""
    return await create_pool(_redis_settings())


async def close_arq_pool(pool: ArqRedis | None) -> None:
    """Close an ARQ Redis pool opened by :func:`create_arq_pool`."""
    if pool is None:
        return
    await pool.aclose()
