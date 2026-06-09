"""Phase 3 end-to-end regression guard (P3-T0).

This is the single end-to-end integration test that drives the WHOLE API path
against real Postgres + the fake (free) image backend and asserts an asset is
retrievable at the end:

    register -> login -> POST /campaigns -> (enqueue) -> drive worker ->
    poll job to completed -> GET /campaigns/{id}/assets -> GET /assets/{id}/download

As of P3-T2 the full enqueue -> persist -> retrieve path is wired and this test
PASSES through PRODUCTION code:

* P3-T1 made ``POST /campaigns`` (and ``/reprocess``) enqueue the
  ``process_campaign_job`` via an injectable ARQ pool (``_job_id == <db job id>``).
* P3-T2 made the REAL worker (``process_campaign_job`` + ``AssetRepository``)
  persist ``generated_assets`` rows idempotently (``ON CONFLICT uq_asset_variant
  DO UPDATE``) with a populated ``storage_key``.
* P3-T3 will do the dual-storage architectural cleanup + S3 presigned download
  verification; the local/fake download path already works after T2.

De-circularisation (P3-T2): the persisting hook the test used to inject is GONE.
The test now supplies only a *generation-only* fake ``process_campaign`` (the
seam the harness fakes anyway -- image-gen + disk), which writes the mocked tiny
PNG to ``file_path`` and returns a ``CampaignOutput``. The REAL worker
(``process_campaign_job``/``_persist_assets``/``AssetRepository.upsert``) does the
PERSISTENCE -- so this test guards the production persistence path, not a
test-supplied hook. The ``strict-xfail`` tripwire is therefore removed.

No paid calls: the image backend is the mocked one (returns a tiny PNG) and
storage is an in-memory fake. ``integration`` tier (real DB, no external spend).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import select

from src.db.models import GeneratedAsset

pytestmark = [pytest.mark.asyncio, pytest.mark.integration, pytest.mark.e2e]


# --- expected asset matrix -------------------------------------------------
# 1 product x 2 locales x 2 aspect ratios => N = 4 expected assets.
PRODUCTS = ["PROD-001"]
LOCALES = ["en-US", "es-MX"]
ASPECT_RATIOS = ["1:1", "16:9"]
EXPECTED_ASSET_COUNT = len(PRODUCTS) * len(LOCALES) * len(ASPECT_RATIOS)
assert EXPECTED_ASSET_COUNT == 4  # 1 x 2 x 2


API = "/api/v1"


# ---------------------------------------------------------------------------
# Brief builder
# ---------------------------------------------------------------------------


def _campaign_brief_payload(campaign_id: str) -> dict:
    """A full ``CampaignBrief``-shaped dict for the ``brief`` field.

    The worker reconstructs ``CampaignBrief(**campaign.brief)``, so the dict
    must satisfy that model: one product, two locales, two aspect ratios.
    """
    return {
        "campaign_id": campaign_id,
        "campaign_name": "Summer 2026 Launch",
        "brand_name": "TechStyle",
        "campaign_message": {
            "locale": "en-US",
            "headline": "Summer Innovation",
            "subheadline": "Discover the Future",
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
        "image_generation_backend": "firefly",
    }


# ---------------------------------------------------------------------------
# Generation-only pipeline fake (image-gen + disk are faked; persistence is NOT)
# ---------------------------------------------------------------------------


def _make_generating_process_campaign(*, output_dir: str, image_backend):
    """Build a *generation-only* ``process_campaign`` coroutine.

    This fakes EXACTLY the seam the harness already fakes -- image generation and
    writing the final asset to disk -- and NOTHING ELSE. For every
    (product, locale, aspect_ratio) it asks the MOCKED image backend for bytes
    and writes them to a real file under *output_dir*, then returns a
    ``CampaignOutput`` whose ``generated_assets`` reference those files.

    It deliberately does NOT persist any DB row: the REAL worker
    (``process_campaign_job`` -> ``_persist_assets`` -> ``AssetRepository.upsert``)
    reads each ``file_path``, saves it through the (fake) storage backend, and
    idempotently upserts the row. That is the production persistence path this
    test guards -- the test supplies no persistence hook of its own.
    """

    async def _process_campaign(brief, brief_path=None):
        from datetime import datetime

        from src.models import CampaignOutput
        from src.models.campaign import GeneratedAsset as AssetModel

        assets: list[AssetModel] = []
        for product in brief.products:
            for locale in brief.target_locales:
                for ratio in brief.aspect_ratios:
                    png = await image_backend.generate_image()
                    ratio_seg = ratio.replace(":", "x")
                    asset_dir = os.path.join(
                        output_dir, product.product_id, locale, ratio_seg
                    )
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


# ---------------------------------------------------------------------------
# Auth helper (real user in the real DB -> real JWT -> real auth on every call)
# ---------------------------------------------------------------------------


async def _register_and_login(client, session) -> dict[str, str]:
    """Seed an editor user in the real DB and return a real Bearer header.

    Intent is the task's "register + login via the API": every subsequent
    request below is authenticated through ``get_current_user``, which decodes
    a REAL JWT and loads the User row from the REAL test DB. We seed the row +
    mint the token directly instead of POSTing ``/auth/register`` + ``/login``
    purely because of a pre-existing ENVIRONMENT bug (passlib 1.7.4 +
    bcrypt 5.0.0: ``hash_password`` raises "password cannot be longer than 72
    bytes" from passlib's broken backend self-test). That bcrypt breakage is
    unrelated to the Phase 3 enqueue->persist->retrieve wiring this test
    guards; seeding directly keeps the failure focused on that path (step 3),
    not the bcrypt env bug. See report / docs.
    """
    from datetime import datetime, timezone

    from src.api.dependencies import create_access_token
    from src.db.models import User

    user = User(
        id=uuid.uuid4(),
        email=f"e2e-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.not.used.for.jwt.login.flow",
        display_name="E2E Editor",
        role="editor",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()

    token = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# The end-to-end test
# ---------------------------------------------------------------------------


async def test_e2e_campaign_enqueue_persist_retrieve(
    real_app_client,
    fake_arq_pool,
    patch_storage_factory,
    image_backend_mock,
    tmp_path,
):
    """Full path: create -> enqueue -> process -> assets retrievable.

    Guards PRODUCTION code end-to-end: P3-T1 enqueue wiring, P3-T2 REAL worker
    persistence (idempotent ``ON CONFLICT uq_asset_variant`` upsert with a
    populated ``storage_key``), and asset retrieval. The only fakes are image
    generation (mocked tiny PNG) and storage (in-memory). The DB persistence is
    real production code -- no test-supplied persistence hook.
    """
    client, session = real_app_client
    gen_output_dir = str(tmp_path / "pipeline_out")

    # --- step 1: register + login (real DB) ---------------------------------
    headers = await _register_and_login(client, session)

    # Make the create/reprocess routes use the recording fake ARQ pool. This
    # override targets the DI seam that P3-T1 MUST add (see module docstring /
    # report): a ``get_arq_pool`` dependency the routes call ``enqueue_job`` on.
    app = client._transport.app  # the FastAPI app behind the ASGI transport
    try:
        from src.api.dependencies import get_arq_pool  # type: ignore

        async def _override_pool():
            return fake_arq_pool

        app.dependency_overrides[get_arq_pool] = _override_pool
    except ImportError:
        # P3-T1 has not added the seam yet. The create route therefore cannot
        # enqueue onto our fake pool, so step 3 below fails (as intended).
        pass

    # --- step 2: create the campaign (1 product x 2 locales x 2 ratios = 4) --
    campaign_key = f"E2E-{uuid.uuid4().hex[:8]}"
    create = await client.post(
        f"{API}/campaigns",
        headers=headers,
        json={
            "campaign_id": campaign_key,
            "campaign_name": "Summer 2026 Launch",
            "brand_name": "TechStyle",
            "image_backend": "firefly",
            "brief": _campaign_brief_payload(campaign_key),
            "target_locales": LOCALES,
            "aspect_ratios": ASPECT_RATIOS,
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()["data"]
    campaign_db_id = created["id"]
    job_db_id = created["latest_job"]["id"]

    # --- step 3: EXACTLY ONE job enqueued with _job_id == <db job id> -------
    # [Fails today: the create route never enqueues anything -> P3-T1.]
    assert fake_arq_pool.live_job_ids() == [job_db_id], (
        "expected exactly one enqueued job whose ARQ _job_id matches the DB job "
        f"id; got live ids {fake_arq_pool.live_job_ids()!r} (create route did "
        "not enqueue -> P3-T1 not wired)"
    )
    assert fake_arq_pool.count_for_job_id(job_db_id) == 1

    # --- step 4: drive the worker, then poll the job to a terminal state ----
    # The fake only GENERATES (image-gen + disk); the REAL worker persists.
    generate = _make_generating_process_campaign(
        output_dir=gen_output_dir, image_backend=image_backend_mock
    )
    await fake_arq_pool.drive(
        campaign_db_id, job_db_id, session=session, process_campaign=generate
    )

    job_resp = await client.get(f"{API}/jobs/{job_db_id}", headers=headers)
    assert job_resp.status_code == 200, job_resp.text
    assert job_resp.json()["data"]["status"] == "completed"

    # --- step 5: GET /campaigns/{id}/assets -> exactly 4 -------------------
    # [Fails today: pipeline persists no rows -> P3-T2.]
    assets_resp = await client.get(
        f"{API}/campaigns/{campaign_db_id}/assets", headers=headers
    )
    assert assets_resp.status_code == 200, assets_resp.text
    assets = assets_resp.json()["data"]
    assert len(assets) == EXPECTED_ASSET_COUNT, (
        f"expected {EXPECTED_ASSET_COUNT} assets "
        f"(products {len(PRODUCTS)} x locales {len(LOCALES)} x ratios "
        f"{len(ASPECT_RATIOS)}); got {len(assets)}"
    )

    # --- step 6: download one asset -> the PNG bytes ------------------------
    # [Fails today: no storage_key / no rows -> P3-T3.]
    asset_id = assets[0]["id"]
    dl = await client.get(f"{API}/assets/{asset_id}/download", headers=headers)
    if dl.status_code == 307:
        # s3-style backends redirect to a presigned URL; acceptable.
        assert dl.headers["location"]
    else:
        assert dl.status_code == 200, dl.text
        assert dl.content.startswith(b"\x89PNG\r\n\x1a\n")

    # --- step 7: CONCURRENCY -- reprocess twice, still exactly 4, no dupes --
    # Two reprocess enqueues in quick succession, each driven, must converge to
    # the SAME 4-row asset set with NO duplicates. This guards the
    # uq_asset_variant race that P3-T1/T2 must handle via idempotent upsert.
    reprocess_job_ids: list[str] = []
    for _ in range(2):
        rp = await client.post(
            f"{API}/campaigns/{campaign_db_id}/reprocess", headers=headers
        )
        assert rp.status_code == 200, rp.text
        reprocess_job_ids.append(rp.json()["data"]["id"])

    # Each reprocess enqueued exactly one (distinct) live job.
    for jid in reprocess_job_ids:
        assert jid in fake_arq_pool.live_job_ids()
        assert fake_arq_pool.count_for_job_id(jid) == 1

    # Drive both reprocess jobs (re-running generation against the same matrix).
    # Real worker persistence again -> idempotent upsert must keep exactly 4.
    for jid in reprocess_job_ids:
        generate_again = _make_generating_process_campaign(
            output_dir=gen_output_dir, image_backend=image_backend_mock
        )
        await fake_arq_pool.drive(
            campaign_db_id, jid, session=session, process_campaign=generate_again
        )

    # Final row set: exactly 4 distinct variants, NO duplicates.
    rows = (
        (
            await session.execute(
                select(
                    GeneratedAsset.product_id,
                    GeneratedAsset.locale,
                    GeneratedAsset.aspect_ratio,
                ).where(GeneratedAsset.campaign_id == uuid.UUID(campaign_db_id))
            )
        )
        .all()
    )
    assert len(rows) == EXPECTED_ASSET_COUNT, (
        f"reprocessing twice produced {len(rows)} rows; expected "
        f"{EXPECTED_ASSET_COUNT} with no duplicates (uq_asset_variant upsert)"
    )
    assert len(set(rows)) == EXPECTED_ASSET_COUNT, "duplicate asset variants found"

    # Leave the session tidy for the teardown rollback. (The app's
    # dependency_overrides are cleared by the real_app_client fixture.)
    await session.rollback()
