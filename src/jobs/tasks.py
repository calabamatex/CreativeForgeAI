"""Background job task definitions."""

import traceback

import structlog

logger = structlog.get_logger(__name__)


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

            await job_repo.complete(job_id, result=output.model_dump(mode="json"))
            await campaign_repo.update_status(campaign.id, "completed")
            await session.commit()

            logger.info("job.completed", campaign_id=campaign_id, job_id=job_id)
        except Exception as e:
            logger.error("job.failed", campaign_id=campaign_id, job_id=job_id, error=str(e))
            await job_repo.fail(job_id, str(e), traceback.format_exc())
            await campaign_repo.update_status(campaign.id, "failed")
            await session.commit()
        finally:
            await pipeline.close()
