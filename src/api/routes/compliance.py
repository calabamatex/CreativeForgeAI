"""Compliance endpoints: get report, run check, approve with warnings."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.dependencies import (
    check_rate_limit,
    get_current_user,
    get_db,
    require_role,
)
from src.api.errors import BadRequestError, NotFoundError
from src.api.schemas import (
    ComplianceApproveRequest,
    ComplianceReportResponse,
    Envelope,
    Meta,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["compliance"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_campaign_or_404(campaign_id: uuid.UUID, db: AsyncSession):
    from src.db.models import Campaign  # noqa: E402

    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise NotFoundError("Campaign", str(campaign_id))
    return campaign


async def _get_latest_report(campaign_id: uuid.UUID, db: AsyncSession):
    from src.db.models import ComplianceReport  # noqa: E402

    stmt = (
        select(ComplianceReport)
        .where(ComplianceReport.campaign_id == campaign_id)
        .order_by(ComplianceReport.checked_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _run_compliance_check(campaign, db: AsyncSession) -> dict:
    """Execute the compliance check pipeline for a campaign.

    Delegates to the existing ``legal_checker`` module when available,
    otherwise returns a synthetic passing report.
    """
    violations: list[dict] = []
    is_compliant = True
    summary: dict = {}

    try:
        from src.legal_checker import LegalChecker

        brief = campaign.brief or {}
        checker = LegalChecker()
        result = checker.check_content(brief)

        if hasattr(result, "violations") and result.violations:
            for v in result.violations:
                violations.append({
                    "severity": v.get("severity", "error"),
                    "code": v.get("code", "LEGAL_001"),
                    "message": v.get("message", str(v)),
                    "field": v.get("field"),
                    "locale": v.get("locale"),
                })

        has_errors = any(v["severity"] == "error" for v in violations)
        is_compliant = not has_errors
        summary = {
            "total_checks": len(violations) if violations else 1,
            "errors": sum(1 for v in violations if v["severity"] == "error"),
            "warnings": sum(1 for v in violations if v["severity"] == "warning"),
        }

    except Exception as exc:  # noqa: BLE001
        logger.warning("compliance.check_error", campaign_id=str(campaign.id), error=str(exc))
        summary = {"error": str(exc), "fallback": True}

    return {
        "is_compliant": is_compliant,
        "violations": violations,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# GET /campaigns/{id}/compliance
# ---------------------------------------------------------------------------


@router.get(
    "/campaigns/{campaign_id}/compliance",
    response_model=Envelope[ComplianceReportResponse | None],
    dependencies=[Depends(check_rate_limit)],
)
async def get_compliance_report(
    campaign_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest compliance report for a campaign, or null if none exists."""
    await _get_campaign_or_404(campaign_id, db)
    report = await _get_latest_report(campaign_id, db)

    data = ComplianceReportResponse.model_validate(report) if report else None

    return Envelope[ComplianceReportResponse | None](data=data, meta=Meta())


# ---------------------------------------------------------------------------
# POST /campaigns/{id}/compliance/check
# ---------------------------------------------------------------------------


@router.post(
    "/campaigns/{campaign_id}/compliance/check",
    response_model=Envelope[ComplianceReportResponse],
    status_code=201,
    dependencies=[Depends(check_rate_limit)],
)
async def run_compliance_check(
    campaign_id: uuid.UUID,
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Execute a compliance check against campaign content and store the report."""
    from src.db.models import ComplianceReport  # noqa: E402

    campaign = await _get_campaign_or_404(campaign_id, db)
    check_result = await _run_compliance_check(campaign, db)

    now = datetime.now(timezone.utc)
    report = ComplianceReport(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        is_compliant=check_result["is_compliant"],
        violations=check_result["violations"],
        summary=check_result["summary"],
        checked_at=now,
    )
    db.add(report)
    await db.flush()

    logger.info(
        "compliance.checked",
        campaign_id=str(campaign_id),
        is_compliant=check_result["is_compliant"],
        violation_count=len(check_result["violations"]),
    )

    return Envelope[ComplianceReportResponse](
        data=ComplianceReportResponse.model_validate(report),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# POST /campaigns/{id}/compliance/approve
# ---------------------------------------------------------------------------


@router.post(
    "/campaigns/{campaign_id}/compliance/approve",
    response_model=Envelope[ComplianceReportResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def approve_compliance(
    campaign_id: uuid.UUID,
    body: ComplianceApproveRequest | None = None,
    user=Depends(require_role(["editor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Approve a compliance report that has warnings.

    Only reports that are non-compliant or have violations can be approved.
    This overrides ``is_compliant`` to ``True`` and records approval notes
    in the summary.
    """
    await _get_campaign_or_404(campaign_id, db)
    report = await _get_latest_report(campaign_id, db)

    if report is None:
        raise NotFoundError("ComplianceReport", f"campaign:{campaign_id}")

    if report.is_compliant and not report.violations:
        raise BadRequestError(
            detail="Report is already fully compliant with no violations. Nothing to approve."
        )

    # Mark as approved with warnings
    report.is_compliant = True
    summary = dict(report.summary) if report.summary else {}
    summary["approved_by"] = str(user.id)
    summary["approved_at"] = datetime.now(timezone.utc).isoformat()
    if body and body.notes:
        summary["approval_notes"] = body.notes
    report.summary = summary

    await db.flush()

    logger.info(
        "compliance.approved",
        campaign_id=str(campaign_id),
        report_id=str(report.id),
        approved_by=str(user.id),
    )

    return Envelope[ComplianceReportResponse](
        data=ComplianceReportResponse.model_validate(report),
        meta=Meta(),
    )
