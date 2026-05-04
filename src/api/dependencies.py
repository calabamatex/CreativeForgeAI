"""FastAPI dependency injection: DB sessions, JWT auth, role guards, rate limiting."""

from __future__ import annotations

import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from fastapi import Cookie, Depends, Header, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches *hashed*."""
    return pwd_context.verify(plain, hashed)


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

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise AuthenticationError("Token is not an access token")

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

    # Stash on request.state for downstream access (e.g. logging middleware)
    request.state.user = user
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
