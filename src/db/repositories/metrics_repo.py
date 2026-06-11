"""Repository for CampaignMetric persistence (P3-T5).

Persists the pipeline's real :class:`~src.models.campaign.TechnicalMetrics`
for a campaign run into the ``campaign_metrics`` table, and reads them back
for the metrics endpoints.

The ``campaign_metrics`` row already has a ``technical_metrics`` JSONB column,
so the full ``TechnicalMetrics`` payload is stored there verbatim -- no schema
change is required. The ``business_metrics`` column is intentionally left as
the empty default: tautological business/ROI metrics were removed earlier (see
``src/pipeline_metrics.py``) and are NOT reintroduced here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models import CampaignMetric

logger = structlog.get_logger(__name__)


class MetricsRepository:
    """Async persistence for the ``campaign_metrics`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        campaign_id: uuid.UUID,
        technical_metrics: dict[str, Any],
    ) -> uuid.UUID:
        """Insert one ``campaign_metrics`` row for a completed run.

        Each run appends a row (history of runs), keyed by ``campaign_id`` and
        ``recorded_at``. The row is flushed (not committed) so the caller can
        commit it inside the same transaction that records the job's terminal
        status -- keeping the metrics row atomic with the rest of the run.

        Args:
            campaign_id: FK to the parent campaign (UUID).
            technical_metrics: A JSON-serialisable dict of the run's real
                ``TechnicalMetrics`` (``TechnicalMetrics.model_dump(mode="json")``).

        Returns:
            The primary key (UUID) of the inserted row.
        """
        metric = CampaignMetric(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            technical_metrics=technical_metrics or {},
            # business_metrics intentionally left at its empty server default.
        )
        self._session.add(metric)
        await self._session.flush()
        logger.info(
            "metrics.recorded",
            metric_id=str(metric.id),
            campaign_id=str(campaign_id),
            total_api_calls=(technical_metrics or {}).get("total_api_calls"),
        )
        return metric.id

    async def get_latest(self, campaign_id: uuid.UUID) -> CampaignMetric | None:
        """Return the most recently recorded metric row for a campaign, or None."""
        stmt = (
            select(CampaignMetric)
            .where(CampaignMetric.campaign_id == campaign_id)
            .order_by(CampaignMetric.recorded_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
