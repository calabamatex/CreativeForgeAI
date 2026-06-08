"""
Integration tests for the main pipeline orchestrator.
"""
import asyncio
import pytest
from unittest.mock import patch, AsyncMock
import json


class TestCreativeAutomationPipeline:
    """Test main pipeline orchestrator."""

    @patch('aiohttp.ClientSession.post')
    @patch('aiohttp.ClientSession.get')
    @pytest.mark.asyncio
    async def test_process_campaign_basic(
        self,
        mock_get,
        mock_post,
        example_brief,
        mock_firefly_response,
        mock_image_bytes,
        tmp_path
    ):
        """Test basic campaign processing."""
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        # Mock Firefly API
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_firefly_response)

        mock_image_response = AsyncMock()
        mock_image_response.status = 200
        mock_image_response.read = AsyncMock(return_value=mock_image_bytes)

        mock_post.return_value.__aenter__.side_effect = [
            mock_api_response,
            mock_image_response
        ]

        # Set output directory to temp
        with patch('src.storage.StorageManager') as mock_storage:
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

    @patch('aiohttp.ClientSession.post')
    @pytest.mark.asyncio
    async def test_process_campaign_with_openai(
        self,
        mock_post,
        example_brief,
        mock_openai_response,
        mock_image_bytes,
        tmp_path
    ):
        """Test campaign processing with OpenAI backend."""
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        # Update brief to use OpenAI
        brief_data = example_brief.copy()
        brief_data["image_generation_backend"] = "openai"

        # Mock OpenAI API
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_openai_response)

        mock_post.return_value.__aenter__.return_value = mock_api_response

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_image_response = AsyncMock()
            mock_image_response.status = 200
            mock_image_response.read = AsyncMock(return_value=mock_image_bytes)
            mock_get.return_value.__aenter__.return_value = mock_image_response

            with patch('src.storage.StorageManager') as mock_storage:
                mock_storage.return_value.create_campaign_directory = lambda x: None
                mock_storage.return_value.save_image = lambda x, y: None
                mock_storage.return_value.get_asset_path = lambda *args: tmp_path / "asset.png"
                mock_storage.return_value.save_report = lambda x, y: tmp_path / "report.json"

                pipeline = CreativeAutomationPipeline()
                brief = CampaignBrief(**brief_data)

                output = await pipeline.process_campaign(brief)

                assert output is not None
                assert output.campaign_id == "TEST-CAMPAIGN-001"

    @patch('aiohttp.ClientSession.post')
    @pytest.mark.asyncio
    async def test_process_campaign_with_gemini(
        self,
        mock_post,
        example_brief,
        mock_gemini_response,
        tmp_path
    ):
        """Test campaign processing with Gemini backend."""
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        # Update brief to use Gemini
        brief_data = example_brief.copy()
        brief_data["image_generation_backend"] = "gemini"

        # Mock Gemini API
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_gemini_response)
        mock_post.return_value.__aenter__.return_value = mock_api_response

        with patch('src.storage.StorageManager') as mock_storage:
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
        from src.models import CampaignBrief

        # Brief says firefly, but we override to openai
        brief_data = example_brief.copy()
        brief_data["image_generation_backend"] = "firefly"

        pipeline = CreativeAutomationPipeline(image_backend="openai")

        # Pipeline should use OpenAI despite brief saying Firefly
        assert pipeline.default_image_backend == "openai"

    @pytest.mark.asyncio
    async def test_pipeline_with_brand_guidelines(
        self,
        example_brief,
        brand_guidelines_text,
        tmp_path
    ):
        """Test pipeline with brand guidelines."""
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        # Create mock brand guidelines file
        guidelines_path = tmp_path / "brand.md"
        guidelines_path.write_text(brand_guidelines_text)

        brief_data = example_brief.copy()
        brief_data["brand_guidelines_file"] = str(guidelines_path)

        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock Claude response for guideline extraction
            extracted = {
                "source_file": str(guidelines_path),
                "primary_colors": ["#0066CC"],
                "primary_font": "Montserrat"
            }

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                'content': [{'text': json.dumps(extracted)}],
                'usage': {'input_tokens': 100, 'output_tokens': 50}
            })
            mock_post.return_value.__aenter__.return_value = mock_response

            # Pipeline should load guidelines
            pipeline = CreativeAutomationPipeline()
            brief = CampaignBrief(**brief_data)

            # Verify brief has guidelines file
            assert brief.brand_guidelines_file == str(guidelines_path)

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, example_brief):
        """Test pipeline error handling."""
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        with patch('src.genai.factory.ImageGenerationFactory.create') as mock_factory:
            # Make image generation fail
            mock_factory.side_effect = Exception("API Error")

            pipeline = CreativeAutomationPipeline()
            brief = CampaignBrief(**example_brief)

            with pytest.raises(Exception):
                await pipeline.process_campaign(brief)

    @pytest.mark.asyncio
    async def test_pipeline_partial_failure(self, example_brief, mock_firefly_response, mock_image_bytes, tmp_path):
        """Test pipeline continues on partial failures."""
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        # Add second product
        brief_data = example_brief.copy()
        brief_data["products"].append({
            "product_id": "TEST-PROD-002",
            "product_name": "Product 2",
            "product_description": "Description",
            "product_category": "Category"
        })

        with patch('aiohttp.ClientSession.post') as mock_post:
            # First product succeeds, second fails
            mock_success = AsyncMock()
            mock_success.status = 200
            mock_success.json = AsyncMock(return_value=mock_firefly_response)

            mock_fail = AsyncMock()
            mock_fail.status = 500

            mock_image = AsyncMock()
            mock_image.status = 200
            mock_image.read = AsyncMock(return_value=mock_image_bytes)

            mock_post.return_value.__aenter__.side_effect = [
                mock_success,
                mock_image,
                mock_fail
            ]

            with patch('src.storage.StorageManager') as mock_storage:
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


