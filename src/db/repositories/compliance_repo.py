"""Repository for ComplianceReport CRUD operations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models import ComplianceReport
from src.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


class ComplianceRepository:
    """Async CRUD operations for the compliance_reports table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        campaign_id: uuid.UUID,
        is_compliant: bool,
        violations: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> ComplianceReport:
        """Create a new compliance report.

        Args:
            campaign_id: FK to the parent campaign.
            is_compliant: Whether the campaign passed all compliance checks.
            violations: List of violation detail dicts.
            summary: Summary object with compliance check results.

        Returns:
            The newly created ``ComplianceReport`` instance.
        """
        report = ComplianceReport(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            is_compliant=is_compliant,
            violations=violations,
            summary=summary,
        )
        self._session.add(report)
        await self._session.flush()
        logger.info(
            "compliance.created",
            report_id=str(report.id),
            campaign_id=str(campaign_id),
            is_compliant=is_compliant,
            violation_count=len(violations),
        )
        return report

    async def get_latest(self, campaign_id: uuid.UUID) -> ComplianceReport | None:
        """Return the most recent compliance report for a campaign, or ``None``.

        Args:
            campaign_id: FK to the parent campaign.

        Returns:
            The latest ``ComplianceReport``, or ``None`` if none exist.
        """
        stmt = (
            select(ComplianceReport)
            .where(ComplianceReport.campaign_id == campaign_id)
            .order_by(ComplianceReport.checked_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_campaign(
        self, campaign_id: uuid.UUID
    ) -> list[ComplianceReport]:
        """Return all compliance reports for a campaign.

        Args:
            campaign_id: FK to the parent campaign.

        Returns:
            A list of ``ComplianceReport`` instances ordered by ``checked_at`` descending.
        """
        stmt = (
            select(ComplianceReport)
            .where(ComplianceReport.campaign_id == campaign_id)
            .order_by(ComplianceReport.checked_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
