"""Text styling and post-processing configuration models."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TextShadow(BaseModel):
    """Text shadow configuration."""
    enabled: bool = Field(default=True, description="Enable drop shadow")
    color: str = Field(default="#000000", description="Shadow color (hex)")
    offset_x: int = Field(default=2, description="Horizontal offset in pixels")
    offset_y: int = Field(default=2, description="Vertical offset in pixels")
    blur_radius: int = Field(default=0, description="Blur radius in pixels")

    model_config = ConfigDict(json_schema_extra={
        "example": {"enabled": True, "color": "#000000", "offset_x": 3, "offset_y": 3, "blur_radius": 2}
    })


class TextOutline(BaseModel):
    """Text outline/stroke configuration."""
    enabled: bool = Field(default=False, description="Enable text outline")
    color: str = Field(default="#FFFFFF", description="Outline color (hex)")
    width: int = Field(default=2, ge=1, le=10, description="Outline width in pixels")

    model_config = ConfigDict(json_schema_extra={
        "example": {"enabled": True, "color": "#FFFFFF", "width": 2}
    })


class TextBackgroundBox(BaseModel):
    """Text background box configuration."""
    enabled: bool = Field(default=False, description="Enable background box")
    color: str = Field(default="#000000", description="Background color (hex)")
    opacity: float = Field(default=0.7, ge=0.0, le=1.0, description="Opacity (0.0-1.0)")
    padding: int = Field(default=10, ge=0, le=50, description="Padding around text in pixels")

    model_config = ConfigDict(json_schema_extra={
        "example": {"enabled": True, "color": "#000000", "opacity": 0.8, "padding": 15}
    })


class TextElementStyle(BaseModel):
    """Styling for a single text element (headline, subheadline, or CTA)."""
    color: str = Field(default="#FFFFFF", description="Text color (hex)")
    font_size_multiplier: float = Field(default=1.0, ge=0.5, le=3.0, description="Font size multiplier")
    font_weight: str = Field(default="regular", description="Font weight: regular, bold, black")

    # Optional effects
    shadow: Optional[TextShadow] = Field(default=None, description="Drop shadow configuration")
    outline: Optional[TextOutline] = Field(default=None, description="Text outline configuration")
    background: Optional[TextBackgroundBox] = Field(default=None, description="Background box configuration")

    # Positioning
    horizontal_align: str = Field(default="center", description="Horizontal alignment: left, center, right")
    max_width_percentage: float = Field(default=0.90, ge=0.1, le=1.0, description="Max width as percentage of image")

    @field_validator('font_weight')
    def validate_font_weight(cls, v):
        valid_weights = {"regular", "bold", "black"}
        if v.lower() not in valid_weights:
            raise ValueError(f"Invalid font weight: {v}. Must be one of {valid_weights}")
        return v.lower()

    @field_validator('horizontal_align')
    def validate_horizontal_align(cls, v):
        valid_aligns = {"left", "center", "right"}
        if v.lower() not in valid_aligns:
            raise ValueError(f"Invalid alignment: {v}. Must be one of {valid_aligns}")
        return v.lower()

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "color": "#FFFFFF", "font_size_multiplier": 1.2, "font_weight": "bold",
            "shadow": {"enabled": True, "color": "#000000"}, "outline": {"enabled": False},
            "horizontal_align": "center",
        }
    })


class TextCustomization(BaseModel):
    """Per-element text customization (Phase 1 feature)."""
    headline: Optional[TextElementStyle] = Field(default=None, description="Headline styling")
    subheadline: Optional[TextElementStyle] = Field(default=None, description="Subheadline styling")
    cta: Optional[TextElementStyle] = Field(default=None, description="CTA styling")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "headline": {"color": "#FFFFFF", "font_weight": "bold", "shadow": {"enabled": True}},
            "cta": {"color": "#FF6600", "outline": {"enabled": True, "color": "#FFFFFF", "width": 2}},
        }
    })


class PostProcessingConfig(BaseModel):
    """Post-processing configuration (Phase 1 feature)."""
    enabled: bool = Field(default=False, description="Enable post-processing")
    sharpening: bool = Field(default=True, description="Apply sharpening")
    sharpening_radius: float = Field(default=2.0, ge=0.1, le=10.0, description="Sharpening radius")
    sharpening_amount: int = Field(default=150, ge=0, le=300, description="Sharpening amount (percentage)")
    color_correction: bool = Field(default=True, description="Apply color correction")
    contrast_boost: float = Field(default=1.1, ge=1.0, le=2.0, description="Contrast boost multiplier")
    saturation_boost: float = Field(default=1.05, ge=1.0, le=2.0, description="Saturation boost multiplier")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "enabled": True, "sharpening": True, "sharpening_radius": 2.0,
            "sharpening_amount": 150, "color_correction": True,
            "contrast_boost": 1.15, "saturation_boost": 1.10,
        }
    })
