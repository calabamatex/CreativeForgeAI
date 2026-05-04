"""Unit tests for Phase 1 features: per-element text control and post-processing."""
import pytest
from PIL import Image
from src.models import (
    TextElementStyle,
    TextShadow,
    TextOutline,
    TextBackgroundBox,
    TextCustomization,
    PostProcessingConfig,
    ComprehensiveBrandGuidelines,
    CampaignMessage
)
from src.image_processor import ImageProcessorV2


class TestTextElementStyle:
    """Test TextElementStyle model validation."""

    def test_default_text_element_style(self):
        """Test default text element style creation."""
        style = TextElementStyle()
        assert style.color == "#FFFFFF"
        assert style.font_size_multiplier == 1.0
        assert style.font_weight == "regular"
        assert style.horizontal_align == "center"
        assert style.max_width_percentage == 0.90

    def test_text_element_with_shadow(self):
        """Test text element with shadow configuration."""
        shadow = TextShadow(enabled=True, color="#000000", offset_x=3, offset_y=3)
        style = TextElementStyle(color="#FFFFFF", shadow=shadow)

        assert style.shadow is not None
        assert style.shadow.enabled is True
        assert style.shadow.color == "#000000"
        assert style.shadow.offset_x == 3

    def test_text_element_with_outline(self):
        """Test text element with outline configuration."""
        outline = TextOutline(enabled=True, color="#FFFFFF", width=2)
        style = TextElementStyle(color="#FF6600", outline=outline)

        assert style.outline is not None
        assert style.outline.enabled is True
        assert style.outline.width == 2

    def test_font_weight_validation(self):
        """Test font weight validation."""
        # Valid weights
        for weight in ["regular", "bold", "black"]:
            style = TextElementStyle(font_weight=weight)
            assert style.font_weight == weight.lower()

        # Invalid weight should raise error
        with pytest.raises(ValueError):
            TextElementStyle(font_weight="invalid")

    def test_horizontal_align_validation(self):
        """Test horizontal alignment validation."""
        # Valid alignments
        for align in ["left", "center", "right"]:
            style = TextElementStyle(horizontal_align=align)
            assert style.horizontal_align == align.lower()

        # Invalid alignment should raise error
        with pytest.raises(ValueError):
            TextElementStyle(horizontal_align="invalid")


class TestTextCustomization:
    """Test TextCustomization model."""

    def test_per_element_customization(self):
        """Test independent per-element styling."""
        customization = TextCustomization(
            headline=TextElementStyle(
                color="#FFFFFF",
                font_weight="bold",
                shadow=TextShadow(enabled=True)
            ),
            subheadline=TextElementStyle(
                color="#CCCCCC",
                shadow=TextShadow(enabled=False)
            ),
            cta=TextElementStyle(
                color="#FF6600",
                outline=TextOutline(enabled=True, color="#FFFFFF", width=2)
            )
        )

        # Verify headline has shadow
        assert customization.headline.shadow.enabled is True

        # Verify subheadline has no shadow
        assert customization.subheadline.shadow.enabled is False

        # Verify CTA has outline
        assert customization.cta.outline.enabled is True
        assert customization.cta.outline.width == 2


class TestPostProcessingConfig:
    """Test PostProcessingConfig model."""

    def test_default_post_processing(self):
        """Test default post-processing configuration."""
        config = PostProcessingConfig()
        assert config.enabled is False
        assert config.sharpening is True
        assert config.color_correction is True

    def test_custom_post_processing(self):
        """Test custom post-processing configuration."""
        config = PostProcessingConfig(
            enabled=True,
            sharpening=True,
            sharpening_radius=2.5,
            sharpening_amount=175,
            contrast_boost=1.2,
            saturation_boost=1.15
        )

        assert config.enabled is True
        assert config.sharpening_radius == 2.5
        assert config.sharpening_amount == 175
        assert config.contrast_boost == 1.2

    def test_post_processing_validation(self):
        """Test post-processing parameter validation."""
        # Valid ranges
        config = PostProcessingConfig(
            sharpening_radius=5.0,  # Max 10.0
            sharpening_amount=250,  # Max 300
            contrast_boost=1.5,     # Max 2.0
            saturation_boost=1.8    # Max 2.0
        )
        assert config.sharpening_radius == 5.0

        # Invalid values should raise error
        with pytest.raises(ValueError):
            PostProcessingConfig(sharpening_radius=15.0)  # > 10.0


class TestBackwardCompatibility:
    """Test backward compatibility with legacy settings."""

    def test_legacy_text_settings_still_work(self):
        """Test that legacy text settings are still supported."""
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.yaml",
            primary_colors=["#0066FF"],
            text_color="#FFFFFF",
            text_shadow=True,
            text_shadow_color="#000000"
        )

        processor = ImageProcessorV2()
        style = processor._get_text_element_style("headline", guidelines)

        # Should convert legacy settings to new style
        assert style.color == "#FFFFFF"
        assert style.shadow is not None
        assert style.shadow.enabled is True
        assert style.shadow.color == "#000000"

    def test_per_element_overrides_legacy(self):
        """Test that per-element settings override legacy global settings."""
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.yaml",
            primary_colors=["#0066FF"],
            text_shadow=True,  # Legacy: shadow enabled globally
            text_customization=TextCustomization(
                headline=TextElementStyle(
                    shadow=TextShadow(enabled=False)  # Override: no shadow for headline
                )
            )
        )

        processor = ImageProcessorV2()
        headline_style = processor._get_text_element_style("headline", guidelines)

        # Should use per-element setting (no shadow)
        assert headline_style.shadow.enabled is False


