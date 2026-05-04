"""Metrics endpoints: campaign metrics and aggregate metrics."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.dependencies import check_rate_limit, get_current_user, get_db
from src.api.errors import NotFoundError
from src.api.schemas import (
    AggregateMetricsResponse,
    CampaignMetricsResponse,
    Envelope,
    Meta,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["metrics"])


# ---------------------------------------------------------------------------
# GET /campaigns/{id}/metrics
# ---------------------------------------------------------------------------


@router.get(
    "/campaigns/{campaign_id}/metrics",
    response_model=Envelope[CampaignMetricsResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def get_campaign_metrics(
    campaign_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return metrics for a single campaign.

    Aggregates asset counts by locale and aspect ratio, plus timing and
    compliance data from the campaign's job and compliance report records.
    """
    from src.db.models import Campaign, ComplianceReport, GeneratedAsset, Job  # noqa: E402

    # Ensure campaign exists
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise NotFoundError("Campaign", str(campaign_id))

    # Total asset count
    total_assets = (
        await db.execute(
            select(func.count()).where(GeneratedAsset.campaign_id == campaign_id)
        )
    ).scalar_one()

    # Assets by locale
    locale_rows = (
        await db.execute(
            select(GeneratedAsset.locale, func.count())
            .where(GeneratedAsset.campaign_id == campaign_id)
            .group_by(GeneratedAsset.locale)
        )
    ).all()
    assets_by_locale = {row[0]: row[1] for row in locale_rows}

    # Assets by aspect ratio
    ratio_rows = (
        await db.execute(
            select(GeneratedAsset.aspect_ratio, func.count())
            .where(GeneratedAsset.campaign_id == campaign_id)
            .group_by(GeneratedAsset.aspect_ratio)
        )
    ).all()
    assets_by_ratio = {row[0]: row[1] for row in ratio_rows}

    # Processing time from latest completed job
    job_stmt = (
        select(Job)
        .where(Job.campaign_id == campaign_id, Job.status == "completed")
        .order_by(Job.completed_at.desc())
        .limit(1)
    )
    job = (await db.execute(job_stmt)).scalar_one_or_none()
    processing_time = 0.0
    if job and job.started_at and job.completed_at:
        processing_time = (job.completed_at - job.started_at).total_seconds()

    # Compliance info from latest report
    report_stmt = (
        select(ComplianceReport)
        .where(ComplianceReport.campaign_id == campaign_id)
        .order_by(ComplianceReport.checked_at.desc())
        .limit(1)
    )
    report = (await db.execute(report_stmt)).scalar_one_or_none()
    compliance_pass_rate = 100.0
    if report:
        violations = report.violations or []
        error_count = sum(1 for v in violations if v.get("severity") == "error")
        total_checks = max(len(violations), 1)
        compliance_pass_rate = round((1.0 - error_count / total_checks) * 100, 2)

    metrics = CampaignMetricsResponse(
        campaign_id=campaign_id,
        total_assets=total_assets,
        assets_by_locale=assets_by_locale,
        assets_by_ratio=assets_by_ratio,
        processing_time_seconds=processing_time,
        api_calls=0,
        cache_hit_rate=0.0,
        compliance_pass_rate=compliance_pass_rate,
        cost_estimate_usd=0.0,
    )

    return Envelope[CampaignMetricsResponse](data=metrics, meta=Meta())


# ---------------------------------------------------------------------------
# GET /metrics/aggregate
# ---------------------------------------------------------------------------


@router.get(
    "/metrics/aggregate",
    response_model=Envelope[AggregateMetricsResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def get_aggregate_metrics(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return platform-wide aggregate metrics."""
    from src.db.models import Campaign, GeneratedAsset, Job  # noqa: E402

    total_campaigns = (
        await db.execute(select(func.count()).select_from(Campaign))
    ).scalar_one()

    total_assets = (
        await db.execute(select(func.count()).select_from(GeneratedAsset))
    ).scalar_one()

    # Campaigns by status
    status_rows = (
        await db.execute(
            select(Campaign.status, func.count()).group_by(Campaign.status)
        )
    ).all()
    campaigns_by_status = {row[0]: row[1] for row in status_rows}

    # Campaigns by backend
    backend_rows = (
        await db.execute(
            select(Campaign.image_backend, func.count()).group_by(Campaign.image_backend)
        )
    ).all()
    campaigns_by_backend = {row[0]: row[1] for row in backend_rows}

    # Average processing time for completed jobs
    avg_time_result = (
        await db.execute(
            select(
                func.avg(
                    func.extract("epoch", Job.completed_at)
                    - func.extract("epoch", Job.started_at)
                )
            ).where(
                Job.status == "completed",
                Job.started_at.isnot(None),
                Job.completed_at.isnot(None),
            )
        )
    ).scalar_one()
    avg_processing_time = round(float(avg_time_result or 0), 2)

    metrics = AggregateMetricsResponse(
        total_campaigns=total_campaigns,
        total_assets=total_assets,
        avg_processing_time_seconds=avg_processing_time,
        total_api_calls=0,
        avg_compliance_pass_rate=0.0,
        campaigns_by_status=campaigns_by_status,
        campaigns_by_backend=campaigns_by_backend,
    )

    return Envelope[AggregateMetricsResponse](data=metrics, meta=Meta())
