"""Integration tests for job endpoints."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from tests.integration.conftest import (
    JOB_ID,
    CAMPAIGN_ID,
    FakeScalarResult,
    _make_job,
)


def _db_returning_sequence(mock_db, *results):
    fake_results = [FakeScalarResult(r) for r in results]
    mock_db.execute = AsyncMock(side_effect=fake_results)


class TestListJobs:
    """GET /api/v1/jobs"""

    @pytest.mark.asyncio
    async def test_list_jobs_paginated(self, authed_client):
        ac, mock_db = authed_client
        j1 = _make_job()
        j2 = _make_job(job_id=uuid.uuid4(), status="completed")

        _db_returning_sequence(mock_db, 2, [j1, j2])

        resp = await ac.get("/api/v1/jobs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert len(body["data"]) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, 0, [])

        resp = await ac.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert body_data(resp) == []

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(self, authed_client):
        ac, mock_db = authed_client
        j = _make_job(status="running")

        _db_returning_sequence(mock_db, 1, [j])

        resp = await ac.get("/api/v1/jobs?status=running")
        assert resp.status_code == 200
        assert len(body_data(resp)) == 1

    @pytest.mark.asyncio
    async def test_list_jobs_unauthenticated(self, client, mock_db):
        resp = await client.get("/api/v1/jobs")
        assert resp.status_code in (401, 403)


class TestGetJob:
    """GET /api/v1/jobs/{id}"""

    @pytest.mark.asyncio
    async def test_get_job_found(self, authed_client):
        ac, mock_db = authed_client
        job = _make_job()

        _db_returning_sequence(mock_db, job)

        resp = await ac.get(f"/api/v1/jobs/{JOB_ID}")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, None)

        resp = await ac.get(f"/api/v1/jobs/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestCancelJob:
    """POST /api/v1/jobs/{id}/cancel"""

    @pytest.mark.asyncio
    async def test_cancel_queued_job(self, authed_client):
        ac, mock_db = authed_client
        job = _make_job(status="queued")

        _db_returning_sequence(mock_db, job)

        resp = await ac.post(f"/api/v1/jobs/{JOB_ID}/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, authed_client):
        ac, mock_db = authed_client
        job = _make_job(status="running")

        _db_returning_sequence(mock_db, job)

        resp = await ac.post(f"/api/v1/jobs/{JOB_ID}/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_completed_job_rejected(self, authed_client):
        ac, mock_db = authed_client
        job = _make_job(status="completed")

        _db_returning_sequence(mock_db, job)

        resp = await ac.post(f"/api/v1/jobs/{JOB_ID}/cancel")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_rejected(self, authed_client):
        ac, mock_db = authed_client
        job = _make_job(status="cancelled")

        _db_returning_sequence(mock_db, job)

        resp = await ac.post(f"/api/v1/jobs/{JOB_ID}/cancel")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, None)

        resp = await ac.post(f"/api/v1/jobs/{uuid.uuid4()}/cancel")
        assert resp.status_code == 404


def body_data(resp):
    return resp.json()["data"]
