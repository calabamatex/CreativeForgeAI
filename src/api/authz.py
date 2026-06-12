"""Centralized object-level authorization (tenant scoping).

Trust model
-----------
Every ``Campaign`` and ``BrandGuideline`` is owned by the user in its
``created_by`` column. Assets, jobs, compliance reports and metrics have no
owner column of their own — their ownership derives from the parent campaign's
``created_by``. A non-admin user may only read or mutate objects they own;
``admin`` may access any object (support/ops, always logged by the routes).

Two deliberate design choices:

* **404, never 403, for non-owned objects.** A 403 confirms the object exists,
  enabling UUID enumeration. 404 is the correct answer for "you may not know
  whether this exists".
* **NULL ``created_by`` is admin-only.** Legacy rows with no owner are not
  visible to any non-admin user rather than being world-readable.

Route handlers must load objects through these helpers (never via a bare
``select(...).where(Model.id == ...)``) so no code path can forget the check.
The WebSocket route (``routes/ws.py``) applies the same ownership rule.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import NotFoundError

ADMIN_ROLES = frozenset({"admin"})


def is_admin(user) -> bool:
    """True if *user* may access objects owned by anyone."""
    return user.role in ADMIN_ROLES


def _owns(user, owner_id) -> bool:
    """Ownership predicate: admins own everything; NULL owner is admin-only."""
    return is_admin(user) or (owner_id is not None and owner_id == user.id)


async def get_owned_campaign(
    campaign_id: uuid.UUID,
    user,
    db: AsyncSession,
    *,
    with_jobs: bool = False,
):
    """Load a campaign the user is allowed to see, else 404.

    ``with_jobs=True`` eagerly loads the jobs relationship (selectinload) for
    handlers that read ``campaign.jobs`` right after.
    """
    from sqlalchemy.orm import selectinload  # noqa: E402

    from src.db.models import Campaign  # noqa: E402

    stmt = select(Campaign).where(Campaign.id == campaign_id)
    if with_jobs:
        stmt = stmt.options(selectinload(Campaign.jobs))
    campaign = (await db.execute(stmt)).scalar_one_or_none()
    if campaign is None or not _owns(user, campaign.created_by):
        raise NotFoundError("Campaign", str(campaign_id))
    return campaign


async def get_owned_brand(brand_id: uuid.UUID, user, db: AsyncSession):
    """Load a brand guideline the user is allowed to see, else 404."""
    from src.db.models import BrandGuideline  # noqa: E402

    stmt = select(BrandGuideline).where(BrandGuideline.id == brand_id)
    brand = (await db.execute(stmt)).scalar_one_or_none()
    if brand is None or not _owns(user, brand.created_by):
        raise NotFoundError("Brand", str(brand_id))
    return brand


async def _campaign_owner_id(campaign_id: uuid.UUID, db: AsyncSession):
    """Return the ``created_by`` of *campaign_id* (None if campaign missing)."""
    from src.db.models import Campaign  # noqa: E402

    stmt = select(Campaign.created_by).where(Campaign.id == campaign_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_owned_asset(asset_id: uuid.UUID, user, db: AsyncSession):
    """Load an asset whose parent campaign the user owns, else 404.

    Admins skip the ownership lookup entirely (one query, same as before
    scoping). Non-admins incur one extra scalar query for the parent
    campaign's owner.
    """
    from src.db.models import GeneratedAsset  # noqa: E402

    stmt = select(GeneratedAsset).where(GeneratedAsset.id == asset_id)
    asset = (await db.execute(stmt)).scalar_one_or_none()
    if asset is None:
        raise NotFoundError("Asset", str(asset_id))
    if not is_admin(user):
        owner_id = await _campaign_owner_id(asset.campaign_id, db)
        if owner_id is None or owner_id != user.id:
            raise NotFoundError("Asset", str(asset_id))
    return asset


async def get_owned_job(job_id: uuid.UUID, user, db: AsyncSession):
    """Load a job whose parent campaign the user owns, else 404."""
    from src.db.models import Job  # noqa: E402

    stmt = select(Job).where(Job.id == job_id)
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Job", str(job_id))
    if not is_admin(user):
        owner_id = await _campaign_owner_id(job.campaign_id, db)
        if owner_id is None or owner_id != user.id:
            raise NotFoundError("Job", str(job_id))
    return job


def owned_campaign_ids_subquery(user):
    """Scalar subquery of campaign ids visible to *user* (None for admins).

    Use to scope queries over campaign-children (jobs, assets, metrics,
    compliance reports):

        owned = owned_campaign_ids_subquery(user)
        if owned is not None:
            stmt = stmt.where(Model.campaign_id.in_(owned))
    """
    from src.db.models import Campaign  # noqa: E402

    if is_admin(user):
        return None
    return select(Campaign.id).where(Campaign.created_by == user.id).scalar_subquery()
