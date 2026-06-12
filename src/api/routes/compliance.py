"""Compliance endpoints: get report, run check, approve with warnings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    check_rate_limit,
    get_current_user,
    get_db,
    require_role,
)
from src.api.errors import BadRequestError, InternalServerError, NotFoundError
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


def _serialize_violation(v) -> dict:
    """Convert a :class:`ComplianceViolation` dataclass into a JSON-safe dict."""
    return {
        "severity": v.severity,
        "category": v.category,
        "field": v.field,
        "violation": v.violation,
        "message": v.message,
        "suggestion": v.suggestion,
    }


def _build_campaign_message(brief: dict):
    """Build a :class:`CampaignMessage` from a campaign brief dict.

    The brief stores the default message under ``campaign_message`` (see
    :class:`src.models.campaign.CampaignBrief`). Older/partial briefs may store
    the headline fields at the top level, so we fall back to that shape.
    """
    from src.models import CampaignMessage  # noqa: E402

    msg = brief.get("campaign_message")
    if isinstance(msg, dict) and msg:
        return CampaignMessage(**msg)

    # Fallback: assemble from top-level keys. ``CampaignMessage`` requires
    # non-empty headline/subheadline/cta, so default missing ones to a single
    # space to keep the checker runnable without fabricating content.
    return CampaignMessage(
        locale=brief.get("locale", "en-US"),
        headline=brief.get("headline") or " ",
        subheadline=brief.get("subheadline") or " ",
        cta=brief.get("cta") or " ",
    )


def _gather_product_contents(brief: dict) -> list[dict]:
    """Extract per-product content dicts (description + features) from a brief."""
    products = brief.get("products") or []
    contents: list[dict] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        contents.append(
            {
                "description": product.get("product_description", ""),
                "features": product.get("key_features", []) or [],
            }
        )
    return contents


async def _run_compliance_check(campaign, db: AsyncSession) -> dict:
    """Execute the REAL legal compliance check for a campaign.

    Loads the campaign's stored legal guidelines (``campaign.legal_guidelines``),
    runs :class:`src.legal_checker.LegalComplianceChecker` against the brief's
    campaign message and product content, and returns the truthful verdict.

    Returns a dict with keys ``is_compliant`` (``True``/``False``/``None``),
    ``violations`` and ``summary``. ``is_compliant is None`` means the campaign
    was NOT checked because no guidelines are configured -- this must never be
    presented as compliant.

    Raises:
        InternalServerError: If the configured guidelines are malformed or the
            checker fails unexpectedly. The error is surfaced as a 5xx and is
            NEVER masked as a passing report.
    """
    from src.legal_checker import LegalComplianceChecker  # noqa: E402
    from src.models import LegalComplianceGuidelines  # noqa: E402

    raw_guidelines = getattr(campaign, "legal_guidelines", None)

    # No guidelines configured -> explicit "not checked" state. NOT compliant.
    if not raw_guidelines or not isinstance(raw_guidelines, dict):
        logger.info("compliance.not_checked", campaign_id=str(campaign.id))
        return {
            "is_compliant": None,
            "violations": [],
            "summary": {
                "status": "not_checked",
                "message": "not checked — no legal guidelines configured",
            },
        }

    brief = campaign.brief or {}

    # Construct the guidelines + checker. A malformed guidelines blob is a
    # server-side configuration error, not a pass.
    try:
        guidelines = LegalComplianceGuidelines(**raw_guidelines)
    except (TypeError, ValueError) as exc:
        logger.error(
            "compliance.guidelines_invalid",
            campaign_id=str(campaign.id),
            error=str(exc),
        )
        raise InternalServerError(detail="Configured legal guidelines are invalid and could not be loaded.") from exc

    # Build the message + product content from the brief. A malformed brief is
    # likewise a server-side error, never a silent pass.
    try:
        message = _build_campaign_message(brief)
        product_contents = _gather_product_contents(brief)
        locales = brief.get("target_locales") or campaign.target_locales or ["en-US"]
        locale = locales[0] if locales else "en-US"
    except (TypeError, ValueError, KeyError) as exc:
        logger.error(
            "compliance.brief_invalid",
            campaign_id=str(campaign.id),
            error=str(exc),
        )
        raise InternalServerError(detail="Campaign brief is invalid and could not be compliance-checked.") from exc

    checker = LegalComplianceChecker(guidelines)

    # Run the checker over the message and every product. Accumulate ALL
    # violations across passes so the persisted report is complete.
    is_compliant, message_violations = checker.check_content(message, product_content=None, locale=locale)
    all_violations = list(message_violations)

    for product_content in product_contents:
        product_compliant, product_violations = checker.check_content(
            message, product_content=product_content, locale=locale
        )
        if not product_compliant:
            is_compliant = False
        all_violations.extend(product_violations)

    violations = [_serialize_violation(v) for v in all_violations]
    summary = {
        "status": "checked",
        "total_violations": len(violations),
        "errors": sum(1 for v in violations if v["severity"] == "error"),
        "warnings": sum(1 for v in violations if v["severity"] == "warning"),
        "info": sum(1 for v in violations if v["severity"] == "info"),
        "guidelines_source": raw_guidelines.get("source_file"),
    }

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

    now = datetime.now(UTC)
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

    # A "not checked" report (is_compliant is None) was never actually
    # evaluated -- approving it would mask the unchecked state as compliant.
    if report.is_compliant is None:
        raise BadRequestError(
            detail=(
                "Report was not checked (no legal guidelines configured). "
                "Run a compliance check with guidelines before approving."
            )
        )

    if report.is_compliant and not report.violations:
        raise BadRequestError(detail="Report is already fully compliant with no violations. Nothing to approve.")

    # Mark as approved with warnings
    report.is_compliant = True
    summary = dict(report.summary) if report.summary else {}
    summary["approved_by"] = str(user.id)
    summary["approved_at"] = datetime.now(UTC).isoformat()
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