class TestImageProcessorV2:
    """Test ImageProcessorV2 functionality."""

    @pytest.fixture
    def test_image(self):
        """Create a test image."""
        return Image.new('RGB', (1024, 1024), color='white')

    @pytest.fixture
    def test_message(self):
        """Create a test message."""
        return CampaignMessage(
            locale="en-US",
            headline="Test Headline",
            subheadline="Test Subheadline",
            cta="Test CTA"
        )

    def test_resize_to_aspect_ratio(self, test_image):
        """Test image resizing to different aspect ratios."""
        processor = ImageProcessorV2()

        # Test 1:1
        resized = processor.resize_to_aspect_ratio(
            self._image_to_bytes(test_image),
            "1:1"
        )
        assert resized.size == (1024, 1024)

        # Test 16:9
        resized = processor.resize_to_aspect_ratio(
            self._image_to_bytes(test_image),
            "16:9"
        )
        assert resized.size == (1920, 1080)

    def test_apply_text_overlay_with_per_element(self, test_image, test_message):
        """Test text overlay with per-element customization."""
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.yaml",
            primary_colors=["#0066FF"],
            text_customization=TextCustomization(
                headline=TextElementStyle(
                    color="#FFFFFF",
                    shadow=TextShadow(enabled=True)
                ),
                cta=TextElementStyle(
                    color="#FF6600",
                    outline=TextOutline(enabled=True, color="#FFFFFF", width=2)
                )
            )
        )

        processor = ImageProcessorV2()
        result = processor.apply_text_overlay(test_image, test_message, guidelines)

        # Image should be modified (not None)
        assert result is not None
        assert isinstance(result, Image.Image)

    def test_apply_post_processing(self, test_image):
        """Test post-processing application."""
        config = PostProcessingConfig(
            enabled=True,
            sharpening=True,
            sharpening_radius=2.0,
            color_correction=True,
            contrast_boost=1.15
        )

        processor = ImageProcessorV2()
        result = processor.apply_post_processing(test_image, config)

        # Image should be modified
        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == test_image.size

    def test_post_processing_disabled(self, test_image):
        """Test that post-processing can be disabled."""
        config = PostProcessingConfig(enabled=False)
        processor = ImageProcessorV2()
        result = processor.apply_post_processing(test_image, config)

        # Should return original image unchanged
        assert result == test_image

    def test_hex_to_rgb(self):
        """Test hex color conversion."""
        processor = ImageProcessorV2()

        # Test various hex formats
        assert processor._hex_to_rgb("#FFFFFF") == (255, 255, 255)
        assert processor._hex_to_rgb("#000000") == (0, 0, 0)
        assert processor._hex_to_rgb("#FF6600") == (255, 102, 0)
        assert processor._hex_to_rgb("0066FF") == (0, 102, 255)  # Without #

    def test_font_caching(self):
        """Test that fonts are cached for performance."""
        processor = ImageProcessorV2()

        # Load same font twice
        font1 = processor._load_font(24, "regular")
        font2 = processor._load_font(24, "regular")

        # Should return same cached instance
        assert "regular_24" in processor.font_cache

    @staticmethod
    def _image_to_bytes(image: Image.Image) -> bytes:
        """Convert PIL Image to bytes."""
        from io import BytesIO
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()


class TestTextEffects:
    """Test individual text effect rendering."""

    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return ImageProcessorV2()

    @pytest.fixture
    def test_image(self):
        """Create test image."""
        return Image.new('RGBA', (1024, 1024), color=(255, 255, 255, 255))

    def test_background_box_rendering(self, processor, test_image):
        """Test background box rendering."""
        background = TextBackgroundBox(
            enabled=True,
            color="#000000",
            opacity=0.8,
            padding=15
        )

        result = processor._draw_background_box(
            test_image, 100, 100, 200, 50, background
        )

        assert result is not None
        assert result.mode == 'RGBA'

    def test_text_outline_rendering(self, processor, test_image):
        """Test text outline rendering."""
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(test_image)
        font = processor._load_font(24, "regular")
        outline = TextOutline(enabled=True, color="#FFFFFF", width=2)

        # Should not raise error
        processor._draw_text_outline(draw, "Test", 100, 100, font, outline)


def test_integration_full_pipeline():
    """Integration test: Full pipeline with Phase 1 features."""
    # Create test image
    test_image = Image.new('RGB', (1024, 1024), color='white')

    # Create message
    message = CampaignMessage(
        locale="en-US",
        headline="Premium Quality",
        subheadline="Professional Results",
        cta="Try Now"
    )

    # Create guidelines with Phase 1 features
    guidelines = ComprehensiveBrandGuidelines(
        source_file="test.yaml",
        primary_colors=["#FF6600", "#0066FF"],
        text_customization=TextCustomization(
            headline=TextElementStyle(
                color="#FFFFFF",
                font_weight="bold",
                shadow=TextShadow(enabled=True, color="#000000")
            ),
            subheadline=TextElementStyle(
                color="#CCCCCC",
                shadow=TextShadow(enabled=False)
            ),
            cta=TextElementStyle(
                color="#FF6600",
                outline=TextOutline(enabled=True, color="#FFFFFF", width=2),
                background=TextBackgroundBox(enabled=True, color="#000000", opacity=0.8)
            )
        ),
        post_processing=PostProcessingConfig(
            enabled=True,
            sharpening=True,
            color_correction=True,
            contrast_boost=1.15
        )
    )

    # Process image
    processor = ImageProcessorV2()

    # Apply text
    result = processor.apply_text_overlay(test_image, message, guidelines)
    assert result is not None

    # Apply post-processing
    final = processor.apply_post_processing(result, guidelines.post_processing)
    assert final is not None
    assert isinstance(final, Image.Image)
