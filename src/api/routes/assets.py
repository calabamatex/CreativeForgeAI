"""Asset endpoints: list, detail, download."""

from __future__ import annotations

import math
import os
import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.authz import get_owned_asset, get_owned_campaign
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

    # Tenant gate: 404 unless the caller owns the parent campaign (or is
    # admin). The asset query below is already scoped to this campaign_id.
    await get_owned_campaign(campaign_id, user, db)

    base = select(GeneratedAsset).where(GeneratedAsset.campaign_id == campaign_id)
    count_q = select(func.count()).select_from(GeneratedAsset).where(GeneratedAsset.campaign_id == campaign_id)

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

    stmt = base.order_by(GeneratedAsset.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
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
    asset = await get_owned_asset(asset_id, user, db)
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
    asset = await get_owned_asset(asset_id, user, db)
    backend = get_default_storage_backend()

    # The storage key is the single source of truth for where the bytes live
    # (it equals the key the worker passed to ``backend.save``). Every asset
    # persisted by the P3-T3 write path has it populated.
    storage_key = asset.storage_key or ""
    if not storage_key:
        raise NotFoundError("Asset storage key", str(asset_id))

    # Infer media type from the key / file_path.
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

    # --- Non-local (S3 / MinIO) backend: 307 redirect to a presigned URL ---
    if not isinstance(backend, LocalStorageBackend):
        try:
            url = await backend.get_url(storage_key)
        except Exception as exc:
            logger.exception(
                "asset.download.presign_failed",
                asset_id=str(asset_id),
                key=storage_key,
            )
            raise NotFoundError("Asset file", str(asset_id)) from exc

        logger.info(
            "asset.download.redirect",
            asset_id=str(asset_id),
            key=storage_key,
        )
        return RedirectResponse(url=url, status_code=307)

    # --- Local backend: resolve the key to a real path and stream it ---
    # Resolution goes THROUGH the backend so P1-T3 path containment
    # (``is_relative_to`` in ``LocalStorageBackend._resolve_path``) is honored.
    try:
        resolved = backend._resolve_path(storage_key)
    except Exception as exc:
        logger.exception(
            "asset.download.resolve_failed",
            asset_id=str(asset_id),
            key=storage_key,
        )
        raise NotFoundError("Asset file", str(asset_id)) from exc

    file_path = str(resolved)
    if not resolved.is_file():
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
