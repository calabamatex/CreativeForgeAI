"""Background job task definitions."""

import traceback

import structlog

logger = structlog.get_logger(__name__)


def _read_asset_bytes(file_path: str) -> bytes:
    """Read the raw bytes of a generated asset from its on-disk path.

    The pipeline writes each final asset to ``file_path`` (via the
    ``StorageManager``); the worker re-reads those bytes so it can persist them
    through the pluggable storage backend and record real width/height/size.
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


async def _persist_assets(session, campaign_pk, output, generation_method: str) -> int:
    """Persist every generated asset from *output* as a ``generated_assets`` row.

    For each asset the worker:

    1. reads the bytes the pipeline wrote to ``file_path``;
    2. saves them under a canonical ``build_asset_key`` via the pluggable
       storage backend (this is what yields a non-null ``storage_key``);
    3. idempotently upserts the DB row (``ON CONFLICT uq_asset_variant``), so a
       reprocess never duplicates or crashes on the unique constraint.

    Returns the number of asset rows written. Does NOT commit -- the caller
    commits the asset rows together with the job's terminal status so the
    whole job is atomic (a ``completed`` job always has all its rows visible).
    """
    from src.db.repositories import AssetRepository
    from src.storage_backend import build_asset_key
    from src.storage_factory import get_storage_backend

    asset_repo = AssetRepository(session)
    backend = get_storage_backend()
    written = 0

    for asset in output.generated_assets:
        try:
            data = _read_asset_bytes(asset.file_path)
        except OSError as exc:
            logger.error(
                "job.asset_read_failed",
                file_path=asset.file_path,
                error=str(exc),
            )
            raise

        fmt = (asset.file_path.rsplit(".", 1)[-1] or "png").lower()
        key = build_asset_key(
            campaign_id=output.campaign_id,
            product_id=asset.product_id,
            locale=asset.locale,
            aspect_ratio=asset.aspect_ratio,
            fmt=fmt,
        )
        await backend.save(key, data, f"image/{'jpeg' if fmt in ('jpg', 'jpeg') else fmt}")

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
            storage_key=key,
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
