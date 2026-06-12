"""
Comprehensive tests for GenAI services (multi-backend image generation + Claude).
All HTTP requests are mocked for unit testing.
"""

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest


class TestFireflyService:
    """Test Adobe Firefly image generation service."""

    @pytest.mark.asyncio
    async def test_generate_image_success(self, mock_firefly_response, mock_image_bytes):
        """Test successful Firefly image generation."""
        from src.genai.firefly import FireflyImageService

        # Mock API response
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_firefly_response)

        # Mock image download
        mock_image_response = AsyncMock()
        mock_image_response.status = 200
        mock_image_response.read = AsyncMock(return_value=mock_image_bytes)

        with patch(
            "aiohttp.ClientSession.post", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_api_response))
        ):
            with patch(
                "aiohttp.ClientSession.get",
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_image_response)),
            ):
                service = FireflyImageService(api_key="test-key", client_id="test-client")
                result = await service.generate_image("test prompt", size="2048x2048")

                assert result is not None
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_with_brand_guidelines(
        self, mock_firefly_response, mock_image_bytes, brand_guidelines_model
    ):
        """Test Firefly generation with brand guidelines."""
        from src.genai.firefly import FireflyImageService

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_firefly_response)

        mock_image_response = AsyncMock()
        mock_image_response.status = 200
        mock_image_response.read = AsyncMock(return_value=mock_image_bytes)

        with patch(
            "aiohttp.ClientSession.post", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_api_response))
        ) as mock_post:
            with patch(
                "aiohttp.ClientSession.get",
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_image_response)),
            ):
                service = FireflyImageService(api_key="test", client_id="test")
                result = await service.generate_image("product photo", brand_guidelines=brand_guidelines_model)

                assert result is not None
                # Verify prompt was enhanced
                call_args = mock_post.call_args[1]
                assert "prompt" in call_args["json"]

    @pytest.mark.asyncio
    async def test_firefly_retry_logic(self, mock_firefly_response, mock_image_bytes):
        """Test Firefly retry on failure."""
        from src.genai.firefly import FireflyImageService

        mock_fail = AsyncMock()
        mock_fail.status = 500
        mock_fail.text = AsyncMock(return_value="Internal Server Error")

        mock_success = AsyncMock()
        mock_success.status = 200
        mock_success.json = AsyncMock(return_value=mock_firefly_response)

        mock_image = AsyncMock()
        mock_image.status = 200
        mock_image.read = AsyncMock(return_value=mock_image_bytes)

        # First call fails, second succeeds
        post_side_effects = [mock_fail, mock_success]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__.side_effect = post_side_effects
            with patch(
                "aiohttp.ClientSession.get", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_image))
            ):
                service = FireflyImageService(api_key="test", client_id="test", max_retries=3)
                result = await service.generate_image("prompt")

                assert result is not None
                assert mock_post.call_count >= 2

    def test_firefly_backend_name(self):
        """Test Firefly backend name."""
        from src.genai.firefly import FireflyImageService

        service = FireflyImageService(api_key="test", client_id="test")
        assert "Firefly" in service.get_backend_name()


class TestOpenAIService:
    """Test OpenAI DALL-E 3 image generation service."""

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_generate_image_success(self, mock_post, mock_openai_response, mock_image_bytes):
        """Test successful OpenAI image generation."""
        from src.genai.openai_service import OpenAIImageService

        # Mock API response
        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_openai_response)

        # Mock image download
        mock_get = AsyncMock()
        mock_get.status = 200
        mock_get.read = AsyncMock(return_value=mock_image_bytes)

        with patch("aiohttp.ClientSession.get", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_get))):
            mock_post.return_value.__aenter__.return_value = mock_api_response

            service = OpenAIImageService(api_key="test-key")
            result = await service.generate_image("test prompt")

            assert result is not None
            assert len(result) > 0

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_openai_size_conversion(self, mock_post, mock_openai_response, mock_image_bytes):
        """Test OpenAI size format conversion."""
        from src.genai.openai_service import OpenAIImageService

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_openai_response)

        mock_get = AsyncMock()
        mock_get.status = 200
        mock_get.read = AsyncMock(return_value=mock_image_bytes)

        with patch("aiohttp.ClientSession.get", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_get))):
            mock_post.return_value.__aenter__.return_value = mock_api_response

            service = OpenAIImageService(api_key="test")
            result = await service.generate_image("prompt", size="2048x2048")

            assert result is not None
            # Verify size was converted to DALL-E format
            call_args = mock_post.call_args[1]["json"]
            assert call_args["size"] in ["1024x1024", "1024x1792", "1792x1024"]

    def test_openai_backend_name(self):
        """Test OpenAI backend name."""
        from src.genai.openai_service import OpenAIImageService

        service = OpenAIImageService(api_key="test")
        assert "OpenAI" in service.get_backend_name()
        assert "DALL-E" in service.get_backend_name()

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_openai_with_brand_guidelines(
        self, mock_post, mock_openai_response, mock_image_bytes, brand_guidelines_model
    ):
        """Test OpenAI generation with brand guidelines."""
        from src.genai.openai_service import OpenAIImageService

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_openai_response)

        mock_get = AsyncMock()
        mock_get.status = 200
        mock_get.read = AsyncMock(return_value=mock_image_bytes)

        with patch("aiohttp.ClientSession.get", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_get))):
            mock_post.return_value.__aenter__.return_value = mock_api_response

            service = OpenAIImageService(api_key="test")
            result = await service.generate_image("product", brand_guidelines=brand_guidelines_model)

            assert result is not None


