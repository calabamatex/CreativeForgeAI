"""Tests for the local filesystem storage backend and key validation utilities.

Covers:
- validate_storage_key: empty, path traversal, invalid chars, valid keys
- build_asset_key: various parameter combinations
- LocalStorageBackend: save, get, delete, get_url, list_keys
- Error handling: missing files, path traversal guard, StorageError wrapping
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.exceptions import StorageError
from src.storage_backend import build_asset_key, validate_storage_key
from src.storage_local import LocalStorageBackend


# ---------------------------------------------------------------------------
# validate_storage_key
# ---------------------------------------------------------------------------


class TestValidateStorageKey:
    """Tests for the validate_storage_key helper."""

    def test_valid_simple_key(self):
        """A plain alphanumeric key should pass validation."""
        validate_storage_key("campaigns/abc/products/xyz/hero.png")

    def test_valid_key_with_hyphens_and_underscores(self):
        """Keys with hyphens and underscores are allowed."""
        validate_storage_key("campaign-1/product_2/en-US/asset.png")

    def test_empty_key_raises(self):
        """An empty string must raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            validate_storage_key("")

    def test_dotdot_raises(self):
        """Keys containing '..' (path traversal) must be rejected."""
        with pytest.raises(ValueError, match=r"\.\."):
            validate_storage_key("campaigns/../etc/passwd")

    def test_invalid_characters_raises(self):
        """Keys with spaces, special chars, or unicode must be rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_storage_key("campaigns/my file.png")

    def test_key_with_only_dots_rejected(self):
        """Keys containing '..' even at the end must be rejected."""
        with pytest.raises(ValueError, match=r"\.\."):
            validate_storage_key("foo/..")

    def test_key_with_at_sign_rejected(self):
        """Keys with @ should be rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_storage_key("campaigns/@latest/asset.png")


# ---------------------------------------------------------------------------
# build_asset_key
# ---------------------------------------------------------------------------


class TestBuildAssetKey:
    """Tests for the build_asset_key helper function."""

    def test_hero_variant(self):
        """Hero variant should produce a 'hero/' path segment."""
        key = build_asset_key("camp1", "prod1", variant="hero")
        assert key == "campaigns/camp1/products/prod1/hero/prod1_hero.png"

    def test_locale_and_aspect_ratio(self):
        """Locale + aspect ratio should appear in path; colon replaced with x."""
        key = build_asset_key("camp1", "prod1", locale="en-US", aspect_ratio="16:9")
        assert "en-US" in key
        assert "16x9" in key
        assert key.endswith(".png")

    def test_locale_only(self):
        """Locale without aspect ratio should still produce a valid key."""
        key = build_asset_key("camp1", "prod1", locale="es-MX")
        assert "es-MX" in key
        assert "asset.png" in key

    def test_custom_format(self):
        """A non-default format should appear in the extension."""
        key = build_asset_key("camp1", "prod1", locale="en-US", aspect_ratio="1:1", fmt="jpg")
        assert key.endswith(".jpg")

    def test_bare_key(self):
        """No locale, no ratio, no variant should still produce a valid key."""
        key = build_asset_key("camp1", "prod1")
        assert key == "campaigns/camp1/products/prod1/asset.png"


# ---------------------------------------------------------------------------
# LocalStorageBackend -- save / get round-trip
# ---------------------------------------------------------------------------


class TestLocalStorageBackendSave:
    """Tests for LocalStorageBackend.save()."""

    async def test_save_creates_file(self, tmp_path: Path):
        """save() should write a file whose contents match the supplied bytes."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        data = b"hello world"
        returned_key = await backend.save("test/greeting.txt", data, "text/plain")

        assert returned_key == "test/greeting.txt"

        written = (tmp_path / "test" / "greeting.txt").read_bytes()
        assert written == data

    async def test_save_creates_nested_directories(self, tmp_path: Path):
        """save() should create any missing parent directories."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("a/b/c/d.png", b"\x89PNG", "image/png")

        assert (tmp_path / "a" / "b" / "c" / "d.png").exists()

    async def test_save_overwrites_existing_file(self, tmp_path: Path):
        """save() on an existing key should overwrite the previous data."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("file.bin", b"old", "application/octet-stream")
        await backend.save("file.bin", b"new", "application/octet-stream")

        assert (tmp_path / "file.bin").read_bytes() == b"new"

    async def test_save_returns_key(self, tmp_path: Path):
        """save() must return the same key that was passed in."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        key = await backend.save("assets/img.png", b"\x00", "image/png")
        assert key == "assets/img.png"


