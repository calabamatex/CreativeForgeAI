"""Authentication endpoints: register, login, refresh, logout, me."""

from __future__ import annotations

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

    # Set httpOnly cookie for browser usage
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

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
    body: RefreshRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access + refresh pair."""
    from src.db.models import User  # noqa: E402

    payload = decode_token(body.refresh_token)

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

    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

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
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

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
