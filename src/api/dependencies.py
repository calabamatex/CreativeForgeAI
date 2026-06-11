"""FastAPI dependency injection: DB sessions, JWT auth, role guards, rate limiting."""

from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import bcrypt
from fastapi import Cookie, Depends, Header, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.errors import (
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
)
from src.db.base import async_session_factory

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_secret_key_raw: str | None = os.getenv("SECRET_KEY")
if not _secret_key_raw or len(_secret_key_raw) < 32:
    raise RuntimeError(
        "SECRET_KEY environment variable must be set and at least 32 characters. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )
SECRET_KEY: str = _secret_key_raw
ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
REFRESH_TOKEN_EXPIRE_DAYS: int = 7

# ---------------------------------------------------------------------------
# Password hashing  (bcrypt, cost 12)
# ---------------------------------------------------------------------------
#
# We use the ``bcrypt`` library directly rather than passlib: passlib 1.7.4 is
# the last (effectively unmaintained) release and reads ``bcrypt.__about__``,
# which bcrypt >= 4.1 removed, tripping a backend self-test and raising on every
# hash/verify call.
#
# bcrypt itself only considers the first 72 bytes of the input and raises on
# anything longer. To support passwords of any length *without* silently
# truncating (which would weaken long passwords), we pre-hash the UTF-8 password
# with SHA-256 and base64-encode the digest before handing it to bcrypt. The
# base64 of a 32-byte digest is 44 ASCII bytes -- comfortably under the 72-byte
# limit -- and preserves the full entropy of the original password.
#
# Stored hashes remain standard bcrypt ``$2b$`` strings, verifiable by
# ``bcrypt.checkpw``; since the same pre-hash is applied on both hash and verify
# this scheme is self-consistent.

_BCRYPT_ROUNDS = 12


def _prehash(plain: str) -> bytes:
    """SHA-256 + base64 the password so bcrypt never sees more than 72 bytes.

    Returns a 44-byte ASCII token regardless of input length, sidestepping
    bcrypt's 72-byte limit while preserving the password's full entropy.
    """
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash (cost 12) of *plain*."""
    return bcrypt.hashpw(_prehash(plain), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches *hashed*.

    Returns ``False`` (rather than raising) for malformed/invalid stored hashes.
    """
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: str,
    role: str,
    extra_claims: dict | None = None,
) -> str:
    """Create a short-lived access JWT."""
    now = datetime.now(timezone.utc)
    claims: dict = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh JWT."""
    now = datetime.now(timezone.utc)
    claims: dict = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT, raising *AuthenticationError* on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        # Log the real error server-side but return a generic message to the client
        logger.warning("auth.token_decode_failed", error=str(exc))
        raise AuthenticationError("Invalid or expired token") from exc


def token_remaining_seconds(payload: dict) -> int:
    """Return how many seconds remain until *payload*'s ``exp``.

    Used to size a denylist entry's TTL so it auto-expires exactly when the
    token would have expired anyway (no unbounded denylist growth). Clamped to
    a minimum of 1s; returns a small default if ``exp`` is somehow absent.
    """
    exp = payload.get("exp")
    if exp is None:
        return 60
    now = datetime.now(timezone.utc).timestamp()
    return max(1, int(exp - now))


async def assert_not_revoked(payload: dict) -> None:
    """Reject a token whose ``jti`` is on the revocation denylist.

    Fail-CLOSED policy: if Redis is unreachable we raise ``AuthenticationError``
    rather than letting a possibly-revoked token through. Revocation is a
    security control, so an outage must not silently re-enable logged-out /
    rotated-away tokens. (The alternative — fail-open — would mean a Redis blip
    quietly disables logout for the duration of the outage, which is worse for a
    security primitive than briefly rejecting otherwise-valid tokens.)
    """
    jti = payload.get("jti")
    if not jti:
        # A token with no jti can never be individually revoked; treat as invalid.
        raise AuthenticationError("Token missing jti claim")
    from src.cache import CacheUnavailable, get_cache  # lazy import

    try:
        revoked = await get_cache().is_denylisted(jti)
    except CacheUnavailable as exc:
        logger.error("auth.revocation_check_unavailable", error=str(exc))
        raise AuthenticationError("Token revocation status unavailable") from exc
    if revoked:
        logger.info("auth.token_revoked", jti=jti)
        raise AuthenticationError("Token has been revoked")


# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield one ``AsyncSession`` per request; commit on success, rollback on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# ARQ pool dependency  (job enqueue seam)
# ---------------------------------------------------------------------------


async def get_arq_pool(request: Request):
    """Return the ARQ Redis pool opened by the app lifespan.

    The pool lives on ``app.state.arq_pool`` (set in ``src.api.main`` lifespan).
    This is the DI seam tests override via
    ``app.dependency_overrides[get_arq_pool]`` to inject a recording fake pool.

    Returns ``None`` when no pool is present (e.g. fully-mocked unit tests whose
    ASGI transport never runs the lifespan and never overrides this seam); the
    enqueue call sites guard on a non-``None`` pool so those tests keep working.
    """
    return getattr(request.app.state, "arq_pool", None)


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Extract and validate the JWT, then load the User row.

    Accepts the token from either:
      1. ``Authorization: Bearer <token>`` header, **or**
      2. ``access_token`` httpOnly cookie.
    """
    token: str | None = None

    # Prefer Authorization header
    if authorization:
        scheme, _, param = authorization.partition(" ")
        if scheme.lower() != "bearer" or not param:
            raise AuthenticationError("Authorization header must use Bearer scheme")
        token = param
    elif access_token:
        token = access_token

    if not token:
        raise AuthenticationError("Missing authentication token")

    user = await resolve_access_token_user(token, db)

    # Stash on request.state for downstream access (e.g. logging middleware)
    request.state.user = user
    return user


