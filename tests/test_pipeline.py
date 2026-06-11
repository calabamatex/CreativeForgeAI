"""
Integration tests for the main pipeline orchestrator.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestCreativeAutomationPipeline:
    """Test main pipeline orchestrator."""

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_process_campaign_basic(
        self, mock_get, mock_post, example_brief, mock_firefly_response, mock_image_bytes, tmp_path
    ):
        """Test basic campaign processing."""
        from src.models import CampaignBrief
        from src.pipeline import CreativeAutomationPipeline

        # Mock Firefly API
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_firefly_response)

        mock_image_response = AsyncMock()
        mock_image_response.status = 200
        mock_image_response.read = AsyncMock(return_value=mock_image_bytes)

        mock_post.return_value.__aenter__.side_effect = [mock_api_response, mock_image_response]

        # Set output directory to temp
        with patch("src.storage.StorageManager") as mock_storage:
            mock_storage.return_value.create_campaign_directory = lambda x: None
            mock_storage.return_value.save_image = lambda x, y: None
            mock_storage.return_value.get_asset_path = lambda *args: tmp_path / "asset.png"
            mock_storage.return_value.save_report = lambda x, y: tmp_path / "report.json"

            pipeline = CreativeAutomationPipeline(image_backend="firefly")
            brief = CampaignBrief(**example_brief)

            output = await pipeline.process_campaign(brief)

            assert output is not None
            assert output.campaign_id == "TEST-CAMPAIGN-001"
            assert output.total_assets >= 0

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_process_campaign_with_openai(
        self, mock_post, example_brief, mock_openai_response, mock_image_bytes, tmp_path
    ):
        """Test campaign processing with OpenAI backend."""
        from src.models import CampaignBrief
        from src.pipeline import CreativeAutomationPipeline

        # Update brief to use OpenAI
        brief_data = example_brief.copy()
        brief_data["image_generation_backend"] = "openai"

        # Mock OpenAI API
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_openai_response)

        mock_post.return_value.__aenter__.return_value = mock_api_response

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_image_response = AsyncMock()
            mock_image_response.status = 200
            mock_image_response.read = AsyncMock(return_value=mock_image_bytes)
            mock_get.return_value.__aenter__.return_value = mock_image_response

            with patch("src.storage.StorageManager") as mock_storage:
                mock_storage.return_value.create_campaign_directory = lambda x: None
                mock_storage.return_value.save_image = lambda x, y: None
                mock_storage.return_value.get_asset_path = lambda *args: tmp_path / "asset.png"
                mock_storage.return_value.save_report = lambda x, y: tmp_path / "report.json"

                pipeline = CreativeAutomationPipeline()
                brief = CampaignBrief(**brief_data)

                output = await pipeline.process_campaign(brief)

                assert output is not None
                assert output.campaign_id == "TEST-CAMPAIGN-001"

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_process_campaign_with_gemini(self, mock_post, example_brief, mock_gemini_response, tmp_path):
        """Test campaign processing with Gemini backend."""
        from src.models import CampaignBrief
        from src.pipeline import CreativeAutomationPipeline

        # Update brief to use Gemini
        brief_data = example_brief.copy()
        brief_data["image_generation_backend"] = "gemini"

        # Mock Gemini API
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_gemini_response)
        mock_post.return_value.__aenter__.return_value = mock_api_response

        with patch("src.storage.StorageManager") as mock_storage:
            mock_storage.return_value.create_campaign_directory = lambda x: None
            mock_storage.return_value.save_image = lambda x, y: None
            mock_storage.return_value.get_asset_path = lambda *args: tmp_path / "asset.png"
            mock_storage.return_value.save_report = lambda x, y: tmp_path / "report.json"

            pipeline = CreativeAutomationPipeline()
            brief = CampaignBrief(**brief_data)

            output = await pipeline.process_campaign(brief)

            assert output is not None

    @pytest.mark.asyncio
    async def test_pipeline_backend_override(self, example_brief):
        """Test pipeline backend override."""
        from src.pipeline import CreativeAutomationPipeline

        # Brief says firefly, but we override to openai
        brief_data = example_brief.copy()
        brief_data["image_generation_backend"] = "firefly"

        pipeline = CreativeAutomationPipeline(image_backend="openai")

        # Pipeline should use OpenAI despite brief saying Firefly
        assert pipeline.default_image_backend == "openai"

    @pytest.mark.asyncio
    async def test_pipeline_with_brand_guidelines(self, example_brief, brand_guidelines_text, tmp_path):
        """Test pipeline with brand guidelines."""
        from src.models import CampaignBrief
        from src.pipeline import CreativeAutomationPipeline

        # Create mock brand guidelines file
        guidelines_path = tmp_path / "brand.md"
        guidelines_path.write_text(brand_guidelines_text)

        brief_data = example_brief.copy()
        brief_data["brand_guidelines_file"] = str(guidelines_path)

        with patch("aiohttp.ClientSession.post") as mock_post:
            # Mock Claude response for guideline extraction
            extracted = {
                "source_file": str(guidelines_path),
                "primary_colors": ["#0066CC"],
                "primary_font": "Montserrat",
            }

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "content": [{"text": json.dumps(extracted)}],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                }
            )
            mock_post.return_value.__aenter__.return_value = mock_response

            # Pipeline should load guidelines
            CreativeAutomationPipeline()
            brief = CampaignBrief(**brief_data)

            # Verify brief has guidelines file
            assert brief.brand_guidelines_file == str(guidelines_path)

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, example_brief):
        """Test pipeline error handling."""
        from src.models import CampaignBrief
        from src.pipeline import CreativeAutomationPipeline

        with patch("src.genai.factory.ImageGenerationFactory.create") as mock_factory:
            # Make image generation fail
            mock_factory.side_effect = Exception("API Error")

            pipeline = CreativeAutomationPipeline()
            brief = CampaignBrief(**example_brief)

            # The injected failure is a bare Exception("API Error"); we only
            # assert it propagates out of the pipeline, not its concrete type.
            with pytest.raises(Exception):  # noqa: B017
                await pipeline.process_campaign(brief)

    @pytest.mark.asyncio
    async def test_pipeline_partial_failure(self, example_brief, mock_firefly_response, mock_image_bytes, tmp_path):
        """Test pipeline continues on partial failures."""
        from src.models import CampaignBrief
        from src.pipeline import CreativeAutomationPipeline

        # Add second product
        brief_data = example_brief.copy()
        brief_data["products"].append(
            {
                "product_id": "TEST-PROD-002",
                "product_name": "Product 2",
                "product_description": "Description",
                "product_category": "Category",
            }
        )

        with patch("aiohttp.ClientSession.post") as mock_post:
            # First product succeeds, second fails
            mock_success = AsyncMock()
            mock_success.status = 200
            mock_success.json = AsyncMock(return_value=mock_firefly_response)

            mock_fail = AsyncMock()
            mock_fail.status = 500

            mock_image = AsyncMock()
            mock_image.status = 200
            mock_image.read = AsyncMock(return_value=mock_image_bytes)

            mock_post.return_value.__aenter__.side_effect = [mock_success, mock_image, mock_fail]

            with patch("src.storage.StorageManager") as mock_storage:
                mock_storage.return_value.create_campaign_directory = lambda x: None
                mock_storage.return_value.save_image = lambda x, y: None
                mock_storage.return_value.get_asset_path = lambda *args: tmp_path / "asset.png"
                mock_storage.return_value.save_report = lambda x, y: tmp_path / "report.json"

                pipeline = CreativeAutomationPipeline()
                brief = CampaignBrief(**brief_data)

                output = await pipeline.process_campaign(brief)

                # Should have errors but still return output
                assert output is not None
                assert len(output.errors) > 0 or output.success_rate < 1.0


class TestPipelineIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline_execution(self, example_brief, mock_firefly_response, mock_image_bytes, tmp_path):
        """Test full pipeline execution."""
        from src.models import CampaignBrief
        from src.pipeline import CreativeAutomationPipeline

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_api = AsyncMock()
            mock_api.status = 200
            mock_api.json = AsyncMock(return_value=mock_firefly_response)

            mock_img = AsyncMock()
            mock_img.status = 200
            mock_img.read = AsyncMock(return_value=mock_image_bytes)

            mock_post.return_value.__aenter__.side_effect = [mock_api, mock_img]

            with patch("src.storage.StorageManager") as mock_storage:
                mock_storage.return_value.create_campaign_directory = lambda x: None
                mock_storage.return_value.save_image = lambda x, y: None
                mock_storage.return_value.get_asset_path = lambda *args: tmp_path / "asset.png"
                mock_storage.return_value.save_report = lambda x, y: tmp_path / "report.json"

                pipeline = CreativeAutomationPipeline()
                brief = CampaignBrief(**example_brief)

                output = await pipeline.process_campaign(brief)

                # Verify output
                assert output.campaign_id == brief.campaign_id
                assert output.campaign_name == brief.campaign_name
                assert output.processing_time_seconds > 0
                assert 0 <= output.success_rate <= 1
