"""Integration tests for /api/v1/brands/* endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from tests.integration.conftest import (
    BRAND_ID,
    USER_ADMIN_ID,
    USER_EDITOR_ID,
    USER_VIEWER_ID,
    FakeScalarResult,
    _make_brand,
    _make_user,
    admin_headers,
    editor_headers,
    viewer_headers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_returning_sequence(mock_db, *results):
    fake_results = [FakeScalarResult(r) for r in results]
    mock_db.execute = AsyncMock(side_effect=fake_results)


# ===================================================================
# GET /api/v1/brands  (list)
# ===================================================================


class TestListBrands:
    """GET /api/v1/brands"""

    async def test_list_brands_paginated(self, authed_client):
        """Returns a paginated brand list."""
        ac, mock_db = authed_client
        b1 = _make_brand(name="BrandA")
        b2 = _make_brand(brand_id=uuid.uuid4(), name="BrandB")

        # Calls: (1) count, (2) select brands
        _db_returning_sequence(mock_db, 2, [b1, b2])

        resp = await ac.get("/api/v1/brands?page=1&per_page=10")

        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert len(body["data"]) == 2

    async def test_list_brands_empty(self, authed_client):
        """Empty result returns valid paginated response."""
        ac, mock_db = authed_client
        _db_returning_sequence(mock_db, 0, [])

        resp = await ac.get("/api/v1/brands")

        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["meta"]["total"] == 0

    async def test_list_brands_unauthenticated(self, client, mock_db):
        """Unauthenticated request returns 401."""
        resp = await client.get("/api/v1/brands")

        assert resp.status_code == 401


# ===================================================================
# POST /api/v1/brands  (create)
# ===================================================================


class TestCreateBrand:
    """POST /api/v1/brands"""

    async def test_create_as_editor(self, client, mock_db, editor_user):
        """Editor can create a brand guideline entry (201)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(editor_user))

        resp = await client.post(
            "/api/v1/brands",
            params={"name": "NewBrand"},
            headers=editor_headers(),
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "NewBrand"
        mock_db.add.assert_called_once()

    async def test_create_as_admin(self, client, mock_db, admin_user):
        """Admin can create a brand guideline entry."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(admin_user))

        resp = await client.post(
            "/api/v1/brands",
            params={"name": "AdminBrand"},
            headers=admin_headers(),
        )

        assert resp.status_code == 201

    async def test_create_rejected_as_viewer(self, client, mock_db, viewer_user):
        """Viewer cannot create brands (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(viewer_user))

        resp = await client.post(
            "/api/v1/brands",
            params={"name": "Nope"},
            headers=viewer_headers(),
        )

        assert resp.status_code == 403

    async def test_create_missing_name(self, client, mock_db, editor_user):
        """Missing brand name triggers 422."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(editor_user))

        resp = await client.post(
            "/api/v1/brands",
            headers=editor_headers(),
        )

        assert resp.status_code == 422


# ===================================================================
# GET /api/v1/brands/{id}  (detail)
# ===================================================================


class TestGetBrand:
    """GET /api/v1/brands/{id}"""

    async def test_get_brand_found(self, authed_client):
        """Existing brand returns 200."""
        ac, mock_db = authed_client
        brand = _make_brand()

        mock_db.execute = AsyncMock(return_value=FakeScalarResult(brand))

        resp = await ac.get(f"/api/v1/brands/{BRAND_ID}")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "TechStyle"
        assert data["primary_font"] == "Montserrat"

    async def test_get_brand_not_found(self, authed_client):
        """Non-existent brand returns 404."""
        ac, mock_db = authed_client
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(None))

        fake_id = uuid.uuid4()
        resp = await ac.get(f"/api/v1/brands/{fake_id}")

        assert resp.status_code == 404

    async def test_get_brand_unauthenticated(self, client, mock_db):
        """Unauthenticated returns 401."""
        resp = await client.get(f"/api/v1/brands/{BRAND_ID}")

        assert resp.status_code == 401


# ===================================================================
# PATCH /api/v1/brands/{id}  (update)
# ===================================================================


class TestUpdateBrand:
    """PATCH /api/v1/brands/{id}"""

    async def test_update_brand_as_editor(self, client, mock_db, editor_user):
        """Editor can update brand fields."""
        brand = _make_brand()

        # Calls: (1) auth lookup, (2) brand lookup
        _db_returning_sequence(mock_db, editor_user, brand)

        resp = await client.patch(
            f"/api/v1/brands/{BRAND_ID}",
            json={
                "name": "Renamed Brand",
                "brand_voice": "Bold and playful",
            },
            headers=editor_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "Renamed Brand"
        assert data["brand_voice"] == "Bold and playful"

    async def test_update_brand_as_admin(self, client, mock_db, admin_user):
        """Admin can update brand fields."""
        brand = _make_brand()
        _db_returning_sequence(mock_db, admin_user, brand)

        resp = await client.patch(
            f"/api/v1/brands/{BRAND_ID}",
            json={"photography_style": "Moody"},
            headers=admin_headers(),
        )

        assert resp.status_code == 200

    async def test_update_rejected_as_viewer(self, client, mock_db, viewer_user):
        """Viewer cannot update brands (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(viewer_user))

        resp = await client.patch(
            f"/api/v1/brands/{BRAND_ID}",
            json={"name": "Nope"},
            headers=viewer_headers(),
        )

        assert resp.status_code == 403

    async def test_update_brand_not_found(self, client, mock_db, editor_user):
        """Updating non-existent brand returns 404."""
        _db_returning_sequence(mock_db, editor_user, None)

        fake_id = uuid.uuid4()
        resp = await client.patch(
            f"/api/v1/brands/{fake_id}",
            json={"name": "Gone"},
            headers=editor_headers(),
        )

        assert resp.status_code == 404

    async def test_update_partial_fields(self, client, mock_db, editor_user):
        """Only supplied fields are updated (partial update)."""
        brand = _make_brand()
        _db_returning_sequence(mock_db, editor_user, brand)

        resp = await client.patch(
            f"/api/v1/brands/{BRAND_ID}",
            json={"primary_colors": ["#FF0000", "#00FF00"]},
            headers=editor_headers(),
        )

        assert resp.status_code == 200


# ===================================================================
# DELETE /api/v1/brands/{id}
# ===================================================================


class TestDeleteBrand:
    """DELETE /api/v1/brands/{id}"""

    async def test_delete_as_admin(self, client, mock_db, admin_user):
        """Admin can delete a brand (204)."""
        brand = _make_brand()
        _db_returning_sequence(mock_db, admin_user, brand)

        resp = await client.delete(
            f"/api/v1/brands/{BRAND_ID}",
            headers=admin_headers(),
        )

        assert resp.status_code == 204
        mock_db.delete.assert_called_once_with(brand)

    async def test_delete_rejected_as_editor(self, client, mock_db, editor_user):
        """Editor cannot delete brands (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(editor_user))

        resp = await client.delete(
            f"/api/v1/brands/{BRAND_ID}",
            headers=editor_headers(),
        )

        assert resp.status_code == 403

    async def test_delete_rejected_as_viewer(self, client, mock_db, viewer_user):
        """Viewer cannot delete brands (403)."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(viewer_user))

        resp = await client.delete(
            f"/api/v1/brands/{BRAND_ID}",
            headers=viewer_headers(),
        )

        assert resp.status_code == 403

    async def test_delete_not_found(self, client, mock_db, admin_user):
        """Deleting non-existent brand returns 404."""
        _db_returning_sequence(mock_db, admin_user, None)

        fake_id = uuid.uuid4()
        resp = await client.delete(
            f"/api/v1/brands/{fake_id}",
            headers=admin_headers(),
        )

        assert resp.status_code == 404


# ===================================================================
# Full CRUD cycle
# ===================================================================


class TestBrandCRUDCycle:
    """Verify create -> read -> update -> delete flows correctly."""

    async def test_full_crud_cycle(self, client, mock_db, admin_user):
        """Exercise the complete CRUD lifecycle for brands."""
        brand = _make_brand(name="CycleBrand")

        # CREATE
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(admin_user))
        resp = await client.post(
            "/api/v1/brands",
            params={"name": "CycleBrand"},
            headers=admin_headers(),
        )
        assert resp.status_code == 201

        # READ
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(brand))
        resp = await client.get(
            f"/api/v1/brands/{BRAND_ID}",
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "CycleBrand"

        # UPDATE
        _db_returning_sequence(mock_db, admin_user, brand)
        resp = await client.patch(
            f"/api/v1/brands/{BRAND_ID}",
            json={"name": "UpdatedCycleBrand"},
            headers=admin_headers(),
        )
        assert resp.status_code == 200

        # DELETE
        _db_returning_sequence(mock_db, admin_user, brand)
        resp = await client.delete(
            f"/api/v1/brands/{BRAND_ID}",
            headers=admin_headers(),
        )
        assert resp.status_code == 204