async def resolve_access_token_user(token: str, db: AsyncSession):
    """Decode an ACCESS token, enforce revocation, and load the active User.

    Shared by ``get_current_user`` (HTTP) and the WebSocket handshake so both
    transports apply the identical decode + denylist + active-user checks.
    Raises ``AuthenticationError`` on any failure.
    """
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise AuthenticationError("Token is not an access token")

    # Reject revoked (logged-out) tokens before doing any DB work.
    await assert_not_revoked(payload)

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token missing subject claim")

    # Lazy import to avoid circular dependency at module level
    from src.db.models import User  # noqa: E402

    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    return user


# ---------------------------------------------------------------------------
# Optional current user (does not fail if unauthenticated)
# ---------------------------------------------------------------------------


async def get_optional_user(
    request: Request,
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Like ``get_current_user`` but returns ``None`` when no token is present."""
    if not authorization and not access_token:
        return None
    try:
        return await get_current_user(request, authorization, access_token, db)
    except AuthenticationError:
        return None


# ---------------------------------------------------------------------------
# Role guard dependency factory
# ---------------------------------------------------------------------------


def require_role(allowed_roles: list[str]):
    """Return a FastAPI dependency that enforces role membership.

    Usage::

        @router.post("/", dependencies=[Depends(require_role(["editor", "admin"]))])
        async def create_campaign(...):
            ...
    """

    async def _guard(user=Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise AuthorizationError(
                f"Role '{user.role}' is not permitted. Required: {allowed_roles}"
            )
        return user

    return _guard


# ---------------------------------------------------------------------------
# In-memory rate limiter (suitable for single-process; swap to Redis for prod)
# ---------------------------------------------------------------------------

_rate_buckets: dict[str, deque[float]] = defaultdict(deque)

RATE_LIMIT_AUTH: int = int(os.getenv("RATE_LIMIT_AUTH", "100"))  # per minute
RATE_LIMIT_UNAUTH: int = int(os.getenv("RATE_LIMIT_UNAUTH", "20"))  # per minute
RATE_WINDOW_SECONDS: int = 60


def _client_key(request: Request) -> str:
    """Derive a rate-limit key from the request (IP + user id if present)."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user.id}"
    return f"ip:{ip}"


async def check_rate_limit(request: Request):
    """Dependency that enforces per-client rate limiting.

    Authenticated users get ``RATE_LIMIT_AUTH`` requests/min;
    anonymous clients get ``RATE_LIMIT_UNAUTH`` requests/min.

    Uses a deque-based sliding window -- O(1) amortised popleft instead
    of rebuilding the entire list each request.
    """
    now = time.monotonic()
    key = _client_key(request)
    is_authed = hasattr(request.state, "user") and request.state.user is not None
    limit = RATE_LIMIT_AUTH if is_authed else RATE_LIMIT_UNAUTH

    bucket = _rate_buckets[key]
    cutoff = now - RATE_WINDOW_SECONDS

    # Prune expired timestamps from the front (oldest first)
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    if len(bucket) >= limit:
        raise RateLimitError(
            f"Rate limit of {limit} requests per minute exceeded"
        )

    bucket.append(now)