# ---------------------------------------------------------------------------
# LocalStorageBackend -- get
# ---------------------------------------------------------------------------


class TestLocalStorageBackendGet:
    """Tests for LocalStorageBackend.get()."""

    async def test_get_returns_saved_data(self, tmp_path: Path):
        """get() should return the exact bytes that were saved."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        original = b"binary-payload-\xff\x00"
        await backend.save("data.bin", original, "application/octet-stream")

        result = await backend.get("data.bin")
        assert result == original

    async def test_get_missing_key_raises(self, tmp_path: Path):
        """get() on a non-existent key must raise StorageError."""
        backend = LocalStorageBackend(base_dir=tmp_path)

        with pytest.raises(StorageError, match="Key not found"):
            await backend.get("does/not/exist.png")

    async def test_get_large_binary(self, tmp_path: Path):
        """get() should correctly handle a large binary payload."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        large = os.urandom(1024 * 1024)  # 1 MiB
        await backend.save("big.bin", large, "application/octet-stream")

        assert await backend.get("big.bin") == large


# ---------------------------------------------------------------------------
# LocalStorageBackend -- delete
# ---------------------------------------------------------------------------


class TestLocalStorageBackendDelete:
    """Tests for LocalStorageBackend.delete()."""

    async def test_delete_removes_file(self, tmp_path: Path):
        """delete() should remove the corresponding file from disk."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("rm_me.txt", b"data", "text/plain")

        assert (tmp_path / "rm_me.txt").exists()

        await backend.delete("rm_me.txt")

        assert not (tmp_path / "rm_me.txt").exists()

    async def test_delete_nonexistent_is_idempotent(self, tmp_path: Path):
        """delete() on a missing key should not raise."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        # Should not raise
        await backend.delete("never_existed.bin")

    async def test_delete_then_get_raises(self, tmp_path: Path):
        """After delete(), a subsequent get() should raise StorageError."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("gone.txt", b"bye", "text/plain")
        await backend.delete("gone.txt")

        with pytest.raises(StorageError, match="Key not found"):
            await backend.get("gone.txt")


# ---------------------------------------------------------------------------
# LocalStorageBackend -- get_url
# ---------------------------------------------------------------------------


class TestLocalStorageBackendGetUrl:
    """Tests for LocalStorageBackend.get_url()."""

    async def test_get_url_returns_file_uri(self, tmp_path: Path):
        """get_url() should return a file:// URI for an existing key."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("img.png", b"\x89PNG", "image/png")

        url = await backend.get_url("img.png")

        assert url.startswith("file://")
        assert "img.png" in url

    async def test_get_url_missing_key_raises(self, tmp_path: Path):
        """get_url() for a non-existent key must raise StorageError."""
        backend = LocalStorageBackend(base_dir=tmp_path)

        with pytest.raises(StorageError, match="Key not found"):
            await backend.get_url("no/such/file.png")

    async def test_get_url_points_to_real_file(self, tmp_path: Path):
        """The path embedded in the file:// URL should point to the actual file."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("deep/path/f.bin", b"\x01\x02", "application/octet-stream")

        url = await backend.get_url("deep/path/f.bin")

        # Extract the path from the file:// URL and verify it exists
        file_path = Path(url.replace("file://", ""))
        assert file_path.is_file()
        assert file_path.read_bytes() == b"\x01\x02"


# ---------------------------------------------------------------------------
# LocalStorageBackend -- list_keys
# ---------------------------------------------------------------------------


class TestLocalStorageBackendListKeys:
    """Tests for LocalStorageBackend.list_keys()."""

    async def test_list_keys_returns_all_keys(self, tmp_path: Path):
        """list_keys with an empty-ish prefix should find all stored files."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("campaigns/a/img.png", b"a", "image/png")
        await backend.save("campaigns/b/img.png", b"b", "image/png")
        await backend.save("campaigns/c/data.json", b"c", "application/json")

        keys = await backend.list_keys("campaigns")
        assert len(keys) == 3

    async def test_list_keys_filters_by_prefix(self, tmp_path: Path):
        """list_keys should return only keys matching the given prefix."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("campaigns/x/one.png", b"1", "image/png")
        await backend.save("campaigns/x/two.png", b"2", "image/png")
        await backend.save("campaigns/y/three.png", b"3", "image/png")

        keys = await backend.list_keys("campaigns/x")
        assert len(keys) == 2
        assert all(k.startswith("campaigns/x/") for k in keys)

    async def test_list_keys_returns_sorted(self, tmp_path: Path):
        """list_keys should return keys in sorted (lexicographic) order."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("campaigns/c.png", b"", "image/png")
        await backend.save("campaigns/a.png", b"", "image/png")
        await backend.save("campaigns/b.png", b"", "image/png")

        keys = await backend.list_keys("campaigns")
        assert keys == sorted(keys)

    async def test_list_keys_empty_dir_returns_empty(self, tmp_path: Path):
        """list_keys on an empty store should return an empty list."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        keys = await backend.list_keys("campaigns")
        assert keys == []

    async def test_list_keys_nonexistent_prefix_returns_empty(self, tmp_path: Path):
        """list_keys for a prefix with no matching keys returns an empty list."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        await backend.save("campaigns/real/file.png", b"data", "image/png")

        keys = await backend.list_keys("campaigns/nope")
        assert keys == []


