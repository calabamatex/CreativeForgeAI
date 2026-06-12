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
    get_arq_pool,
    get_current_user,
    get_db,
    require_role,
)
from src.api.errors import BadRequestError, NotFoundError
from src.cache import get_cache
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
# Read-through cache configuration
# ---------------------------------------------------------------------------
#
# Short TTL: list/detail are read-heavy but mutate often; 30s keeps reads cheap
# while bounding staleness. Explicit invalidation on every mutation means a
# change is reflected on the very next read regardless of TTL — the TTL is just
# a backstop for anything we don't (or can't) invalidate precisely.
CAMPAIGN_CACHE_TTL_SECONDS: int = 30

# Key scheme (all under the cache's global prefix, e.g. "adobegenai:"):
#   List family:  "campaigns:list:page={p}:per_page={pp}:status={s}:backend={b}"
#   Detail:       "campaigns:detail:{campaign_id}"
#
# Scoping note: GET /campaigns is NOT user/tenant-scoped — every authenticated
# user sees the same global campaign list (the query filters only by
# status/backend, never by created_by). The response therefore depends solely
# on page/per_page/status/backend, so the list key captures exactly those
# inputs and intentionally omits the user id. There is no cross-user leakage
# because there is no per-user view to leak. If the list ever becomes
# user-scoped, a ":user={user.id}" segment MUST be added to the list key.
_CAMPAIGN_LIST_PREFIX = "campaigns:list:"


def _list_cache_key(page: int, per_page: int, status: str | None, backend: str | None) -> str:
    """Build the cache key for a GET /campaigns list response."""
    return (
        f"{_CAMPAIGN_LIST_PREFIX}page={page}:per_page={per_page}"
        f":status={status or '*'}:backend={backend or '*'}"
    )


def _detail_cache_key(campaign_id) -> str:
    """Build the cache key for a GET /campaigns/{id} detail response."""
    return f"campaigns:detail:{campaign_id}"


async def _invalidate_campaign_caches(campaign_id) -> None:
    """Invalidate all cached reads affected by a mutation to *campaign_id*.

    Drops the single detail key for the campaign and the entire list family
    (every page/filter combination) so the next read repopulates from the DB.
    Safe-on-failure: each cache op no-ops if Redis is unavailable.
    """
    cache = get_cache()
    await cache.delete(_detail_cache_key(campaign_id))
    await cache.invalidate_pattern(f"{_CAMPAIGN_LIST_PREFIX}*")


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

    cache = get_cache()
    status_val = status.value if status else None
    cache_key = _list_cache_key(page, per_page, status_val, backend)

    # Read-through: serve from cache on hit. We cache only the data payload
    # (items + total), NOT the envelope's meta, so every response still gets a
    # fresh request_id/timestamp.
    cached = await cache.get(cache_key)
    if cached is not None:
        return PaginatedEnvelope[CampaignListItem](
            data=[CampaignListItem.model_validate(item) for item in cached["items"]],
            meta=PaginationMeta(
                page=page,
                per_page=per_page,
                total=cached["total"],
                total_pages=max(1, math.ceil(cached["total"] / per_page)),
            ),
        )

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

    # Populate cache with the data payload (items serialised via Pydantic so the
    # JSON round-trips cleanly; total is needed to rebuild pagination meta).
    await cache.set(
        cache_key,
        {
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
        },
        ttl=CAMPAIGN_CACHE_TTL_SECONDS,
    )

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
    pool=Depends(get_arq_pool),
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

    # Capture ids before commit (expire_on_commit=False keeps the ORM objects
    # usable, but the response payload only needs these strings to enqueue).
    campaign_id_str = str(campaign.id)
    job_id_str = str(job.id)

    # Commit-then-enqueue: the Job/Campaign rows MUST be committed and visible
    # before the job is enqueued, otherwise the worker can dequeue and query a
    # row that isn't there yet (the enqueue racing the DB write). We commit
    # explicitly here; the get_db dependency's end-of-request commit is then a
    # harmless no-op.
    await db.commit()

    # Idempotent enqueue: _job_id == the DB job id, so a duplicate enqueue for
    # the same job is deduped by ARQ (and by the recording fake pool in tests).
    if pool is not None:
        await pool.enqueue_job(
            "process_campaign_job",
            campaign_id_str,
            job_id_str,
            _job_id=job_id_str,
        )

    # Invalidate cached reads: the new campaign must appear in the list (and its
    # detail must be fetchable) on the very next read, not after the TTL.
    await _invalidate_campaign_caches(campaign_id_str)

    logger.info(
        "campaign.created",
        campaign_id=campaign_id_str,
        job_id=job_id_str,
        user_id=str(user.id),
    )

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
    cache = get_cache()
    cache_key = _detail_cache_key(campaign_id)

    # Read-through: serve the cached data payload on hit (meta stays fresh).
    cached = await cache.get(cache_key)
    if cached is not None:
        return Envelope[CampaignResponse](
            data=CampaignResponse.model_validate(cached),
            meta=Meta(),
        )

    campaign = await _get_campaign_or_404(campaign_id, db)
    ac = await _count_assets(campaign_id, db)
    job = await _latest_job(campaign_id, db)

    response = _campaign_to_response(campaign, ac, job)
    await cache.set(
        cache_key,
        response.model_dump(mode="json"),
        ttl=CAMPAIGN_CACHE_TTL_SECONDS,
    )

    return Envelope[CampaignResponse](
        data=response,
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

    # Invalidate so the updated fields are reflected on the next list/detail read.
    await _invalidate_campaign_caches(str(campaign_id))

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

    # Invalidate so the deleted campaign disappears from list/detail immediately.
    await _invalidate_campaign_caches(str(campaign_id))

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
    pool=Depends(get_arq_pool),
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

    campaign_id_str = str(campaign.id)
    job_id_str = str(job.id)

    # Commit-then-enqueue (see create_campaign): the new Job row + the campaign
    # status flip must be committed before the worker can pick the job up.
    await db.commit()

    if pool is not None:
        await pool.enqueue_job(
            "process_campaign_job",
            campaign_id_str,
            job_id_str,
            _job_id=job_id_str,
        )

    # Status flipped to "processing" — invalidate so list/detail reflect it.
    await _invalidate_campaign_caches(campaign_id_str)

    logger.info("campaign.reprocess", campaign_id=campaign_id_str, job_id=job_id_str)

    return Envelope[JobResponse](
        data=JobResponse.model_validate(job),
        meta=Meta(),
    )
