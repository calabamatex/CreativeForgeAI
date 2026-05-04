"""Repository for Job CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models import Job
from src.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


class JobRepository:
    """Async CRUD operations for the jobs table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, campaign_id: uuid.UUID) -> Job:
        """Create a new job for a campaign.

        The job is initialized with ``status="queued"`` and ``progress_percent=0``.

        Args:
            campaign_id: FK to the parent campaign.

        Returns:
            The newly created ``Job`` instance.
        """
        job = Job(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            status="queued",
            progress_percent=0,
        )
        self._session.add(job)
        await self._session.flush()
        logger.info(
            "job.created",
            job_id=str(job.id),
            campaign_id=str(campaign_id),
        )
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        """Return a job by primary key, or ``None``."""
        stmt = select(Job).where(Job.id == job_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_campaign(self, campaign_id: uuid.UUID) -> Job | None:
        """Return the most recent job for a given campaign, or ``None``.

        Args:
            campaign_id: FK to the parent campaign.

        Returns:
            The latest ``Job`` for this campaign, or ``None``.
        """
        stmt = (
            select(Job)
            .where(Job.campaign_id == campaign_id)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_progress(
        self,
        job_id: uuid.UUID,
        progress_percent: int,
        current_stage: str,
    ) -> Job:
        """Update a job's progress and current stage.

        If the job has not been started yet (``started_at`` is ``None``),
        sets ``started_at`` to now and transitions status to ``"running"``.

        Args:
            job_id: Primary key of the job.
            progress_percent: Integer 0-100.
            current_stage: Description of the current pipeline stage.

        Returns:
            The updated ``Job`` instance.

        Raises:
            NotFoundError: If the job does not exist.
        """
        job = await self.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job", str(job_id))

        now = datetime.now(timezone.utc)
        job.progress_percent = progress_percent
        job.current_stage = current_stage

        if job.started_at is None:
            job.started_at = now
            job.status = "running"

        await self._session.flush()
        logger.info(
            "job.progress",
            job_id=str(job_id),
            progress=progress_percent,
            stage=current_stage,
        )
        return job

    async def complete(
        self,
        job_id: uuid.UUID,
        result: dict[str, Any] | None = None,
    ) -> Job:
        """Mark a job as completed.

        Args:
            job_id: Primary key of the job.
            result: Optional result payload.

        Returns:
            The updated ``Job`` instance.

        Raises:
            NotFoundError: If the job does not exist.
        """
        job = await self.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job", str(job_id))

        now = datetime.now(timezone.utc)
        job.status = "completed"
        job.progress_percent = 100
        job.completed_at = now
        job.result = result

        await self._session.flush()
        logger.info("job.completed", job_id=str(job_id))
        return job

    async def fail(
        self,
        job_id: uuid.UUID,
        error_message: str,
        error_trace: str | None = None,
    ) -> Job:
        """Mark a job as failed.

        Args:
            job_id: Primary key of the job.
            error_message: Human-readable error description.
            error_trace: Optional full stack trace.

        Returns:
            The updated ``Job`` instance.

        Raises:
            NotFoundError: If the job does not exist.
        """
        job = await self.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job", str(job_id))

        now = datetime.now(timezone.utc)
        job.status = "failed"
        job.completed_at = now
        job.error_message = error_message
        job.error_trace = error_trace

        await self._session.flush()
        logger.error(
            "job.failed",
            job_id=str(job_id),
            error=error_message,
        )
        return job

    async def cancel(self, job_id: uuid.UUID) -> Job:
        """Mark a job as cancelled.

        Args:
            job_id: Primary key of the job.

        Returns:
            The updated ``Job`` instance.

        Raises:
            NotFoundError: If the job does not exist.
        """
        job = await self.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job", str(job_id))

        now = datetime.now(timezone.utc)
        job.status = "cancelled"
        job.completed_at = now

        await self._session.flush()
        logger.info("job.cancelled", job_id=str(job_id))
        return job

    async def list_jobs(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Job]:
        """Return a paginated list of jobs with optional status filter.

        Args:
            status: Optional status filter (e.g. ``"queued"``, ``"running"``).
            limit: Maximum number of rows.
            offset: Number of rows to skip.

        Returns:
            A list of ``Job`` instances ordered by ``created_at`` descending.
        """
        stmt = (
            select(Job)
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if status is not None:
            stmt = stmt.where(Job.status == status)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
