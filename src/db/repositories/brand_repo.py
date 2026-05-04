"""Repository for BrandGuideline CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models import BrandGuideline
from src.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


class BrandRepository:
    """Async CRUD operations for the brand_guidelines table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        primary_colors: list[str] | None = None,
        primary_font: str = "Arial",
        secondary_colors: list[str] | None = None,
        secondary_font: str | None = None,
        brand_voice: str | None = None,
        photography_style: str | None = None,
        prohibited_elements: list[str] | None = None,
        logo_config: dict[str, Any] | None = None,
        text_customization: dict[str, Any] | None = None,
        post_processing: dict[str, Any] | None = None,
        raw_extracted_data: dict[str, Any] | None = None,
        source_file_path: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> BrandGuideline:
        """Create a new brand guideline record.

        Args:
            name: Unique brand guideline name.
            primary_colors: List of primary hex colour strings.
            primary_font: Primary font family name.
            secondary_colors: Optional secondary colours.
            secondary_font: Optional secondary font.
            brand_voice: Descriptive brand voice / tone.
            photography_style: Photography style notes.
            prohibited_elements: List of prohibited visual elements.
            logo_config: Logo placement and sizing config as JSON.
            text_customization: Per-element text styling as JSON.
            post_processing: Image post-processing settings as JSON.
            raw_extracted_data: Raw data extracted from source documents.
            source_file_path: Path to original guideline document.
            created_by: Optional FK to the creating user.

        Returns:
            The newly created ``BrandGuideline`` instance.
        """
        brand = BrandGuideline(
            id=uuid.uuid4(),
            name=name,
            primary_colors=primary_colors or [],
            secondary_colors=secondary_colors,
            primary_font=primary_font,
            secondary_font=secondary_font,
            brand_voice=brand_voice,
            photography_style=photography_style,
            prohibited_elements=prohibited_elements or [],
            logo_config=logo_config or {},
            text_customization=text_customization,
            post_processing=post_processing,
            raw_extracted_data=raw_extracted_data,
            source_file_path=source_file_path,
            created_by=created_by,
        )
        self._session.add(brand)
        await self._session.flush()
        logger.info("brand.created", brand_id=str(brand.id), name=name)
        return brand

    async def get_by_id(self, brand_id: uuid.UUID) -> BrandGuideline | None:
        """Return a brand guideline by primary key, or ``None``."""
        stmt = select(BrandGuideline).where(BrandGuideline.id == brand_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, brand_id: uuid.UUID, **kwargs: object) -> BrandGuideline:
        """Update an existing brand guideline.

        Args:
            brand_id: UUID primary key.
            **kwargs: Column names and their new values.

        Returns:
            The updated ``BrandGuideline`` instance.

        Raises:
            NotFoundError: If the brand guideline does not exist.
        """
        brand = await self.get_by_id(brand_id)
        if brand is None:
            raise NotFoundError("BrandGuideline", str(brand_id))

        for key, value in kwargs.items():
            if hasattr(brand, key):
                setattr(brand, key, value)

        brand.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        logger.info(
            "brand.updated", brand_id=str(brand_id), fields=list(kwargs.keys())
        )
        return brand

    async def delete(self, brand_id: uuid.UUID) -> None:
        """Delete a brand guideline by primary key.

        Raises:
            NotFoundError: If the brand guideline does not exist.
        """
        brand = await self.get_by_id(brand_id)
        if brand is None:
            raise NotFoundError("BrandGuideline", str(brand_id))

        await self._session.delete(brand)
        await self._session.flush()
        logger.info("brand.deleted", brand_id=str(brand_id))

    async def list_brands(
        self, limit: int = 20, offset: int = 0
    ) -> list[BrandGuideline]:
        """Return a paginated list of brand guidelines.

        Args:
            limit: Maximum number of rows.
            offset: Number of rows to skip.

        Returns:
            A list of ``BrandGuideline`` instances ordered by ``created_at`` descending.
        """
        stmt = (
            select(BrandGuideline)
            .order_by(BrandGuideline.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
