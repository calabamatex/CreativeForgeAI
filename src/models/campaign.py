"""Campaign brief, output, and metrics models."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime

from src.models.enums import Product, CampaignMessage


class CampaignBrief(BaseModel):
    """Complete campaign brief with all configuration."""
    campaign_id: str = Field(..., description="Unique campaign identifier")
    campaign_name: str = Field(..., description="Campaign display name")
    brand_name: str = Field(..., description="Brand name")
    target_market: Optional[str] = Field(default="Global", description="Target market")
    target_audience: Optional[str] = Field(default="General", description="Target audience")
    campaign_message: CampaignMessage = Field(..., description="Default campaign message")
    products: List[Product] = Field(..., min_length=1, description="List of products")
    aspect_ratios: List[str] = Field(
        default=["1:1", "9:16", "16:9"],
        description="Target aspect ratios"
    )
    output_formats: List[str] = Field(
        default=["png", "jpg"],
        description="Output image formats"
    )
    image_generation_backend: str = Field(
        default="firefly",
        description="Image generation backend: 'firefly', 'openai', 'gemini', or 'claude'"
    )
    brand_guidelines_file: Optional[str] = Field(
        default=None,
        description="Path to brand guidelines document"
    )
    localization_guidelines_file: Optional[str] = Field(
        default=None,
        description="Path to localization guidelines document"
    )
    legal_compliance_file: Optional[str] = Field(
        default=None,
        description="Path to legal compliance guidelines document"
    )
    enable_localization: bool = Field(
        default=False,
        description="Enable multi-locale generation"
    )
    target_locales: List[str] = Field(
        default_factory=lambda: ["en-US"],
        description="Target locales for campaign"
    )

    @field_validator('campaign_id')
    def validate_campaign_id(cls, v):
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError(f"campaign_id must not contain path traversal characters: {v!r}")
        return v

    @field_validator('target_locales')
    def validate_target_locales(cls, v):
        for locale in v:
            if '..' in locale or '/' in locale or '\\' in locale:
                raise ValueError(f"Locale must not contain path traversal characters: {locale!r}")
        return v

    @field_validator('products')
    def validate_products(cls, v):
        if len(v) < 1:
            raise ValueError("At least one product is required")
        return v

    @field_validator('aspect_ratios')
    def validate_aspect_ratios(cls, v):
        valid_ratios = {"1:1", "9:16", "16:9", "4:5"}
        for ratio in v:
            if ratio not in valid_ratios:
                raise ValueError(f"Invalid aspect ratio: {ratio}. Must be one of {valid_ratios}")
        return v

    @field_validator('image_generation_backend')
    def validate_backend(cls, v):
        valid_backends = {"firefly", "openai", "dall-e", "dalle", "gemini", "imagen", "claude"}
        if v.lower() not in valid_backends:
            raise ValueError(
                f"Invalid image generation backend: {v}. "
                f"Must be one of {valid_backends}"
            )
        return v.lower()

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "campaign_id": "SUMMER2026",
            "campaign_name": "Summer Collection Launch",
            "brand_name": "TechStyle",
            "campaign_message": {"locale": "en-US", "headline": "Summer Innovation", "subheadline": "Discover the Future", "cta": "Explore Now"},
            "products": [],
            "enable_localization": True,
            "target_locales": ["en-US", "es-MX", "fr-CA"],
        }
    })


class GeneratedAsset(BaseModel):
    """Metadata for a generated campaign asset."""
    product_id: str = Field(..., description="Associated product ID")
    locale: str = Field(..., description="Asset locale")
    aspect_ratio: str = Field(..., description="Asset aspect ratio")
    file_path: str = Field(..., description="Path to generated asset file")
    generation_method: str = Field(..., description="Generation method (firefly, reuse, etc.)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Generation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "product_id": "PROD-001", "locale": "en-US", "aspect_ratio": "1:1",
            "file_path": "/output/campaign/en-US/PROD-001/1x1/asset.png",
            "generation_method": "firefly", "timestamp": "2026-01-13T10:30:00",
        }
    })


class TechnicalMetrics(BaseModel):
    """Advanced technical metrics for campaign generation."""
    backend_used: str = Field(..., description="AI backend used (firefly, openai, gemini)")
    total_api_calls: int = Field(default=0, description="Total API calls made")
    cache_hits: int = Field(default=0, description="Number of cache hits (hero image reuse)")
    cache_misses: int = Field(default=0, description="Number of cache misses")
    cache_hit_rate: float = Field(default=0.0, description="Cache hit rate percentage (0-100)")
    retry_count: int = Field(default=0, description="Total number of retries across all operations")
    retry_reasons: List[str] = Field(default_factory=list, description="Reasons for retries")
    avg_api_response_time_ms: float = Field(default=0.0, description="Average API response time in milliseconds")
    min_api_response_time_ms: float = Field(default=0.0, description="Minimum API response time")
    max_api_response_time_ms: float = Field(default=0.0, description="Maximum API response time")
    image_processing_time_ms: float = Field(default=0.0, description="Total image processing time")
    localization_time_ms: float = Field(default=0.0, description="Total localization time")
    compliance_check_time_ms: float = Field(default=0.0, description="Total compliance checking time")
    peak_memory_mb: float = Field(default=0.0, description="Peak memory usage in MB")
    system_info: Dict[str, str] = Field(default_factory=dict, description="System environment details")
    full_error_traces: List[Dict[str, str]] = Field(default_factory=list, description="Full error stack traces")


class CampaignOutput(BaseModel):
    """Complete campaign output with all generated assets and metadata."""
    campaign_id: str = Field(..., description="Campaign identifier")
    campaign_name: str = Field(..., description="Campaign name")
    generated_assets: List[GeneratedAsset] = Field(
        default_factory=list,
        description="List of all generated assets"
    )
    total_assets: int = Field(default=0, description="Total number of assets generated")
    locales_processed: List[str] = Field(default_factory=list, description="Locales processed")
    products_processed: List[str] = Field(default_factory=list, description="Products processed")
    processing_time_seconds: float = Field(default=0.0, description="Total processing time")
    success_rate: float = Field(default=1.0, description="Success rate (0-1)")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    generation_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Generation completion timestamp"
    )

    # Enhanced metrics (v1.3.0+)
    technical_metrics: Optional[TechnicalMetrics] = Field(
        default=None,
        description="Advanced technical metrics"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "campaign_id": "SUMMER2026",
            "campaign_name": "Summer Collection",
            "generated_assets": [],
            "total_assets": 12,
            "locales_processed": ["en-US", "es-MX"],
            "products_processed": ["PROD-001", "PROD-002"],
            "processing_time_seconds": 145.3,
            "success_rate": 0.95,
            "technical_metrics": {"backend_used": "firefly", "total_api_calls": 15, "cache_hits": 10, "cache_hit_rate": 66.7},
        }
    })
