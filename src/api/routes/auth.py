"""Authentication endpoints: register, login, refresh, logout, me."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.dependencies import (
    assert_not_revoked,
    check_rate_limit,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_db,
    hash_password,
    token_remaining_seconds,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from src.cache import CacheUnavailable, get_cache
from src.api.errors import (
    AuthenticationError,
    ConflictError,
)
from src.api.schemas import (
    Envelope,
    LoginRequest,
    Meta,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Auth cookies
# ---------------------------------------------------------------------------
#
# Token model (P5-T3): the browser never reads either token. Both the access
# token AND the refresh token are issued as httpOnly cookies so JavaScript
# (hence XSS) cannot exfiltrate them. The frontend authenticates purely by the
# cookies riding along on same-origin ``fetch(..., {credentials:"include"})``.
#
# CSRF posture: cookies are ``SameSite=Lax``. Lax keeps the cookie OFF
# cross-site sub-resource requests (the classic CSRF vector: a hidden
# ``fetch``/``<img>``/auto-submitted form from an attacker page), so a forged
# background POST from evil.com carries no credentials and is rejected as 401.
# Residual risk: Lax (unlike Strict) DOES send the cookie on a *top-level*
# cross-site navigation that is a GET (e.g. a user clicking a link to our site).
# Our state-changing endpoints are POST/PATCH/DELETE only and are never reached
# by a top-level GET navigation, so the practical CSRF surface here is empty.
# Combined with the credentialed CORS allowlist (no ``*`` origin — see
# ``main.py``), which blocks cross-origin JS from reading any response, this is
# an acceptable CSRF defense for a same-origin SPA. (A double-submit CSRF token
# would be the next hardening step if cross-subdomain hosting were introduced.)

_REFRESH_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
_REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"

# ``Secure`` cookies are only returned by browsers over HTTPS. In production this
# MUST be true; for local HTTP dev/tests it has to be false or the cookie never
# rides back. Defaults to true (secure-by-default); set COOKIE_SECURE=false for
# plain-HTTP local runs.
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    """Set the access + refresh tokens as httpOnly, SameSite=Lax cookies."""
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    # The refresh cookie is scoped to the refresh endpoint only, so it is not
    # sent on every API call (smaller attack surface, less header bloat).
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        path=_REFRESH_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Delete both auth cookies (used on logout)."""
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
    )


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=Envelope[UserResponse],
    status_code=201,
    dependencies=[Depends(check_rate_limit)],
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account."""
    from src.db.models import User  # noqa: E402

    # Check for existing email
    stmt = select(User).where(User.email == body.email)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(detail=f"Email '{body.email}' is already registered")

    now = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=body.role.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()

    logger.info("auth.register", user_id=str(user.id), email=user.email)

    return Envelope[UserResponse](
        data=UserResponse.model_validate(user),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=Envelope[TokenResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email + password, returning JWT tokens.

    The access token is also set as an httpOnly cookie for browser clients.
    """
    from src.db.models import User  # noqa: E402

    stmt = select(User).where(User.email == body.email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    access = create_access_token(str(user.id), user.role)
    refresh = create_refresh_token(str(user.id))

    # Set httpOnly access + refresh cookies for browser usage. The body still
    # echoes the tokens for non-browser API clients (CLI/tests), but a cookie
    # browser never reads them.
    _set_auth_cookies(response, access, refresh)

    logger.info("auth.login", user_id=str(user.id))

    return Envelope[TokenResponse](
        data=TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=Envelope[TokenResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def refresh_token(
    response: Response,
    body: RefreshRequest | None = None,
    refresh_cookie: str | None = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access + refresh pair.

    The refresh token is read from the request body (non-browser API clients)
    when present, else from the ``refresh_token`` httpOnly cookie (browser
    clients, which cannot read the cookie to put it in a body). Body wins when
    both are present: it is the explicit token the API client chose to rotate,
    independent of whatever rotated cookie the jar happens to be carrying.
    """
    from src.db.models import User  # noqa: E402

    presented = (body.refresh_token if body else None) or refresh_cookie
    if not presented:
        raise AuthenticationError("Missing refresh token")

    payload = decode_token(presented)

    if payload.get("type") != "refresh":
        raise AuthenticationError("Token is not a refresh token")

    # Refresh-token ROTATION: the presented refresh token is single-use. If its
    # jti is already on the denylist it has been consumed before — reject and
    # flag, since reuse of a rotated-away refresh token can indicate token
    # theft (the legitimate client and an attacker both holding the same token).
    old_jti = payload.get("jti")
    if not old_jti:
        raise AuthenticationError("Token missing jti claim")
    try:
        if await get_cache().is_denylisted(old_jti):
            logger.warning(
                "auth.refresh_reuse_detected",
                jti=old_jti,
                user_id=payload.get("sub"),
            )
            raise AuthenticationError("Refresh token has already been used")
    except CacheUnavailable as exc:
        # Fail CLOSED: we cannot prove the token has not already been consumed.
        logger.error("auth.refresh_revocation_unavailable", error=str(exc))
        raise AuthenticationError("Token revocation status unavailable") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token missing subject claim")

    stmt = select(User).where(User.id == uuid.UUID(user_id))
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    # Consume the presented refresh token: denylist its jti for its remaining
    # lifetime so it can never be exchanged again (rotation). TTL = remaining
    # life keeps the denylist bounded.
    try:
        await get_cache().denylist_jti(old_jti, token_remaining_seconds(payload))
    except CacheUnavailable as exc:
        logger.error("auth.refresh_rotation_failed", error=str(exc))
        raise AuthenticationError("Token revocation status unavailable") from exc

    access = create_access_token(str(user.id), user.role)
    refresh = create_refresh_token(str(user.id))

    # Rotation: issue a fresh refresh cookie (the old jti was just denylisted).
    _set_auth_cookies(response, access, refresh)

    logger.info("auth.refresh", user_id=str(user.id))

    return Envelope[TokenResponse](
        data=TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
        meta=Meta(),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
):
    """Revoke the current access token and clear the cookie.

    Server-side revocation (jti denylist) means a bearer token presented after
    logout is rejected for its remaining lifetime, instead of staying valid
    until it naturally expires. The denylist TTL equals the token's remaining
    life so the entry self-expires (no unbounded growth).
    """
    _clear_auth_cookies(response)

    # Resolve the presented token (header preferred, else cookie) and revoke it.
    token: str | None = None
    if authorization:
        scheme, _, param = authorization.partition(" ")
        if scheme.lower() == "bearer" and param:
            token = param
    if token is None and access_token:
        token = access_token

    if token:
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            if jti:
                await get_cache().denylist_jti(jti, token_remaining_seconds(payload))
                logger.info("auth.logout", jti=jti, revoked=True)
                return
        except CacheUnavailable as exc:
            # Cookie is cleared; surface the failure so the caller knows the
            # bearer token was NOT server-side revoked (it remains valid until
            # natural expiry). Fail-closed on the revocation guarantee.
            logger.error("auth.logout_revocation_failed", error=str(exc))
            raise AuthenticationError("Logout incomplete: revocation unavailable") from exc
        except AuthenticationError:
            # Already-invalid/expired token: nothing to revoke; cookie cleared.
            logger.info("auth.logout", revoked=False, reason="invalid_token")
            return

    logger.info("auth.logout", revoked=False)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=Envelope[UserResponse])
async def get_me(user=Depends(get_current_user)):
    """Return the currently authenticated user."""
    return Envelope[UserResponse](
        data=UserResponse.model_validate(user),
        meta=Meta(),
    )
