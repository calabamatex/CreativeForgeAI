"""Storage management for campaign outputs."""
import json
import re
import shutil
from pathlib import Path
from PIL import Image
from datetime import datetime, timezone
from typing import Dict, List, Optional
import structlog
from src.models import CampaignOutput, CampaignBrief
from src.config import get_config
from src.exceptions import StorageError

logger = structlog.get_logger(__name__)

_SAFE_PATH_RE = re.compile(r"^[a-zA-Z0-9._\-]+$")


class StorageManager:
    """Manage campaign output file organization."""

    def __init__(self):
        self.config = get_config()
        self.output_dir = self.config.OUTPUT_DIR

    @staticmethod
    def _sanitize_component(value: str, name: str) -> str:
        """Sanitize a single path component to prevent directory traversal."""
        if ".." in value or "/" in value or "\\" in value:
            raise StorageError(
                message=f"Invalid characters in {name}: {value!r}",
                detail="Path components must not contain '..', '/', or '\\\\'",
            )
        if not value:
            raise StorageError(message=f"Empty {name} is not allowed")
        return value

    def create_campaign_directory(self, campaign_id: str) -> Path:
        """Create campaign output directory structure."""
        self._sanitize_component(campaign_id, "campaign_id")
        campaign_dir = self.output_dir / campaign_id
        campaign_dir.mkdir(parents=True, exist_ok=True)
        return campaign_dir

    def get_asset_path(
        self,
        campaign_id: str,
        locale: str,
        product_id: str,
        aspect_ratio: str,
        format: str = "png"
    ) -> Path:
        """Generate path for campaign asset."""
        # Validate all path components
        self._sanitize_component(campaign_id, "campaign_id")
        self._sanitize_component(locale, "locale")
        self._sanitize_component(product_id, "product_id")

        # Normalize aspect ratio for directory name
        ratio_dir = aspect_ratio.replace(":", "x")

        # Structure: product_id/campaign_id/locale/ratio/filename
        path = (
            self.output_dir / product_id / campaign_id / locale /
            ratio_dir / f"{product_id}_{ratio_dir}_{locale}.{format}"
        )

        # Create directories
        path.parent.mkdir(parents=True, exist_ok=True)

        return path
    
    def save_image(self, image: Image.Image, path: Path) -> None:
        """Save image to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, optimize=True, quality=95)
    
    def save_report(
        self,
        campaign_output: CampaignOutput,
        campaign_id: str,
        product_id: str
    ) -> Path:
        """
        Save per-product campaign report JSON with enhanced metrics.

        Reports are saved to output/campaign_reports/ with filename format:
        campaign_report_CAMPAIGN_ID_PRODUCT_ID_YYYY-MM-DD.json

        Historical reports are preserved (not overwritten).
        """
        # Create campaign_reports directory at root output level
        reports_dir = self.output_dir / "campaign_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for filename (YYYY-MM-DD format)
        timestamp = datetime.now().strftime("%Y-%m-%d")

        # New filename format: campaign_report_CAMPAIGN_ID_PRODUCT_ID_YYYY-MM-DD.json
        filename = f"campaign_report_{campaign_id}_{product_id}_{timestamp}.json"
        report_path = reports_dir / filename

        # Filter assets for this product only
        product_assets = [
            asset for asset in campaign_output.generated_assets
            if asset.product_id == product_id
        ]

        # Create product-specific output
        product_output = campaign_output.model_copy(update={
            "generated_assets": product_assets,
            "total_assets": len(product_assets),
            "products_processed": [product_id]
        })

        with open(report_path, 'w') as f:
            json.dump(product_output.model_dump(), f, indent=2, default=str)

        return report_path

    def backup_campaign_brief(self, brief_path: str) -> Path:
        """
        Backup original campaign brief with UTC timestamp.

        Args:
            brief_path: Path to original campaign brief

        Returns:
            Path to backup file
        """
        brief_file = Path(brief_path)

        if not brief_file.exists():
            raise FileNotFoundError(f"Campaign brief not found: {brief_path}")

        # Generate UTC timestamp for backup filename
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        backup_name = f"{brief_file.stem}_{timestamp}{brief_file.suffix}"
        backup_path = brief_file.parent / backup_name

        # Copy original to backup
        shutil.copy2(brief_file, backup_path)

        return backup_path

    def update_campaign_brief(
        self,
        brief_path: str,
        campaign_output: CampaignOutput,
        hero_images: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Update original campaign brief with generated asset paths.

        Args:
            brief_path: Path to campaign brief to update
            campaign_output: Campaign output with generated assets
            hero_images: Optional dict of product_id -> hero_image_path
        """
        brief_file = Path(brief_path)

        # Load current brief
        with open(brief_file, 'r') as f:
            brief_data = json.load(f)

        # Group generated assets by product_id and locale
        assets_by_product: Dict[str, Dict[str, Dict[str, str]]] = {}

        for asset in campaign_output.generated_assets:
            product_id = asset.product_id
            locale = asset.locale
            ratio = asset.aspect_ratio

            if product_id not in assets_by_product:
                assets_by_product[product_id] = {}

            if locale not in assets_by_product[product_id]:
                assets_by_product[product_id][locale] = {}

            # Store asset path by aspect ratio
            assets_by_product[product_id][locale][ratio] = asset.file_path

        # Update products with generated assets
        for product in brief_data.get('products', []):
            product_id = product['product_id']

            if product_id in assets_by_product or (hero_images and product_id in hero_images):
                # Initialize or update existing_assets
                if 'existing_assets' not in product or product['existing_assets'] is None:
                    product['existing_assets'] = {}

                # Add hero image if provided
                if hero_images and product_id in hero_images:
                    product['existing_assets']['hero'] = hero_images[product_id]

                # Add generated assets organized by locale and aspect ratio
                if product_id in assets_by_product:
                    for locale, ratios in assets_by_product[product_id].items():
                        for ratio, file_path in ratios.items():
                            # Use descriptive key format: {locale}_{ratio}
                            asset_key = f"{locale}_{ratio}"
                            product['existing_assets'][asset_key] = file_path

        # Write updated brief back to original file
        with open(brief_file, 'w') as f:
            json.dump(brief_data, f, indent=2)

        logger.info("storage.brief_updated", path=str(brief_file))
