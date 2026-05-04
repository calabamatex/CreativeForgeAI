"""
Pydantic data models for Creative Automation Pipeline.
All models use Pydantic v2 for validation and serialization.

Split into submodules for maintainability (AC-10: 500-line limit):
- enums: AspectRatio, Market, Product, CampaignMessage
- text_styles: TextShadow, TextOutline, TextBackgroundBox, TextElementStyle, etc.
- guidelines: ComprehensiveBrandGuidelines, LegalComplianceGuidelines, LocalizationGuidelines
- campaign: CampaignBrief, GeneratedAsset, TechnicalMetrics, CampaignOutput
"""

from src.models.enums import (
    AspectRatio,
    Market,
    Product,
    CampaignMessage,
)
from src.models.text_styles import (
    TextShadow,
    TextOutline,
    TextBackgroundBox,
    TextElementStyle,
    TextCustomization,
    PostProcessingConfig,
)
from src.models.guidelines import (
    ComprehensiveBrandGuidelines,
    LegalComplianceGuidelines,
    LocalizationGuidelines,
)
from src.models.campaign import (
    CampaignBrief,
    GeneratedAsset,
    TechnicalMetrics,
    CampaignOutput,
)

__all__ = [
    # Enums
    "AspectRatio",
    "Market",
    # Core models
    "Product",
    "CampaignMessage",
    # Text styles
    "TextShadow",
    "TextOutline",
    "TextBackgroundBox",
    "TextElementStyle",
    "TextCustomization",
    "PostProcessingConfig",
    # Guidelines
    "ComprehensiveBrandGuidelines",
    "LegalComplianceGuidelines",
    "LocalizationGuidelines",
    # Campaign
    "CampaignBrief",
    "GeneratedAsset",
    "TechnicalMetrics",
    "CampaignOutput",
]
