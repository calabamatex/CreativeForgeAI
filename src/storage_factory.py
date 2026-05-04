"""Factory for creating the configured storage backend."""

from __future__ import annotations

import os
from functools import lru_cache

import structlog

from src.storage_backend import StorageBackend

logger = structlog.get_logger(__name__)

_BACKEND_TYPES = {"local", "s3"}


def get_storage_backend(backend_type: str | None = None) -> StorageBackend:
    """Return a :class:`StorageBackend` instance for the requested type.

    The backend type is determined by (in priority order):

    1. The *backend_type* argument.
    2. The ``STORAGE_BACKEND`` environment variable.
    3. Defaults to ``"local"``.

    Args:
        backend_type: ``"local"`` or ``"s3"``.

    Returns:
        A configured :class:`StorageBackend` instance.

    Raises:
        ValueError: If the backend type is not recognised.
    """
    chosen = (backend_type or os.getenv("STORAGE_BACKEND", "local")).lower().strip()

    if chosen not in _BACKEND_TYPES:
        raise ValueError(
            f"Unknown storage backend '{chosen}'. "
            f"Supported: {', '.join(sorted(_BACKEND_TYPES))}"
        )

    logger.info("storage.factory", backend=chosen)

    if chosen == "s3":
        from src.storage_s3 import S3StorageBackend

        return S3StorageBackend()

    # Default: local
    from src.storage_local import LocalStorageBackend

    return LocalStorageBackend()


@lru_cache(maxsize=1)
def get_default_storage_backend() -> StorageBackend:
    """Return a cached singleton of the default storage backend.

    Useful as a FastAPI dependency so only one instance is created.
    """
    return get_storage_backend()
