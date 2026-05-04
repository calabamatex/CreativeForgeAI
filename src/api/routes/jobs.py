"""Job endpoints: list, detail, cancel."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.dependencies import (
    check_rate_limit,
    get_current_user,
    get_db,
    require_role,
)
from src.api.errors import BadRequestError, NotFoundError
from src.api.schemas import (
    Envelope,
    JobResponse,
    JobStatus,
    Meta,
    PaginatedEnvelope,
    PaginationMeta,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_job_or_404(job_id: uuid.UUID, db: AsyncSession):
    from src.db.models import Job  # noqa: E402

    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise NotFoundError("Job", str(job_id))
    return job


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedEnvelope[JobResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: JobStatus | None = Query(None),
    campaign_id: uuid.UUID | None = Query(None),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List jobs with pagination and optional filters."""
    from src.db.models import Job  # noqa: E402

    base = select(Job)
    count_q = select(func.count()).select_from(Job)

    if status:
        base = base.where(Job.status == status.value)
        count_q = count_q.where(Job.status == status.value)
    if campaign_id:
        base = base.where(Job.campaign_id == campaign_id)
        count_q = count_q.where(Job.campaign_id == campaign_id)

    total = (await db.execute(count_q)).scalar_one()
    total_pages = max(1, math.ceil(total / per_page))

    stmt = base.order_by(Job.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    items = [JobResponse.model_validate(j) for j in jobs]

    return PaginatedEnvelope[JobResponse](
        data=items,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


# ---------------------------------------------------------------------------
# GET /jobs/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/{job_id}",
    response_model=Envelope[JobResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def get_job(
    job_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current status of a single job."""
    job = await _get_job_or_404(job_id, db)
    return Envelope[JobResponse](
        data=JobResponse.model_validate(job),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# POST /jobs/{id}/cancel
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/cancel",
    response_model=Envelope[JobResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def cancel_job(
    job_id: uuid.UUID,
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a queued or running job."""
    job = await _get_job_or_404(job_id, db)

    terminal_states = {
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    }
    if job.status in terminal_states:
        raise BadRequestError(
            detail=f"Job is already in terminal state '{job.status}' and cannot be cancelled"
        )

    job.status = JobStatus.CANCELLED.value
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("job.cancelled", job_id=str(job_id), user_id=str(user.id))

    return Envelope[JobResponse](
        data=JobResponse.model_validate(job),
        meta=Meta(),
    )
