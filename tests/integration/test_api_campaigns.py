"""Integration tests for /api/v1/campaigns/* endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from tests.integration.conftest import (
    CAMPAIGN_ID,
    USER_ADMIN_ID,
    USER_EDITOR_ID,
    USER_VIEWER_ID,
    FakeScalarResult,
    _make_campaign,
    _make_job,
    _make_user,
    admin_headers,
    editor_headers,
    viewer_headers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_returning_sequence(mock_db, *results):
    """Configure mock_db.execute to return different FakeScalarResults
    on successive calls, cycling through *results*.
    """
    fake_results = [FakeScalarResult(r) for r in results]
    mock_db.execute = AsyncMock(side_effect=fake_results)


# ===================================================================
# GET /api/v1/campaigns  (list)
# ===================================================================


class TestListCampaigns:
    """GET /api/v1/campaigns"""

    async def test_list_campaigns_paginated(self, authed_client):
        """Returns a paginated list with meta information."""
        ac, mock_db = authed_client
        c1 = _make_campaign(campaign_id="C1", campaign_name="First")
        c2 = _make_campaign(
            campaign_uuid=uuid.uuid4(),
            campaign_id="C2",
            campaign_name="Second",
        )

        # Calls: (1) count query -> scalar_one(), (2) select campaigns -> .all() returns tuples
        _db_returning_sequence(
            mock_db,
            2,                    # total count
            [(c1, 0), (c2, 3)],  # campaign rows as (Campaign, asset_count) tuples
        )

        resp = await ac.get("/api/v1/campaigns?page=1&per_page=10")

        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        assert body["meta"]["total"] == 2
        assert body["meta"]["page"] == 1
        assert len(body["data"]) == 2

    async def test_list_campaigns_filter_by_status(self, authed_client):
        """Filtering by status=draft returns only draft campaigns."""
        ac, mock_db = authed_client
        draft = _make_campaign(status="draft")

        # Calls: (1) count, (2) select with tuples
        _db_returning_sequence(
            mock_db,
            1,              # count
            [(draft, 0)],   # results as (Campaign, asset_count)
        )

        resp = await ac.get("/api/v1/campaigns?status=draft")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["status"] == "draft"

    async def test_list_campaigns_empty(self, authed_client):
        """An empty result set returns valid paginated response."""
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, 0, [])

        resp = await ac.get("/api/v1/campaigns")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    async def test_list_campaigns_unauthenticated(self, client, mock_db):
        """Unauthenticated request returns 401."""
        resp = await client.get("/api/v1/campaigns")

        assert resp.status_code == 401


# ===================================================================
# POST /api/v1/campaigns  (create)
# ===================================================================


class TestCreateCampaign:
    """POST /api/v1/campaigns"""

    async def test_create_as_editor(self, client, mock_db, editor_user):
        """An editor can create a campaign; returns 201."""
        # get_current_user lookup -> editor user
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(editor_user))

        resp = await client.post(
            "/api/v1/campaigns",
            json={
                "campaign_id": "WINTER2026",
                "campaign_name": "Winter 2026",
                "brand_name": "TechStyle",
                "brief": {"headline": "Winter is coming"},
            },
            headers=editor_headers(),
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["campaign_name"] == "Winter 2026"
        assert data["status"] == "draft"
        # Two add calls: campaign + job
        assert mock_db.add.call_count >= 2

    async def test_create_as_admin(self, client, mock_db, admin_user):
        """An admin can also create campaigns."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(admin_user))

        resp = await client.post(
            "/api/v1/campaigns",
            json={
                "campaign_id": "SPRING2026",
                "campaign_name": "Spring 2026",
                "brand_name": "StyleCo",
                "brief": {},
            },
            headers=admin_headers(),
        )

        assert resp.status_code == 201

    async def test_create_rejected_as_viewer(self, client, mock_db, viewer_user):
        """A viewer is forbidden from creating campaigns (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(viewer_user))

        resp = await client.post(
            "/api/v1/campaigns",
            json={
                "campaign_id": "NOPE",
                "campaign_name": "Should Fail",
                "brand_name": "X",
                "brief": {},
            },
            headers=viewer_headers(),
        )

        assert resp.status_code == 403

    async def test_create_missing_required_field(self, client, mock_db, editor_user):
        """Missing campaign_name triggers 422."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(editor_user))

        resp = await client.post(
            "/api/v1/campaigns",
            json={
                "campaign_id": "INCOMPLETE",
                "brand_name": "X",
            },
            headers=editor_headers(),
        )

        assert resp.status_code == 422