class TestPipelineSemaphore:
    """Tests for the lazily-bound concurrency semaphore (P2-T3)."""

    def test_semaphore_not_created_at_construction(self, mock_env_vars):
        """The semaphore must NOT be created in __init__.

        Construction may happen outside/before the event loop that later runs
        the campaign (e.g. under ARQ workers), so the semaphore must be created
        lazily on first async use, not eagerly at construction time.
        """
        from src.pipeline import CreativeAutomationPipeline

        pipeline = CreativeAutomationPipeline()

        assert pipeline._api_semaphore is None
        assert pipeline._max_concurrent_requests >= 1

    def test_semaphore_lazy_binding(
        self,
        mock_env_vars,
        example_brief,
        mock_image_bytes,
        tmp_path,
    ):
        """Construct outside any loop, then run on a fresh loop.

        This exercises the loop-binding bug: a semaphore created at construction
        time binds to whatever loop is current then. Here the pipeline is built
        in a context with NO running loop, and ``process_campaign`` is awaited
        inside a *separate* ``asyncio.run`` event loop. With eager construction
        this can raise ``RuntimeError: ... bound to a different event loop`` /
        "got Future attached to a different loop". With lazy creation the
        semaphore binds to the running loop and no such error occurs.
        """
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        # Fake image backend so no paid API calls are made.
        fake_image_service = AsyncMock()
        fake_image_service.generate_image = AsyncMock(return_value=mock_image_bytes)
        fake_image_service.get_backend_name = lambda: "fake"

        brief = CampaignBrief(**example_brief)

        with patch(
            "src.genai.factory.ImageGenerationFactory.create",
            return_value=fake_image_service,
        ), patch("src.storage.StorageManager") as mock_storage:
            mock_storage.return_value.create_campaign_directory = lambda x: None
            mock_storage.return_value.save_image = lambda x, y: None
            mock_storage.return_value.get_asset_path = lambda *args: tmp_path / "asset.png"
            mock_storage.return_value.save_report = lambda x, y: tmp_path / "report.json"

            # Construct the pipeline with NO running event loop. If __init__
            # eagerly created the semaphore, it would (try to) bind here.
            with pytest.raises(RuntimeError):
                asyncio.get_running_loop()
            pipeline = CreativeAutomationPipeline(image_backend="firefly")

            # Semaphore must not exist yet (lazy creation).
            assert pipeline._api_semaphore is None

            # Avoid any real Claude localization call for the es-MX locale; this
            # also exercises the second semaphore use site.
            pipeline.claude_service.localize_message = AsyncMock(
                return_value=brief.campaign_message
            )

            # Await on a brand-new event loop, distinct from construction.
            output = asyncio.run(pipeline.process_campaign(brief))

            # No loop-binding error was raised, and the semaphore was created
            # lazily, bound to the asyncio.run loop.
            assert output is not None
            assert output.campaign_id == "TEST-CAMPAIGN-001"
            assert isinstance(pipeline._api_semaphore, asyncio.Semaphore)


class TestPipelineIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline_execution(
        self,
        example_brief,
        mock_firefly_response,
        mock_image_bytes,
        tmp_path
    ):
        """Test full pipeline execution."""
        from src.pipeline import CreativeAutomationPipeline
        from src.models import CampaignBrief

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_api = AsyncMock()
            mock_api.status = 200
            mock_api.json = AsyncMock(return_value=mock_firefly_response)

            mock_img = AsyncMock()
            mock_img.status = 200
            mock_img.read = AsyncMock(return_value=mock_image_bytes)

            mock_post.return_value.__aenter__.side_effect = [
                mock_api, mock_img
            ]

            with patch('src.storage.StorageManager') as mock_storage:
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
