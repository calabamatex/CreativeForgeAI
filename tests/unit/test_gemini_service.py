"""Tests for Gemini image generation service."""
import pytest
import base64
import json
from unittest.mock import patch, AsyncMock, MagicMock

from src.genai.gemini_service import GeminiImageService
from src.models import ComprehensiveBrandGuidelines


@pytest.fixture
def gemini_service():
    with patch("src.genai.gemini_service.get_config") as mock_config:
        config = mock_config.return_value
        config.GEMINI_API_KEY = "test-api-key"
        return GeminiImageService(api_key="test-api-key")


class TestGetAspectRatio:
    """Test aspect ratio detection from dimensions."""

    def test_square(self, gemini_service):
        assert gemini_service._get_aspect_ratio(1024, 1024) == "1:1"

    def test_landscape_16_9(self, gemini_service):
        assert gemini_service._get_aspect_ratio(1920, 1080) == "16:9"

    def test_portrait_9_16(self, gemini_service):
        assert gemini_service._get_aspect_ratio(1080, 1920) == "9:16"

    def test_4_3(self, gemini_service):
        assert gemini_service._get_aspect_ratio(1024, 768) == "4:3"

    def test_3_4(self, gemini_service):
        assert gemini_service._get_aspect_ratio(768, 1024) == "3:4"

    def test_unusual_defaults_to_square(self, gemini_service):
        assert gemini_service._get_aspect_ratio(500, 300) == "1:1"


class TestGetNegativePrompt:
    """Test negative prompt generation from brand guidelines."""

    def test_no_guidelines(self, gemini_service):
        assert gemini_service._get_negative_prompt(None) == ""

    def test_no_prohibited_elements(self, gemini_service):
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.pdf",
            prohibited_elements=[],
        )
        assert gemini_service._get_negative_prompt(guidelines) == ""

    def test_with_prohibited_elements(self, gemini_service):
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.pdf",
            prohibited_elements=["text", "watermark", "logos", "borders"],
        )
        result = gemini_service._get_negative_prompt(guidelines)
        assert "text" in result
        assert "watermark" in result

    def test_max_five_elements(self, gemini_service):
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.pdf",
            prohibited_elements=["a", "b", "c", "d", "e", "f", "g"],
        )
        result = gemini_service._get_negative_prompt(guidelines)
        # Should only include first 5
        assert result.count(",") == 4


class TestGetBackendName:
    """Test backend name reporting."""

    def test_backend_name(self, gemini_service):
        assert gemini_service.get_backend_name() == "Google Gemini Imagen 4"


class TestValidateConfig:
    """Test configuration validation."""

    def test_valid_config(self, gemini_service):
        is_valid, errors = gemini_service.validate_config()
        assert is_valid is True
        assert errors == []

    def test_missing_api_key(self):
        with patch("src.genai.gemini_service.get_config") as mock_config:
            config = mock_config.return_value
            config.GEMINI_API_KEY = None
            service = GeminiImageService(api_key=None)
            is_valid, errors = service.validate_config()
            assert is_valid is False
            assert len(errors) == 1
            assert "GEMINI_API_KEY" in errors[0]


class TestGenerateImage:
    """Test image generation with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_successful_generation(self, gemini_service):
        fake_image = b"fake-image-bytes"
        fake_response_data = {
            "predictions": [{"bytesBase64Encoded": base64.b64encode(fake_image).decode()}]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=fake_response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(gemini_service, "_get_session", return_value=mock_session):
            result = await gemini_service.generate_image("a product photo")

        assert result == fake_image

    @pytest.mark.asyncio
    async def test_unexpected_response_format(self, gemini_service):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"unexpected": "format"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(gemini_service, "_get_session", return_value=mock_session):
            with pytest.raises(Exception, match="unexpected response"):
                await gemini_service.generate_image("test")

    @pytest.mark.asyncio
    async def test_api_error_exhausts_retries(self, gemini_service):
        gemini_service.max_retries = 2

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(gemini_service, "_get_session", return_value=mock_session):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception, match="Gemini API error"):
                    await gemini_service.generate_image("test")

    @pytest.mark.asyncio
    async def test_with_brand_guidelines(self, gemini_service):
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.pdf",
            prohibited_elements=["text", "watermark"],
        )

        fake_image = b"branded-image"
        fake_response_data = {
            "predictions": [{"bytesBase64Encoded": base64.b64encode(fake_image).decode()}]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=fake_response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(gemini_service, "_get_session", return_value=mock_session):
            result = await gemini_service.generate_image("product photo", brand_guidelines=guidelines)

        assert result == fake_image
