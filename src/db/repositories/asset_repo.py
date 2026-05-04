"""Repository for GeneratedAsset CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models import GeneratedAsset
from src.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


class AssetRepository:
    """Async CRUD operations for the generated_assets table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        campaign_id: uuid.UUID,
        product_id: str,
        locale: str,
        aspect_ratio: str,
        file_path: str,
        storage_key: str,
        generation_method: str,
        file_size_bytes: int | None = None,
        width: int | None = None,
        height: int | None = None,
        generation_time_ms: float | None = None,
    ) -> GeneratedAsset:
        """Create a new generated asset record.

        Args:
            campaign_id: FK to the parent campaign (UUID).
            product_id: Human-readable product identifier.
            locale: Locale code (e.g. ``"en-US"``).
            aspect_ratio: Aspect ratio string (e.g. ``"1:1"``).
            file_path: Local or absolute file path to the asset.
            storage_key: Cloud storage key / object path.
            generation_method: How the image was produced (e.g. ``"firefly"``).
            file_size_bytes: Optional file size.
            width: Optional image width in pixels.
            height: Optional image height in pixels.
            generation_time_ms: Optional generation latency.

        Returns:
            The newly created ``GeneratedAsset`` instance.
        """
        asset = GeneratedAsset(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            product_id=product_id,
            locale=locale,
            aspect_ratio=aspect_ratio,
            file_path=file_path,
            storage_key=storage_key,
            generation_method=generation_method,
            file_size_bytes=file_size_bytes,
            width=width,
            height=height,
            generation_time_ms=generation_time_ms,
        )
        self._session.add(asset)
        await self._session.flush()
        logger.info(
            "asset.created",
            asset_id=str(asset.id),
            campaign_id=str(campaign_id),
            product_id=product_id,
            locale=locale,
            aspect_ratio=aspect_ratio,
        )
        return asset

    async def get_by_id(self, asset_id: uuid.UUID) -> GeneratedAsset | None:
        """Return an asset by primary key, or ``None``."""
        stmt = select(GeneratedAsset).where(GeneratedAsset.id == asset_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_campaign(
        self,
        campaign_id: uuid.UUID,
        product_id: str | None = None,
        locale: str | None = None,
        aspect_ratio: str | None = None,
    ) -> list[GeneratedAsset]:
        """List assets for a campaign with optional filters.

        Args:
            campaign_id: FK to the parent campaign.
            product_id: Optional product filter.
            locale: Optional locale filter.
            aspect_ratio: Optional aspect-ratio filter.

        Returns:
            A list of matching ``GeneratedAsset`` instances.
        """
        stmt = (
            select(GeneratedAsset)
            .where(GeneratedAsset.campaign_id == campaign_id)
            .order_by(GeneratedAsset.created_at.desc())
        )

        if product_id is not None:
            stmt = stmt.where(GeneratedAsset.product_id == product_id)
        if locale is not None:
            stmt = stmt.where(GeneratedAsset.locale == locale)
        if aspect_ratio is not None:
            stmt = stmt.where(GeneratedAsset.aspect_ratio == aspect_ratio)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_campaign(self, campaign_id: uuid.UUID) -> int:
        """Return the total number of assets for a given campaign.

        Args:
            campaign_id: FK to the parent campaign.

        Returns:
            Integer count.
        """
        stmt = (
            select(func.count())
            .select_from(GeneratedAsset)
            .where(GeneratedAsset.campaign_id == campaign_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
