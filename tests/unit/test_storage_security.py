"""Security tests for storage path handling."""
import pytest
from pathlib import Path
from unittest.mock import patch

from src.storage import StorageManager
from src.exceptions import StorageError


class TestPathTraversalPrevention:
    """Verify that path components cannot escape the output directory."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a StorageManager with a known output directory."""
        with patch("src.storage.get_config") as mock_config:
            config = mock_config.return_value
            config.OUTPUT_DIR = tmp_path / "output"
            config.OUTPUT_DIR.mkdir()
            mgr = StorageManager()
            mgr.output_dir = config.OUTPUT_DIR
            return mgr

    def test_normal_path_stays_within_output(self, storage):
        path = storage.get_asset_path("campaign-1", "en-US", "prod-1", "1:1", "png")
        assert str(storage.output_dir) in str(path.resolve())

    def test_campaign_id_traversal_rejected(self, storage):
        with pytest.raises(StorageError):
            storage.get_asset_path("../../../etc", "en-US", "prod-1", "1:1", "png")

    def test_product_id_traversal_rejected(self, storage):
        with pytest.raises(StorageError):
            storage.get_asset_path("campaign-1", "en-US", "../../secrets", "1:1", "png")

    def test_locale_traversal_rejected(self, storage):
        with pytest.raises(StorageError):
            storage.get_asset_path("campaign-1", "../../../tmp", "prod-1", "1:1", "png")

    def test_backslash_traversal_rejected(self, storage):
        with pytest.raises(StorageError):
            storage.get_asset_path("campaign-1", "en-US", "..\\..\\secrets", "1:1", "png")

    def test_empty_campaign_id_rejected(self, storage):
        with pytest.raises(StorageError):
            storage.get_asset_path("", "en-US", "prod-1", "1:1", "png")

    def test_aspect_ratio_normalized(self, storage):
        """Aspect ratio colons are replaced to prevent path issues."""
        path = storage.get_asset_path("campaign-1", "en-US", "prod-1", "16:9", "png")
        assert "16x9" in str(path)
        assert "16:9" not in str(path)

    def test_create_campaign_directory_traversal_rejected(self, storage):
        with pytest.raises(StorageError):
            storage.create_campaign_directory("../../etc")


class TestSanitizeComponent:
    """Test the _sanitize_component static method directly."""

    def test_clean_values_pass(self):
        assert StorageManager._sanitize_component("campaign-1", "test") == "campaign-1"
        assert StorageManager._sanitize_component("en-US", "test") == "en-US"
        assert StorageManager._sanitize_component("product.v2", "test") == "product.v2"

    def test_dot_dot_rejected(self):
        with pytest.raises(StorageError):
            StorageManager._sanitize_component("..", "test")

    def test_slash_rejected(self):
        with pytest.raises(StorageError):
            StorageManager._sanitize_component("a/b", "test")

    def test_backslash_rejected(self):
        with pytest.raises(StorageError):
            StorageManager._sanitize_component("a\\b", "test")

    def test_empty_rejected(self):
        with pytest.raises(StorageError):
            StorageManager._sanitize_component("", "test")
