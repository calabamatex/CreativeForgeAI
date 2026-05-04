"""Pydantic v2 request / response schemas for the Creative Automation API layer.

Every endpoint returns a consistent envelope:
    {"data": <payload>, "meta": {"request_id": "..."}}

All response models use ``model_config = ConfigDict(from_attributes=True)``
so they can be constructed directly from SQLAlchemy ORM instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Shared envelope
# ---------------------------------------------------------------------------


class Meta(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Envelope(BaseModel, Generic[T]):
    """Standard response envelope wrapping *data* + *meta*."""

    data: T
    meta: Meta = Field(default_factory=Meta)


class PaginationMeta(Meta):
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


class PaginatedEnvelope(BaseModel, Generic[T]):
    """Response envelope for paginated lists."""

    data: list[T]
    meta: PaginationMeta


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.VIEWER

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "user@example.com",
            "password": "secureP@ss1",
            "display_name": "Jane Doe",
            "role": "editor",
        }
    })


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 min in seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Campaign schemas
# ---------------------------------------------------------------------------


class CampaignCreateRequest(BaseModel):
    """Payload for creating a new campaign."""
    campaign_id: str = Field(..., min_length=1, max_length=100, description="Unique campaign identifier string")
    campaign_name: str = Field(..., min_length=1, max_length=255)
    brand_name: str = Field(..., min_length=1, max_length=255)
    brand_guidelines_id: uuid.UUID | None = None
    image_backend: str = Field(default="firefly")
    brief: dict[str, Any] = Field(default_factory=dict)
    target_locales: list[str] = Field(default_factory=lambda: ["en-US"])
    aspect_ratios: list[str] = Field(default_factory=lambda: ["1:1", "9:16", "16:9"])

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "campaign_id": "SUMMER2026",
            "campaign_name": "Summer 2026 Launch",
            "brand_name": "TechStyle",
            "image_backend": "firefly",
            "brief": {"headline": "Summer Innovation", "cta": "Shop Now"},
            "target_locales": ["en-US", "es-MX"],
            "aspect_ratios": ["1:1", "16:9"],
        }
    })


class CampaignUpdateRequest(BaseModel):
    """Partial-update payload for an existing campaign (draft only)."""
    campaign_name: str | None = Field(None, min_length=1, max_length=255)
    brief: dict[str, Any] | None = None
    target_locales: list[str] | None = None
    aspect_ratios: list[str] | None = None
    image_backend: str | None = None


class CampaignResponse(BaseModel):
    """Full campaign representation returned by the API."""
    id: uuid.UUID
    campaign_id: str
    campaign_name: str
    brand_name: str
    status: str
    image_backend: str
    brand_guidelines_id: uuid.UUID | None = None
    brief: dict[str, Any]
    target_locales: list[str]
    aspect_ratios: list[str]
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    asset_count: int = 0
    latest_job: Optional[JobResponse] = None

    model_config = ConfigDict(from_attributes=True)


class CampaignListItem(BaseModel):
    id: uuid.UUID
    campaign_id: str
    campaign_name: str
    brand_name: str
    status: str
    image_backend: str
    asset_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Asset schemas (maps to GeneratedAsset ORM model)
# ---------------------------------------------------------------------------


class AssetResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    product_id: str
    locale: str
    aspect_ratio: str
    file_path: str
    storage_key: str
    file_size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    generation_method: str
    generation_time_ms: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Brand schemas (maps to BrandGuideline ORM model)
# ---------------------------------------------------------------------------


class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "TechStyle",
        }
    })


class BrandUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    primary_colors: list[str] | None = None
    secondary_colors: list[str] | None = None
    primary_font: str | None = None
    secondary_font: str | None = None
    brand_voice: str | None = None
    photography_style: str | None = None


class BrandResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_file_path: str | None = None
    primary_colors: Any = None
    secondary_colors: Any = None
    primary_font: str | None = None
    secondary_font: str | None = None
    brand_voice: str | None = None
    photography_style: str | None = None
    raw_extracted_data: dict | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Compliance schemas (maps to ComplianceReport ORM model)
# ---------------------------------------------------------------------------


class ComplianceReportResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    is_compliant: bool
    violations: list[dict[str, Any]]
    summary: dict[str, Any]
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceApproveRequest(BaseModel):
    notes: str | None = None


# ---------------------------------------------------------------------------
# Job schemas (maps to Job ORM model)
# ---------------------------------------------------------------------------


class JobResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    status: str
    progress_percent: int = 0
    current_stage: str | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Metrics schemas
# ---------------------------------------------------------------------------


class CampaignMetricsResponse(BaseModel):
    campaign_id: uuid.UUID
    total_assets: int = 0
    assets_by_locale: dict[str, int] = Field(default_factory=dict)
    assets_by_ratio: dict[str, int] = Field(default_factory=dict)
    processing_time_seconds: float = 0.0
    api_calls: int = 0
    cache_hit_rate: float = 0.0
    compliance_pass_rate: float = 0.0
    cost_estimate_usd: float = 0.0


class AggregateMetricsResponse(BaseModel):
    total_campaigns: int = 0
    total_assets: int = 0
    avg_processing_time_seconds: float = 0.0
    total_api_calls: int = 0
    avg_compliance_pass_rate: float = 0.0
    campaigns_by_status: dict[str, int] = Field(default_factory=dict)
    campaigns_by_backend: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Settings schemas
# ---------------------------------------------------------------------------


class BackendInfo(BaseModel):
    name: str
    available: bool
    description: str | None = None


class SettingsResponse(BaseModel):
    default_backend: str = "firefly"
    available_backends: list[BackendInfo] = Field(default_factory=list)
    max_concurrent_requests: int = 5
    rate_limit_auth: int = 100
    rate_limit_unauth: int = 20
    enable_localization: bool = True
    enable_compliance_check: bool = True
    supported_locales: list[str] = Field(default_factory=lambda: ["en-US"])


class SettingsUpdateRequest(BaseModel):
    default_backend: str | None = None
    max_concurrent_requests: int | None = Field(None, ge=1, le=50)
    enable_localization: bool | None = None
    enable_compliance_check: bool | None = None
    supported_locales: list[str] | None = None


# ---------------------------------------------------------------------------
# Rebuild forward-refs (CampaignResponse references JobResponse)
# ---------------------------------------------------------------------------
CampaignResponse.model_rebuild()