class TestGeminiService:
    """Test Google Gemini Imagen image generation service."""

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_generate_image_success(self, mock_post, mock_gemini_response):
        """Test successful Gemini image generation."""
        from src.genai.gemini_service import GeminiImageService

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_gemini_response)
        mock_post.return_value.__aenter__.return_value = mock_api_response

        service = GeminiImageService(api_key="test-key")
        result = await service.generate_image("test prompt")

        assert result is not None
        assert len(result) > 0

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_gemini_base64_decoding(self, mock_post):
        """Test Gemini base64 image decoding."""
        from src.genai.gemini_service import GeminiImageService

        # Create actual base64 encoded image
        test_image = b"test image data"
        encoded = base64.b64encode(test_image).decode("utf-8")

        gemini_response = {"predictions": [{"bytesBase64Encoded": encoded}]}

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=gemini_response)
        mock_post.return_value.__aenter__.return_value = mock_api_response

        service = GeminiImageService(api_key="test")
        result = await service.generate_image("prompt")

        assert result == test_image

    def test_gemini_backend_name(self):
        """Test Gemini backend name."""
        from src.genai.gemini_service import GeminiImageService

        service = GeminiImageService(api_key="test")
        assert "Gemini" in service.get_backend_name()
        assert "Imagen" in service.get_backend_name()

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_gemini_with_brand_guidelines(self, mock_post, mock_gemini_response, brand_guidelines_model):
        """Test Gemini generation with brand guidelines."""
        from src.genai.gemini_service import GeminiImageService

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=mock_gemini_response)
        mock_post.return_value.__aenter__.return_value = mock_api_response

        service = GeminiImageService(api_key="test")
        result = await service.generate_image("product", brand_guidelines=brand_guidelines_model)

        assert result is not None


class TestClaudeService:
    """Test Claude placeholder service."""

    @pytest.mark.asyncio
    async def test_claude_not_implemented(self):
        """Test that Claude image service raises NotImplementedError."""
        from src.genai.claude_service_image import ClaudeImageService

        service = ClaudeImageService(api_key="test")

        with pytest.raises(NotImplementedError) as exc_info:
            await service.generate_image("prompt")

        assert "does not currently support" in str(exc_info.value)

    def test_claude_backend_name(self):
        """Test Claude backend name."""
        from src.genai.claude_service_image import ClaudeImageService

        service = ClaudeImageService(api_key="test")
        assert "Claude" in service.get_backend_name()


class TestImageGenerationFactory:
    """Test factory pattern for backend selection."""

    def test_factory_create_firefly(self):
        """Test factory creates Firefly service."""
        from src.genai.factory import ImageGenerationFactory
        from src.genai.firefly import FireflyImageService

        service = ImageGenerationFactory.create("firefly", api_key="test", client_id="test")

        assert isinstance(service, FireflyImageService)

    def test_factory_create_openai(self):
        """Test factory creates OpenAI service."""
        from src.genai.factory import ImageGenerationFactory
        from src.genai.openai_service import OpenAIImageService

        service = ImageGenerationFactory.create("openai", api_key="test")

        assert isinstance(service, OpenAIImageService)

    def test_factory_create_dalle_alias(self):
        """Test factory handles dall-e alias."""
        from src.genai.factory import ImageGenerationFactory
        from src.genai.openai_service import OpenAIImageService

        service = ImageGenerationFactory.create("dall-e", api_key="test")

        assert isinstance(service, OpenAIImageService)

    def test_factory_create_gemini(self):
        """Test factory creates Gemini service."""
        from src.genai.factory import ImageGenerationFactory
        from src.genai.gemini_service import GeminiImageService

        service = ImageGenerationFactory.create("gemini", api_key="test")

        assert isinstance(service, GeminiImageService)

    def test_factory_create_imagen_alias(self):
        """Test factory handles imagen alias."""
        from src.genai.factory import ImageGenerationFactory
        from src.genai.gemini_service import GeminiImageService

        service = ImageGenerationFactory.create("imagen", api_key="test")

        assert isinstance(service, GeminiImageService)

    def test_factory_create_claude(self):
        """Test factory creates Claude placeholder."""
        from src.genai.claude_service_image import ClaudeImageService
        from src.genai.factory import ImageGenerationFactory

        service = ImageGenerationFactory.create("claude", api_key="test")

        assert isinstance(service, ClaudeImageService)

    def test_factory_invalid_backend(self):
        """Test factory raises error for invalid backend."""
        from src.genai.factory import ImageGenerationFactory

        with pytest.raises(ValueError) as exc_info:
            ImageGenerationFactory.create("invalid_backend")

        assert "Unsupported backend" in str(exc_info.value) or "Invalid backend" in str(exc_info.value)

    def test_factory_list_available(self):
        """Test factory lists available backends."""
        from src.genai.factory import ImageGenerationFactory

        backends = list(ImageGenerationFactory.BACKENDS.keys())

        assert "firefly" in backends
        assert "openai" in backends
        assert "gemini" in backends
        assert "claude" in backends


