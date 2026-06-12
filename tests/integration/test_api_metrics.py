"""Integration tests for metrics endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from tests.integration.conftest import (
    CAMPAIGN_ID,
    FakeScalarResult,
    _make_campaign,
    _make_job,
)

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


def _db_returning_sequence(mock_db, *results):
    fake_results = [FakeScalarResult(r) for r in results]
    mock_db.execute = AsyncMock(side_effect=fake_results)


class TestGetCampaignMetrics:
    """GET /api/v1/campaigns/{id}/metrics"""

    @pytest.mark.asyncio
    async def test_campaign_metrics_success(self, authed_client):
        ac, mock_db = authed_client
        campaign = _make_campaign()

        # Queries: campaign, total_assets, locale_rows, ratio_rows, job,
        # report, metric_row
        _db_returning_sequence(
            mock_db,
            campaign,  # campaign lookup
            5,  # total asset count
            [("en-US", 3), ("es-MX", 2)],  # assets by locale
            [("1:1", 3), ("16:9", 2)],  # assets by ratio
            None,  # no completed job
            None,  # no compliance report
            None,  # no persisted metric row
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
        job.started_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        job.completed_at = datetime(2026, 3, 1, 12, 2, 30, tzinfo=UTC)

        _db_returning_sequence(
            mock_db,
            campaign,
            10,
            [],  # no locale breakdown
            [],  # no ratio breakdown
            job,  # completed job
            None,  # no compliance report
            None,  # no persisted metric row
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

        # Queries: total_campaigns, total_assets, status_rows, backend_rows,
        # avg_time, total_api_calls, compliance reports
        _db_returning_sequence(
            mock_db,
            10,  # total campaigns
            100,  # total assets
            [("draft", 3), ("completed", 7)],  # by status
            [("firefly", 8), ("openai", 2)],  # by backend
            42.5,  # avg processing time
            150,  # total api calls (summed JSONB)
            # compliance reports: one clean, one with an error violation
            [([],), ([{"severity": "error"}],)],
        )

        resp = await ac.get("/api/v1/metrics/aggregate")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total_campaigns"] == 10
        assert body["total_assets"] == 100
        assert body["avg_processing_time_seconds"] == 42.5
        assert body["total_api_calls"] == 150
        # avg of (100% clean, 0% one-error) == 50.0
        assert body["avg_compliance_pass_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_aggregate_metrics_empty(self, authed_client):
        ac, mock_db = authed_client

        _db_returning_sequence(mock_db, 0, 0, [], [], 0, 0, [])

        resp = await ac.get("/api/v1/metrics/aggregate")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total_campaigns"] == 0
        assert body["total_api_calls"] == 0
        assert body["avg_compliance_pass_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_aggregate_metrics_unauthenticated(self, client, mock_db):
        resp = await client.get("/api/v1/metrics/aggregate")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Real-DB end-to-end: persisted TechnicalMetrics served by the endpoints
# ---------------------------------------------------------------------------
#
# These exercise the PRODUCTION persistence path (worker -> MetricsRepository ->
# campaign_metrics row) against real Postgres via the harness, then assert the
# metrics endpoints serve the REAL recorded values (non-zero api_calls, a real
# cache_hit_rate, and a cost computed from the configurable price table) instead
# of the old hardcoded zeros. No paid calls: image gen is mocked, storage is the
# in-memory fake.


PRODUCTS = ["PROD-001"]
LOCALES = ["en-US", "es-MX"]
ASPECT_RATIOS = ["1:1", "16:9"]
# 1 product x 2 locales x 2 ratios = 4 generated images = 4 API calls.
EXPECTED_API_CALLS = len(PRODUCTS) * len(LOCALES) * len(ASPECT_RATIOS)

API = "/api/v1"

# Real TechnicalMetrics the fake pipeline returns for the run. These are the
# values we assert flow through persistence -> endpoint unchanged.
RUN_CACHE_HITS = 1
RUN_CACHE_MISSES = 3
RUN_CACHE_HIT_RATE = round(RUN_CACHE_HITS / (RUN_CACHE_HITS + RUN_CACHE_MISSES) * 100, 2)  # 25.0


def _brief_payload(campaign_id: str, backend: str) -> dict:
    return {
        "campaign_id": campaign_id,
        "campaign_name": "Metrics 2026 Launch",
        "brand_name": "TechStyle",
        "campaign_message": {
            "locale": "en-US",
            "headline": "Metrics",
            "subheadline": "Real numbers",
            "cta": "Shop Now",
        },
        "products": [
            {
                "product_id": PRODUCTS[0],
                "product_name": "Premium Wireless Headphones",
                "product_description": "High-fidelity wireless headphones.",
                "product_category": "Electronics",
            }
        ],
        "target_locales": LOCALES,
        "aspect_ratios": ASPECT_RATIOS,
        "enable_localization": True,
        "image_generation_backend": backend,
    }


def _make_metrics_process_campaign(*, output_dir, image_backend, backend_name):
    """Generation-only fake that ALSO returns real TechnicalMetrics.

    Like the e2e harness fake it generates images (mocked) + writes them to
    disk and persists NOTHING itself -- the real worker persists. The only
    addition is a populated ``technical_metrics`` so the worker's
    ``_persist_metrics`` writes a real campaign_metrics row.
    """
    import os

    async def _process_campaign(brief, brief_path=None):
        from datetime import datetime

        from src.models import CampaignOutput, TechnicalMetrics
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

        tech = TechnicalMetrics(
            backend_used=backend_name,
            total_api_calls=len(assets),
            cache_hits=RUN_CACHE_HITS,
            cache_misses=RUN_CACHE_MISSES,
            cache_hit_rate=RUN_CACHE_HIT_RATE,
            avg_api_response_time_ms=120.0,
            image_processing_time_ms=50.0,
            localization_time_ms=10.0,
            compliance_check_time_ms=5.0,
            peak_memory_mb=42.0,
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
            technical_metrics=tech,
        )

    return _process_campaign


async def _seed_editor(session) -> dict[str, str]:
    from datetime import datetime

    from src.api.dependencies import create_access_token
    from src.db.models import User

    user = User(
        id=uuid.uuid4(),
        email=f"metrics-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.not.used.for.jwt.login.flow",
        display_name="Metrics Editor",
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
@pytest.mark.asyncio
async def test_metrics_endpoint_serves_persisted_technical_metrics(
    real_app_client,
    fake_arq_pool,
    patch_storage_factory,
    image_backend_mock,
    tmp_path,
):
    """Run -> persist TechnicalMetrics -> GET /metrics serves real values."""
    from src.config import get_config

    client, session = real_app_client
    backend = "openai"  # priced backend so cost_estimate_usd is non-zero
    headers = await _seed_editor(session)

    app = client._transport.app
    from src.api.dependencies import get_arq_pool

    async def _override_pool():
        return fake_arq_pool

    app.dependency_overrides[get_arq_pool] = _override_pool

    campaign_key = f"METRICS-{uuid.uuid4().hex[:8]}"
    create = await client.post(
        f"{API}/campaigns",
        headers=headers,
        json={
            "campaign_id": campaign_key,
            "campaign_name": "Metrics 2026 Launch",
            "brand_name": "TechStyle",
            "image_backend": backend,
            "brief": _brief_payload(campaign_key, backend),
            "target_locales": LOCALES,
            "aspect_ratios": ASPECT_RATIOS,
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()["data"]
    campaign_db_id = created["id"]
    job_db_id = created["latest_job"]["id"]

    generate = _make_metrics_process_campaign(
        output_dir=str(tmp_path / "out"),
        image_backend=image_backend_mock,
        backend_name=backend,
    )
    await fake_arq_pool.drive(campaign_db_id, job_db_id, session=session, process_campaign=generate)

    job_resp = await client.get(f"{API}/jobs/{job_db_id}", headers=headers)
    assert job_resp.json()["data"]["status"] == "completed", job_resp.text

    # --- per-campaign metrics serve the REAL persisted values ---------------
    m = await client.get(f"{API}/campaigns/{campaign_db_id}/metrics", headers=headers)
    assert m.status_code == 200, m.text
    data = m.json()["data"]
    assert data["api_calls"] == EXPECTED_API_CALLS  # non-zero, real
    assert data["api_calls"] > 0
    assert data["cache_hit_rate"] == RUN_CACHE_HIT_RATE  # real, not 0.0

    # cost == api_calls x configured unit price for the backend.
    expected_cost = get_config().estimate_image_cost_usd(backend, EXPECTED_API_CALLS)
    assert expected_cost > 0  # openai is priced
    assert data["cost_estimate_usd"] == expected_cost

    # --- aggregate reflects the persisted row -------------------------------
    agg = await client.get(f"{API}/metrics/aggregate", headers=headers)
    assert agg.status_code == 200, agg.text
    agg_data = agg.json()["data"]
    assert agg_data["total_api_calls"] >= EXPECTED_API_CALLS
    assert agg_data["total_api_calls"] > 0

    app.dependency_overrides.pop(get_arq_pool, None)
    await session.rollback()


def test_unit_price_table_and_estimate():
    """Unit-level proof of the honest cost model and the price table.

    Known backends (and their aliases) carry the documented public list price;
    unknown/unpriced backends honestly yield 0.0 (never a placeholder). The
    estimate is exactly ``api_calls x unit_price``, with env override support.
    """
    from src.config import Config

    cfg = Config()
    # Documented defaults present.
    assert cfg.get_image_unit_price("openai") == 0.04
    assert cfg.get_image_unit_price("firefly") == 0.04
    assert cfg.get_image_unit_price("gemini") == 0.04
    # Aliases resolve to canonical keys.
    assert cfg.get_image_unit_price("dall-e") == cfg.get_image_unit_price("openai")
    assert cfg.get_image_unit_price("imagen") == cfg.get_image_unit_price("gemini")
    # Unpriced backend -> honest 0.0 (no placeholder).
    assert cfg.get_image_unit_price("fake") == 0.0
    assert cfg.get_image_unit_price(None) == 0.0
    # estimate = api_calls x unit_price.
    assert cfg.estimate_image_cost_usd("openai", 4) == round(4 * 0.04, 4)
    assert cfg.estimate_image_cost_usd("fake", 4) == 0.0


def test_price_table_env_override(monkeypatch):
    """IMAGE_BACKEND_PRICES env var overrides individual backend prices."""
    from src.config import Config

    monkeypatch.setenv("IMAGE_BACKEND_PRICES", "openai:0.10,gemini:0.0")
    cfg = Config()
    assert cfg.get_image_unit_price("openai") == 0.10
    assert cfg.get_image_unit_price("gemini") == 0.0
    # Untouched backends keep their documented default.
    assert cfg.get_image_unit_price("firefly") == 0.04
    assert cfg.estimate_image_cost_usd("openai", 5) == round(5 * 0.10, 4)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_zero_for_unpriced_backend(
    real_app_client,
    fake_arq_pool,
    patch_storage_factory,
    image_backend_mock,
    tmp_path,
    monkeypatch,
):
    """A zero-priced backend yields cost 0.0 but still real api_calls/cache rate.

    Drives a real run on a VALID backend ("gemini") whose price we override to
    0.0 via the IMAGE_BACKEND_PRICES env var, proving the cost is an honest 0.0
    derived from the price table -- not a hardcoded placeholder -- while
    api_calls and cache_hit_rate remain the real recorded values.
    """
    import src.config as config_module

    monkeypatch.setenv("IMAGE_BACKEND_PRICES", "gemini:0.0")
    # Reload the global config so the route's get_config() sees the override.
    config_module.reload_config()

    client, session = real_app_client
    backend = "gemini"  # valid brief backend, priced at 0.0 via override
    headers = await _seed_editor(session)

    app = client._transport.app
    from src.api.dependencies import get_arq_pool

    async def _override_pool():
        return fake_arq_pool

    app.dependency_overrides[get_arq_pool] = _override_pool

    campaign_key = f"METRICS-{uuid.uuid4().hex[:8]}"
    create = await client.post(
        f"{API}/campaigns",
        headers=headers,
        json={
            "campaign_id": campaign_key,
            "campaign_name": "Metrics Unpriced",
            "brand_name": "TechStyle",
            "image_backend": backend,
            "brief": _brief_payload(campaign_key, backend),
            "target_locales": LOCALES,
            "aspect_ratios": ASPECT_RATIOS,
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()["data"]

    generate = _make_metrics_process_campaign(
        output_dir=str(tmp_path / "out"),
        image_backend=image_backend_mock,
        backend_name=backend,
    )
    await fake_arq_pool.drive(
        created["id"],
        created["latest_job"]["id"],
        session=session,
        process_campaign=generate,
    )

    m = await client.get(f"{API}/campaigns/{created['id']}/metrics", headers=headers)
    assert m.status_code == 200, m.text
    data = m.json()["data"]
    assert data["api_calls"] == EXPECTED_API_CALLS  # still real
    assert data["cache_hit_rate"] == RUN_CACHE_HIT_RATE  # still real
    assert data["cost_estimate_usd"] == 0.0  # honest zero, not a placeholder

    app.dependency_overrides.pop(get_arq_pool, None)
    await session.rollback()
    # Restore the unmodified global config for subsequent tests.
    config_module.reload_config()
