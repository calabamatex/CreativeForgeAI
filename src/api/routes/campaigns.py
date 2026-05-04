"""Campaign CRUD endpoints with job queuing and reprocessing."""

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
    CampaignCreateRequest,
    CampaignListItem,
    CampaignResponse,
    CampaignStatus,
    CampaignUpdateRequest,
    Envelope,
    JobResponse,
    Meta,
    PaginatedEnvelope,
    PaginationMeta,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_campaign_or_404(campaign_id: uuid.UUID, db: AsyncSession):
    """Load a campaign by primary key, raising 404 if missing.

    Uses selectinload for the jobs relationship since it is commonly
    accessed right after fetching the campaign (e.g. latest_job lookup).
    """
    from src.db.models import Campaign, Job  # noqa: E402
    from sqlalchemy.orm import selectinload  # noqa: E402

    stmt = (
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(selectinload(Campaign.jobs))
    )
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise NotFoundError("Campaign", str(campaign_id))
    return campaign


async def _count_assets(campaign_id: uuid.UUID, db: AsyncSession) -> int:
    from src.db.models import GeneratedAsset  # noqa: E402

    stmt = select(func.count()).select_from(GeneratedAsset).where(GeneratedAsset.campaign_id == campaign_id)
    result = await db.execute(stmt)
    return result.scalar_one()


