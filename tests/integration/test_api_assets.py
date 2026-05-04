"""Integration tests for /api/v1/assets/* and /api/v1/campaigns/{id}/assets endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from tests.integration.conftest import (
    ASSET_ID,
    CAMPAIGN_ID,
    FakeScalarResult,
    _make_asset,
    _make_campaign,
    admin_headers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_returning_sequence(mock_db, *results):
    """Configure mock_db.execute to yield ``FakeScalarResult(r)`` for each *r*."""
    fake_results = [FakeScalarResult(r) for r in results]
    mock_db.execute = AsyncMock(side_effect=fake_results)


# ===================================================================
# GET /api/v1/campaigns/{id}/assets  (list)
# ===================================================================


class TestListCampaignAssets:
    """GET /api/v1/campaigns/{campaign_id}/assets"""

    async def test_list_assets_success(self, authed_client):
        """Returns paginated asset list for an existing campaign."""
        ac, mock_db = authed_client
        campaign_pk = CAMPAIGN_ID  # column value returned by the campaign-exists check
        asset = _make_asset()

        # Calls:
        #  (1) _campaign_exists select(Campaign.id) -> campaign PK scalar
        #  (2) count query -> total
        #  (3) select assets -> list
        _db_returning_sequence(mock_db, campaign_pk, 1, [asset])

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/assets")

        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["product_id"] == "PROD-001"

    async def test_list_assets_empty(self, authed_client):
        """An empty assets list returns valid paginated response."""
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 0, [])

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/assets")

        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["meta"]["total"] == 0

    async def test_list_assets_campaign_not_found(self, authed_client):
        """Listing assets for a non-existent campaign returns 404."""
        ac, mock_db = authed_client
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(None))

        fake_id = uuid.uuid4()
        resp = await ac.get(f"/api/v1/campaigns/{fake_id}/assets")

        assert resp.status_code == 404

    async def test_list_assets_filter_by_locale(self, authed_client):
        """Locale filter is accepted and forwarded to query."""
        ac, mock_db = authed_client
        asset = _make_asset()

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 1, [asset])

        resp = await ac.get(
            f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?locale=en-US"
        )

        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    async def test_list_assets_filter_by_aspect_ratio(self, authed_client):
        """Aspect ratio filter is accepted."""
        ac, mock_db = authed_client
        asset = _make_asset()

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 1, [asset])

        resp = await ac.get(
            f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?aspect_ratio=1:1"
        )

        assert resp.status_code == 200

    async def test_list_assets_filter_by_generation_method(self, authed_client):
        """Generation method filter is accepted."""
        ac, mock_db = authed_client
        asset = _make_asset()

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 1, [asset])

        resp = await ac.get(
            f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?generation_method=firefly"
        )

        assert resp.status_code == 200

    async def test_list_assets_pagination(self, authed_client):
        """Custom page and per_page are reflected in meta."""
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 50, [])

        resp = await ac.get(
            f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?page=3&per_page=5"
        )

        assert resp.status_code == 200
        meta = resp.json()["meta"]
        assert meta["page"] == 3
        assert meta["per_page"] == 5
        assert meta["total"] == 50

    async def test_list_assets_unauthenticated(self, client, mock_db):
        """Unauthenticated access returns 401."""
        resp = await client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/assets")

        assert resp.status_code == 401


# ===================================================================
# GET /api/v1/assets/{id}  (detail)
# ===================================================================


class TestGetAsset:
    """GET /api/v1/assets/{asset_id}"""

    async def test_get_asset_found(self, authed_client):
        """Returns 200 with full asset metadata."""
        ac, mock_db = authed_client
        asset = _make_asset()

        mock_db.execute = AsyncMock(return_value=FakeScalarResult(asset))

        resp = await ac.get(f"/api/v1/assets/{ASSET_ID}")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["locale"] == "en-US"
        assert data["aspect_ratio"] == "1:1"
        assert data["generation_method"] == "firefly"
        assert data["file_size_bytes"] == 102400
        assert data["width"] == 1024
        assert data["height"] == 1024

    async def test_get_asset_not_found(self, authed_client):
        """Non-existent asset returns 404."""
        ac, mock_db = authed_client
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(None))

        fake_id = uuid.uuid4()
        resp = await ac.get(f"/api/v1/assets/{fake_id}")

        assert resp.status_code == 404

    async def test_get_asset_unauthenticated(self, client, mock_db):
        """Unauthenticated access returns 401."""
        resp = await client.get(f"/api/v1/assets/{ASSET_ID}")

        assert resp.status_code == 401
