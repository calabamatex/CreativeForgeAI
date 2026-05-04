"""Logo overlay and post-processing effects for image processing (Phase 1)."""

from PIL import Image, ImageFilter, ImageEnhance
from typing import Tuple, Optional
import structlog

from src.models import ComprehensiveBrandGuidelines, PostProcessingConfig

logger = structlog.get_logger(__name__)


def apply_logo_overlay(
    image: Image.Image,
    logo_path: str,
    brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None,
) -> Image.Image:
    """Apply logo overlay to image with positioning and sizing based on brand guidelines."""
    try:
        logo = Image.open(logo_path)
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')

        # Get settings
        placement = "bottom-right"
        clearspace = 20
        min_size = 50
        max_size = 200
        opacity = 1.0
        scale = 0.15

        if brand_guidelines is not None:
            placement = brand_guidelines.logo_placement
            clearspace = brand_guidelines.logo_clearspace
            min_size = brand_guidelines.logo_min_size
            max_size = brand_guidelines.logo_max_size
            opacity = brand_guidelines.logo_opacity
            scale = brand_guidelines.logo_scale

        # Calculate target size
        target_width = int(image.width * scale)
        target_width = max(min_size, min(max_size, target_width))
        aspect_ratio = logo.height / logo.width
        target_height = int(target_width * aspect_ratio)

        # Resize logo
        logo_resized = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Apply opacity
        if opacity < 1.0:
            logo_with_opacity = logo_resized.copy()
            alpha = logo_with_opacity.getchannel('A')
            alpha = alpha.point(lambda p: int(p * opacity))
            logo_with_opacity.putalpha(alpha)
            logo_resized = logo_with_opacity

        # Calculate position
        x, y = _calculate_logo_position(
            image.size, logo_resized.size, placement, clearspace
        )

        # Composite
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        logo_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        logo_layer.paste(logo_resized, (x, y), logo_resized)
        result = Image.alpha_composite(image, logo_layer)

        return result.convert('RGB')

    except FileNotFoundError:
        logger.warning("image_effects.logo_not_found", path=logo_path)
        return image
    except Exception as e:
        logger.error("image_effects.logo_overlay_error", error=str(e))
        return image


def _calculate_logo_position(
    image_size: Tuple[int, int],
    logo_size: Tuple[int, int],
    placement: str,
    clearspace: int,
) -> Tuple[int, int]:
    """Calculate logo position based on placement setting."""
    img_width, img_height = image_size
    logo_width, logo_height = logo_size

    positions = {
        "top-left": (clearspace, clearspace),
        "top-right": (img_width - logo_width - clearspace, clearspace),
        "bottom-left": (clearspace, img_height - logo_height - clearspace),
        "bottom-right": (img_width - logo_width - clearspace, img_height - logo_height - clearspace),
    }

    return positions.get(placement.lower(), positions["bottom-right"])


def apply_post_processing(
    image: Image.Image,
    config: Optional[PostProcessingConfig] = None,
) -> Image.Image:
    """
    Apply post-processing enhancements (Phase 1 feature).

    Enhancements:
    - Sharpening (unsharp mask)
    - Color correction (contrast, saturation)
    """
    if config is None or not config.enabled:
        return image

    img = image.copy()

    # 1. Sharpening
    if config.sharpening:
        img = _apply_sharpening(
            img, radius=config.sharpening_radius, amount=config.sharpening_amount
        )

    # 2. Color correction
    if config.color_correction:
        img = _apply_color_correction(
            img, contrast=config.contrast_boost, saturation=config.saturation_boost
        )

    return img


def _apply_sharpening(
    image: Image.Image,
    radius: float = 2.0,
    amount: int = 150,
) -> Image.Image:
    """Apply unsharp mask sharpening."""
    percent = amount / 100.0
    return image.filter(
        ImageFilter.UnsharpMask(radius=radius, percent=int(percent * 100), threshold=3)
    )


def _apply_color_correction(
    image: Image.Image,
    contrast: float = 1.1,
    saturation: float = 1.05,
) -> Image.Image:
    """Apply color correction enhancements."""
    img = image

    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast)

    if saturation != 1.0:
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(saturation)

    return img
