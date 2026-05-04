"""Local filesystem storage backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import aiofiles
import structlog

from src.exceptions import StorageError
from src.storage_backend import StorageBackend, validate_storage_key

logger = structlog.get_logger(__name__)


class LocalStorageBackend(StorageBackend):
    """Store assets on the local filesystem.

    Files are written under *base_dir* using the storage key as a
    relative path.  In development ``get_url`` returns ``file://`` URLs.

    Args:
        base_dir: Root directory for all stored files.
            Defaults to ``./output``.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            base_dir = os.getenv("OUTPUT_DIR", "./output")
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "storage.local.init",
            base_dir=str(self._base_dir),
        )

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def _resolve_path(self, key: str) -> Path:
        """Turn a storage key into an absolute filesystem path."""
        validate_storage_key(key)
        resolved = (self._base_dir / key).resolve()
        # Guard against path traversal
        if not str(resolved).startswith(str(self._base_dir)):
            raise StorageError(
                f"Resolved path escapes base directory: {key}"
            )
        return resolved

    # ----- StorageBackend interface -----------------------------------------

    async def save(self, key: str, data: bytes, content_type: str) -> str:
        """Write *data* to the local filesystem under *key*."""
        path = self._resolve_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, "wb") as fh:
                await fh.write(data)
            logger.info(
                "storage.local.saved",
                key=key,
                size=len(data),
                content_type=content_type,
                path=str(path),
            )
            return key
        except OSError as exc:
            raise StorageError(
                f"Failed to save key '{key}': {exc}"
            ) from exc

    async def get(self, key: str) -> bytes:
        """Read the file identified by *key*."""
        path = self._resolve_path(key)
        if not path.is_file():
            raise StorageError(f"Key not found: {key}")
        try:
            async with aiofiles.open(path, "rb") as fh:
                data = await fh.read()
            logger.debug("storage.local.get", key=key, size=len(data))
            return data
        except OSError as exc:
            raise StorageError(
                f"Failed to read key '{key}': {exc}"
            ) from exc

    async def delete(self, key: str) -> None:
        """Delete the file for *key*.  No error if already absent."""
        path = self._resolve_path(key)
        try:
            if path.is_file():
                path.unlink()
                logger.info("storage.local.deleted", key=key)
            else:
                logger.debug("storage.local.delete_noop", key=key)
        except OSError as exc:
            raise StorageError(
                f"Failed to delete key '{key}': {exc}"
            ) from exc

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a ``file://`` URL pointing at the asset.

        *expires_in* is ignored for local storage.
        """
        path = self._resolve_path(key)
        if not path.is_file():
            raise StorageError(f"Key not found: {key}")
        url = path.as_uri()
        logger.debug("storage.local.get_url", key=key, url=url)
        return url

    async def list_keys(self, prefix: str) -> List[str]:
        """Walk the local directory tree and return matching keys."""
        validate_storage_key(prefix.rstrip("/") or "campaigns")
        search_dir = self._resolve_path(prefix) if prefix else self._base_dir
        if not search_dir.is_dir():
            return []
        keys: List[str] = []
        for root, _dirs, files in os.walk(search_dir):
            for name in files:
                full = Path(root) / name
                relative = full.relative_to(self._base_dir)
                key = str(relative).replace(os.sep, "/")
                keys.append(key)
        keys.sort()
        logger.debug(
            "storage.local.list_keys",
            prefix=prefix,
            count=len(keys),
        )
        return keys
