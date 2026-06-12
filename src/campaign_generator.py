"""Campaign brief generator from templates."""

import json
import re
from pathlib import Path


class CampaignGenerator:
    """Generate campaign briefs from templates."""

    def __init__(self, template_path: str | None = None):
        """Initialize generator with template path."""
        if template_path:
            self.template_path = Path(template_path)
        else:
            # Default template
            self.template_path = Path(__file__).parent.parent / "examples" / "templates" / "campaign_template.json"

    def load_template(self) -> str:
        """Load template content."""
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        with open(self.template_path) as f:
            return f.read()

    def generate(
        self, campaign_id: str, campaign_name: str, output_path: str | None = None, interactive: bool = False, **kwargs
    ) -> Path:
        """
        Generate a new campaign brief from template.

        Args:
            campaign_id: Unique campaign identifier
            campaign_name: Human-readable campaign name
            output_path: Where to save the generated file (optional)
            interactive: If True, prompt for all values
            **kwargs: Template variable values

        Returns:
            Path to generated campaign file
        """
        # Load template
        template_content = self.load_template()

        # Prepare replacements
        replacements = {
            "CAMPAIGN_ID": campaign_id,
            "CAMPAIGN_NAME": campaign_name,
        }

        # Map kwargs to template placeholders
        kwarg_mapping = {
            "brand_name": "BRAND_NAME",
            "target_market": "TARGET_MARKET",
            "target_audience": "TARGET_AUDIENCE",
            "headline": "HEADLINE",
            "subheadline": "SUBHEADLINE",
            "cta": "CTA",
            "product_id": "PRODUCT_ID",
            "product_name": "PRODUCT_NAME",
            "product_description": "PRODUCT_DESCRIPTION",
            "product_category": "PRODUCT_CATEGORY",
            "generation_prompt": "GENERATION_PROMPT",
        }

        for kwarg, placeholder in kwarg_mapping.items():
            if kwarg in kwargs and kwargs[kwarg]:
                replacements[placeholder] = kwargs[kwarg]

        if interactive:
            # Interactive mode - prompt for each placeholder
            placeholders = self._extract_placeholders(template_content)
            for placeholder in placeholders:
                if placeholder not in replacements:
                    default = self._get_default_value(placeholder)
                    value = input(f"{placeholder} [{default}]: ").strip() or default
                    replacements[placeholder] = value
        else:
            # Use provided kwargs and defaults
            replacements.update(kwargs)
            # Fill remaining with defaults
            placeholders = self._extract_placeholders(template_content)
            for placeholder in placeholders:
                if placeholder not in replacements:
                    replacements[placeholder] = self._get_default_value(placeholder)

        # Replace placeholders
        result = template_content
        for key, value in replacements.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))

        # Determine output path
        if not output_path:
            safe_id = re.sub(r"[^a-z0-9_-]", "_", campaign_id.lower())
            output_path = f"examples/{safe_id}_campaign.json"

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save generated campaign
        with open(output_file, "w") as f:
            f.write(result)

        return output_file

    def _extract_placeholders(self, template: str) -> list:
        """Extract all {{PLACEHOLDER}} values from template."""
        pattern = r"\{\{([A-Z_0-9]+)\}\}"
        return list(set(re.findall(pattern, template)))

    def _get_default_value(self, placeholder: str) -> str:
        """Get default value for a placeholder."""
        defaults = {
            "BRAND_NAME": "Your Brand",
            "TARGET_MARKET": "North America",
            "TARGET_AUDIENCE": "General consumers",
            "HEADLINE": "Discover Something Amazing",
            "SUBHEADLINE": "Experience Quality and Innovation",
            "CTA": "Learn More",
            "PRODUCT_ID": "PRODUCT-001",
            "PRODUCT_NAME": "Premium Product",
            "PRODUCT_DESCRIPTION": "High-quality product with exceptional features",
            "PRODUCT_CATEGORY": "General",
            "FEATURE_1": "High quality",
            "FEATURE_2": "Great value",
            "FEATURE_3": "Trusted brand",
            "GENERATION_PROMPT": "professional product photo, modern design, studio lighting",
        }
        return defaults.get(placeholder, placeholder.lower().replace("_", " "))

    def quick_generate(self, campaign_id: str, campaign_name: str, products: list, **kwargs) -> Path:
        """
        Quick generate with product list.

        Args:
            campaign_id: Campaign identifier
            campaign_name: Campaign name
            products: List of product dicts with keys: id, name, description, category, features, prompt
            **kwargs: Additional campaign parameters

        Returns:
            Path to generated file
        """
        # Load template and parse
        template_content = self.load_template()
        template_data = json.loads(template_content.replace("{{", "PLACEHOLDER_").replace("}}", ""))

        # Update basic info
        template_data["campaign_id"] = campaign_id
        template_data["campaign_name"] = campaign_name

        # Update campaign message if provided
        if "headline" in kwargs:
            template_data["campaign_message"]["headline"] = kwargs["headline"]
        if "subheadline" in kwargs:
            template_data["campaign_message"]["subheadline"] = kwargs["subheadline"]
        if "cta" in kwargs:
            template_data["campaign_message"]["cta"] = kwargs["cta"]

        # Update other fields
        for key in [
            "brand_name",
            "target_market",
            "target_audience",
            "aspect_ratios",
            "target_locales",
            "image_generation_backend",
            "enable_localization",
            "brand_guidelines_file",
            "localization_guidelines_file",
        ]:
            if key in kwargs:
                template_data[key] = kwargs[key]

        # Replace products
        template_data["products"] = []
        for product in products:
            template_data["products"].append(
                {
                    "product_id": product.get("id", "PRODUCT-001"),
                    "product_name": product.get("name", "Product"),
                    "product_description": product.get("description", ""),
                    "product_category": product.get("category", "General"),
                    "key_features": product.get("features", []),
                    "existing_assets": product.get("existing_assets", None),
                    "generation_prompt": product.get("prompt", None),
                }
            )

        # Save
        safe_id = re.sub(r"[^a-z0-9_-]", "_", campaign_id.lower())
        output_path = Path(f"examples/{safe_id}_campaign.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(template_data, f, indent=2)

        return output_path