# ===================================================================
# GET /api/v1/campaigns/{id}  (detail)
# ===================================================================


class TestGetCampaign:
    """GET /api/v1/campaigns/{id}"""

    async def test_get_campaign_found(self, authed_client):
        """Existing campaign returns 200 with full details."""
        ac, mock_db = authed_client
        campaign = _make_campaign()
        job = _make_job()

        # Calls: (1) campaign lookup, (2) count assets, (3) latest job
        _db_returning_sequence(mock_db, campaign, 5, job)

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["campaign_id"] == "SUMMER2026"
        assert data["asset_count"] == 5
        assert data["latest_job"] is not None

    async def test_get_campaign_not_found(self, authed_client):
        """Non-existent campaign returns 404."""
        ac, mock_db = authed_client
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(None))

        fake_id = uuid.uuid4()
        resp = await ac.get(f"/api/v1/campaigns/{fake_id}")

        assert resp.status_code == 404

    async def test_get_campaign_unauthenticated(self, client, mock_db):
        """Unauthenticated access returns 401."""
        resp = await client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}")

        assert resp.status_code == 401


# ===================================================================
# PATCH /api/v1/campaigns/{id}  (update)
# ===================================================================


class TestUpdateCampaign:
    """PATCH /api/v1/campaigns/{id}"""

    async def test_update_draft_campaign(self, client, mock_db, editor_user):
        """Updating a draft campaign succeeds."""
        campaign = _make_campaign(status="draft")
        job = _make_job()

        # Calls: (1) auth lookup, (2) campaign lookup,
        #        (3) count assets, (4) latest job
        _db_returning_sequence(mock_db, editor_user, campaign, 0, job)

        resp = await client.patch(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            json={"campaign_name": "Updated Name"},
            headers=editor_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["campaign_name"] == "Updated Name"

    async def test_update_non_draft_rejected(self, client, mock_db, editor_user):
        """Updating a campaign that is not in draft status returns 400."""
        campaign = _make_campaign(status="completed")

        # Calls: (1) auth lookup, (2) campaign lookup
        _db_returning_sequence(mock_db, editor_user, campaign)

        resp = await client.patch(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            json={"campaign_name": "Nope"},
            headers=editor_headers(),
        )

        assert resp.status_code == 400
        assert "draft" in resp.json()["detail"].lower()

    async def test_update_rejected_as_viewer(self, client, mock_db, viewer_user):
        """Viewers cannot update campaigns (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(viewer_user))

        resp = await client.patch(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            json={"campaign_name": "Rejected"},
            headers=viewer_headers(),
        )

        assert resp.status_code == 403

    async def test_update_not_found(self, client, mock_db, editor_user):
        """Updating a non-existent campaign returns 404."""
        _db_returning_sequence(mock_db, editor_user, None)

        fake_id = uuid.uuid4()
        resp = await client.patch(
            f"/api/v1/campaigns/{fake_id}",
            json={"campaign_name": "Gone"},
            headers=editor_headers(),
        )

        assert resp.status_code == 404


# ===================================================================
# DELETE /api/v1/campaigns/{id}
# ===================================================================


class TestDeleteCampaign:
    """DELETE /api/v1/campaigns/{id}"""

    async def test_delete_as_admin(self, client, mock_db, admin_user):
        """Admin can delete a campaign (204)."""
        campaign = _make_campaign()

        # Calls: (1) auth lookup, (2) campaign lookup
        _db_returning_sequence(mock_db, admin_user, campaign)

        resp = await client.delete(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            headers=admin_headers(),
        )

        assert resp.status_code == 204
        mock_db.delete.assert_called_once_with(campaign)

    async def test_delete_rejected_as_editor(self, client, mock_db, editor_user):
        """Editors cannot delete campaigns (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(editor_user))

        resp = await client.delete(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            headers=editor_headers(),
        )

        assert resp.status_code == 403

    async def test_delete_rejected_as_viewer(self, client, mock_db, viewer_user):
        """Viewers cannot delete campaigns (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(viewer_user))

        resp = await client.delete(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            headers=viewer_headers(),
        )

        assert resp.status_code == 403

    async def test_delete_not_found(self, client, mock_db, admin_user):
        """Deleting a non-existent campaign returns 404."""
        _db_returning_sequence(mock_db, admin_user, None)

        fake_id = uuid.uuid4()
        resp = await client.delete(
            f"/api/v1/campaigns/{fake_id}",
            headers=admin_headers(),
        )

        assert resp.status_code == 404
