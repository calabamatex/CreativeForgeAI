"""Integration tests for /api/v1/campaigns/* endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from datetime import datetime, timezone

from sqlalchemy import select

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


# ===================================================================
# Enqueue wiring (P3-T1) -- REAL DB harness + recording fake ARQ pool
# ===================================================================


async def _seed_editor_and_headers(session) -> dict[str, str]:
    """Seed a real editor user in the test DB and return a real Bearer header.

    Mirrors the e2e test's approach (direct seed + mint, dodging the known
    passlib/bcrypt env bug). Every subsequent request authenticates through the
    real ``get_current_user`` against the real test DB.
    """
    import uuid as _uuid

    from src.api.dependencies import create_access_token
    from src.db.models import User

    user = User(
        id=_uuid.uuid4(),
        email=f"enq-{_uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.not.used.for.jwt.login.flow",
        display_name="Enqueue Editor",
        role="editor",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()

    token = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestEnqueueOnCreate:
    """POST /campaigns and /reprocess enqueue process_campaign_job (P3-T1)."""

    async def test_create_enqueues_exactly_one_job_with_db_job_id(
        self, real_app_client, fake_arq_pool
    ):
        """Creating a campaign enqueues exactly one job whose _job_id == db job id,
        and the Job row is committed (queryable) before/at enqueue time.
        """
        from src.db.models import Job
        from src.api.dependencies import get_arq_pool

        client, session = real_app_client
        headers = await _seed_editor_and_headers(session)

        app = client._transport.app

        async def _override_pool():
            return fake_arq_pool

        app.dependency_overrides[get_arq_pool] = _override_pool

        campaign_key = f"ENQ-{uuid.uuid4().hex[:8]}"
        resp = await client.post(
            "/api/v1/campaigns",
            headers=headers,
            json={
                "campaign_id": campaign_key,
                "campaign_name": "Enqueue Test",
                "brand_name": "TechStyle",
                "image_backend": "firefly",
                "brief": {"headline": "Go"},
                "target_locales": ["en-US"],
                "aspect_ratios": ["1:1"],
            },
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        job_db_id = data["latest_job"]["id"]
        campaign_db_id = data["id"]

        # Exactly one live enqueue, _job_id == the DB job id.
        assert fake_arq_pool.live_job_ids() == [job_db_id]
        assert fake_arq_pool.count_for_job_id(job_db_id) == 1

        # The single recorded enqueue carries the right function + positional args.
        record = fake_arq_pool.jobs_for("process_campaign_job")[0]
        assert record.function_name == "process_campaign_job"
        assert record.args == (campaign_db_id, job_db_id)
        assert record.job_id == job_db_id

        # Commit-then-enqueue proof: the Job row is committed and queryable via a
        # FRESH query (not just pending in the unit-of-work).
        row = (
            await session.execute(
                select(Job).where(Job.id == uuid.UUID(job_db_id))
            )
        ).scalar_one_or_none()
        assert row is not None
        assert row.status == "queued"

    async def test_duplicate_enqueue_same_job_id_is_deduped(
        self, real_app_client, fake_arq_pool
    ):
        """A second enqueue with the same _job_id is deduped (not run twice)."""
        from src.api.dependencies import get_arq_pool

        client, session = real_app_client
        headers = await _seed_editor_and_headers(session)

        app = client._transport.app

        async def _override_pool():
            return fake_arq_pool

        app.dependency_overrides[get_arq_pool] = _override_pool

        campaign_key = f"ENQ-{uuid.uuid4().hex[:8]}"
        resp = await client.post(
            "/api/v1/campaigns",
            headers=headers,
            json={
                "campaign_id": campaign_key,
                "campaign_name": "Dedupe Test",
                "brand_name": "TechStyle",
                "image_backend": "firefly",
                "brief": {"headline": "Go"},
                "target_locales": ["en-US"],
                "aspect_ratios": ["1:1"],
            },
        )
        assert resp.status_code == 201, resp.text
        job_db_id = resp.json()["data"]["latest_job"]["id"]
        campaign_db_id = resp.json()["data"]["id"]

        # Simulate a duplicate enqueue for the SAME job id (e.g. a retry/replay).
        dup = await fake_arq_pool.enqueue_job(
            "process_campaign_job",
            campaign_db_id,
            job_db_id,
            _job_id=job_db_id,
        )
        # ARQ returns None when a job with this _job_id already exists.
        assert dup is None
        # Still exactly one LIVE job; the dupe is recorded as deduped.
        assert fake_arq_pool.live_job_ids() == [job_db_id]
        assert fake_arq_pool.count_for_job_id(job_db_id) == 2  # 1 live + 1 deduped

    async def test_reprocess_enqueues_job(self, real_app_client, fake_arq_pool):
        """Reprocessing a campaign enqueues exactly one job whose _job_id == db job id."""
        import uuid as _uuid

        from src.db.models import Campaign
        from src.api.dependencies import get_arq_pool

        client, session = real_app_client
        headers = await _seed_editor_and_headers(session)

        # Seed a campaign directly so we can reprocess it.
        campaign = Campaign(
            id=_uuid.uuid4(),
            campaign_id=f"RP-{_uuid.uuid4().hex[:8]}",
            campaign_name="Reprocess Me",
            brand_name="TechStyle",
            status="completed",
            image_backend="firefly",
            brief={"headline": "Go"},
            target_locales=["en-US"],
            aspect_ratios=["1:1"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(campaign)
        await session.flush()
        campaign_db_id = str(campaign.id)

        app = client._transport.app

        async def _override_pool():
            return fake_arq_pool

        app.dependency_overrides[get_arq_pool] = _override_pool

        resp = await client.post(
            f"/api/v1/campaigns/{campaign_db_id}/reprocess",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        job_db_id = resp.json()["data"]["id"]

        assert fake_arq_pool.live_job_ids() == [job_db_id]
        assert fake_arq_pool.count_for_job_id(job_db_id) == 1
        record = fake_arq_pool.jobs_for("process_campaign_job")[0]
        assert record.args == (campaign_db_id, job_db_id)
        assert record.job_id == job_db_id
