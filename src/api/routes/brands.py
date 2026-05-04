"""Brand guideline endpoints: list, create (with file upload), detail, update, delete."""

from __future__ import annotations

import math
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Query, UploadFile
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
from src.security import validate_upload_extension, validate_upload_size
from src.api.schemas import (
    BrandCreateRequest,
    BrandResponse,
    BrandUpdateRequest,
    Envelope,
    Meta,
    PaginatedEnvelope,
    PaginationMeta,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/brands", tags=["brands"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_brand_or_404(brand_id: uuid.UUID, db: AsyncSession):
    from src.db.models import BrandGuideline  # noqa: E402

    stmt = select(BrandGuideline).where(BrandGuideline.id == brand_id)
    result = await db.execute(stmt)
    brand = result.scalar_one_or_none()
    if brand is None:
        raise NotFoundError("Brand", str(brand_id))
    return brand


async def _extract_guidelines(file_path: str) -> dict:
    """Run guideline extraction on the uploaded file.

    Delegates to the existing ``brand_parser`` module when available;
    falls back to returning an empty dict.
    """
    try:
        from src.parsers.brand_parser import parse_brand_guidelines

        guidelines = parse_brand_guidelines(file_path)
        if hasattr(guidelines, "model_dump"):
            return guidelines.model_dump()
        if isinstance(guidelines, dict):
            return guidelines
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("brand.extract_failed", path=file_path, error=str(exc))
        return {}


# ---------------------------------------------------------------------------
# GET /brands
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedEnvelope[BrandResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def list_brands(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all brand guideline entries with pagination."""
    from src.db.models import BrandGuideline  # noqa: E402

    total = (
        await db.execute(select(func.count()).select_from(BrandGuideline))
    ).scalar_one()
    total_pages = max(1, math.ceil(total / per_page))

    stmt = (
        select(BrandGuideline)
        .order_by(BrandGuideline.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    brands = result.scalars().all()

    items = [BrandResponse.model_validate(b) for b in brands]

    return PaginatedEnvelope[BrandResponse](
        data=items,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


# ---------------------------------------------------------------------------
# POST /brands
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=Envelope[BrandResponse],
    status_code=201,
    dependencies=[Depends(check_rate_limit)],
)
async def create_brand(
    body: BrandCreateRequest = Depends(),
    guidelines_file: UploadFile | None = File(None),
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new brand guideline entry.

    Optionally upload a brand guidelines document (PDF, DOCX, YAML) which
    will be parsed and its extracted values stored as ``raw_extracted_data``.
    """
    from src.db.models import BrandGuideline  # noqa: E402

    now = datetime.now(timezone.utc)
    saved_path: str | None = None
    extracted: dict = {}

    # Persist uploaded file if present
    if guidelines_file and guidelines_file.filename:
        # Validate file extension (AC-17.2)
        try:
            validate_upload_extension(guidelines_file.filename)
        except ValueError as exc:
            raise BadRequestError(detail=str(exc))

        # Read content and validate size (max 10 MB)
        content = await guidelines_file.read()
        try:
            validate_upload_size(len(content))
        except ValueError as exc:
            raise BadRequestError(detail=str(exc))

        upload_dir = os.path.join("uploads", "brands")
        os.makedirs(upload_dir, exist_ok=True)
        # Use UUID-only filename to prevent path traversal via filenames
        safe_ext = os.path.splitext(guidelines_file.filename)[1].lower()
        dest = os.path.join(upload_dir, f"{uuid.uuid4()}{safe_ext}")
        with open(dest, "wb") as fh:
            fh.write(content)
        saved_path = dest
        extracted = await _extract_guidelines(dest)

    brand = BrandGuideline(
        id=uuid.uuid4(),
        name=body.name,
        source_file_path=saved_path,
        raw_extracted_data=extracted or None,
        primary_colors=extracted.get("primary_colors", []),
        secondary_colors=extracted.get("secondary_colors", []),
        primary_font=extracted.get("primary_font", "Arial"),
        secondary_font=extracted.get("secondary_font"),
        brand_voice=extracted.get("brand_voice"),
        photography_style=extracted.get("photography_style"),
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(brand)
    await db.flush()

    logger.info("brand.created", brand_id=str(brand.id), user_id=str(user.id))

    return Envelope[BrandResponse](
        data=BrandResponse.model_validate(brand),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# GET /brands/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}",
    response_model=Envelope[BrandResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def get_brand(
    brand_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return detail for a single brand guideline entry."""
    brand = await _get_brand_or_404(brand_id, db)
    return Envelope[BrandResponse](
        data=BrandResponse.model_validate(brand),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# PATCH /brands/{id}
# ---------------------------------------------------------------------------


@router.patch(
    "/{brand_id}",
    response_model=Envelope[BrandResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def update_brand(
    brand_id: uuid.UUID,
    body: BrandUpdateRequest,
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update overrides on an existing brand guideline entry."""
    brand = await _get_brand_or_404(brand_id, db)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(brand, field, value)
    brand.updated_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("brand.updated", brand_id=str(brand_id), fields=list(updates.keys()))

    return Envelope[BrandResponse](
        data=BrandResponse.model_validate(brand),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# DELETE /brands/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{brand_id}",
    status_code=204,
    dependencies=[Depends(check_rate_limit)],
)
async def delete_brand(
    brand_id: uuid.UUID,
    user=Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a brand guideline entry (Admin only)."""
    brand = await _get_brand_or_404(brand_id, db)
    await db.delete(brand)
    await db.flush()
    logger.info("brand.deleted", brand_id=str(brand_id), user_id=str(user.id))
