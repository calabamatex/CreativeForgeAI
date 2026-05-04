"""Asset endpoints: list, detail, download."""

from __future__ import annotations

import math
import os
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.dependencies import check_rate_limit, get_current_user, get_db
from src.api.errors import NotFoundError
from src.api.schemas import (
    AssetResponse,
    Envelope,
    Meta,
    PaginatedEnvelope,
    PaginationMeta,
)
from src.storage_factory import get_default_storage_backend
from src.storage_local import LocalStorageBackend

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["assets"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_asset_or_404(asset_id: uuid.UUID, db: AsyncSession):
    from src.db.models import GeneratedAsset  # noqa: E402

    stmt = select(GeneratedAsset).where(GeneratedAsset.id == asset_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    if asset is None:
        raise NotFoundError("Asset", str(asset_id))
    return asset


async def _campaign_exists(campaign_id: uuid.UUID, db: AsyncSession) -> None:
    from src.db.models import Campaign  # noqa: E402

    stmt = select(Campaign.id).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise NotFoundError("Campaign", str(campaign_id))


# ---------------------------------------------------------------------------
# GET /campaigns/{id}/assets
# ---------------------------------------------------------------------------


@router.get(
    "/campaigns/{campaign_id}/assets",
    response_model=PaginatedEnvelope[AssetResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def list_campaign_assets(
    campaign_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    locale: str | None = Query(None),
    aspect_ratio: str | None = Query(None),
    generation_method: str | None = Query(None),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List assets belonging to a campaign, with optional filtering."""
    from src.db.models import GeneratedAsset  # noqa: E402

    await _campaign_exists(campaign_id, db)

    base = select(GeneratedAsset).where(GeneratedAsset.campaign_id == campaign_id)
    count_q = (
        select(func.count())
        .select_from(GeneratedAsset)
        .where(GeneratedAsset.campaign_id == campaign_id)
    )

    if locale:
        base = base.where(GeneratedAsset.locale == locale)
        count_q = count_q.where(GeneratedAsset.locale == locale)
    if aspect_ratio:
        base = base.where(GeneratedAsset.aspect_ratio == aspect_ratio)
        count_q = count_q.where(GeneratedAsset.aspect_ratio == aspect_ratio)
    if generation_method:
        base = base.where(GeneratedAsset.generation_method == generation_method)
        count_q = count_q.where(GeneratedAsset.generation_method == generation_method)

    total = (await db.execute(count_q)).scalar_one()
    total_pages = max(1, math.ceil(total / per_page))

    stmt = (
        base.order_by(GeneratedAsset.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    assets = result.scalars().all()

    items = [AssetResponse.model_validate(a) for a in assets]

    return PaginatedEnvelope[AssetResponse](
        data=items,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


# ---------------------------------------------------------------------------
# GET /assets/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/assets/{asset_id}",
    response_model=Envelope[AssetResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def get_asset(
    asset_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return metadata for a single asset."""
    asset = await _get_asset_or_404(asset_id, db)
    return Envelope[AssetResponse](
        data=AssetResponse.model_validate(asset),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# GET /assets/{id}/download
# ---------------------------------------------------------------------------


@router.get(
    "/assets/{asset_id}/download",
    dependencies=[Depends(check_rate_limit)],
)
async def download_asset(
    asset_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the actual asset file.

    For local storage this streams the file via ``FileResponse``.
    For S3 storage this redirects to a presigned URL.
    """
    asset = await _get_asset_or_404(asset_id, db)
    backend = get_default_storage_backend()

    # Determine the storage key to use
    storage_key = asset.storage_key or ""

    # Infer media type from the key / file_path
    _path_hint = storage_key or asset.file_path or ""
    ext = os.path.splitext(_path_hint)[1].lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    # --- S3 backend: redirect to presigned URL ---
    if not isinstance(backend, LocalStorageBackend):
        if not storage_key:
            raise NotFoundError("Asset storage key", str(asset_id))
        try:
            url = await backend.get_url(storage_key)
        except Exception:
            logger.exception(
                "asset.download.presign_failed",
                asset_id=str(asset_id),
                key=storage_key,
            )
            raise NotFoundError("Asset file", str(asset_id))

        logger.info(
            "asset.download.redirect",
            asset_id=str(asset_id),
            key=storage_key,
        )
        return RedirectResponse(url=url, status_code=307)

    # --- Local backend: stream the file directly ---
    # Try storage key first (new path), then fall back to legacy file_path
    file_path = asset.file_path
    if storage_key:
        try:
            # Attempt to resolve via the backend
            resolved = backend._resolve_path(storage_key)
            if resolved.is_file():
                file_path = str(resolved)
        except Exception:
            pass  # fall through to file_path

    if not os.path.isfile(file_path):
        raise NotFoundError("Asset file", str(asset_id))

    filename = os.path.basename(file_path)
    logger.info(
        "asset.download",
        asset_id=str(asset_id),
        path=file_path,
    )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )
