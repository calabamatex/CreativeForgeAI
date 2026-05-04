"""
Creative Automation Pipeline - Reference Implementation
Version: 1.0.0
"""

__version__ = "2.0.0"
__author__ = "Creative Automation Team"

from src.models import (
    Product,
    CampaignMessage,
    CampaignBrief,
    ComprehensiveBrandGuidelines,
    LocalizationGuidelines,
    GeneratedAsset,
    CampaignOutput
)

from src.config import Config, get_config

__all__ = [
    "Product",
    "CampaignMessage",
    "CampaignBrief",
    "ComprehensiveBrandGuidelines",
    "LocalizationGuidelines",
    "GeneratedAsset",
    "CampaignOutput",
    "Config",
    "get_config",
]
