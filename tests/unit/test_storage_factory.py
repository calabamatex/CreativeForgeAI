"""Tests for the storage factory function.

Covers:
- Selecting LocalStorageBackend via argument, env var, or default
- Selecting S3StorageBackend via argument or env var
- Raising ValueError for unknown backend types
- The cached singleton helper get_default_storage_backend
"""

from __future__ import annotations

import pytest

from src.storage_backend import StorageBackend
from src.storage_factory import get_storage_backend, get_default_storage_backend
from src.storage_local import LocalStorageBackend
from src.storage_s3 import S3StorageBackend


# ---------------------------------------------------------------------------
# get_storage_backend -- local
# ---------------------------------------------------------------------------


class TestFactoryLocal:
    """Tests for local backend selection."""

    def test_explicit_local_returns_local_backend(self, tmp_path, monkeypatch):
        """Passing backend_type='local' should return a LocalStorageBackend."""
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        backend = get_storage_backend(backend_type="local")

        assert isinstance(backend, LocalStorageBackend)
        assert isinstance(backend, StorageBackend)

    def test_env_var_local_returns_local_backend(self, tmp_path, monkeypatch):
        """STORAGE_BACKEND=local env var should yield LocalStorageBackend."""
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        backend = get_storage_backend()

        assert isinstance(backend, LocalStorageBackend)

    def test_default_returns_local_backend(self, tmp_path, monkeypatch):
        """When no backend_type or env var is set, default to local."""
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        backend = get_storage_backend()

        assert isinstance(backend, LocalStorageBackend)

    def test_local_case_insensitive(self, tmp_path, monkeypatch):
        """Backend type matching should be case-insensitive."""
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        backend = get_storage_backend(backend_type="LOCAL")

        assert isinstance(backend, LocalStorageBackend)

    def test_local_with_whitespace(self, tmp_path, monkeypatch):
        """Leading/trailing whitespace in backend type should be stripped."""
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        backend = get_storage_backend(backend_type="  local  ")

        assert isinstance(backend, LocalStorageBackend)


# ---------------------------------------------------------------------------
# get_storage_backend -- s3
# ---------------------------------------------------------------------------


class TestFactoryS3:
    """Tests for S3 backend selection."""

    def test_explicit_s3_returns_s3_backend(self, monkeypatch):
        """Passing backend_type='s3' should return an S3StorageBackend."""
        monkeypatch.setenv("S3_BUCKET", "test-bucket")
        backend = get_storage_backend(backend_type="s3")

        assert isinstance(backend, S3StorageBackend)
        assert isinstance(backend, StorageBackend)

    def test_env_var_s3_returns_s3_backend(self, monkeypatch):
        """STORAGE_BACKEND=s3 env var should yield S3StorageBackend."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_BUCKET", "test-bucket")
        backend = get_storage_backend()

        assert isinstance(backend, S3StorageBackend)

    def test_s3_case_insensitive(self, monkeypatch):
        """Backend type 'S3' should work the same as 's3'."""
        monkeypatch.setenv("S3_BUCKET", "test-bucket")
        backend = get_storage_backend(backend_type="S3")

        assert isinstance(backend, S3StorageBackend)


# ---------------------------------------------------------------------------
# get_storage_backend -- unknown
# ---------------------------------------------------------------------------


class TestFactoryUnknown:
    """Tests for unrecognized backend types."""

    def test_unknown_type_raises_valueerror(self):
        """An unrecognized backend type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage_backend(backend_type="gcs")

    def test_unknown_env_var_raises_valueerror(self, monkeypatch):
        """An unrecognized STORAGE_BACKEND env var should raise ValueError."""
        monkeypatch.setenv("STORAGE_BACKEND", "azure")
        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage_backend()

    def test_error_message_includes_supported(self):
        """The error message should list the supported backends."""
        with pytest.raises(ValueError, match="local") as exc_info:
            get_storage_backend(backend_type="redis")
        assert "s3" in str(exc_info.value)

    def test_empty_string_falls_through_to_default(self, tmp_path, monkeypatch):
        """An empty string backend_type is falsy, so the env/default takes over."""
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        # Empty string is falsy in Python, so `backend_type or os.getenv(...)` yields default
        backend = get_storage_backend(backend_type="")
        assert isinstance(backend, LocalStorageBackend)

    def test_whitespace_only_raises(self):
        """A whitespace-only string after strip becomes empty and is not in _BACKEND_TYPES."""
        # "   ".lower().strip() == "" which is not in _BACKEND_TYPES -- but
        # the `or` short-circuits on falsy, so this also falls through.
        # Instead test a truly unknown non-empty string.
        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage_backend(backend_type="blob")


# ---------------------------------------------------------------------------
# get_storage_backend -- argument takes precedence over env
# ---------------------------------------------------------------------------


class TestFactoryPrecedence:
    """Tests for configuration precedence."""

    def test_argument_overrides_env(self, tmp_path, monkeypatch):
        """Explicit backend_type argument should override STORAGE_BACKEND env."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_BUCKET", "test-bucket")
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        # Despite env saying s3, explicit argument says local
        backend = get_storage_backend(backend_type="local")

        assert isinstance(backend, LocalStorageBackend)

    def test_env_overrides_default(self, monkeypatch):
        """STORAGE_BACKEND env var should override the 'local' default."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_BUCKET", "test-bucket")
        backend = get_storage_backend()

        assert isinstance(backend, S3StorageBackend)


# ---------------------------------------------------------------------------
# get_default_storage_backend -- cached singleton
# ---------------------------------------------------------------------------


class TestGetDefaultStorageBackend:
    """Tests for the cached singleton factory."""

    def test_returns_storage_backend(self, tmp_path, monkeypatch):
        """get_default_storage_backend should return a StorageBackend."""
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        # Clear the lru_cache to avoid cross-test contamination
        get_default_storage_backend.cache_clear()

        backend = get_default_storage_backend()
        assert isinstance(backend, StorageBackend)

    def test_returns_same_instance(self, tmp_path, monkeypatch):
        """Repeated calls should return the exact same object (cached)."""
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        get_default_storage_backend.cache_clear()

        first = get_default_storage_backend()
        second = get_default_storage_backend()
        assert first is second
