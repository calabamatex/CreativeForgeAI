"""ARQ worker configuration for background job processing."""

import os

from arq.connections import RedisSettings

from src.jobs.tasks import process_campaign_job


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


async def startup(ctx):
    """Initialize worker resources on startup."""
    pass


async def shutdown(ctx):
    """Cleanup worker resources on shutdown."""
    pass


class WorkerSettings:
    """ARQ worker settings."""

    functions = [process_campaign_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 5
    job_timeout = 600  # 10 minutes
