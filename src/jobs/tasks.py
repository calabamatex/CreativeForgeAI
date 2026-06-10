"""Background job task definitions."""

import traceback

import structlog

logger = structlog.get_logger(__name__)


def _read_asset_bytes(file_path: str) -> bytes:
    """Read the raw bytes of a generated asset from its on-disk path.

    Fallback path only: the production pipeline now hands the worker the final
    asset bytes IN MEMORY (``GeneratedAsset.metadata["image_bytes"]``), so no
    disk round-trip happens for real runs. This reader is retained for callers
    that still materialise the asset on disk first (e.g. the generation-only
    integration fake, or reused existing on-disk assets without inline bytes).
    """
    with open(file_path, "rb") as fh:
        return fh.read()


def _image_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Return ``(width, height)`` for *data*, or ``(None, None)`` if undecodable."""
    from io import BytesIO

    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as img:
            return img.width, img.height
    except Exception:  # noqa: BLE001 - dimensions are best-effort metadata
        return None, None


def _resolve_asset_bytes_and_key(asset, campaign_id: str):
    """Return ``(data, storage_key, fmt)`` for one generated asset.

    This is the SINGLE place that decides what bytes and what canonical key the
    worker will save, so the key written to the DB always equals the key passed
    to ``backend.save``.

    Source of the bytes (in priority order):

    1. In-memory bytes the production pipeline handed us
       (``metadata["image_bytes"]``) -- the normal path, NO disk round-trip.
    2. Otherwise, read them from ``file_path`` on disk (the generation-only
       integration fake, or a reused existing on-disk asset).
    """
    from src.storage_backend import build_asset_key

    meta = asset.metadata or {}
    data = meta.get("image_bytes")
    fmt = (meta.get("fmt") or asset.file_path.rsplit(".", 1)[-1] or "png").lower()

    if data is None:
        # Fallback: asset was materialised on disk first.
        data = _read_asset_bytes(asset.file_path)

    # Prefer the canonical key the pipeline already computed; otherwise build it
    # from the variant tuple. Either way the SAME key lands in storage and DB.
    key = meta.get("storage_key") or build_asset_key(
        campaign_id=campaign_id,
        product_id=asset.product_id,
        locale=asset.locale,
        aspect_ratio=asset.aspect_ratio,
        fmt=fmt,
    )
    return data, key, fmt


async def _persist_assets(session, campaign_pk, output, generation_method: str) -> int:
    """Persist every generated asset from *output* as a ``generated_assets`` row.

    Single asset-bytes write path (P3-T3): for each asset the worker

    1. resolves the final bytes + canonical key (in-memory bytes from the
       pipeline, or a disk fallback) via :func:`_resolve_asset_bytes_and_key`;
    2. saves them EXACTLY ONCE through the pluggable storage backend
       (``backend.save(key, data, content_type)``) -- no disk-write -> reread
       redundancy; the returned key is what lands in ``storage_key``;
    3. idempotently upserts the DB row (``ON CONFLICT uq_asset_variant``), so a
       reprocess never duplicates or crashes on the unique constraint.

    The key passed to ``backend.save`` and the key written to the DB are the
    SAME value, guaranteeing ``storage_key`` consistency.

    Returns the number of asset rows written. Does NOT commit -- the caller
    commits the asset rows together with the job's terminal status so the
    whole job is atomic (a ``completed`` job always has all its rows visible).
    """
    from src.db.repositories import AssetRepository
    from src.storage_factory import get_storage_backend

    asset_repo = AssetRepository(session)
    backend = get_storage_backend()
    written = 0

    for asset in output.generated_assets:
        try:
            data, key, fmt = _resolve_asset_bytes_and_key(asset, output.campaign_id)
        except OSError as exc:
            logger.error(
                "job.asset_read_failed",
                file_path=asset.file_path,
                error=str(exc),
            )
            raise

        content_type = f"image/{'jpeg' if fmt in ('jpg', 'jpeg') else fmt}"
        # The ONE asset-bytes write. The returned key is authoritative.
        saved_key = await backend.save(key, data, content_type)

        width, height = _image_dimensions(data)
        gen_time = None
        if asset.metadata:
            gen_time = asset.metadata.get("generation_time_ms")

        await asset_repo.upsert(
            campaign_id=campaign_pk,
            product_id=asset.product_id,
            locale=asset.locale,
            aspect_ratio=asset.aspect_ratio,
            file_path=asset.file_path,
            storage_key=saved_key,
            generation_method=asset.generation_method or generation_method,
            file_size_bytes=len(data),
            width=width,
            height=height,
            generation_time_ms=gen_time,
        )
        written += 1

    return written


async def process_campaign_job(ctx, campaign_id: str, job_id: str):
    """ARQ worker function to process a campaign in the background."""
    from src.db.base import async_session_factory
    from src.db.repositories import CampaignRepository, JobRepository
    from src.models import CampaignBrief
    from src.pipeline import CreativeAutomationPipeline

    logger.info("job.started", campaign_id=campaign_id, job_id=job_id)

    async with async_session_factory() as session:
        campaign_repo = CampaignRepository(session)
        job_repo = JobRepository(session)

        job = await job_repo.get_by_id(job_id)
        campaign = await campaign_repo.get_by_id(campaign_id)

        if not campaign or not job:
            logger.error("job.not_found", campaign_id=campaign_id, job_id=job_id)
            return

        await job_repo.update_progress(job_id, 5, "validating")
        await session.commit()

        pipeline = CreativeAutomationPipeline(image_backend=campaign.image_backend)
        try:
            brief = CampaignBrief(**campaign.brief)

            await job_repo.update_progress(job_id, 10, "processing")
            await session.commit()

            output = await pipeline.process_campaign(brief)

            # Persist every generated asset as a real DB row with a populated
            # storage_key. These writes are NOT committed until the job's
            # terminal status update below, so the asset rows and the
            # ``completed`` status commit atomically in ONE transaction: a
            # ``completed`` job always has all its asset rows visible, and a
            # failure leaves no partial set attributed to ``completed``.
            persisted = await _persist_assets(
                session, campaign.id, output, campaign.image_backend
            )

            # Strip the transient inline asset bytes before serialising the job
            # result: they were only an in-memory carrier for the single
            # backend.save above and must NOT be JSON-serialised into the
            # ``jobs.result`` column.
            for _asset in output.generated_assets:
                if _asset.metadata:
                    _asset.metadata.pop("image_bytes", None)

            await job_repo.complete(job_id, result=output.model_dump(mode="json"))
            await campaign_repo.update_status(campaign.id, "completed")
            await session.commit()

            logger.info(
                "job.completed",
                campaign_id=campaign_id,
                job_id=job_id,
                assets_persisted=persisted,
            )
        except Exception as e:
            logger.error("job.failed", campaign_id=campaign_id, job_id=job_id, error=str(e))
            # Roll back any partially-persisted asset rows so the failed job
            # never leaves a partial set behind, then record the failure.
            await session.rollback()
            await job_repo.fail(job_id, str(e), traceback.format_exc())
            await campaign_repo.update_status(campaign.id, "failed")
            await session.commit()
        finally:
            await pipeline.close()
