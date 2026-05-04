"""
Tests for image processing operations (resize, overlay, etc.).
"""
import pytest
from PIL import Image
import io


class TestImageProcessor:
    """Test ImageProcessor class."""

    def test_resize_to_aspect_ratio_square(self, mock_image_bytes):
        """Test resizing to square aspect ratio."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor

        processor = ImageProcessor()
        result = processor.resize_to_aspect_ratio(mock_image_bytes, "1:1")

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (1024, 1024)

    def test_resize_to_aspect_ratio_story(self, mock_image_bytes):
        """Test resizing to story aspect ratio."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor

        processor = ImageProcessor()
        result = processor.resize_to_aspect_ratio(mock_image_bytes, "9:16")

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (1080, 1920)

    def test_resize_to_aspect_ratio_landscape(self, mock_image_bytes):
        """Test resizing to landscape aspect ratio."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor

        processor = ImageProcessor()
        result = processor.resize_to_aspect_ratio(mock_image_bytes, "16:9")

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (1920, 1080)

    def test_apply_text_overlay(self, mock_image_bytes, example_campaign_message):
        """Test applying text overlay to image."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor
        from src.models import CampaignMessage

        processor = ImageProcessor()
        message = CampaignMessage(**example_campaign_message)

        # First resize the image bytes
        resized_image = processor.resize_to_aspect_ratio(mock_image_bytes, "1:1")

        # Then apply overlay
        result = processor.apply_text_overlay(
            resized_image,
            message,
            brand_guidelines=None
        )

        assert result is not None
        assert isinstance(result, Image.Image)

    def test_apply_text_overlay_with_guidelines(self, mock_image_bytes, example_campaign_message, brand_guidelines_model):
        """Test text overlay with brand guidelines."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor
        from src.models import CampaignMessage

        processor = ImageProcessor()
        message = CampaignMessage(**example_campaign_message)

        # Resize first
        resized_image = processor.resize_to_aspect_ratio(mock_image_bytes, "1:1")

        # Apply with guidelines
        result = processor.apply_text_overlay(
            resized_image,
            message,
            brand_guidelines=brand_guidelines_model
        )

        assert result is not None
        assert isinstance(result, Image.Image)

    def test_resize_different_ratios(self, mock_image_bytes):
        """Test resizing to all supported ratios."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor

        processor = ImageProcessor()

        ratios_sizes = {
            "1:1": (1024, 1024),
            "9:16": (1080, 1920),
            "16:9": (1920, 1080),
            "4:5": (1080, 1350)
        }

        for ratio, expected_size in ratios_sizes.items():
            result = processor.resize_to_aspect_ratio(mock_image_bytes, ratio)
            assert result.size == expected_size

    def test_image_format_conversion(self, mock_image_bytes):
        """Test image format conversion."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor

        processor = ImageProcessor()

        # Resize to get Image object
        image = processor.resize_to_aspect_ratio(mock_image_bytes, "1:1")

        # Convert to different format
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=85)

        assert output.getvalue() is not None
        assert len(output.getvalue()) > 0


class TestImageProcessorIntegration:
    """Integration tests for image processor."""

    def test_full_processing_pipeline(self, mock_image_bytes, example_campaign_message):
        """Test complete image processing pipeline."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor
        from src.models import CampaignMessage

        processor = ImageProcessor()
        message = CampaignMessage(**example_campaign_message)

        # Resize
        resized = processor.resize_to_aspect_ratio(mock_image_bytes, "1:1")

        # Apply overlay
        final = processor.apply_text_overlay(resized, message)

        assert final is not None
        assert isinstance(final, Image.Image)
        assert final.size == (1024, 1024)

    def test_process_multiple_aspect_ratios(self, mock_image_bytes, example_campaign_message):
        """Test processing multiple aspect ratios."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor
        from src.models import CampaignMessage

        processor = ImageProcessor()
        message = CampaignMessage(**example_campaign_message)

        ratios = ["1:1", "9:16", "16:9"]
        results = []

        for ratio in ratios:
            resized = processor.resize_to_aspect_ratio(mock_image_bytes, ratio)
            final = processor.apply_text_overlay(resized, message)
            results.append(final)

        assert len(results) == 3
        assert all(isinstance(r, Image.Image) for r in results)

    def test_text_overlay_maintains_image_quality(self, mock_image_bytes, example_campaign_message):
        """Test that text overlay maintains image quality."""
        from src.image_processor import ImageProcessorV2 as ImageProcessor
        from src.models import CampaignMessage

        processor = ImageProcessor()
        message = CampaignMessage(**example_campaign_message)

        # Process image
        resized = processor.resize_to_aspect_ratio(mock_image_bytes, "1:1")
        with_text = processor.apply_text_overlay(resized, message)

        # Both should be same size
        assert resized.size == with_text.size
        assert resized.mode == with_text.mode