# ---------------------------------------------------------------------------
# LocalStorageBackend -- key validation / path traversal
# ---------------------------------------------------------------------------


class TestLocalStorageBackendValidation:
    """Tests for key validation and path-traversal prevention."""

    async def test_empty_key_raises_valueerror(self, tmp_path: Path):
        """An empty key must raise ValueError before any I/O."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        with pytest.raises(ValueError, match="must not be empty"):
            await backend.save("", b"data", "text/plain")

    async def test_dotdot_key_raises_valueerror(self, tmp_path: Path):
        """A key containing '..' must be rejected."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            await backend.save("../../etc/passwd", b"pwned", "text/plain")

    async def test_invalid_chars_in_key_raises(self, tmp_path: Path):
        """Special characters not in the allowed set must raise ValueError."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        with pytest.raises(ValueError, match="invalid characters"):
            await backend.get("file with spaces.txt")

    async def test_get_rejects_invalid_key(self, tmp_path: Path):
        """get() should also validate the key before doing I/O."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        with pytest.raises(ValueError):
            await backend.get("")

    async def test_delete_rejects_invalid_key(self, tmp_path: Path):
        """delete() should also validate the key."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        with pytest.raises(ValueError):
            await backend.delete("../escape")


# ---------------------------------------------------------------------------
# LocalStorageBackend -- base_dir property
# ---------------------------------------------------------------------------


class TestLocalStorageBackendInit:
    """Tests for LocalStorageBackend initialization."""

    def test_base_dir_is_created(self, tmp_path: Path):
        """The constructor should create the base directory if it does not exist."""
        target = tmp_path / "new_storage_root"
        assert not target.exists()

        backend = LocalStorageBackend(base_dir=target)

        assert target.exists()
        assert target.is_dir()
        assert backend.base_dir == target.resolve()

    def test_base_dir_property(self, tmp_path: Path):
        """The base_dir property should return the resolved path."""
        backend = LocalStorageBackend(base_dir=tmp_path)
        assert backend.base_dir == tmp_path.resolve()

    def test_default_base_dir_uses_env(self, tmp_path: Path, monkeypatch):
        """When no base_dir is given, OUTPUT_DIR env var should be used."""
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "from_env"))
        backend = LocalStorageBackend()
        assert "from_env" in str(backend.base_dir)
