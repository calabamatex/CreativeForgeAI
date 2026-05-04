"""Repository for Campaign CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models import Campaign
from src.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


class CampaignRepository:
    """Async CRUD operations for the campaigns table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        campaign_id: str,
        campaign_name: str,
        brand_name: str,
        brief: dict[str, Any],
        image_backend: str = "firefly",
        target_locales: list[str] | None = None,
        aspect_ratios: list[str] | None = None,
        brand_guidelines_id: uuid.UUID | None = None,
        localization_guidelines: dict[str, Any] | None = None,
        legal_guidelines: dict[str, Any] | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Campaign:
        """Create a new campaign.

        Args:
            campaign_id: Unique human-readable campaign identifier.
            campaign_name: Display name.
            brand_name: Associated brand.
            brief: Full campaign brief as JSON.
            image_backend: Generation backend (``"firefly"``, ``"openai"``, etc.).
            target_locales: List of locale codes.
            aspect_ratios: List of aspect ratio strings.
            brand_guidelines_id: Optional FK to brand_guidelines.
            localization_guidelines: Optional localization rules JSON.
            legal_guidelines: Optional legal rules JSON.
            created_by: Optional FK to the creating user.

        Returns:
            The newly created ``Campaign`` instance.
        """
        campaign = Campaign(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            brand_name=brand_name,
            brief=brief,
            image_backend=image_backend,
            target_locales=target_locales or ["en-US"],
            aspect_ratios=aspect_ratios or ["1:1", "9:16", "16:9"],
            brand_guidelines_id=brand_guidelines_id,
            localization_guidelines=localization_guidelines,
            legal_guidelines=legal_guidelines,
            created_by=created_by,
            status="draft",
        )
        self._session.add(campaign)
        await self._session.flush()
        logger.info(
            "campaign.created",
            campaign_id=campaign_id,
            pk=str(campaign.id),
        )
        return campaign

    async def get_by_id(self, campaign_pk: uuid.UUID) -> Campaign | None:
        """Return a campaign by its UUID primary key."""
        stmt = select(Campaign).where(Campaign.id == campaign_pk)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_campaign_id(self, campaign_id: str) -> Campaign | None:
        """Return a campaign by its human-readable campaign_id string."""
        stmt = select(Campaign).where(Campaign.campaign_id == campaign_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, pk: uuid.UUID, **kwargs: object) -> Campaign:
        """Update a campaign by primary key.

        Args:
            pk: UUID primary key of the campaign.
            **kwargs: Column names and new values.

        Returns:
            The updated ``Campaign`` instance.

        Raises:
            NotFoundError: If the campaign does not exist.
        """
        campaign = await self.get_by_id(pk)
        if campaign is None:
            raise NotFoundError("Campaign", str(pk))

        for key, value in kwargs.items():
            if hasattr(campaign, key):
                setattr(campaign, key, value)

        campaign.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        logger.info("campaign.updated", pk=str(pk), fields=list(kwargs.keys()))
        return campaign

    async def update_status(
        self,
        pk: uuid.UUID,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> Campaign:
        """Convenience method to transition a campaign's status.

        Args:
            pk: UUID primary key.
            status: New status value (e.g. ``"running"``, ``"completed"``).
            result: Optional result payload to persist.

        Returns:
            The updated ``Campaign``.

        Raises:
            NotFoundError: If the campaign does not exist.
        """
        campaign = await self.get_by_id(pk)
        if campaign is None:
            raise NotFoundError("Campaign", str(pk))

        campaign.status = status
        if result is not None:
            campaign.brief = {**campaign.brief, "result": result}
        campaign.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        logger.info("campaign.status_updated", pk=str(pk), status=status)
        return campaign

    async def delete(self, pk: uuid.UUID) -> None:
        """Delete a campaign by primary key.

        Raises:
            NotFoundError: If the campaign does not exist.
        """
        campaign = await self.get_by_id(pk)
        if campaign is None:
            raise NotFoundError("Campaign", str(pk))

        await self._session.delete(campaign)
        await self._session.flush()
        logger.info("campaign.deleted", pk=str(pk))

    async def list_campaigns(
        self,
        status: str | None = None,
        cursor: datetime | None = None,
        limit: int = 20,
    ) -> list[Campaign]:
        """Return a paginated list of campaigns with optional filters.

        Uses cursor-based pagination on ``created_at``.

        Args:
            status: Optional status filter.
            cursor: If provided, only return campaigns created before this timestamp.
            limit: Maximum number of rows.

        Returns:
            A list of ``Campaign`` instances ordered by ``created_at`` descending.
        """
        stmt = select(Campaign).order_by(Campaign.created_at.desc()).limit(limit)

        if status is not None:
            stmt = stmt.where(Campaign.status == status)
        if cursor is not None:
            stmt = stmt.where(Campaign.created_at < cursor)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
