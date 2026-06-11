"""Smoke tests proving the real-DB / fake-pool / fake-storage harness works.

These genuinely exercise Postgres (the dedicated ``genai_platform_test`` DB
built via ``alembic upgrade head``) — not mocks. They verify:

* a real ``GeneratedAsset`` row persists and can be queried back,
* the ``uq_asset_variant`` UniqueConstraint raises ``IntegrityError`` on a
  duplicate (campaign_id, product_id, locale, aspect_ratio),
* per-test isolation (rows from a prior test are not visible),
* the fake ARQ pool records enqueues and ``_job_id`` dedupe is observable,
* the fake storage backend round-trips bytes,
* the pool can drive the real ``process_campaign_job`` in-process.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.db.models import Campaign, GeneratedAsset, Job

pytestmark = pytest.mark.asyncio

# Fixed campaign_id reused across two tests to prove isolation. If the row
# inserted in ``test_insert_and_query_asset`` leaked, the later test would see
# it (and a unique-constraint clash on the campaign's ``campaign_id``).
SHARED_CAMPAIGN_KEY = "HARNESS-ISO-001"


async def _make_campaign(session, campaign_key: str = SHARED_CAMPAIGN_KEY) -> Campaign:
    campaign = Campaign(
        id=uuid.uuid4(),
        campaign_id=campaign_key,
        campaign_name="Harness Campaign",
        brand_name="HarnessBrand",
        brief={"headline": "Harness"},
        image_backend="firefly",
        target_locales=["en-US"],
        aspect_ratios=["1:1"],
        status="draft",
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def test_insert_and_query_asset(real_db_session):
    """A real GeneratedAsset row persists and can be read back."""
    campaign = await _make_campaign(real_db_session)

    asset = GeneratedAsset(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        product_id="PROD-1",
        locale="en-US",
        aspect_ratio="1:1",
        file_path="/tmp/a.png",
        storage_key="campaigns/HARNESS-ISO-001/products/PROD-1/en-US/1x1/asset.png",
        generation_method="firefly",
    )
    real_db_session.add(asset)
    await real_db_session.commit()  # commits to the savepoint only

    fetched = (await real_db_session.execute(select(GeneratedAsset).where(GeneratedAsset.id == asset.id))).scalar_one()
    assert fetched.product_id == "PROD-1"
    assert fetched.locale == "en-US"
    assert fetched.created_at is not None  # server_default applied -> real DB


async def test_per_test_isolation(real_db_session):
    """The campaign/asset inserted by the previous test must NOT be visible.

    If isolation were broken, this campaign_id would already exist and the
    query below would find a row (and the later insert would clash).
    """
    existing = (
        await real_db_session.execute(select(Campaign).where(Campaign.campaign_id == SHARED_CAMPAIGN_KEY))
    ).scalar_one_or_none()
    assert existing is None, "row from a prior test leaked -> isolation broken"

    # And we can reuse the same key cleanly within this fresh transaction.
    campaign = await _make_campaign(real_db_session)
    assert campaign.id is not None


async def test_uq_asset_variant_constraint(real_db_session):
    """Duplicate (campaign, product, locale, aspect_ratio) -> IntegrityError."""
    campaign = await _make_campaign(real_db_session, campaign_key="HARNESS-UQ-001")

    common = dict(
        campaign_id=campaign.id,
        product_id="PROD-DUP",
        locale="en-US",
        aspect_ratio="1:1",
        generation_method="firefly",
    )
    real_db_session.add(
        GeneratedAsset(
            id=uuid.uuid4(),
            file_path="/tmp/1.png",
            storage_key="k1",
            **common,
        )
    )
    await real_db_session.flush()

    real_db_session.add(
        GeneratedAsset(
            id=uuid.uuid4(),
            file_path="/tmp/2.png",
            storage_key="k2",
            **common,
        )
    )
    with pytest.raises(IntegrityError) as exc_info:
        await real_db_session.flush()
    assert "uq_asset_variant" in str(exc_info.value).lower()


async def test_fake_storage_round_trip(fake_storage_backend, tiny_png):
    """save() returns the key; get() returns the exact bytes; list/exists work."""
    key = "campaigns/X/products/Y/en-US/1x1/asset.png"
    returned = await fake_storage_backend.save(key, tiny_png, "image/png")
    assert returned == key
    assert await fake_storage_backend.get(key) == tiny_png
    assert fake_storage_backend.exists(key)
    assert key in await fake_storage_backend.list_keys("campaigns/X/")
    # tiny_png is a real, decodable PNG.
    assert tiny_png.startswith(b"\x89PNG\r\n\x1a\n")


async def test_fake_pool_records_and_dedupes(fake_arq_pool):
    """enqueue_job records calls; a duplicate _job_id is observable as deduped."""
    jid = "job-abc"
    first = await fake_arq_pool.enqueue_job("process_campaign_job", "camp-1", jid, _job_id=jid)
    second = await fake_arq_pool.enqueue_job("process_campaign_job", "camp-1", jid, _job_id=jid)

    assert first is not None and first.deduped is False
    assert second is None  # ARQ-style: dedup returns None
    # Exactly one *live* enqueue for this job id, though two attempts recorded.
    assert fake_arq_pool.live_job_ids() == [jid]
    assert fake_arq_pool.count_for_job_id(jid) == 2
    assert fake_arq_pool.enqueued[1].deduped is True


async def test_pool_drives_real_task(real_db_session, fake_arq_pool, fake_storage_backend):
    """The pool drives the real ``process_campaign_job`` in-process.

    Proves the drive mechanism end-to-end: a real campaign + job are inserted
    via the real repositories against real Postgres, the enqueue is recorded,
    and ``drive`` runs the REAL task coroutine in-process (patching its session
    factory to our isolated session and its heavy pipeline to a fake whose
    ``process_campaign`` we supply). We assert the real task actually executed
    by observing that our supplied ``process_campaign`` was invoked with the
    campaign's brief.

    The task's own ``job_repo.update_progress`` / ``complete`` write tz-AWARE
    datetimes into ``jobs.started_at`` / ``jobs.completed_at``. Since P3-T0b
    those columns are ``TIMESTAMP WITH TIME ZONE``, so the real task now drives
    the job all the way to a terminal ``"completed"`` state against real
    Postgres (this previously raised a ``DBAPIError`` from the tz mismatch —
    see docs/FOUND_ISSUES.md P3-T0b). We assert both that our supplied
    ``process_campaign`` was invoked AND that the job reached ``"completed"``.
    """
    from src.db.repositories import CampaignRepository, JobRepository

    campaign_repo = CampaignRepository(real_db_session)
    job_repo = JobRepository(real_db_session)

    campaign = await campaign_repo.create(
        campaign_id="HARNESS-DRIVE-001",
        campaign_name="Drive Me",
        brand_name="Brand",
        brief={
            "campaign_id": "HARNESS-DRIVE-001",
            "campaign_name": "Drive Me",
            "brand_name": "Brand",
            "products": [
                {
                    "product_id": "P1",
                    "product_name": "Widget",
                    "product_description": "A widget",
                    "product_category": "tools",
                }
            ],
            "target_locales": ["en-US"],
            "aspect_ratios": ["1:1"],
            "campaign_message": {
                "locale": "en-US",
                "headline": "Hi",
                "subheadline": "There",
                "cta": "Buy",
            },
        },
    )
    job = await job_repo.create(campaign_id=campaign.id)
    await real_db_session.flush()

    # Record the enqueue, then drive it.
    await fake_arq_pool.enqueue_job(
        "process_campaign_job",
        str(campaign.id),
        str(job.id),
        _job_id=str(job.id),
    )
    assert fake_arq_pool.count_for_job_id(str(job.id)) == 1

    # Track that the REAL task actually invoked our supplied pipeline hook.
    seen_briefs = []

    async def _record_process_campaign(brief, brief_path=None):
        from datetime import datetime

        from src.models import CampaignOutput

        seen_briefs.append(brief)
        return CampaignOutput(
            campaign_id=brief.campaign_id,
            campaign_name=brief.campaign_name,
            generated_assets=[],
            total_assets=0,
            locales_processed=list(getattr(brief, "target_locales", []) or []),
            products_processed=[p.product_id for p in getattr(brief, "products", [])],
            processing_time_seconds=0.0,
            success_rate=1.0,
            errors=[],
            generation_timestamp=datetime.now(),
            technical_metrics=None,
        )

    # Driving runs the REAL ``process_campaign_job`` against real Postgres. Since
    # P3-T0b the ``jobs.started_at`` / ``jobs.completed_at`` columns are
    # ``TIMESTAMP WITH TIME ZONE``, so the task's tz-aware datetime writes are
    # accepted and the job drives all the way to a terminal state (no more
    # ``DBAPIError`` from the old tz mismatch).
    await fake_arq_pool.drive(
        str(campaign.id),
        str(job.id),
        session=real_db_session,
        process_campaign=_record_process_campaign,
    )

    # The real coroutine executed: it invoked our pipeline hook with the brief.
    assert len(seen_briefs) == 1
    assert seen_briefs[0].campaign_id == "HARNESS-DRIVE-001"

    # And the job reached a terminal ``"completed"`` state with timestamps set.
    fetched_job = (await real_db_session.execute(select(Job).where(Job.id == job.id))).scalar_one()
    assert fetched_job.status == "completed"
    assert fetched_job.progress_percent == 100
    assert fetched_job.started_at is not None
    assert fetched_job.completed_at is not None

    # Roll the session back to a clean state so teardown is tidy.
    await real_db_session.rollback()
