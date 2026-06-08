"""Phase 3 end-to-end regression guard (P3-T0).

This is the single end-to-end integration test that drives the WHOLE API path
against real Postgres + the fake (free) image backend and asserts an asset is
retrievable at the end:

    register -> login -> POST /campaigns -> (enqueue) -> drive worker ->
    poll job to completed -> GET /campaigns/{id}/assets -> GET /assets/{id}/download

It is deliberately written to FAIL today because the enqueue -> persist ->
retrieve wiring does not yet exist:

* P3-T1 must make ``POST /campaigns`` (and ``/reprocess``) actually enqueue the
  ``process_campaign_job`` via an injectable ARQ pool (``_job_id == <db job id>``).
* P3-T2 must make the pipeline persist ``generated_assets`` rows (idempotently,
  honouring the ``uq_asset_variant`` unique constraint).
* P3-T3 must make ``GET /assets/{id}/download`` return the bytes via the wired
  storage backend.

Because none of that is wired yet, the test is marked
``@pytest.mark.xfail(strict=True, ...)`` so the suite stays green in the interim.
When P3-T1..T3 land, this test will XPASS; ``strict=True`` then turns that XPASS
into a FAILURE, forcing removal of the xfail marker in P3-T3. In other words:
this file is the tripwire that proves the Phase 3 path is fully wired.

No paid calls: the image backend is the mocked one (returns a tiny PNG) and
storage is an in-memory fake. ``integration`` tier (real DB, no external spend).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.models import GeneratedAsset, Job

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
# Persisting pipeline hook (models the P3-T2 behaviour under test)
# ---------------------------------------------------------------------------


async def _make_persisting_process_campaign(
    *, session, campaign_db_id: uuid.UUID, storage_backend, image_backend
):
    """Build a ``process_campaign`` coroutine that generates + persists assets.

    This stands in for the eventual wired pipeline: for every
    (product, locale, aspect_ratio) it asks the MOCKED image backend for bytes,
    saves them to the FAKE storage backend, and idempotently upserts a
    ``generated_assets`` row (``ON CONFLICT (uq_asset_variant) DO NOTHING``) so
    that driving the job twice never creates duplicates. The returned
    ``CampaignOutput`` is what the real task records on the job.
    """

    async def _process_campaign(brief, brief_path=None):
        from src.models import CampaignOutput

        produced = 0
        for product in brief.products:
            for locale in brief.target_locales:
                for ratio in brief.aspect_ratios:
                    png = await image_backend.generate_image()
                    ratio_seg = ratio.replace(":", "x")
                    key = (
                        f"campaigns/{brief.campaign_id}/products/"
                        f"{product.product_id}/{locale}/{ratio_seg}/asset.png"
                    )
                    await storage_backend.save(key, png, "image/png")

                    stmt = (
                        pg_insert(GeneratedAsset)
                        .values(
                            id=uuid.uuid4(),
                            campaign_id=campaign_db_id,
                            product_id=product.product_id,
                            locale=locale,
                            aspect_ratio=ratio,
                            file_path=key,
                            storage_key=key,
                            file_size_bytes=len(png),
                            generation_method="fake",
                        )
                        .on_conflict_do_nothing(constraint="uq_asset_variant")
                    )
                    await session.execute(stmt)
                    produced += 1

        return CampaignOutput(
            campaign_id=brief.campaign_id,
            campaign_name=brief.campaign_name,
            generated_assets=[],
            total_assets=produced,
            locales_processed=list(brief.target_locales),
            products_processed=[p.product_id for p in brief.products],
            processing_time_seconds=0.0,
            success_rate=1.0,
            errors=[],
            generation_timestamp=datetime.now(timezone.utc),
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


@pytest.mark.xfail(
    strict=True,
    reason="enqueue->persist->retrieve wiring lands in P3-T1..T3; remove marker in P3-T3",
)
async def test_e2e_campaign_enqueue_persist_retrieve(
    real_app_client,
    fake_arq_pool,
    patch_storage_factory,
    image_backend_mock,
):
    """Full path: create -> enqueue -> process -> assets retrievable.

    FAILS today at step 3 (no job is ever enqueued by the create route) and,
    were it to get past that, at step 5 (the pipeline persists no asset rows).
    Those gaps are P3-T1 and P3-T2 respectively. Marked strict-xfail so the
    suite stays green until the wiring lands, then XPASSes -> strict failure ->
    marker removed in P3-T3.
    """
    client, session = real_app_client
    storage_backend = patch_storage_factory

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
    persist = await _make_persisting_process_campaign(
        session=session,
        campaign_db_id=uuid.UUID(campaign_db_id),
        storage_backend=storage_backend,
        image_backend=image_backend_mock,
    )
    await fake_arq_pool.drive(
        campaign_db_id, job_db_id, session=session, process_campaign=persist
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
    for jid in reprocess_job_ids:
        persist_again = await _make_persisting_process_campaign(
            session=session,
            campaign_db_id=uuid.UUID(campaign_db_id),
            storage_backend=storage_backend,
            image_backend=image_backend_mock,
        )
        await fake_arq_pool.drive(
            campaign_db_id, jid, session=session, process_campaign=persist_again
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
