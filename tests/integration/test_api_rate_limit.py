"""Integration tests for the Redis-backed rate limiter and safe XFF handling (P4-T2).

These tests exercise the REAL Compose Redis (the ``_connect_revocation_cache``
autouse fixture in conftest connects the cache singleton). They assert that:

* the configured per-minute limit is ENFORCED (exceeding it -> 429 RFC 7807 body
  with a ``Retry-After`` header),
* counters actually live in Redis (the ``ratelimit:*`` keys are written),
* two independent app instances sharing one Redis share the same limit
  (i.e. the limiter is process-shared, not per-process),
* a spoofed ``X-Forwarded-For`` is IGNORED when proxies are not trusted (limit
  keys on the socket peer), and HONOURED when the source is a trusted proxy.

A tiny test-only route is mounted so the limiter is tested in isolation from any
real endpoint's auth/DB logic; ``get_db`` is overridden to a no-op.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from src.api.dependencies import check_rate_limit, get_db
from src.api.errors import AppError, app_error_handler, generic_exception_handler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_limited_app(limit_unauth: int = 5, limit_auth: int = 5) -> FastAPI:
    """Build a minimal app with one rate-limited route and the error handlers.

    The rate-limit constants are patched on the dependencies module so a tiny
    limit makes the tests fast and deterministic. We re-import to read fresh
    env-free constants is unnecessary; we set the module attributes directly.
    """
    import src.api.dependencies as deps

    deps.RATE_LIMIT_UNAUTH = limit_unauth
    deps.RATE_LIMIT_AUTH = limit_auth

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    @app.get("/ping", dependencies=[Depends(check_rate_limit)])
    async def _ping(request: Request):  # noqa: ANN202
        # request_id is normally set by middleware; provide a default for the
        # RFC 7807 builder.
        return {"ok": True}

    async def _override_db():
        yield None

    app.dependency_overrides[get_db] = _override_db
    return app


async def _flush_rate_keys() -> None:
    """Delete all ``ratelimit:*`` keys so each test starts clean."""
    from src.cache import get_cache

    cache = get_cache()
    redis = cache._redis  # the connected client (per-test, from conftest)
    assert redis is not None, "Redis must be connected for rate-limit tests"
    pattern = cache._key(f"{cache._RATE_PREFIX}*")
    async for key in redis.scan_iter(match=pattern, count=200):
        await redis.delete(key)


async def _count_rate_keys() -> int:
    from src.cache import get_cache

    cache = get_cache()
    redis = cache._redis
    pattern = cache._key(f"{cache._RATE_PREFIX}*")
    n = 0
    async for _ in redis.scan_iter(match=pattern, count=200):
        n += 1
    return n


@pytest_asyncio.fixture(autouse=True)
async def _clean_rate_keys():
    """Flush rate-limit keys before and after each test for isolation."""
    await _flush_rate_keys()
    yield
    await _flush_rate_keys()


# ---------------------------------------------------------------------------
# Enforcement + Redis-backing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limit_enforced_and_429_problem_json():
    """Exceeding the unauth limit returns a 429 RFC 7807 body + Retry-After."""
    app = _build_limited_app(limit_unauth=3)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First 3 succeed.
        for _ in range(3):
            r = await ac.get("/ping")
            assert r.status_code == 200, r.text
        # 4th is rate-limited.
        r = await ac.get("/ping")
        assert r.status_code == 429
        body = r.json()
        assert body["status"] == 429
        assert body["type"] == "urn:adobe-genai:error:rate_limit_exceeded"
        assert body["title"] == "Rate Limit Exceeded"
        assert "retry_after" in body
        assert r.headers.get("Retry-After") is not None
        assert int(r.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_counters_live_in_redis():
    """Hitting the limited route writes ratelimit:* keys into Redis."""
    app = _build_limited_app(limit_unauth=10)
    transport = ASGITransport(app=app)
    assert await _count_rate_keys() == 0
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/ping")
        assert r.status_code == 200
    assert await _count_rate_keys() >= 1


@pytest.mark.asyncio
async def test_limit_shared_across_two_app_instances():
    """Two separate app instances (simulating two workers) share one Redis
    counter, so the combined request count is limited globally."""
    limit = 4
    app_a = _build_limited_app(limit_unauth=limit)
    app_b = _build_limited_app(limit_unauth=limit)
    transport_a = ASGITransport(app=app_a)
    transport_b = ASGITransport(app=app_b)

    async with (
        AsyncClient(transport=transport_a, base_url="http://test") as ca,
        AsyncClient(transport=transport_b, base_url="http://test") as cb,
    ):
        # Alternate between the two instances; total allowed across BOTH is
        # `limit`, proving the counter is shared (not per-process).
        statuses = []
        for i in range(limit + 2):
            client = ca if i % 2 == 0 else cb
            r = await client.get("/ping")
            statuses.append(r.status_code)

    ok = sum(1 for s in statuses if s == 200)
    limited = sum(1 for s in statuses if s == 429)
    assert ok == limit, f"expected {limit} allowed, got statuses={statuses}"
    assert limited == 2, f"expected 2 limited, got statuses={statuses}"


# ---------------------------------------------------------------------------
# Safe X-Forwarded-For handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spoofed_xff_ignored_when_proxies_not_trusted():
    """With TRUST_FORWARDED_FOR off (default), a rotating spoofed XFF does NOT
    create fresh buckets — the limit keys on the socket peer, so the spoofer is
    still limited after `limit` requests."""
    from src.config import reload_config

    # Default config: TRUST_FORWARDED_FOR off.
    reload_config()
    app = _build_limited_app(limit_unauth=3)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        statuses = []
        for i in range(5):
            # Each request claims a different forged client IP.
            r = await ac.get("/ping", headers={"X-Forwarded-For": f"9.9.9.{i}"})
            statuses.append(r.status_code)
    # Despite rotating XFF, only 3 succeed (all keyed on the same socket peer).
    assert statuses.count(200) == 3, statuses
    assert statuses.count(429) == 2, statuses


@pytest.mark.asyncio
async def test_xff_honoured_when_source_is_trusted_proxy(monkeypatch):
    """When TRUST_FORWARDED_FOR is on AND the socket peer is a trusted proxy,
    the right-most untrusted XFF hop is used as the client IP, so two distinct
    forwarded clients get independent buckets."""
    # ASGITransport reports the socket peer as 127.0.0.1; trust it as the proxy.
    monkeypatch.setenv("TRUST_FORWARDED_FOR", "true")
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")
    from src.config import reload_config

    reload_config()
    try:
        app = _build_limited_app(limit_unauth=2)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Client A (1.1.1.1) makes 2 requests -> both OK, 3rd limited.
            a1 = await ac.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
            a2 = await ac.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
            a3 = await ac.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
            # Client B (2.2.2.2) is a DIFFERENT bucket -> still allowed.
            b1 = await ac.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"})
        assert (a1.status_code, a2.status_code) == (200, 200)
        assert a3.status_code == 429
        assert b1.status_code == 200, "distinct forwarded client should have its own bucket"
    finally:
        # Restore default config for other tests.
        monkeypatch.delenv("TRUST_FORWARDED_FOR", raising=False)
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        reload_config()


@pytest.mark.asyncio
async def test_right_most_untrusted_hop_selected(monkeypatch):
    """A spoofer prepending a fake IP to the LEFT of the chain cannot change the
    bucket: the limiter selects the right-most NON-trusted-proxy hop."""
    monkeypatch.setenv("TRUST_FORWARDED_FOR", "true")
    # Trust the socket peer (127.0.0.1) and an intermediate proxy 10.0.0.1.
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,10.0.0.1")
    from src.config import reload_config

    reload_config()
    try:
        app = _build_limited_app(limit_unauth=2)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Chain: <spoofed>, <real client 3.3.3.3>, <trusted proxy 10.0.0.1>
            # right-most untrusted hop = 3.3.3.3 regardless of the spoofed left.
            hdr1 = {"X-Forwarded-For": "6.6.6.6, 3.3.3.3, 10.0.0.1"}
            hdr2 = {"X-Forwarded-For": "7.7.7.7, 3.3.3.3, 10.0.0.1"}
            r1 = await ac.get("/ping", headers=hdr1)
            r2 = await ac.get("/ping", headers=hdr2)
            r3 = await ac.get("/ping", headers=hdr1)  # same real client -> limited
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429, "varying the spoofed left hop must not reset the bucket"
    finally:
        monkeypatch.delenv("TRUST_FORWARDED_FOR", raising=False)
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        reload_config()
