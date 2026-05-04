"""Main pipeline orchestrator for creative automation."""
import asyncio
import time
import psutil
from io import BytesIO
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from PIL import Image
import structlog

from src.models import (
    CampaignBrief,
    CampaignMessage,
    ComprehensiveBrandGuidelines,
    GeneratedAsset,
    CampaignOutput,
    LegalComplianceGuidelines,
    LocalizationGuidelines,
    Product,
)
from src.config import get_config
from src.exceptions import ComplianceError, StorageError, BackendUnavailableError
from src.genai.factory import ImageGenerationFactory
from src.genai.claude import ClaudeService
from src.parsers.brand_parser import BrandGuidelinesParser
from src.parsers.localization_parser import LocalizationGuidelinesParser
from src.parsers.legal_parser import LegalComplianceParser
from src.image_processor import ImageProcessorV2 as ImageProcessor
from src.legal_checker import LegalComplianceChecker
from src.storage import StorageManager
from src.pipeline_metrics import RawMetricData, compute_technical_metrics

logger = structlog.get_logger(__name__)


@dataclass
class _MetricsState:
    """Mutable metrics accumulator used during campaign processing."""

    api_response_times: list = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    retry_count: int = 0
    retry_reasons: list = field(default_factory=list)
    full_error_traces: list = field(default_factory=list)
    total_api_calls: int = 0
    image_processing_total_ms: float = 0.0
    localization_total_ms: float = 0.0
    compliance_check_total_ms: float = 0.0
    peak_memory_mb: float = 0.0


