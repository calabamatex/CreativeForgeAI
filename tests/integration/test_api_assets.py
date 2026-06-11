"""Integration tests for /api/v1/assets/* and /api/v1/campaigns/{id}/assets endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC
from unittest.mock import AsyncMock

import pytest

from tests.integration.conftest import (
    ASSET_ID,
    CAMPAIGN_ID,
    FakeScalarResult,
    _make_asset,
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

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?locale=en-US")

        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    async def test_list_assets_filter_by_aspect_ratio(self, authed_client):
        """Aspect ratio filter is accepted."""
        ac, mock_db = authed_client
        asset = _make_asset()

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 1, [asset])

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?aspect_ratio=1:1")

        assert resp.status_code == 200

    async def test_list_assets_filter_by_generation_method(self, authed_client):
        """Generation method filter is accepted."""
        ac, mock_db = authed_client
        asset = _make_asset()

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 1, [asset])

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?generation_method=firefly")

        assert resp.status_code == 200

    async def test_list_assets_pagination(self, authed_client):
        """Custom page and per_page are reflected in meta."""
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, CAMPAIGN_ID, 50, [])

        resp = await ac.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/assets?page=3&per_page=5")

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


# ===================================================================
# REAL worker persistence (P3-T2): run a job, then list assets.
# Uses the real-DB harness (Postgres test DB + fake pool/storage). The
# pipeline's image-gen + disk write are faked; the PERSISTENCE is the real
# ``process_campaign_job`` -> ``AssetRepository.upsert`` path. Reprocessing
# must converge to the SAME row count (proves the ON CONFLICT upsert).
# ===================================================================


_E2E_API = "/api/v1"
_E2E_PRODUCTS = ["PROD-API-1"]
_E2E_LOCALES = ["en-US", "es-MX"]
_E2E_RATIOS = ["1:1", "16:9"]
_E2E_EXPECTED = len(_E2E_PRODUCTS) * len(_E2E_LOCALES) * len(_E2E_RATIOS)  # 4


def _e2e_brief_payload(campaign_id: str) -> dict:
    return {
        "campaign_id": campaign_id,
        "campaign_name": "Asset Persistence Test",
        "brand_name": "TechStyle",
        "campaign_message": {
            "locale": "en-US",
            "headline": "Persist Me",
            "subheadline": "Idempotently",
            "cta": "Go",
        },
        "products": [
            {
                "product_id": _E2E_PRODUCTS[0],
                "product_name": "Test Widget",
                "product_description": "A widget for testing.",
                "product_category": "Electronics",
            }
        ],
        "target_locales": _E2E_LOCALES,
        "aspect_ratios": _E2E_RATIOS,
        "enable_localization": True,
        "image_generation_backend": "firefly",
    }


def _make_generating_process_campaign(*, output_dir, image_backend):
    """Generation-only fake: writes the mocked PNG to disk, returns CampaignOutput.

    The REAL worker reads those files and persists rows -- this fake never
    touches the DB, so the persistence under test is production code.
    """
    import os

    async def _process_campaign(brief, brief_path=None):
        from datetime import datetime

        from src.models import CampaignOutput
        from src.models.campaign import GeneratedAsset as AssetModel

        assets = []
        for product in brief.products:
            for locale in brief.target_locales:
                for ratio in brief.aspect_ratios:
                    png = await image_backend.generate_image()
                    ratio_seg = ratio.replace(":", "x")
                    asset_dir = os.path.join(output_dir, product.product_id, locale, ratio_seg)
                    os.makedirs(asset_dir, exist_ok=True)
                    file_path = os.path.join(asset_dir, "asset.png")
                    with open(file_path, "wb") as fh:
                        fh.write(png)
                    assets.append(
                        AssetModel(
                            product_id=product.product_id,
                            locale=locale,
                            aspect_ratio=ratio,
                            file_path=file_path,
                            generation_method="fake",
                            metadata={"generation_time_ms": 1.0},
                        )
                    )

        return CampaignOutput(
            campaign_id=brief.campaign_id,
            campaign_name=brief.campaign_name,
            generated_assets=assets,
            total_assets=len(assets),
            locales_processed=list(brief.target_locales),
            products_processed=[p.product_id for p in brief.products],
            processing_time_seconds=0.0,
            success_rate=1.0,
            errors=[],
            generation_timestamp=datetime.now(),
            technical_metrics=None,
        )

    return _process_campaign


async def _seed_editor_header(session):
    from datetime import datetime

    from src.api.dependencies import create_access_token
    from src.db.models import User

    user = User(
        id=uuid.uuid4(),
        email=f"assets-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.not.used.in.jwt.flow",
        display_name="Asset Editor",
        role="editor",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    token = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
@pytest.mark.e2e
class TestWorkerAssetPersistence:
    """The real worker persists assets; reprocess is idempotent."""

    async def test_run_job_persists_then_reprocess_is_idempotent(
        self,
        real_app_client,
        fake_arq_pool,
        patch_storage_factory,
        image_backend_mock,
        tmp_path,
    ):
        client, session = real_app_client
        out_dir = str(tmp_path / "out")
        headers = await _seed_editor_header(session)

        # Route the create/reprocess enqueues onto the recording fake pool.
        app = client._transport.app
        from src.api.dependencies import get_arq_pool

        async def _override_pool():
            return fake_arq_pool

        app.dependency_overrides[get_arq_pool] = _override_pool

        # --- create campaign ---
        ckey = f"ASSETS-{uuid.uuid4().hex[:8]}"
        create = await client.post(
            f"{_E2E_API}/campaigns",
            headers=headers,
            json={
                "campaign_id": ckey,
                "campaign_name": "Asset Persistence Test",
                "brand_name": "TechStyle",
                "image_backend": "firefly",
                "brief": _e2e_brief_payload(ckey),
                "target_locales": _E2E_LOCALES,
                "aspect_ratios": _E2E_RATIOS,
            },
        )
        assert create.status_code == 201, create.text
        created = create.json()["data"]
        campaign_db_id = created["id"]
        job_db_id = created["latest_job"]["id"]

        # --- drive the REAL worker (generation faked, persistence real) ---
        gen = _make_generating_process_campaign(output_dir=out_dir, image_backend=image_backend_mock)
        await fake_arq_pool.drive(campaign_db_id, job_db_id, session=session, process_campaign=gen)

        # --- GET /campaigns/{id}/assets -> exactly 4 ---
        resp = await client.get(f"{_E2E_API}/campaigns/{campaign_db_id}/assets", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["meta"]["total"] == _E2E_EXPECTED
        assert len(resp.json()["data"]) == _E2E_EXPECTED

        # Every persisted row has a non-null storage_key.
        for item in resp.json()["data"]:
            assert item["storage_key"]

        # --- reprocess -> drive again -> still exactly 4 (no dupes) ---
        rp = await client.post(f"{_E2E_API}/campaigns/{campaign_db_id}/reprocess", headers=headers)
        assert rp.status_code == 200, rp.text
        reprocess_job_id = rp.json()["data"]["id"]

        gen2 = _make_generating_process_campaign(output_dir=out_dir, image_backend=image_backend_mock)
        await fake_arq_pool.drive(campaign_db_id, reprocess_job_id, session=session, process_campaign=gen2)

        resp2 = await client.get(f"{_E2E_API}/campaigns/{campaign_db_id}/assets", headers=headers)
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["meta"]["total"] == _E2E_EXPECTED, (
            "reprocess must not double assets (uq_asset_variant upsert)"
        )

        await session.rollback()


# ===================================================================
# P3-T3: /assets/{id}/download resolves THROUGH the pluggable backend
# for BOTH a real local filesystem backend AND a real S3/MinIO backend.
#
# These tests stand up a REAL backend (not the in-memory fake), patch the
# storage factory so BOTH the worker (``get_storage_backend``) and the
# download route (``get_default_storage_backend``) resolve to that SAME
# instance, drive the real worker to save the bytes ONCE, then download and
# assert the returned bytes equal the originally generated PNG.
#
# * local -> FileResponse (200) streaming the file (P1-T3 containment honored)
# * s3    -> 307 redirect to a presigned URL whose fetched bytes MATCH
#
# The s3 case talks to the Compose MinIO (``integration`` tier, NOT paid).
# ===================================================================


def _patch_factory_to(backend):
    """Patch both storage-factory entry points to *backend* (one instance)."""
    from unittest.mock import patch as _patch

    import src.storage_factory as sf

    sf.get_default_storage_backend.cache_clear()
    return _patch.object(sf, "get_storage_backend", return_value=backend), _patch.object(
        sf, "get_default_storage_backend", return_value=backend
    )


async def _create_campaign_and_get_ids(client, headers, fake_arq_pool):
    ckey = f"DL-{uuid.uuid4().hex[:8]}"
    create = await client.post(
        f"{_E2E_API}/campaigns",
        headers=headers,
        json={
            "campaign_id": ckey,
            "campaign_name": "Download Backend Test",
            "brand_name": "TechStyle",
            "image_backend": "firefly",
            "brief": _e2e_brief_payload(ckey),
            "target_locales": _E2E_LOCALES,
            "aspect_ratios": _E2E_RATIOS,
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()["data"]
    return created["id"], created["latest_job"]["id"]


@pytest.mark.integration
@pytest.mark.e2e
class TestBackendDownload:
    """Download resolves through the backend for real local + real S3/MinIO."""

    async def _run(
        self,
        *,
        backend,
        client,
        session,
        fake_arq_pool,
        image_backend_mock,
        out_dir,
        expected_png,
    ):
        headers = await _seed_editor_header(session)

        app = client._transport.app
        from src.api.dependencies import get_arq_pool

        async def _override_pool():
            return fake_arq_pool

        app.dependency_overrides[get_arq_pool] = _override_pool

        campaign_db_id, job_db_id = await _create_campaign_and_get_ids(client, headers, fake_arq_pool)

        p1, p2 = _patch_factory_to(backend)
        with p1, p2:
            # Drive the REAL worker: it saves bytes ONCE through *backend*.
            gen = _make_generating_process_campaign(output_dir=out_dir, image_backend=image_backend_mock)
            await fake_arq_pool.drive(campaign_db_id, job_db_id, session=session, process_campaign=gen)

            resp = await client.get(f"{_E2E_API}/campaigns/{campaign_db_id}/assets", headers=headers)
            assert resp.status_code == 200, resp.text
            items = resp.json()["data"]
            assert len(items) == _E2E_EXPECTED
            asset_id = items[0]["id"]
            storage_key = items[0]["storage_key"]
            assert storage_key, "storage_key must be populated"

            # storage_key consistency: the key in the DB is exactly the key the
            # backend stored under (so a direct backend.get returns the bytes).
            stored = await backend.get(storage_key)
            assert stored == expected_png

            dl = await client.get(f"{_E2E_API}/assets/{asset_id}/download", headers=headers)
            return dl, storage_key

    async def test_local_backend_streams_file_response(
        self,
        real_app_client,
        fake_arq_pool,
        image_backend_mock,
        tmp_path,
        tiny_png,
    ):
        from src.storage_local import LocalStorageBackend

        client, session = real_app_client
        backend = LocalStorageBackend(base_dir=str(tmp_path / "local_store"))

        dl, storage_key = await self._run(
            backend=backend,
            client=client,
            session=session,
            fake_arq_pool=fake_arq_pool,
            image_backend_mock=image_backend_mock,
            out_dir=str(tmp_path / "gen_out"),
            expected_png=tiny_png,
        )

        # Local -> 200 FileResponse streaming the ACTUAL bytes.
        assert dl.status_code == 200, dl.text
        assert dl.content == tiny_png
        assert dl.content.startswith(b"\x89PNG\r\n\x1a\n")
        # File physically present under the containment-checked base dir.
        assert backend._resolve_path(storage_key).is_file()

        await session.rollback()

    async def test_s3_backend_redirects_to_working_presigned_url(
        self,
        real_app_client,
        fake_arq_pool,
        image_backend_mock,
        tmp_path,
        tiny_png,
    ):
        import httpx
        from src.exceptions import StorageError
        from src.storage_s3 import S3StorageBackend

        client, session = real_app_client
        try:
            backend = S3StorageBackend()
        except StorageError as exc:
            pytest.skip(f"S3/MinIO not configured: {exc}")

        # Use a unique key namespace so concurrent runs never collide, and clean
        # up afterwards.
        dl, storage_key = await self._run(
            backend=backend,
            client=client,
            session=session,
            fake_arq_pool=fake_arq_pool,
            image_backend_mock=image_backend_mock,
            out_dir=str(tmp_path / "gen_out"),
            expected_png=tiny_png,
        )

        try:
            # S3 -> 307 redirect to a presigned URL.
            assert dl.status_code == 307, dl.text
            url = dl.headers["location"]
            assert url, "redirect must carry a Location header"

            # Fetching the presigned URL returns the SAME bytes.
            async with httpx.AsyncClient() as http:
                fetched = await http.get(url)
            assert fetched.status_code == 200, fetched.text
            assert fetched.content == tiny_png
            assert fetched.content.startswith(b"\x89PNG\r\n\x1a\n")
        finally:
            # Best-effort cleanup of every key written by this run.
            for key in await backend.list_keys(storage_key.rsplit("/products/", 1)[0]):
                await backend.delete(key)
            await session.rollback()
