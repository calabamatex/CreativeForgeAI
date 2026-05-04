"""SQLAlchemy ORM models for the Creative Automation Pipeline."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="viewer"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships -- use lazy="raise" for collections to prevent
    # accidental N+1 queries; use selectinload() explicitly when needed.
    brand_guidelines: Mapped[list["BrandGuideline"]] = relationship(
        back_populates="creator", lazy="raise"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="creator", lazy="raise"
    )


# ---------------------------------------------------------------------------
# Brand Guidelines
# ---------------------------------------------------------------------------

class BrandGuideline(Base):
    __tablename__ = "brand_guidelines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_path: Mapped[Optional[str]] = mapped_column(String(500))
    primary_colors: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="[]"
    )
    secondary_colors: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="[]"
    )
    primary_font: Mapped[Optional[str]] = mapped_column(
        String(100), server_default="Arial"
    )
    secondary_font: Mapped[Optional[str]] = mapped_column(String(100))
    brand_voice: Mapped[Optional[str]] = mapped_column(Text)
    photography_style: Mapped[Optional[str]] = mapped_column(Text)
    prohibited_elements: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="[]"
    )
    logo_config: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}"
    )
    text_customization: Mapped[Optional[dict]] = mapped_column(JSONB)
    post_processing: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_extracted_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship(
        back_populates="brand_guidelines", lazy="selectin"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="brand_guidelines", lazy="raise"
    )


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft"
    )
    brief: Mapped[dict] = mapped_column(JSONB, nullable=False)
    image_backend: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="firefly"
    )
    target_locales: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default='["en-US"]'
    )
    aspect_ratios: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default='["1:1","9:16","16:9"]'
    )
    brand_guidelines_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brand_guidelines.id")
    )
    localization_guidelines: Mapped[Optional[dict]] = mapped_column(JSONB)
    legal_guidelines: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships -- scalar FKs use selectin (cheap, 1 row each);
    # collections use lazy="raise" to force explicit loading and prevent
    # accidental eager-loading of potentially large result sets.
    brand_guidelines: Mapped[Optional["BrandGuideline"]] = relationship(
        back_populates="campaigns", lazy="selectin"
    )
    creator: Mapped[Optional["User"]] = relationship(
        back_populates="campaigns", lazy="selectin"
    )
    products: Mapped[list["CampaignProduct"]] = relationship(
        back_populates="campaign", lazy="raise", cascade="all, delete-orphan"
    )
    assets: Mapped[list["GeneratedAsset"]] = relationship(
        back_populates="campaign", lazy="raise", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="campaign", lazy="raise"
    )
    compliance_reports: Mapped[list["ComplianceReport"]] = relationship(
        back_populates="campaign", lazy="raise", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["CampaignMetric"]] = relationship(
        back_populates="campaign", lazy="raise", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_campaigns_status", "status"),
        Index("ix_campaigns_brand_name", "brand_name"),
        Index("ix_campaigns_created_by", "created_by"),
    )


# ---------------------------------------------------------------------------
# Campaign Products
# ---------------------------------------------------------------------------

class CampaignProduct(Base):
    __tablename__ = "campaign_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_description: Mapped[str] = mapped_column(Text, nullable=False)
    product_category: Mapped[str] = mapped_column(String(100), nullable=False)
    key_features: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="[]"
    )
    generation_prompt: Mapped[Optional[str]] = mapped_column(Text)
    hero_image_path: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        back_populates="products", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "product_id", name="uq_campaign_product"),
        Index("ix_campaign_products_campaign_id", "campaign_id"),
        Index("ix_campaign_products_product_category", "product_category"),
    )


# ---------------------------------------------------------------------------
# Generated Assets
# ---------------------------------------------------------------------------

class GeneratedAsset(Base):
    __tablename__ = "generated_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    generation_method: Mapped[str] = mapped_column(String(50), nullable=False)
    generation_time_ms: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        back_populates="assets", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "product_id",
            "locale",
            "aspect_ratio",
            name="uq_asset_variant",
        ),
        Index("ix_generated_assets_campaign_id", "campaign_id"),
        Index("ix_generated_assets_locale", "locale"),
        Index("ix_generated_assets_generation_method", "generation_method"),
    )


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="queued"
    )
    progress_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    current_stage: Mapped[Optional[str]] = mapped_column(String(50))
    started_at: Mapped[Optional[datetime]] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_trace: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        back_populates="jobs", lazy="raise"
    )

    __table_args__ = (
        Index("ix_jobs_campaign_id", "campaign_id"),
        Index("ix_jobs_status", "status"),
    )


# ---------------------------------------------------------------------------
# Compliance Reports
# ---------------------------------------------------------------------------

class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    violations: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    summary: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    checked_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        back_populates="compliance_reports", lazy="raise"
    )

    __table_args__ = (
        Index("ix_compliance_reports_campaign_id", "campaign_id"),
        Index("ix_compliance_reports_is_compliant", "is_compliant"),
    )


# ---------------------------------------------------------------------------
# Campaign Metrics
# ---------------------------------------------------------------------------

class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    technical_metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    business_metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        back_populates="metrics", lazy="raise"
    )

    __table_args__ = (
        Index("ix_campaign_metrics_campaign_id", "campaign_id"),
        Index("ix_campaign_metrics_recorded_at", "recorded_at"),
    )