class CreativeAutomationPipeline:
    """Main pipeline orchestrator."""

    def __init__(self, image_backend: str = None):
        config = get_config()
        self.default_image_backend = image_backend
        self.image_service = None
        self.claude_service = ClaudeService()
        self.brand_parser = BrandGuidelinesParser(self.claude_service)
        self.locale_parser = LocalizationGuidelinesParser(self.claude_service)
        self.legal_parser = LegalComplianceParser(self.claude_service)
        self.image_processor = ImageProcessor()
        self.storage = StorageManager()
        self._api_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)

    # ------------------------------------------------------------------
    # Extracted helpers
    # ------------------------------------------------------------------

    async def _load_guidelines(
        self, brief: CampaignBrief, metrics: _MetricsState
    ) -> Tuple[Optional[ComprehensiveBrandGuidelines], Optional[LocalizationGuidelines], Optional[LegalComplianceGuidelines]]:
        """Load brand, localization, and legal guidelines.

        Returns (brand_guidelines, localization_guidelines, legal_guidelines).
        Raises ComplianceError if legal check finds blocking errors.
        """
        brand_guidelines = None
        localization_guidelines = None
        legal_guidelines = None

        if brief.brand_guidelines_file:
            logger.info("pipeline.loading_guidelines", type="brand", file=brief.brand_guidelines_file)
            try:
                brand_guidelines = await self.brand_parser.parse(brief.brand_guidelines_file)
                logger.info("pipeline.guidelines_loaded", type="brand")
            except (FileNotFoundError, ValueError, OSError) as e:
                logger.warning("pipeline.guidelines_load_failed", type="brand", error=str(e))

        if brief.enable_localization and brief.localization_guidelines_file:
            logger.info("pipeline.loading_guidelines", type="localization", file=brief.localization_guidelines_file)
            try:
                localization_guidelines = await self.locale_parser.parse(brief.localization_guidelines_file)
                logger.info("pipeline.guidelines_loaded", type="localization")
            except (FileNotFoundError, ValueError, OSError) as e:
                logger.warning("pipeline.guidelines_load_failed", type="localization", error=str(e))

        if brief.legal_compliance_file:
            legal_guidelines = await self._run_legal_compliance(brief, metrics)

        return brand_guidelines, localization_guidelines, legal_guidelines

    async def _run_legal_compliance(
        self, brief: CampaignBrief, metrics: _MetricsState
    ) -> Optional[LegalComplianceGuidelines]:
        """Load legal guidelines and run compliance pre-check.

        Returns parsed legal guidelines, or None if file is missing.
        Raises ComplianceError if blocking violations are found.
        """
        logger.info("pipeline.loading_guidelines", type="legal", file=brief.legal_compliance_file)
        try:
            legal_guidelines = await self.legal_parser.parse(brief.legal_compliance_file)
            logger.info("pipeline.guidelines_loaded", type="legal")

            logger.info("pipeline.compliance_check_started")
            check_start = time.time()
            checker = LegalComplianceChecker(legal_guidelines)

            is_compliant, violations = checker.check_content(
                brief.campaign_message,
                product_content=None,
                locale=brief.target_locales[0] if brief.target_locales else "en-US",
            )

            for product in brief.products:
                product_content = {
                    "description": product.product_description,
                    "features": product.key_features,
                }
                product_compliant, _ = checker.check_content(
                    brief.campaign_message,
                    product_content=product_content,
                    locale=brief.target_locales[0] if brief.target_locales else "en-US",
                )
                if not product_compliant:
                    is_compliant = False

            if violations:
                logger.warning("pipeline.compliance_violations_found", report=checker.generate_report())
                summary = checker.get_violation_summary()
                if summary["errors"] > 0:
                    logger.error("pipeline.compliance_blocked", errors=summary["errors"])
                    raise ComplianceError(
                        message=f"Campaign blocked: {summary['errors']} compliance error(s) must be resolved",
                        detail=checker.generate_report(),
                        error_count=summary["errors"],
                        violations=violations,
                    )
                elif summary["warnings"] > 0:
                    logger.warning("pipeline.compliance_warnings", warnings=summary["warnings"])
            else:
                logger.info("pipeline.compliance_passed")

            metrics.compliance_check_total_ms = (time.time() - check_start) * 1000
            return legal_guidelines

        except FileNotFoundError as e:
            logger.warning("pipeline.guidelines_load_failed", type="legal", error=str(e))
            return None
        except ComplianceError:
            raise
        except Exception as e:
            logger.warning("pipeline.compliance_check_error", error=str(e))
            return None

    async def _get_hero_image(
        self,
        product: Product,
        brand_guidelines: Optional[ComprehensiveBrandGuidelines],
        backend_name: str,
        metrics: _MetricsState,
    ) -> Tuple[bytes, Optional[str], bool]:
        """Load existing or generate a new hero image for a product.

        Returns (image_bytes, saved_path_or_None, was_saved).
        """
        if product.existing_assets and "hero" in product.existing_assets:
            logger.info("pipeline.using_existing_hero", path=product.existing_assets["hero"])
            try:
                with open(product.existing_assets["hero"], "rb") as f:
                    hero_bytes = f.read()
                metrics.cache_hits += 1
                return hero_bytes, product.existing_assets["hero"], True
            except (FileNotFoundError, IOError) as e:
                logger.warning("pipeline.existing_hero_unreadable", error=str(e), backend=backend_name)
                # Fall through to generate

        logger.info("pipeline.generating_hero", backend=backend_name)
        prompt = (
            product.generation_prompt
            or f"professional product photo of {product.product_name}, {product.product_description}"
        )

        api_start = time.time()
        async with self._api_semaphore:
            hero_bytes = await self.image_service.generate_image(
                prompt, size="2048x2048", brand_guidelines=brand_guidelines
            )
        api_ms = (time.time() - api_start) * 1000
        metrics.api_response_times.append(api_ms)
        metrics.total_api_calls += 1
        metrics.cache_misses += 1
        logger.info("pipeline.hero_generated")

        return hero_bytes, None, False

    def _save_hero_image(
        self, hero_bytes: bytes, product_id: str, campaign_id: str
    ) -> str:
        """Save hero image bytes to disk, return the saved path."""
        hero_dir = self.storage.output_dir / product_id / campaign_id / "hero"
        hero_dir.mkdir(parents=True, exist_ok=True)
        hero_path = str(hero_dir / f"{product_id}_hero.png")
        hero_img = Image.open(BytesIO(hero_bytes))
        hero_img.save(hero_path, optimize=True, quality=95)
        logger.info("pipeline.hero_saved", path=hero_path)
        return hero_path

    def _generate_asset_for_ratio(
        self,
        hero_image_bytes: bytes,
        localized_message: CampaignMessage,
        product: Product,
        ratio: str,
        brief: CampaignBrief,
        brand_guidelines: Optional[ComprehensiveBrandGuidelines],
    ) -> Tuple[Path, float]:
        """Process a hero image into a final asset for one aspect ratio.

        Returns (asset_path, processing_time_ms).
        """
        img_proc_start = time.time()

        resized = self.image_processor.resize_to_aspect_ratio(hero_image_bytes, ratio)
        final = self.image_processor.apply_text_overlay(resized, localized_message, brand_guidelines)

        if product.existing_assets and "logo" in product.existing_assets:
            logo_path = product.existing_assets["logo"]
            if Path(logo_path).exists():
                final = self.image_processor.apply_logo_overlay(final, logo_path, brand_guidelines)

        if brand_guidelines and brand_guidelines.post_processing:
            final = self.image_processor.apply_post_processing(final, brand_guidelines.post_processing)

        proc_ms = (time.time() - img_proc_start) * 1000

        output_format = brief.output_formats[0] if brief.output_formats else "png"
        asset_path = self.storage.get_asset_path(
            brief.campaign_id, localized_message.locale if hasattr(localized_message, 'locale') else "en-US",
            product.product_id, ratio, output_format,
        )
        self.storage.save_image(final, asset_path)
        logger.info("pipeline.asset_saved", path=str(asset_path))

        return asset_path, proc_ms

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------

    async def process_campaign(
        self,
        brief: CampaignBrief,
        brief_path: Optional[str] = None,
    ) -> CampaignOutput:
        """Process complete campaign and generate all assets."""
        start_time = time.time()
        process = psutil.Process()
        metrics = _MetricsState(peak_memory_mb=process.memory_info().rss / (1024 * 1024))

        # Backup brief
        if brief_path:
            try:
                backup_path = self.storage.backup_campaign_brief(brief_path)
                logger.info("pipeline.brief_backed_up", path=str(backup_path))
            except OSError as e:
                logger.warning("pipeline.brief_backup_failed", error=str(e))

        # Initialize backend
        backend = self.default_image_backend or brief.image_generation_backend
        try:
            self.image_service = ImageGenerationFactory.create(backend)
            backend_name = self.image_service.get_backend_name()
        except (ValueError, KeyError) as e:
            logger.error("pipeline.backend_init_failed", backend=backend, error=str(e))
            raise BackendUnavailableError(
                message=f"Failed to initialize backend '{backend}': {e}",
                backend=backend,
            ) from e

        logger.info(
            "pipeline.campaign_started",
            campaign_name=brief.campaign_name,
            campaign_id=brief.campaign_id,
            backend=backend_name,
            products=len(brief.products),
            locales=brief.target_locales,
        )

        # Load guidelines (may raise ComplianceError)
        brand_guidelines, localization_guidelines, _ = await self._load_guidelines(brief, metrics)

        # Process products
        logger.info("pipeline.generating_assets", products=len(brief.products))
        generated_assets: List[GeneratedAsset] = []
        hero_images: Dict[str, str] = {}
        errors: List[str] = []

        for product in brief.products:
            logger.info("pipeline.processing_product", product_name=product.product_name, product_id=product.product_id)
            try:
                # Get hero image
                hero_bytes, hero_path, was_cached = await self._get_hero_image(
                    product, brand_guidelines, backend_name, metrics
                )

                # Save hero if newly generated
                if not was_cached:
                    hero_path = self._save_hero_image(hero_bytes, product.product_id, brief.campaign_id)

                # Process locales
                for locale in brief.target_locales:
                    logger.info("pipeline.processing_locale", locale=locale)

                    if locale != brief.campaign_message.locale and localization_guidelines:
                        loc_start = time.time()
                        async with self._api_semaphore:
                            localized_message = await self.claude_service.localize_message(
                                brief.campaign_message, locale, localization_guidelines
                            )
                        metrics.localization_total_ms += (time.time() - loc_start) * 1000
                    else:
                        localized_message = brief.campaign_message

                    # Generate asset for each ratio
                    for ratio in brief.aspect_ratios:
                        asset_key = f"{locale}_{ratio}"

                        if product.existing_assets and asset_key in product.existing_assets:
                            existing_path = product.existing_assets[asset_key]
                            if Path(existing_path).exists():
                                logger.info("pipeline.using_existing_asset", ratio=ratio, path=existing_path)
                                asset_path = Path(existing_path)
                            else:
                                logger.warning("pipeline.existing_asset_missing", ratio=ratio)
                                asset_path, proc_ms = self._generate_asset_for_ratio(
                                    hero_bytes, localized_message, product, ratio, brief, brand_guidelines
                                )
                                metrics.image_processing_total_ms += proc_ms
                        else:
                            logger.info("pipeline.generating_variation", ratio=ratio)
                            asset_path, proc_ms = self._generate_asset_for_ratio(
                                hero_bytes, localized_message, product, ratio, brief, brand_guidelines
                            )
                            metrics.image_processing_total_ms += proc_ms

                        generated_assets.append(GeneratedAsset(
                            product_id=product.product_id,
                            locale=locale,
                            aspect_ratio=ratio,
                            file_path=str(asset_path),
                            generation_method=backend,
                            timestamp=datetime.now(),
                        ))

                if hero_path:
                    hero_images[product.product_id] = hero_path

            except Exception as e:
                error_msg = f"Error processing product {product.product_id}: {e}"
                logger.error("pipeline.product_failed", product_id=product.product_id, error=str(e), exc_info=True)
                errors.append(error_msg)
                metrics.full_error_traces.append({
                    "product_id": product.product_id,
                    "error": str(e),
                })

            current_mem = process.memory_info().rss / (1024 * 1024)
            metrics.peak_memory_mb = max(metrics.peak_memory_mb, current_mem)

        # Build output
        elapsed_time = time.time() - start_time
        total_expected = len(brief.products) * len(brief.target_locales) * len(brief.aspect_ratios)
        success_rate = len(generated_assets) / total_expected if total_expected > 0 else 0.0

        raw_data = RawMetricData(
            backend=backend,
            total_api_calls=metrics.total_api_calls,
            cache_hits=metrics.cache_hits,
            cache_misses=metrics.cache_misses,
            retry_count=metrics.retry_count,
            retry_reasons=metrics.retry_reasons,
            api_response_times=metrics.api_response_times,
            image_processing_total_ms=metrics.image_processing_total_ms,
            localization_total_ms=metrics.localization_total_ms,
            compliance_check_total_ms=metrics.compliance_check_total_ms,
            peak_memory_mb=metrics.peak_memory_mb,
            full_error_traces=metrics.full_error_traces,
        )
        technical_metrics = compute_technical_metrics(raw_data)

        output = CampaignOutput(
            campaign_id=brief.campaign_id,
            campaign_name=brief.campaign_name,
            generated_assets=generated_assets,
            total_assets=len(generated_assets),
            locales_processed=brief.target_locales,
            products_processed=[p.product_id for p in brief.products],
            processing_time_seconds=elapsed_time,
            success_rate=success_rate,
            errors=errors,
            generation_timestamp=datetime.now(),
            technical_metrics=technical_metrics,
        )

        # Save reports
        report_paths = []
        for product in brief.products:
            report_path = self.storage.save_report(output, brief.campaign_id, product.product_id)
            report_paths.append(report_path)
            logger.info("pipeline.report_saved", path=str(report_path))

        if brief_path:
            try:
                self.storage.update_campaign_brief(brief_path, output, hero_images)
            except OSError as e:
                logger.warning("pipeline.brief_update_failed", error=str(e))

        logger.info(
            "pipeline.campaign_complete",
            total_assets=output.total_assets,
            processing_time_seconds=round(elapsed_time, 1),
            success_rate=round(success_rate * 100, 1),
            reports=len(report_paths),
        )

        return output

    async def close(self):
        """Clean up all HTTP sessions."""
        if self.image_service:
            await self.image_service.close()
        if hasattr(self.claude_service, "close"):
            await self.claude_service.close()
