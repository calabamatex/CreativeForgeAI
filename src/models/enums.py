"""Enum types and basic product/message models."""

from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict, Field, field_validator
from enum import Enum


class AspectRatio(str, Enum):
    """Supported aspect ratios for campaign assets."""
    SQUARE = "1:1"
    STORY = "9:16"
    LANDSCAPE = "16:9"
    PORTRAIT = "4:5"


class Market(str, Enum):
    """Supported markets/locales."""
    EN_US = "en-US"
    ES_MX = "es-MX"
    FR_CA = "fr-CA"
    PT_BR = "pt-BR"
    DE_DE = "de-DE"
    JA_JP = "ja-JP"
    KO_KR = "ko-KR"


class Product(BaseModel):
    """Product information for campaign asset generation."""
    product_id: str = Field(..., description="Unique product identifier")
    product_name: str = Field(..., description="Product display name")
    product_description: str = Field(..., description="Detailed product description")
    product_category: str = Field(..., description="Product category")
    key_features: List[str] = Field(default_factory=list, description="Key product features")
    existing_assets: Optional[Dict[str, str]] = Field(
        default=None,
        description="Paths to existing assets (hero, logo, etc.)"
    )
    generation_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt for image generation"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "product_id": "HEADPHONES-001",
            "product_name": "Premium Wireless Headphones",
            "product_description": "High-fidelity wireless headphones with active noise cancellation",
            "product_category": "Electronics",
            "key_features": ["Active Noise Cancellation", "40-hour battery", "Premium audio quality"],
            "generation_prompt": "professional product photo of premium wireless headphones",
        }
    })


class CampaignMessage(BaseModel):
    """Campaign messaging for specific locale."""
    locale: str = Field(default="en-US", description="Target locale code")
    headline: str = Field(..., min_length=1, description="Main headline")
    subheadline: str = Field(..., min_length=1, description="Supporting subheadline")
    cta: str = Field(..., min_length=1, description="Call-to-action text")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "locale": "en-US",
            "headline": "Elevate Your Sound",
            "subheadline": "Experience Premium Audio Quality",
            "cta": "Shop Now",
        }
    })
