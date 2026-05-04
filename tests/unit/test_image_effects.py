"""Tests for image effects: logo overlay and post-processing."""
import pytest
from PIL import Image
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.image_effects import (
    apply_logo_overlay,
    apply_post_processing,
    _calculate_logo_position,
    _apply_sharpening,
    _apply_color_correction,
)
from src.models import ComprehensiveBrandGuidelines, PostProcessingConfig


@pytest.fixture
def sample_image():
    """Create a simple RGB test image."""
    return Image.new("RGB", (1024, 1024), color=(128, 128, 128))


@pytest.fixture
def sample_logo(tmp_path):
    """Create a small RGBA logo file on disk."""
    logo = Image.new("RGBA", (100, 50), color=(255, 0, 0, 200))
    path = tmp_path / "logo.png"
    logo.save(path)
    return str(path)


@pytest.fixture
def brand_guidelines():
    return ComprehensiveBrandGuidelines(
        source_file="test.pdf",
        logo_placement="top-left",
        logo_clearspace=10,
        logo_min_size=30,
        logo_max_size=150,
        logo_opacity=0.8,
        logo_scale=0.10,
    )


class TestApplyLogoOverlay:
    """Test logo overlay application."""

    def test_overlay_with_defaults(self, sample_image, sample_logo):
        result = apply_logo_overlay(sample_image, sample_logo)
        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size

    def test_overlay_with_brand_guidelines(self, sample_image, sample_logo, brand_guidelines):
        result = apply_logo_overlay(sample_image, sample_logo, brand_guidelines)
        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size

    def test_missing_logo_returns_original(self, sample_image):
        result = apply_logo_overlay(sample_image, "/nonexistent/logo.png")
        assert result is sample_image

    def test_invalid_logo_returns_original(self, sample_image, tmp_path):
        bad_file = tmp_path / "bad.png"
        bad_file.write_text("not an image")
        result = apply_logo_overlay(sample_image, str(bad_file))
        assert result.size == sample_image.size

    def test_opacity_applied(self, sample_image, sample_logo):
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.pdf",
            logo_opacity=0.5,
        )
        result = apply_logo_overlay(sample_image, sample_logo, guidelines)
        assert isinstance(result, Image.Image)

    def test_full_opacity(self, sample_image, sample_logo):
        guidelines = ComprehensiveBrandGuidelines(
            source_file="test.pdf",
            logo_opacity=1.0,
        )
        result = apply_logo_overlay(sample_image, sample_logo, guidelines)
        assert isinstance(result, Image.Image)


class TestCalculateLogoPosition:
    """Test logo position calculation."""

    def test_bottom_right(self):
        x, y = _calculate_logo_position((1000, 1000), (100, 50), "bottom-right", 20)
        assert x == 880
        assert y == 930

    def test_top_left(self):
        x, y = _calculate_logo_position((1000, 1000), (100, 50), "top-left", 20)
        assert x == 20
        assert y == 20

    def test_top_right(self):
        x, y = _calculate_logo_position((1000, 1000), (100, 50), "top-right", 20)
        assert x == 880
        assert y == 20

    def test_bottom_left(self):
        x, y = _calculate_logo_position((1000, 1000), (100, 50), "bottom-left", 20)
        assert x == 20
        assert y == 930

    def test_invalid_placement_defaults_to_bottom_right(self):
        x, y = _calculate_logo_position((1000, 1000), (100, 50), "center", 20)
        assert x == 880
        assert y == 930


class TestApplyPostProcessing:
    """Test post-processing effects."""

    def test_disabled_returns_original(self, sample_image):
        config = PostProcessingConfig(enabled=False)
        result = apply_post_processing(sample_image, config)
        assert result is sample_image

    def test_none_config_returns_original(self, sample_image):
        result = apply_post_processing(sample_image, None)
        assert result is sample_image

    def test_sharpening_only(self, sample_image):
        config = PostProcessingConfig(
            enabled=True,
            sharpening=True,
            color_correction=False,
        )
        result = apply_post_processing(sample_image, config)
        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size

    def test_color_correction_only(self, sample_image):
        config = PostProcessingConfig(
            enabled=True,
            sharpening=False,
            color_correction=True,
            contrast_boost=1.2,
            saturation_boost=1.1,
        )
        result = apply_post_processing(sample_image, config)
        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size

    def test_full_processing(self, sample_image):
        config = PostProcessingConfig(
            enabled=True,
            sharpening=True,
            sharpening_radius=3.0,
            sharpening_amount=200,
            color_correction=True,
            contrast_boost=1.15,
            saturation_boost=1.10,
        )
        result = apply_post_processing(sample_image, config)
        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size


class TestSharpening:
    """Test sharpening helper."""

    def test_default_sharpening(self, sample_image):
        result = _apply_sharpening(sample_image)
        assert isinstance(result, Image.Image)
        assert result.size == sample_image.size

    def test_custom_params(self, sample_image):
        result = _apply_sharpening(sample_image, radius=5.0, amount=200)
        assert isinstance(result, Image.Image)


class TestColorCorrection:
    """Test color correction helper."""

    def test_no_change(self, sample_image):
        result = _apply_color_correction(sample_image, contrast=1.0, saturation=1.0)
        assert isinstance(result, Image.Image)

    def test_contrast_boost(self, sample_image):
        result = _apply_color_correction(sample_image, contrast=1.5, saturation=1.0)
        assert isinstance(result, Image.Image)

    def test_saturation_boost(self, sample_image):
        result = _apply_color_correction(sample_image, contrast=1.0, saturation=1.5)
        assert isinstance(result, Image.Image)

    def test_both(self, sample_image):
        result = _apply_color_correction(sample_image, contrast=1.2, saturation=1.1)
        assert isinstance(result, Image.Image)
