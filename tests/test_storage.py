"""
Tests for storage manager (file system operations).
"""
import pytest
from pathlib import Path
import json
from PIL import Image
import io


class TestStorageManager:
    """Test StorageManager class."""

    def test_create_campaign_directory(self, mock_env_vars, tmp_path, monkeypatch):
        """Test creating campaign directory structure."""
        from src.storage import StorageManager

        # Mock OUTPUT_DIR to use tmp_path
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        storage = StorageManager()
        campaign_dir = storage.create_campaign_directory("TEST-CAMPAIGN")

        assert campaign_dir.exists()
        assert campaign_dir.is_dir()
        assert "TEST-CAMPAIGN" in str(campaign_dir)

    def test_get_asset_path(self, mock_env_vars, tmp_path, monkeypatch):
        """Test generating asset file paths."""
        from src.storage import StorageManager

        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        storage = StorageManager()
        storage.create_campaign_directory("TEST")

        path = storage.get_asset_path(
            campaign_id="TEST",
            locale="en-US",
            product_id="PROD-001",
            aspect_ratio="1:1",
            format="png"
        )

        assert path is not None
        assert "TEST" in str(path)
        assert "en-US" in str(path)
        assert "PROD-001" in str(path)
        assert "png" in str(path)
        # Check that it normalized the aspect ratio
        assert "1x1" in str(path)

    def test_save_image(self, mock_env_vars, tmp_path, monkeypatch):
        """Test saving image to disk."""
        from src.storage import StorageManager

        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        storage = StorageManager()
        storage.create_campaign_directory("TEST")

        path = storage.get_asset_path(
            "TEST", "en-US", "P1", "1:1", "png"
        )

        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        storage.save_image(img, path)

        assert path.exists()
        assert path.stat().st_size > 0

    def test_save_report(self, mock_env_vars, tmp_path, monkeypatch):
        """Test saving campaign report."""
        from src.storage import StorageManager
        from src.models import CampaignOutput, GeneratedAsset

        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        storage = StorageManager()
        storage.create_campaign_directory("TEST")

        assets = [
            GeneratedAsset(
                product_id="PROD-001",
                locale="en-US",
                aspect_ratio="1:1",
                file_path="/tmp/test.png",
                generation_method="firefly",
            )
        ]

        output = CampaignOutput(
            campaign_id="TEST",
            campaign_name="Test Campaign",
            generated_assets=assets,
            total_assets=1,
        )

        report_path = storage.save_report(output, "TEST", "PROD-001")

        assert report_path.exists()
        assert report_path.suffix == ".json"

        # Verify report content
        with open(report_path) as f:
            data = json.load(f)
            assert data["campaign_id"] == "TEST"
            assert data["total_assets"] == 1

    def test_directory_structure(self, mock_env_vars, tmp_path, monkeypatch):
        """Test complete directory structure creation."""
        from src.storage import StorageManager
        from src import config

        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        config._config = None  # Force config reload

        storage = StorageManager()
        storage.create_campaign_directory("TEST")

        # Create paths for multiple assets
        for locale in ["en-US", "es-MX"]:
            for product in ["P1", "P2"]:
                path = storage.get_asset_path("TEST", locale, product, "1:1", "png")
                # Path parent directories are created automatically

        # Verify structure
        assert (tmp_path / "TEST").exists()

    def test_aspect_ratio_normalization(self, mock_env_vars, tmp_path, monkeypatch):
        """Test aspect ratio normalization in paths."""
        from src.storage import StorageManager

        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        storage = StorageManager()

        path = storage.get_asset_path("TEST", "en-US", "P1", "16:9", "png")

        # Should normalize 16:9 to 16x9 in path
        assert "16x9" in str(path)

    def test_list_campaign_assets(self, mock_env_vars, tmp_path, monkeypatch):
        """Test listing all assets in a campaign."""
        from src.storage import StorageManager
        from src import config

        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        config._config = None  # Force config reload

        storage = StorageManager()
        storage.create_campaign_directory("TEST")

        # Save multiple assets
        for i in range(3):
            path = storage.get_asset_path("TEST", "en-US", f"P{i}", "1:1", "png")
            img = Image.new('RGB', (100, 100), color='blue')
            storage.save_image(img, path)

        # List assets - assets are stored under output_dir/product_id/campaign_id/...
        assets = list(tmp_path.rglob("*.png"))

        assert len(assets) == 3


class TestStorageIntegration:
    """Integration tests for storage operations."""

    def test_full_campaign_storage(self, mock_env_vars, tmp_path, monkeypatch):
        """Test storing complete campaign output."""
        from src.storage import StorageManager
        from src.models import CampaignOutput, GeneratedAsset

        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        storage = StorageManager()
        storage.create_campaign_directory("FULL-TEST")

        # Save multiple assets
        assets = []
        for locale in ["en-US", "es-MX"]:
            for product in ["P1", "P2"]:
                for ratio in ["1:1", "9:16"]:
                    path = storage.get_asset_path(
                        "FULL-TEST", locale, product, ratio, "png"
                    )
                    img = Image.new('RGB', (100, 100), color='green')
                    storage.save_image(img, path)

                    asset = GeneratedAsset(
                        product_id=product,
                        locale=locale,
                        aspect_ratio=ratio,
                        file_path=str(path),
                        generation_method="firefly"
                    )
                    assets.append(asset)

        # Save report
        output = CampaignOutput(
            campaign_id="FULL-TEST",
            campaign_name="Full Test Campaign",
            generated_assets=assets,
            total_assets=len(assets),
            locales_processed=["en-US", "es-MX"],
            products_processed=["P1", "P2"]
        )

        report_path = storage.save_report(output, "FULL-TEST", "P1")

        # Verify everything
        assert len(assets) == 8  # 2 locales * 2 products * 2 ratios
        assert report_path.exists()

        # Verify all files exist
        for asset in assets:
            assert Path(asset.file_path).exists()