async def _latest_job(campaign_id: uuid.UUID, db: AsyncSession):
    from src.db.models import Job  # noqa: E402

    stmt = (
        select(Job)
        .where(Job.campaign_id == campaign_id)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _campaign_to_response(campaign, asset_count: int, job=None) -> CampaignResponse:
    """Map an ORM Campaign row to the API response schema."""
    return CampaignResponse(
        id=campaign.id,
        campaign_id=campaign.campaign_id,
        campaign_name=campaign.campaign_name,
        brand_name=campaign.brand_name,
        status=campaign.status,
        image_backend=campaign.image_backend,
        brand_guidelines_id=campaign.brand_guidelines_id,
        brief=campaign.brief,
        target_locales=campaign.target_locales,
        aspect_ratios=campaign.aspect_ratios,
        created_by=campaign.created_by,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        asset_count=asset_count,
        latest_job=JobResponse.model_validate(job) if job else None,
    )


# ---------------------------------------------------------------------------
# GET /campaigns
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedEnvelope[CampaignListItem],
    dependencies=[Depends(check_rate_limit)],
)
async def list_campaigns(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: CampaignStatus | None = Query(None),
    backend: str | None = Query(None),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List campaigns with pagination and optional filters.

    Uses a single query with a correlated subquery for asset counts
    to avoid N+1 query overhead.
    """
    from src.db.models import Campaign, GeneratedAsset  # noqa: E402
    from sqlalchemy.orm import load_only  # noqa: E402

    # Build filter conditions once, reuse for both count and data queries
    filters = []
    if status:
        filters.append(Campaign.status == status.value)
    if backend:
        filters.append(Campaign.image_backend == backend)

    # Total count query
    count_q = select(func.count()).select_from(Campaign)
    for f in filters:
        count_q = count_q.where(f)
    total = (await db.execute(count_q)).scalar_one()
    total_pages = max(1, math.ceil(total / per_page))

    # Asset count as a correlated subquery (eliminates N+1)
    asset_count_subq = (
        select(func.count())
        .where(GeneratedAsset.campaign_id == Campaign.id)
        .correlate(Campaign)
        .scalar_subquery()
        .label("asset_count")
    )

    # Single query: campaigns + asset count
    stmt = (
        select(Campaign, asset_count_subq)
        .options(load_only(
            Campaign.id,
            Campaign.campaign_id,
            Campaign.campaign_name,
            Campaign.brand_name,
            Campaign.status,
            Campaign.image_backend,
            Campaign.created_at,
            Campaign.updated_at,
        ))
        .order_by(Campaign.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    for f in filters:
        stmt = stmt.where(f)

    result = await db.execute(stmt)
    rows = result.all()

    items: list[CampaignListItem] = [
        CampaignListItem(
            id=c.id,
            campaign_id=c.campaign_id,
            campaign_name=c.campaign_name,
            brand_name=c.brand_name,
            status=c.status,
            image_backend=c.image_backend,
            asset_count=ac or 0,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c, ac in rows
    ]

    return PaginatedEnvelope[CampaignListItem](
        data=items,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


# ---------------------------------------------------------------------------
# POST /campaigns
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=Envelope[CampaignResponse],
    status_code=201,
    dependencies=[Depends(check_rate_limit)],
)
async def create_campaign(
    body: CampaignCreateRequest,
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new campaign and queue a generation job."""
    from src.db.models import Campaign, Job  # noqa: E402

    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id=uuid.uuid4(),
        campaign_id=body.campaign_id,
        campaign_name=body.campaign_name,
        brand_name=body.brand_name,
        status=CampaignStatus.DRAFT.value,
        image_backend=body.image_backend,
        brand_guidelines_id=body.brand_guidelines_id,
        brief=body.brief,
        target_locales=body.target_locales,
        aspect_ratios=body.aspect_ratios,
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(campaign)

    # Queue initial generation job
    job = Job(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        status="queued",
        progress_percent=0,
        created_at=now,
    )
    db.add(job)
    await db.flush()

    logger.info("campaign.created", campaign_id=str(campaign.id), user_id=str(user.id))

    return Envelope[CampaignResponse](
        data=_campaign_to_response(campaign, asset_count=0, job=job),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# GET /campaigns/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}",
    response_model=Envelope[CampaignResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def get_campaign(
    campaign_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return detailed information about a single campaign."""
    campaign = await _get_campaign_or_404(campaign_id, db)
    ac = await _count_assets(campaign_id, db)
    job = await _latest_job(campaign_id, db)

    return Envelope[CampaignResponse](
        data=_campaign_to_response(campaign, ac, job),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# PATCH /campaigns/{id}
# ---------------------------------------------------------------------------


@router.patch(
    "/{campaign_id}",
    response_model=Envelope[CampaignResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def update_campaign(
    campaign_id: uuid.UUID,
    body: CampaignUpdateRequest,
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a campaign (only allowed while it is in *draft* status)."""
    campaign = await _get_campaign_or_404(campaign_id, db)

    if campaign.status != CampaignStatus.DRAFT.value:
        raise BadRequestError(
            detail="Only campaigns in 'draft' status can be updated"
        )

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(campaign, field, value)
    campaign.updated_at = datetime.now(timezone.utc)

    await db.flush()

    ac = await _count_assets(campaign_id, db)
    job = await _latest_job(campaign_id, db)

    logger.info("campaign.updated", campaign_id=str(campaign_id), fields=list(updates.keys()))

    return Envelope[CampaignResponse](
        data=_campaign_to_response(campaign, ac, job),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# DELETE /campaigns/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{campaign_id}",
    status_code=204,
    dependencies=[Depends(check_rate_limit)],
)
async def delete_campaign(
    campaign_id: uuid.UUID,
    user=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a campaign (Admin only)."""
    campaign = await _get_campaign_or_404(campaign_id, db)
    await db.delete(campaign)
    await db.flush()
    logger.info("campaign.deleted", campaign_id=str(campaign_id), user_id=str(user.id))


# ---------------------------------------------------------------------------
# POST /campaigns/{id}/reprocess
# ---------------------------------------------------------------------------


@router.post(
    "/{campaign_id}/reprocess",
    response_model=Envelope[JobResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def reprocess_campaign(
    campaign_id: uuid.UUID,
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Queue a new generation job for an existing campaign."""
    from src.db.models import Job  # noqa: E402

    campaign = await _get_campaign_or_404(campaign_id, db)

    campaign.status = CampaignStatus.PROCESSING.value
    campaign.updated_at = datetime.now(timezone.utc)

    job = Job(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        status="queued",
        progress_percent=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    logger.info("campaign.reprocess", campaign_id=str(campaign_id), job_id=str(job.id))

    return Envelope[JobResponse](
        data=JobResponse.model_validate(job),
        meta=Meta(),
    )
