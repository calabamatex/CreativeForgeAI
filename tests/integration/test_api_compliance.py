"""Integration tests for compliance endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.integration.conftest import (
    CAMPAIGN_ID,
    FakeScalarResult,
    _make_campaign,
)


REPORT_ID = uuid.UUID("50000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_compliance_report(
    report_id: uuid.UUID = REPORT_ID,
    campaign_id: uuid.UUID = CAMPAIGN_ID,
    is_compliant: bool = True,
    violations: list | None = None,
    summary: dict | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = report_id
    r.campaign_id = campaign_id
    r.is_compliant = is_compliant
    r.violations = violations or []
    r.summary = summary or {"total_checks": 1, "errors": 0, "warnings": 0}
    r.checked_at = NOW
    return r


def _db_returning_sequence(mock_db, *results):
    fake_results = [FakeScalarResult(r) for r in results]
    mock_db.execute = AsyncMock(side_effect=fake_results)


class TestGetComplianceReport:
    """GET /api/v1/campaigns/{id}/compliance"""

    @pytest.mark.asyncio
    async def test_get_report_found(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()
        report = _make_compliance_report()

        _db_returning_sequence(mock_db, campaign, report)

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/compliance")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["is_compliant"] is True

    @pytest.mark.asyncio
    async def test_get_report_none_exists(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()

        _db_returning_sequence(mock_db, campaign, None)

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/compliance")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    @pytest.mark.asyncio
    async def test_get_report_campaign_not_found(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, None)

        fake_id = uuid.uuid4()
        resp = await ac.get(f"/api/v1/campaigns/{fake_id}/compliance")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_report_unauthenticated(self, client, mock_db):
        resp = await client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/compliance")
        assert resp.status_code in (401, 403)


class TestRunComplianceCheck:
    """POST /api/v1/campaigns/{id}/compliance/check"""

    @pytest.mark.asyncio
    async def test_run_check_success(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()

        _db_returning_sequence(mock_db, campaign)

        resp = await ac.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/compliance/check")
        assert resp.status_code == 201
        body = resp.json()
        assert "data" in body
        assert "is_compliant" in body["data"]

    @pytest.mark.asyncio
    async def test_run_check_campaign_not_found(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, None)

        resp = await ac.post(f"/api/v1/campaigns/{uuid.uuid4()}/compliance/check")
        assert resp.status_code == 404


class TestApproveCompliance:
    """POST /api/v1/campaigns/{id}/compliance/approve"""

    @pytest.mark.asyncio
    async def test_approve_with_violations(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()
        report = _make_compliance_report(
            is_compliant=False,
            violations=[{"severity": "warning", "code": "W001", "message": "needs review"}],
        )

        _db_returning_sequence(mock_db, campaign, report)

        resp = await ac.post(
            f"/api/v1/campaigns/{CAMPAIGN_ID}/compliance/approve",
            json={"notes": "Reviewed and accepted"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["is_compliant"] is True

    @pytest.mark.asyncio
    async def test_approve_already_compliant_rejected(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()
        report = _make_compliance_report(is_compliant=True, violations=[])

        _db_returning_sequence(mock_db, campaign, report)

        resp = await ac.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/compliance/approve")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_approve_no_report_exists(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()

        _db_returning_sequence(mock_db, campaign, None)

        resp = await ac.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/compliance/approve")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_campaign_not_found(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, None)

        resp = await ac.post(f"/api/v1/campaigns/{uuid.uuid4()}/compliance/approve")
        assert resp.status_code == 404