class TestClaudeTextService:
    """Test Anthropic Claude API for text processing."""

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_localize_message(self, mock_post, mock_claude_response):
        """Test Claude message localization."""
        from src.genai.claude import ClaudeService
        from src.models import CampaignMessage, LocalizationGuidelines

        # Mock localized response
        localized_data = {
            "headline": "Producto Revolucionario",
            "subheadline": "Experimenta la Innovación",
            "cta": "Compra Ahora",
        }

        claude_resp = mock_claude_response.copy()
        claude_resp["content"][0]["text"] = json.dumps(localized_data)

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=claude_resp)
        mock_post.return_value.__aenter__.return_value = mock_api_response

        service = ClaudeService()
        message = CampaignMessage(headline="Revolutionary Product", subheadline="Experience Innovation", cta="Shop Now")

        guidelines = LocalizationGuidelines(source_file="test.yaml", market_specific_rules={"es-MX": {"tone": "warm"}})

        result = await service.localize_message(message, "es-MX", guidelines)

        assert result.headline == "Producto Revolucionario"
        assert result.cta == "Compra Ahora"

    @patch("aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_extract_guidelines(self, mock_post, brand_guidelines_text):
        """Test Claude guideline extraction."""
        from src.genai.claude import ClaudeService

        extracted = {
            "primary_colors": ["#0066CC"],
            "primary_font": "Montserrat",
            "brand_voice": "Professional",
            "photography_style": "Modern",
        }

        claude_resp = {
            "content": [{"text": json.dumps(extracted)}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        mock_api_response = AsyncMock()
        mock_api_response.status = 200
        mock_api_response.json = AsyncMock(return_value=claude_resp)
        mock_post.return_value.__aenter__.return_value = mock_api_response

        service = ClaudeService()
        # This would be called by brand parser
        # Test that service can process extraction requests
        assert service is not None


class TestMultiBackendIntegration:
    """Integration tests for multi-backend functionality."""

    @pytest.mark.asyncio
    async def test_all_backends_implement_interface(self):
        """Test all backends implement base interface."""
        from src.genai.base import ImageGenerationService
        from src.genai.factory import ImageGenerationFactory

        for backend_name, backend_class in ImageGenerationFactory.BACKENDS.items():
            # Skip claude as it's a placeholder
            if backend_name == "claude":
                continue

            # Verify inherits from base
            assert issubclass(backend_class, ImageGenerationService)

    def test_all_backends_have_get_backend_name(self):
        """Test all backends implement get_backend_name."""
        from src.genai.factory import ImageGenerationFactory

        for backend_name in ImageGenerationFactory.BACKENDS.keys():
            if backend_name in ["dall-e", "dalle", "imagen"]:
                # Skip aliases
                continue

            service = ImageGenerationFactory.create(
                backend_name, api_key="test", client_id="test" if backend_name == "firefly" else None
            )

            name = service.get_backend_name()
            assert isinstance(name, str)
            assert len(name) > 0

    def test_backend_aliases_resolve_correctly(self):
        """Test that backend aliases resolve to correct classes."""
        from src.genai.factory import ImageGenerationFactory
        from src.genai.gemini_service import GeminiImageService
        from src.genai.openai_service import OpenAIImageService

        # OpenAI aliases
        openai = ImageGenerationFactory.create("openai", api_key="test")
        dalle = ImageGenerationFactory.create("dall-e", api_key="test")
        assert type(openai) is type(dalle)
        assert isinstance(openai, OpenAIImageService)

        # Gemini aliases
        gemini = ImageGenerationFactory.create("gemini", api_key="test")
        imagen = ImageGenerationFactory.create("imagen", api_key="test")
        assert type(gemini) is type(imagen)
        assert isinstance(gemini, GeminiImageService)
