"""Integration tests for metrics endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.integration.conftest import (
    CAMPAIGN_ID,
    FakeScalarResult,
    _make_campaign,
    _make_job,
)


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _db_returning_sequence(mock_db, *results):
    fake_results = [FakeScalarResult(r) for r in results]
    mock_db.execute = AsyncMock(side_effect=fake_results)


class TestGetCampaignMetrics:
    """GET /api/v1/campaigns/{id}/metrics"""

    @pytest.mark.asyncio
    async def test_campaign_metrics_success(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()

        # Queries: campaign, total_assets, locale_rows, ratio_rows, job, report
        _db_returning_sequence(
            mock_db,
            campaign,           # campaign lookup
            5,                  # total asset count
            [("en-US", 3), ("es-MX", 2)],  # assets by locale
            [("1:1", 3), ("16:9", 2)],     # assets by ratio
            None,               # no completed job
            None,               # no compliance report
        )

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/metrics")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total_assets"] == 5
        assert body["assets_by_locale"]["en-US"] == 3

    @pytest.mark.asyncio
    async def test_campaign_metrics_not_found(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, None)

        resp = await ac.get(f"/api/v1/campaigns/{uuid.uuid4()}/metrics")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_campaign_metrics_with_job(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()

        job = _make_job(status="completed")
        job.started_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        job.completed_at = datetime(2026, 3, 1, 12, 2, 30, tzinfo=timezone.utc)

        _db_returning_sequence(
            mock_db,
            campaign,
            10,
            [],     # no locale breakdown
            [],     # no ratio breakdown
            job,    # completed job
            None,   # no compliance report
        )

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/metrics")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["processing_time_seconds"] == 150.0

    @pytest.mark.asyncio
    async def test_campaign_metrics_unauthenticated(self, client, mock_db):
        resp = await client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/metrics")
        assert resp.status_code in (401, 403)


class TestGetAggregateMetrics:
    """GET /api/v1/metrics/aggregate"""

    @pytest.mark.asyncio
    async def test_aggregate_metrics_success(self, authed_client):
        ac, mock_db = authed_client

        # Queries: total_campaigns, total_assets, status_rows, backend_rows, avg_time
        _db_returning_sequence(
            mock_db,
            10,                             # total campaigns
            100,                            # total assets
            [("draft", 3), ("completed", 7)],  # by status
            [("firefly", 8), ("openai", 2)],   # by backend
            42.5,                           # avg processing time
        )

        resp = await ac.get("/api/v1/metrics/aggregate")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total_campaigns"] == 10
        assert body["total_assets"] == 100
        assert body["avg_processing_time_seconds"] == 42.5

    @pytest.mark.asyncio
    async def test_aggregate_metrics_empty(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, 0, 0, [], [], 0)

        resp = await ac.get("/api/v1/metrics/aggregate")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total_campaigns"] == 0

    @pytest.mark.asyncio
    async def test_aggregate_metrics_unauthenticated(self, client, mock_db):
        resp = await client.get("/api/v1/metrics/aggregate")
        assert resp.status_code in (401, 403)
