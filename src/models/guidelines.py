"""Brand, legal, and localization guideline models."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from src.models.text_styles import TextCustomization, PostProcessingConfig


class ComprehensiveBrandGuidelines(BaseModel):
    """Brand guidelines extracted from external documents."""
    source_file: str = Field(..., description="Source guideline document path")
    primary_colors: List[str] = Field(default_factory=list, description="Primary brand colors (hex)")
    secondary_colors: Optional[List[str]] = Field(default_factory=list, description="Secondary colors")
    primary_font: str = Field(default="Arial", description="Primary font family")
    secondary_font: Optional[str] = Field(default=None, description="Secondary font family")
    brand_voice: str = Field(default="Professional", description="Brand voice and tone")
    photography_style: str = Field(default="Modern", description="Photography style guidelines")
    prohibited_uses: List[str] = Field(default_factory=list, description="Prohibited brand uses")
    prohibited_elements: List[str] = Field(default_factory=list, description="Prohibited visual elements")
    approved_taglines: List[str] = Field(default_factory=list, description="Approved brand taglines")

    # Logo placement and sizing
    logo_placement: str = Field(default="bottom-right", description="Logo position: top-left, top-right, bottom-left, bottom-right")
    logo_clearspace: int = Field(default=20, description="Minimum logo clearspace in pixels from edges")
    logo_min_size: int = Field(default=50, description="Minimum logo width in pixels")
    logo_max_size: int = Field(default=200, description="Maximum logo width in pixels")
    logo_opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Logo opacity (0.0-1.0, 1.0=fully opaque)")
    logo_scale: float = Field(default=0.15, ge=0.05, le=0.5, description="Logo size as percentage of image width (0.05-0.5)")

    # Text overlay customization (LEGACY - for backward compatibility)
    text_shadow: bool = Field(default=True, description="Enable drop shadow on text overlays")
    text_color: str = Field(default="#FFFFFF", description="Text overlay color (hex)")
    text_shadow_color: str = Field(default="#000000", description="Text shadow color (hex)")
    text_background: bool = Field(default=False, description="Enable semi-transparent background box behind text")
    text_background_color: str = Field(default="#000000", description="Text background box color (hex)")
    text_background_opacity: float = Field(default=0.5, ge=0.0, le=1.0, description="Text background opacity (0.0-1.0)")

    # NEW: Per-element text customization (Phase 1) - takes precedence over legacy settings
    text_customization: Optional[TextCustomization] = Field(default=None, description="Per-element text styling")

    # NEW: Post-processing configuration (Phase 1)
    post_processing: Optional[PostProcessingConfig] = Field(default=None, description="Image post-processing settings")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "source_file": "brand_guidelines.pdf",
            "primary_colors": ["#0066FF", "#1A1A1A"],
            "primary_font": "Montserrat",
            "brand_voice": "Bold, innovative, customer-focused",
            "photography_style": "Clean, modern, minimalist product photography",
        }
    })


class LegalComplianceGuidelines(BaseModel):
    """Legal compliance guidelines for content validation."""
    source_file: str = Field(..., description="Source guideline document path")

    # Prohibited content
    prohibited_words: List[str] = Field(
        default_factory=list,
        description="Words that must not appear in any content"
    )
    prohibited_phrases: List[str] = Field(
        default_factory=list,
        description="Phrases that must not appear in any content"
    )

    # Required disclaimers
    required_disclaimers: Dict[str, str] = Field(
        default_factory=dict,
        description="Required disclaimer text by category (e.g., 'financial', 'health')"
    )

    # Claims and restrictions
    prohibited_claims: List[str] = Field(
        default_factory=list,
        description="Marketing claims that cannot be made (e.g., 'cure cancer', 'guaranteed results')"
    )
    restricted_terms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Terms that require specific context or disclaimers"
    )

    # Age and audience restrictions
    age_restrictions: Optional[int] = Field(
        default=None,
        description="Minimum age requirement (e.g., 18 for alcohol)"
    )
    restricted_audiences: List[str] = Field(
        default_factory=list,
        description="Audiences that cannot be targeted (e.g., 'children', 'minors')"
    )

    # Geographic restrictions
    restricted_regions: List[str] = Field(
        default_factory=list,
        description="Regions/countries where content is prohibited"
    )

    # Industry-specific compliance
    industry_regulations: List[str] = Field(
        default_factory=list,
        description="Applicable regulations (e.g., 'FDA', 'FTC', 'GDPR', 'COPPA')"
    )

    # Trademark and copyright
    protected_trademarks: List[str] = Field(
        default_factory=list,
        description="Competitor trademarks that must not be used"
    )

    # Content standards
    require_substantiation: bool = Field(
        default=False,
        description="Whether claims require scientific substantiation"
    )
    prohibit_superlatives: bool = Field(
        default=False,
        description="Whether superlatives like 'best', 'perfect' are prohibited"
    )

    # Locale-specific restrictions
    locale_restrictions: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Locale-specific legal restrictions"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "source_file": "legal_guidelines.yaml",
            "prohibited_words": ["guarantee", "free", "cure"],
            "prohibited_claims": ["guaranteed results", "clinically proven"],
            "age_restrictions": 18,
            "industry_regulations": ["FTC", "FDA"],
        }
    })


class LocalizationGuidelines(BaseModel):
    """Localization guidelines for multi-market campaigns."""
    source_file: str = Field(..., description="Source guideline document path")
    supported_locales: List[str] = Field(default_factory=list, description="List of supported locales")
    market_specific_rules: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Market-specific rules and preferences"
    )
    prohibited_terms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Prohibited terms per locale"
    )
    translation_glossary: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Translation glossary per locale"
    )
    tone_guidelines: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Tone guidelines per locale"
    )
    cultural_considerations: Optional[Dict[str, List[str]]] = Field(
        default_factory=dict,
        description="Cultural considerations per locale"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "source_file": "localization_rules.yaml",
            "supported_locales": ["en-US", "es-MX", "fr-CA"],
            "market_specific_rules": {"es-MX": {"tone": "warm", "formality": "formal"}},
            "prohibited_terms": {"es-MX": ["barato", "oferta"]},
        }
    })
