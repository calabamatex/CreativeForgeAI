"""
Comprehensive tests for Pydantic data models.
Tests validation, serialization, and model constraints.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError


class TestProduct:
    """Test Product model validation."""

    def test_valid_product(self, example_product):
        """Test creating a valid product."""
        from src.models import Product

        product = Product(**example_product)

        assert product.product_id == "TEST-PROD-001"
        assert product.product_name == "Test Product"
        assert len(product.key_features) == 3

    def test_product_with_minimal_fields(self):
        """Test product with only required fields."""
        from src.models import Product

        product = Product(
            product_id="MIN-001",
            product_name="Minimal Product",
            product_description="Description",
            product_category="Category",
        )

        assert product.key_features == []
        assert product.existing_assets is None
        assert product.generation_prompt is None

    def test_product_with_existing_assets(self):
        """Test product with existing assets."""
        from src.models import Product

        product = Product(
            product_id="ASSET-001",
            product_name="Product with Assets",
            product_description="Description",
            product_category="Category",
            existing_assets={"hero": "/path/to/hero.jpg", "logo": "/path/to/logo.png"},
        )

        assert "hero" in product.existing_assets
        assert product.existing_assets["hero"] == "/path/to/hero.jpg"

    def test_product_with_custom_prompt(self):
        """Test product with custom generation prompt."""
        from src.models import Product

        custom_prompt = "ultra realistic product photography, 8K resolution"

        product = Product(
            product_id="CUSTOM-001",
            product_name="Custom Product",
            product_description="Description",
            product_category="Category",
            generation_prompt=custom_prompt,
        )

        assert product.generation_prompt == custom_prompt


class TestCampaignMessage:
    """Test CampaignMessage model validation."""

    def test_valid_campaign_message(self, example_campaign_message):
        """Test creating a valid campaign message."""
        from src.models import CampaignMessage

        message = CampaignMessage(**example_campaign_message)

        assert message.locale == "en-US"
        assert message.headline == "Test Headline"
        assert message.subheadline == "Test Subheadline"
        assert message.cta == "Test CTA"

    def test_campaign_message_default_locale(self):
        """Test campaign message with default locale."""
        from src.models import CampaignMessage

        message = CampaignMessage(headline="Headline", subheadline="Subheadline", cta="CTA")

        assert message.locale == "en-US"

    def test_campaign_message_empty_strings_fail(self):
        """Test that empty strings are rejected."""
        from src.models import CampaignMessage

        with pytest.raises(ValidationError) as exc_info:
            CampaignMessage(headline="", subheadline="Sub", cta="CTA")

        assert "headline" in str(exc_info.value)

    def test_campaign_message_different_locales(self):
        """Test campaign messages in different locales."""
        from src.models import CampaignMessage

        locales = ["en-US", "es-MX", "fr-CA", "pt-BR", "de-DE"]

        for locale in locales:
            message = CampaignMessage(locale=locale, headline="Headline", subheadline="Sub", cta="CTA")
            assert message.locale == locale


class TestComprehensiveBrandGuidelines:
    """Test ComprehensiveBrandGuidelines model."""

    def test_valid_brand_guidelines(self, brand_guidelines_model):
        """Test creating valid brand guidelines."""
        assert brand_guidelines_model.source_file == "test_guidelines.pdf"
        assert len(brand_guidelines_model.primary_colors) == 2
        assert brand_guidelines_model.primary_font == "Montserrat"

    def test_brand_guidelines_minimal(self):
        """Test brand guidelines with minimal required fields."""
        from src.models import ComprehensiveBrandGuidelines

        guidelines = ComprehensiveBrandGuidelines(source_file="minimal.pdf")

        assert guidelines.primary_colors == []
        assert guidelines.primary_font == "Arial"  # Default
        assert guidelines.brand_voice == "Professional"  # Default

    def test_brand_guidelines_with_all_fields(self):
        """Test brand guidelines with all optional fields."""
        from src.models import ComprehensiveBrandGuidelines

        guidelines = ComprehensiveBrandGuidelines(
            source_file="complete.pdf",
            primary_colors=["#FF0000", "#00FF00"],
            secondary_colors=["#0000FF"],
            primary_font="Helvetica",
            secondary_font="Arial",
            brand_voice="Bold and innovative",
            photography_style="Dynamic action shots",
            logo_clearspace=30,
            logo_min_size=100,
            prohibited_uses=["No dark backgrounds"],
            prohibited_elements=["No gradients"],
            approved_taglines=["Tagline 1", "Tagline 2"],
        )

        assert len(guidelines.primary_colors) == 2
        assert guidelines.logo_clearspace == 30
        assert len(guidelines.approved_taglines) == 2


class TestLocalizationGuidelines:
    """Test LocalizationGuidelines model."""

    def test_valid_localization_guidelines(self, localization_guidelines_model):
        """Test creating valid localization guidelines."""
        assert localization_guidelines_model.source_file == "test_localization.yaml"
        assert len(localization_guidelines_model.supported_locales) == 3
        assert "en-US" in localization_guidelines_model.market_specific_rules

    def test_localization_guidelines_minimal(self):
        """Test localization guidelines with minimal fields."""
        from src.models import LocalizationGuidelines

        guidelines = LocalizationGuidelines(source_file="minimal.yaml")

        assert guidelines.supported_locales == []
        assert guidelines.market_specific_rules == {}
        assert guidelines.prohibited_terms == {}

    def test_market_specific_rules_structure(self):
        """Test market-specific rules structure."""
        from src.models import LocalizationGuidelines

        guidelines = LocalizationGuidelines(
            source_file="test.yaml",
            market_specific_rules={
                "en-US": {"tone": "casual", "formality": "informal"},
                "es-MX": {"tone": "warm", "formality": "formal"},
            },
        )

        assert "en-US" in guidelines.market_specific_rules
        assert guidelines.market_specific_rules["en-US"]["tone"] == "casual"

    def test_prohibited_terms_by_locale(self):
        """Test prohibited terms structure."""
        from src.models import LocalizationGuidelines

        guidelines = LocalizationGuidelines(
            source_file="test.yaml", prohibited_terms={"en-US": ["cheap", "discount"], "es-MX": ["barato"]}
        )

        assert len(guidelines.prohibited_terms["en-US"]) == 2
        assert "cheap" in guidelines.prohibited_terms["en-US"]


class TestCampaignBrief:
    """Test CampaignBrief model validation."""

    def test_valid_campaign_brief(self, example_brief):
        """Test creating valid campaign brief."""
        from src.models import CampaignBrief

        brief = CampaignBrief(**example_brief)

        assert brief.campaign_id == "TEST-CAMPAIGN-001"
        assert len(brief.products) == 1
        assert brief.enable_localization is True
        assert len(brief.target_locales) == 2

    def test_campaign_brief_backend_validation(self, example_product):
        """Test image generation backend validation."""
        from src.models import CampaignBrief, CampaignMessage, Product

        # Valid backends
        valid_backends = ["firefly", "openai", "dall-e", "dalle", "gemini", "imagen", "claude"]

        for backend in valid_backends:
            brief = CampaignBrief(
                campaign_id="TEST",
                campaign_name="Test",
                brand_name="Brand",
                campaign_message=CampaignMessage(headline="H", subheadline="S", cta="C"),
                products=[Product(**example_product)],
                image_generation_backend=backend,
            )
            # Backend should be normalized to lowercase
            assert brief.image_generation_backend in valid_backends

    def test_campaign_brief_invalid_backend(self):
        """Test that invalid backend raises error."""
        from src.models import CampaignBrief, CampaignMessage

        with pytest.raises(ValidationError) as exc_info:
            CampaignBrief(
                campaign_id="TEST",
                campaign_name="Test",
                brand_name="Brand",
                campaign_message=CampaignMessage(headline="H", subheadline="S", cta="C"),
                products=[],
                image_generation_backend="invalid_backend",
            )

        assert "image_generation_backend" in str(exc_info.value)

    def test_campaign_brief_aspect_ratio_validation(self, example_product):
        """Test aspect ratio validation."""
        from src.models import CampaignBrief, CampaignMessage, Product

        valid_ratios = ["1:1", "9:16", "16:9", "4:5"]

        brief = CampaignBrief(
            campaign_id="TEST",
            campaign_name="Test",
            brand_name="Brand",
            campaign_message=CampaignMessage(headline="H", subheadline="S", cta="C"),
            products=[Product(**example_product)],
            aspect_ratios=valid_ratios,
        )

        assert len(brief.aspect_ratios) == 4

    def test_campaign_brief_invalid_aspect_ratio(self):
        """Test that invalid aspect ratio raises error."""
        from src.models import CampaignBrief, CampaignMessage

        with pytest.raises(ValidationError) as exc_info:
            CampaignBrief(
                campaign_id="TEST",
                campaign_name="Test",
                brand_name="Brand",
                campaign_message=CampaignMessage(headline="H", subheadline="S", cta="C"),
                products=[],
                aspect_ratios=["1:1", "invalid:ratio"],
            )

        assert "aspect_ratios" in str(exc_info.value)

    def test_campaign_brief_default_values(self, example_product):
        """Test campaign brief default values."""
        from src.models import CampaignBrief, CampaignMessage, Product

        brief = CampaignBrief(
            campaign_id="TEST",
            campaign_name="Test",
            brand_name="Brand",
            campaign_message=CampaignMessage(headline="H", subheadline="S", cta="C"),
            products=[Product(**example_product)],
        )

        assert brief.aspect_ratios == ["1:1", "9:16", "16:9"]
        assert brief.output_formats == ["png", "jpg"]
        assert brief.image_generation_backend == "firefly"
        assert brief.enable_localization is False
        assert brief.target_locales == ["en-US"]

    def test_campaign_brief_with_guideline_files(self, example_product):
        """Test campaign brief with guideline file paths."""
        from src.models import CampaignBrief, CampaignMessage, Product

        brief = CampaignBrief(
            campaign_id="TEST",
            campaign_name="Test",
            brand_name="Brand",
            campaign_message=CampaignMessage(headline="H", subheadline="S", cta="C"),
            products=[Product(**example_product)],
            brand_guidelines_file="path/to/brand.pdf",
            localization_guidelines_file="path/to/locale.yaml",
        )

        assert brief.brand_guidelines_file == "path/to/brand.pdf"
        assert brief.localization_guidelines_file == "path/to/locale.yaml"

    def test_campaign_brief_multi_locale(self, example_product):
        """Test campaign brief with multiple target locales."""
        from src.models import CampaignBrief, CampaignMessage, Product

        brief = CampaignBrief(
            campaign_id="TEST",
            campaign_name="Test",
            brand_name="Brand",
            campaign_message=CampaignMessage(headline="H", subheadline="S", cta="C"),
            products=[Product(**example_product)],
            enable_localization=True,
            target_locales=["en-US", "es-MX", "fr-CA", "pt-BR", "de-DE"],
        )

        assert len(brief.target_locales) == 5
        assert brief.enable_localization is True


class TestGeneratedAsset:
    """Test GeneratedAsset model."""

    def test_valid_generated_asset(self):
        """Test creating a valid generated asset."""
        from src.models import GeneratedAsset

        asset = GeneratedAsset(
            product_id="PROD-001",
            locale="en-US",
            aspect_ratio="1:1",
            file_path="/output/asset.png",
            generation_method="firefly",
        )

        assert asset.product_id == "PROD-001"
        assert asset.locale == "en-US"
        assert asset.aspect_ratio == "1:1"
        assert asset.generation_method == "firefly"

    def test_generated_asset_with_metadata(self):
        """Test asset with additional metadata."""
        from src.models import GeneratedAsset

        asset = GeneratedAsset(
            product_id="P1",
            locale="es-MX",
            aspect_ratio="16:9",
            file_path="/path/to/asset.jpg",
            generation_method="openai",
            metadata={"prompt": "test prompt", "seed": 12345, "backend": "dall-e-3"},
        )

        assert "prompt" in asset.metadata
        assert asset.metadata["seed"] == 12345
        assert asset.metadata["backend"] == "dall-e-3"

    def test_generated_asset_timestamp_auto(self):
        """Test that timestamp is auto-generated."""
        from src.models import GeneratedAsset

        asset = GeneratedAsset(
            product_id="P1", locale="en-US", aspect_ratio="1:1", file_path="/path", generation_method="firefly"
        )

        assert asset.timestamp is not None
        assert isinstance(asset.timestamp, datetime)


class TestCampaignOutput:
    """Test CampaignOutput model."""

    def test_valid_campaign_output(self):
        """Test creating valid campaign output."""
        from src.models import CampaignOutput, GeneratedAsset

        assets = [
            GeneratedAsset(
                product_id="P1", locale="en-US", aspect_ratio="1:1", file_path="/path1.png", generation_method="firefly"
            ),
            GeneratedAsset(
                product_id="P1", locale="es-MX", aspect_ratio="1:1", file_path="/path2.png", generation_method="firefly"
            ),
        ]

        output = CampaignOutput(
            campaign_id="CAMP-001",
            campaign_name="Test Campaign",
            generated_assets=assets,
            total_assets=2,
            locales_processed=["en-US", "es-MX"],
            products_processed=["P1"],
            processing_time_seconds=120.5,
            success_rate=1.0,
        )

        assert output.total_assets == 2
        assert len(output.generated_assets) == 2
        assert output.success_rate == 1.0

    def test_campaign_output_with_errors(self):
        """Test campaign output with errors."""
        from src.models import CampaignOutput

        output = CampaignOutput(
            campaign_id="CAMP-002",
            campaign_name="Test Campaign",
            generated_assets=[],
            total_assets=0,
            locales_processed=[],
            products_processed=[],
            processing_time_seconds=10.0,
            success_rate=0.0,
            errors=["Error processing product P1", "Error generating locale es-MX"],
        )

        assert len(output.errors) == 2
        assert output.success_rate == 0.0

    def test_campaign_output_defaults(self):
        """Test campaign output default values."""
        from src.models import CampaignOutput

        output = CampaignOutput(campaign_id="CAMP-003", campaign_name="Test Campaign")

        assert output.total_assets == 0
        assert output.generated_assets == []
        assert output.success_rate == 1.0
        assert output.errors == []
        assert isinstance(output.generation_timestamp, datetime)
