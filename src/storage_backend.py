"""Abstract storage backend interface for pluggable asset storage."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import List

import structlog

logger = structlog.get_logger(__name__)

# Allowed key pattern: alphanumeric, slashes, hyphens, underscores, dots
_VALID_KEY_RE = re.compile(r"^[a-zA-Z0-9/_\-\.]+$")


def validate_storage_key(key: str) -> None:
    """Validate that a storage key is safe and well-formed.

    Raises:
        ValueError: If the key is empty, contains ``..``, or uses
            characters outside the allowed set.
    """
    if not key:
        raise ValueError("Storage key must not be empty")
    if ".." in key:
        raise ValueError(f"Storage key must not contain '..': {key}")
    if not _VALID_KEY_RE.match(key):
        raise ValueError(
            f"Storage key contains invalid characters: {key}. "
            "Only alphanumeric, '/', '-', '_', and '.' are allowed."
        )


def build_asset_key(
    campaign_id: str,
    product_id: str,
    locale: str | None = None,
    aspect_ratio: str | None = None,
    fmt: str = "png",
    variant: str | None = None,
) -> str:
    """Build a canonical storage key for an asset.

    Key format examples::

        campaigns/{campaign_id}/products/{product_id}/hero/{product_id}_hero.png
        campaigns/{campaign_id}/products/{product_id}/{locale}/{aspect_ratio}/asset.{fmt}

    Args:
        campaign_id: Campaign identifier.
        product_id: Product identifier.
        locale: Optional locale code (e.g. ``en-US``).
        aspect_ratio: Optional aspect ratio string (e.g. ``16:9``).
            Colons are replaced with ``x`` for filesystem safety.
        fmt: File format extension (default ``png``).
        variant: Optional variant name (e.g. ``hero``).

    Returns:
        A normalised storage key string.
    """
    base = f"campaigns/{campaign_id}/products/{product_id}"

    if variant == "hero":
        key = f"{base}/hero/{product_id}_hero.{fmt}"
    elif locale and aspect_ratio:
        safe_ratio = aspect_ratio.replace(":", "x")
        key = f"{base}/{locale}/{safe_ratio}/asset.{fmt}"
    elif locale:
        key = f"{base}/{locale}/asset.{fmt}"
    else:
        key = f"{base}/asset.{fmt}"

    validate_storage_key(key)
    return key


class StorageBackend(ABC):
    """Abstract base class for all storage backends.

    Every concrete backend must implement all five async methods.
    """

    @abstractmethod
    async def save(self, key: str, data: bytes, content_type: str) -> str:
        """Persist binary data under *key*.

        Args:
            key: Logical storage key (e.g.
                ``campaigns/abc/products/xyz/hero/xyz_hero.png``).
            data: Raw bytes to store.
            content_type: MIME type (e.g. ``image/png``).

        Returns:
            The key that was written (may be normalised).

        Raises:
            StorageError: If the write fails.
        """

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve binary data stored under *key*.

        Raises:
            StorageError: If the key does not exist or the read fails.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object stored under *key*.

        Idempotent -- deleting a non-existent key should not raise.

        Raises:
            StorageError: If the delete fails for a reason other
                than the key not existing.
        """

    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a URL suitable for downloading the asset.

        For local storage this returns a ``file://`` URL.
        For S3 this returns a presigned URL.

        Args:
            key: Storage key.
            expires_in: URL lifetime in seconds (only meaningful for
                cloud backends).

        Returns:
            A URL string.

        Raises:
            StorageError: If the URL cannot be generated.
        """

    @abstractmethod
    async def list_keys(self, prefix: str) -> List[str]:
        """List all keys matching *prefix*.

        Args:
            prefix: Key prefix to filter by
                (e.g. ``campaigns/abc/products/``).

        Returns:
            A list of matching keys.

        Raises:
            StorageError: If the listing fails.
        """
