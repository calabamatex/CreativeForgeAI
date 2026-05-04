"""Enhanced image processing with per-element text control and post-processing (Phase 1)."""
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional
from io import BytesIO
import structlog
from src.models import (
    CampaignMessage,
    ComprehensiveBrandGuidelines,
    TextElementStyle,
    TextShadow,
    TextOutline,
    TextBackgroundBox,
    PostProcessingConfig,
)
from src.image_effects import (
    apply_logo_overlay as _apply_logo_overlay,
    apply_post_processing as _apply_post_processing,
)


logger = structlog.get_logger(__name__)


class ImageProcessorV2:
    """Enhanced image processor with Phase 1 features."""

    def __init__(self):
        self.font_cache = {}  # Cache loaded fonts for performance

    def resize_to_aspect_ratio(
        self,
        image_bytes: bytes,
        target_ratio: str
    ) -> Image.Image:
        """Resize image to target aspect ratio."""
        image = Image.open(BytesIO(image_bytes))

        ratio_map = {
            "1:1": (1024, 1024),
            "9:16": (1080, 1920),
            "16:9": (1920, 1080),
            "4:5": (1080, 1350)
        }

        target_size = ratio_map.get(target_ratio, (1024, 1024))

        # Calculate crop box to maintain aspect ratio
        img_ratio = image.width / image.height
        target_img_ratio = target_size[0] / target_size[1]

        if img_ratio > target_img_ratio:
            # Image is wider, crop width
            new_width = int(image.height * target_img_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, image.height))
        else:
            # Image is taller, crop height
            new_height = int(image.width / target_img_ratio)
            top = (image.height - new_height) // 2
            image = image.crop((0, top, image.width, top + new_height))

        # Resize to target
        return image.resize(target_size, Image.Resampling.LANCZOS)

    def apply_text_overlay(
        self,
        image: Image.Image,
        message: CampaignMessage,
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None
    ) -> Image.Image:
        """Apply campaign message text overlay with per-element customization."""
        img = image.copy()
        width, height = img.size
        min_dimension = min(width, height)

        # Text elements to draw: (element_name, text, y_ratio, base_size_ratio)
        elements = [
            ("headline", message.headline, 0.65, 0.08),
            ("subheadline", message.subheadline, 0.77, 0.05),
            ("cta", message.cta, 0.88, 0.06)
        ]

        # Convert to RGBA for effect rendering
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        for element_name, text, y_ratio, base_size_ratio in elements:
            # Get styling for this specific element
            style = self._get_text_element_style(element_name, brand_guidelines)

            # Calculate font size with multiplier
            base_font_size = int(min_dimension * base_size_ratio * style.font_size_multiplier)

            # Calculate max width based on style preference
            margin = int(width * 0.05)
            max_text_width = int(width * style.max_width_percentage) - (2 * margin)

            # Calculate vertical position
            y_pos = int(height * y_ratio)

            # Fit text to width
            font, final_text = self._fit_text_to_width(
                text, base_font_size, max_text_width, style.font_weight
            )

            # Calculate horizontal position based on alignment
            x_pos = self._calculate_x_position(img, final_text, font, style.horizontal_align)

            # Render the text element with all effects
            img = self._render_text_element(img, final_text, (x_pos, y_pos), font, style, min_dimension)

        # Convert back to RGB
        return img.convert('RGB')

    def _get_text_element_style(
        self,
        element_name: str,
        brand_guidelines: Optional[ComprehensiveBrandGuidelines]
    ) -> TextElementStyle:
        """
        Get styling for a text element with fallback to legacy settings.

        Priority:
        1. Per-element customization (if available)
        2. Legacy global settings
        3. Defaults
        """
        # Default style
        default_style = TextElementStyle(
            color="#FFFFFF",
            shadow=TextShadow(enabled=True, color="#000000", offset_x=2, offset_y=2)
        )

        if brand_guidelines is None:
            return default_style

        # Check for new per-element customization
        if brand_guidelines.text_customization is not None:
            element_style = getattr(brand_guidelines.text_customization, element_name, None)
            if element_style is not None:
                return element_style

        # Fallback to legacy global settings
        legacy_shadow = None
        if brand_guidelines.text_shadow:
            legacy_shadow = TextShadow(
                enabled=True,
                color=brand_guidelines.text_shadow_color,
                offset_x=2,
                offset_y=2
            )

        legacy_background = None
        if brand_guidelines.text_background:
            legacy_background = TextBackgroundBox(
                enabled=True,
                color=brand_guidelines.text_background_color,
                opacity=brand_guidelines.text_background_opacity,
                padding=10
            )

        return TextElementStyle(
            color=brand_guidelines.text_color,
            shadow=legacy_shadow,
            background=legacy_background
        )

    def _render_text_element(
        self,
        img: Image.Image,
        text: str,
        position: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        style: TextElementStyle,
        min_dimension: int
    ) -> Image.Image:
        """Render a single text element with all effects."""
        x_pos, y_pos = position
        draw = ImageDraw.Draw(img)

        # Get text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 1. Draw background box (if enabled)
        if style.background and style.background.enabled:
            img = self._draw_background_box(
                img, x_pos, y_pos, text_width, text_height, style.background
            )
            draw = ImageDraw.Draw(img)  # Recreate draw after compositing

        # 2. Draw outline (if enabled)
        if style.outline and style.outline.enabled:
            self._draw_text_outline(draw, text, x_pos, y_pos, font, style.outline)

        # 3. Draw shadow (if enabled)
        if style.shadow and style.shadow.enabled:
            shadow_x = x_pos + style.shadow.offset_x
            shadow_y = y_pos + style.shadow.offset_y
            draw.text((shadow_x, shadow_y), text, fill=style.shadow.color, font=font)

        # 4. Draw main text
        draw.text((x_pos, y_pos), text, fill=style.color, font=font)

        return img

    def _draw_background_box(
        self,
        img: Image.Image,
        x: int,
        y: int,
        text_width: int,
        text_height: int,
        background: TextBackgroundBox
    ) -> Image.Image:
        """Draw semi-transparent background box behind text."""
        padding = background.padding

        # Create overlay for transparency
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # Convert hex color to RGBA
        bg_rgb = self._hex_to_rgb(background.color)
        bg_rgba = bg_rgb + (int(background.opacity * 255),)

        # Draw rounded rectangle
        box = [
            x - padding,
            y - padding,
            x + text_width + padding,
            y + text_height + padding
        ]
        overlay_draw.rectangle(box, fill=bg_rgba)

        # Composite onto image
        return Image.alpha_composite(img, overlay)

    def _draw_text_outline(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        font: ImageFont.FreeTypeFont,
        outline: TextOutline
    ):
        """Draw text outline/stroke effect."""
        width = outline.width

        # Draw text in a circle pattern for outline effect
        for offset_x in range(-width, width + 1):
            for offset_y in range(-width, width + 1):
                # Skip center (main text will be drawn later)
                if offset_x == 0 and offset_y == 0:
                    continue
                draw.text(
                    (x + offset_x, y + offset_y),
                    text,
                    fill=outline.color,
                    font=font
                )

    def _calculate_x_position(
        self,
        img: Image.Image,
        text: str,
        font: ImageFont.FreeTypeFont,
        align: str
    ) -> int:
        """Calculate x position based on horizontal alignment."""
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        margin = int(img.width * 0.05)

        if align == "left":
            return margin
        elif align == "right":
            return img.width - text_width - margin
        else:  # center
            return (img.width - text_width) // 2

    def _fit_text_to_width(
        self,
        text: str,
        initial_size: int,
        max_width: int,
        weight: str
    ) -> Tuple[ImageFont.FreeTypeFont, str]:
        """
        Dynamically adjust font size to fit text within max_width.
        Returns (font, text) tuple.
        """
        min_font_size = 12

        # Try decreasing font size until text fits
        for size in range(initial_size, min_font_size - 1, -2):
            font = self._load_font(size, weight)
            # Create temporary draw to measure text
            temp_img = Image.new('RGBA', (max_width * 2, 100))
            temp_draw = ImageDraw.Draw(temp_img)
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                return (font, text)

        # If still too large, try wrapping
        font = self._load_font(min_font_size, weight)
        words = text.split()

        if len(words) > 3:
            temp_img = Image.new('RGBA', (max_width * 2, 100))
            temp_draw = ImageDraw.Draw(temp_img)
            lines = self._wrap_text(text, font, max_width, temp_draw)
            if len(lines) <= 2:
                return (font, '\n'.join(lines))

        # Last resort: truncate
        truncated = text
        temp_img = Image.new('RGBA', (max_width * 2, 100))
        temp_draw = ImageDraw.Draw(temp_img)
        while len(truncated) > 5:
            bbox = temp_draw.textbbox((0, 0), truncated + "...", font=font)
            if bbox[2] - bbox[0] <= max_width:
                return (font, truncated + "...")
            truncated = truncated[:-1]

        return (font, text)

    def _wrap_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
        draw: ImageDraw.ImageDraw
    ) -> list:
        """Wrap text into multiple lines that fit within max_width."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)

            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def _load_font(self, size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
        """Load font with caching for performance."""
        cache_key = f"{weight}_{size}"
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]

        # Font paths by weight
        font_paths = {
            "regular": [
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ],
            "bold": [
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ],
            "black": [
                "/Library/Fonts/Arial Black.ttf",
                "C:/Windows/Fonts/ariblk.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        }

        paths = font_paths.get(weight, font_paths["regular"])

        for font_path in paths:
            try:
                font = ImageFont.truetype(font_path, size)
                self.font_cache[cache_key] = font
                return font
            except (IOError, OSError):
                continue

        # Fallback
        try:
            font = ImageFont.truetype("Arial", size)
            self.font_cache[cache_key] = font
            return font
        except (IOError, OSError):
            return ImageFont.load_default()

    def apply_logo_overlay(
        self,
        image: Image.Image,
        logo_path: str,
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None,
    ) -> Image.Image:
        """Apply logo overlay (delegated to src.image_effects)."""
        return _apply_logo_overlay(image, logo_path, brand_guidelines)

    def apply_post_processing(
        self,
        image: Image.Image,
        config: Optional[PostProcessingConfig] = None,
    ) -> Image.Image:
        """Apply post-processing enhancements (delegated to src.image_effects)."""
        return _apply_post_processing(image, config)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
