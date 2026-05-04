"""Integration tests for settings endpoints and health check."""
from __future__ import annotations

import pytest

from tests.integration.conftest import (
    FakeScalarResult,
    _make_user,
    USER_EDITOR_ID,
    USER_VIEWER_ID,
)


class TestHealthCheck:
    """GET /health"""

    @pytest.mark.asyncio
    async def test_health_check(self, client, mock_db):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "version" in body


class TestGetSettings:
    """GET /api/v1/settings"""

    @pytest.mark.asyncio
    async def test_get_settings_as_admin(self, authed_client):
        ac, mock_db = authed_client

        resp = await ac.get("/api/v1/settings")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert "default_backend" in body
        assert "available_backends" in body
        assert isinstance(body["available_backends"], list)
        assert "max_concurrent_requests" in body
        assert "supported_locales" in body

    @pytest.mark.asyncio
    async def test_get_settings_unauthenticated(self, client, mock_db):
        resp = await client.get("/api/v1/settings")
        assert resp.status_code in (401, 403)


class TestUpdateSettings:
    """PATCH /api/v1/settings"""

    @pytest.mark.asyncio
    async def test_update_settings_as_admin(self, authed_client):
        ac, mock_db = authed_client

        resp = await ac.patch(
            "/api/v1/settings",
            json={"enable_localization": False, "max_concurrent_requests": 10},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["enable_localization"] is False
        assert body["max_concurrent_requests"] == 10

    @pytest.mark.asyncio
    async def test_update_settings_unauthenticated(self, client, mock_db):
        resp = await client.patch("/api/v1/settings", json={"enable_localization": False})
        assert resp.status_code in (401, 403)


class TestListBackends:
    """GET /api/v1/settings/backends"""

    @pytest.mark.asyncio
    async def test_list_backends_as_admin(self, authed_client):
        ac, mock_db = authed_client

        resp = await ac.get("/api/v1/settings/backends")
        assert resp.status_code == 200
        backends = resp.json()["data"]
        assert isinstance(backends, list)
        assert len(backends) >= 3  # firefly, openai, gemini at minimum
        names = {b["name"] for b in backends}
        assert "firefly" in names
        assert "openai" in names
        assert "gemini" in names

    @pytest.mark.asyncio
    async def test_list_backends_unauthenticated(self, client, mock_db):
        resp = await client.get("/api/v1/settings/backends")
        assert resp.status_code in (401, 403)
