"""Async Redis caching layer for the Creative Automation Pipeline.

Provides a thin wrapper around ``redis.asyncio`` with:
- Async get / set / delete / invalidate_pattern operations
- Configurable TTL (default 5 minutes)
- JSON serialisation for complex values
- Graceful degradation: all public methods return ``None`` / succeed
  silently when Redis is unavailable so callers never need to handle
  connection errors.

Typical usage::

    from src.cache import get_cache

    cache = get_cache()
    await cache.connect()

    # Store a value (auto-serialises dicts/lists to JSON)
    await cache.set("campaigns:list:page1", campaign_data, ttl=300)

    # Retrieve
    data = await cache.get("campaigns:list:page1")

    # Invalidate by prefix
    await cache.invalidate_pattern("campaigns:*")

    await cache.close()
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

# Default TTL: 5 minutes
DEFAULT_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_KEY_PREFIX: str = os.getenv("CACHE_KEY_PREFIX", "adobegenai:")


class RedisCache:
    """Async Redis cache with JSON serialisation and graceful fallback."""

    def __init__(
        self,
        url: str = REDIS_URL,
        default_ttl: int = DEFAULT_TTL_SECONDS,
        key_prefix: str = CACHE_KEY_PREFIX,
    ) -> None:
        self._url = url
        self._default_ttl = default_ttl
        self._prefix = key_prefix
        self._redis: Any = None  # redis.asyncio.Redis instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open a connection pool to Redis."""
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]

            self._redis = aioredis.from_url(
                self._url,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Verify connectivity
            await self._redis.ping()
            logger.info("cache.connected", url=self._url)
        except Exception as exc:
            logger.warning("cache.connect_failed", error=str(exc))
            self._redis = None

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None
            logger.info("cache.closed")

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the Redis client is available."""
        return self._redis is not None

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _key(self, key: str) -> str:
        """Return the prefixed cache key."""
        return f"{self._prefix}{key}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value by *key*.

        Returns the deserialised Python object, or ``None`` on miss /
        connection error.
        """
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(self._key(key))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.debug("cache.get_error", key=key, error=str(exc))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Store *value* under *key* with an optional TTL (seconds).

        Returns ``True`` on success, ``False`` on failure.
        """
        if self._redis is None:
            return False
        try:
            serialised = json.dumps(value, default=str)
            await self._redis.set(
                self._key(key),
                serialised,
                ex=ttl or self._default_ttl,
            )
            return True
        except Exception as exc:
            logger.debug("cache.set_error", key=key, error=str(exc))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a single cache entry.

        Returns ``True`` if the key existed and was deleted.
        """
        if self._redis is None:
            return False
        try:
            result = await self._redis.delete(self._key(key))
            return result > 0
        except Exception as exc:
            logger.debug("cache.delete_error", key=key, error=str(exc))
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching *pattern* (e.g. ``"campaigns:*"``).

        Uses ``SCAN`` internally to avoid blocking Redis with ``KEYS``.
        Returns the number of deleted keys.
        """
        if self._redis is None:
            return 0
        try:
            full_pattern = self._key(pattern)
            deleted = 0
            async for key in self._redis.scan_iter(match=full_pattern, count=100):
                await self._redis.delete(key)
                deleted += 1
            if deleted:
                logger.info(
                    "cache.invalidated",
                    pattern=pattern,
                    deleted=deleted,
                )
            return deleted
        except Exception as exc:
            logger.debug("cache.invalidate_error", pattern=pattern, error=str(exc))
            return 0

    async def exists(self, key: str) -> bool:
        """Check whether *key* exists in the cache."""
        if self._redis is None:
            return False
        try:
            return bool(await self._redis.exists(self._key(key)))
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Return the module-level ``RedisCache`` singleton.

    Call ``await get_cache().connect()`` during application startup.
    """
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache
