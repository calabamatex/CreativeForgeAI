"""Integration tests for /api/v1/auth/* endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from jose import jwt
from src.api.dependencies import SECRET_KEY

from tests.integration.conftest import (
    ALGORITHM,
    USER_ADMIN_ID,
    USER_EDITOR_ID,
    FakeScalarResult,
    _make_user,
    admin_headers,
    make_refresh_token,
)

# ---------------------------------------------------------------------------
# Helper: patch password hashing so we avoid bcrypt version issues in CI
# ---------------------------------------------------------------------------

_FIXED_HASH = "hashed:ok"


def _mock_hash(plain: str) -> str:
    return f"hashed:{plain}"


def _mock_verify(plain: str, hashed: str) -> bool:
    return hashed == f"hashed:{plain}"


# ===================================================================
# POST /api/v1/auth/register
# ===================================================================


class TestRegister:
    """POST /api/v1/auth/register"""

    @patch("src.api.routes.auth.hash_password", side_effect=_mock_hash)
    async def test_register_success(self, _hp, client, mock_db):
        """Registering with valid data returns 201 and user payload."""
        # No existing user with that email
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(None))

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "Str0ngP@ss!",
                "display_name": "New User",
                "role": "editor",
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert "data" in body
        assert body["data"]["email"] == "new@example.com"
        assert body["data"]["display_name"] == "New User"
        assert body["data"]["role"] == "editor"
        assert body["data"]["is_active"] is True

        # Verify db.add was called (new user row inserted)
        mock_db.add.assert_called_once()

    async def test_register_duplicate_email(self, client, mock_db):
        """Registering with an already-taken email returns 409."""
        existing = _make_user(email="dup@example.com")
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(existing))

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@example.com",
                "password": "Str0ngP@ss!",
                "display_name": "Dup User",
            },
        )

        assert resp.status_code == 409
        # Generic message: must NOT echo the email back (user enumeration).
        assert "dup@example.com" not in resp.json()["detail"]

    async def test_register_invalid_email(self, client, mock_db):
        """An invalid email address triggers 422 validation error."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "Str0ngP@ss!",
                "display_name": "Bad Email",
            },
        )

        assert resp.status_code == 422

    async def test_register_short_password(self, client, mock_db):
        """A password shorter than 8 chars triggers 422."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@example.com",
                "password": "abc",
                "display_name": "Short",
            },
        )

        assert resp.status_code == 422

    async def test_register_missing_display_name(self, client, mock_db):
        """Omitting display_name triggers 422."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "no_name@example.com",
                "password": "Str0ngP@ss!",
            },
        )

        assert resp.status_code == 422


# ===================================================================
# POST /api/v1/auth/login
# ===================================================================


class TestLogin:
    """POST /api/v1/auth/login"""

    @patch("src.api.routes.auth.verify_password", side_effect=_mock_verify)
    async def test_login_success(self, _vp, client, mock_db):
        """Valid credentials return 200 with access and refresh tokens."""
        user = _make_user(email="login@example.com", role="editor")
        user.password_hash = "hashed:Correct1!"

        mock_db.execute = AsyncMock(return_value=FakeScalarResult(user))

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "Correct1!"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify the access token cookie is set
        set_cookie = resp.headers.get("set-cookie", "")
        assert "access_token" in set_cookie

    @patch("src.api.routes.auth.verify_password", side_effect=_mock_verify)
    async def test_login_wrong_password(self, _vp, client, mock_db):
        """Wrong password returns 401."""
        user = _make_user(email="wrong@example.com")
        user.password_hash = "hashed:RealPassword1!"

        mock_db.execute = AsyncMock(return_value=FakeScalarResult(user))

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "WrongPassword!"},
        )

        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    async def test_login_nonexistent_user(self, client, mock_db):
        """Login with an email that does not exist returns 401."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(None))

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "Anything1!"},
        )

        assert resp.status_code == 401

    @patch("src.api.routes.auth.verify_password", side_effect=_mock_verify)
    async def test_login_deactivated_user(self, _vp, client, mock_db):
        """Login for a deactivated account returns 401."""
        user = _make_user(email="deactivated@example.com", is_active=False)
        user.password_hash = "hashed:ValidPass1!"

        mock_db.execute = AsyncMock(return_value=FakeScalarResult(user))

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "deactivated@example.com", "password": "ValidPass1!"},
        )

        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"].lower()


# ===================================================================
# POST /api/v1/auth/refresh
# ===================================================================


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_valid_token(self, client, mock_db):
        """A valid refresh token returns new token pair."""
        user = _make_user(user_id=USER_EDITOR_ID, email="refresh@example.com", role="editor")
        refresh = make_refresh_token(USER_EDITOR_ID)

        mock_db.execute = AsyncMock(return_value=FakeScalarResult(user))

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_expired_token(self, client, mock_db):
        """An expired refresh token returns 401."""
        now = datetime.now(UTC)
        claims = {
            "sub": str(USER_EDITOR_ID),
            "type": "refresh",
            "iat": now - timedelta(days=10),
            "exp": now - timedelta(days=1),
            "jti": str(uuid.uuid4()),
        }
        expired_token = jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_token},
        )

        assert resp.status_code == 401

    async def test_refresh_with_access_token_rejected(self, client, mock_db):
        """Using an access token (type=access) as refresh is rejected."""
        from src.api.dependencies import create_access_token

        access = create_access_token(str(USER_EDITOR_ID), "editor")

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access},
        )

        assert resp.status_code == 401
        assert "refresh" in resp.json()["detail"].lower()

    async def test_refresh_user_not_found(self, client, mock_db):
        """Refresh for a deleted user returns 401."""
        refresh = make_refresh_token(uuid.UUID("99999999-9999-9999-9999-999999999999"))
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(None))

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )

        assert resp.status_code == 401

    async def test_refresh_rotation_invalidates_old_token(self, client, mock_db):
        """Refresh ROTATES: the presented refresh token is consumed (single-use).

        First refresh succeeds and returns a NEW pair. Replaying the OLD refresh
        token is rejected (401) and flagged as reuse; the NEW refresh token still
        works. Exercises the real Redis denylist (the consumed jti is stored).
        """
        from jose import jwt as _jwt
        from src.cache import get_cache

        user = _make_user(user_id=USER_EDITOR_ID, email="rotate@example.com", role="editor")
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(user))

        old_refresh = make_refresh_token(USER_EDITOR_ID)
        old_jti = _jwt.get_unverified_claims(old_refresh)["jti"]

        # 1) First refresh works and rotates.
        first = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert first.status_code == 200
        new_refresh = first.json()["data"]["refresh_token"]
        assert new_refresh != old_refresh

        # 2) A REAL denylist entry exists for the consumed (old) refresh jti.
        assert await get_cache().is_denylisted(old_jti) is True

        # 3) Replaying the OLD refresh token is rejected (reuse detection).
        replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert replay.status_code == 401
        assert "already been used" in replay.json()["detail"].lower()

        # 4) The NEW refresh token still works.
        second = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
        assert second.status_code == 200


# ===================================================================
# GET /api/v1/auth/me
# ===================================================================


class TestMe:
    """GET /api/v1/auth/me"""

    async def test_me_authenticated(self, client, mock_db, admin_user):
        """An authenticated user can retrieve their own profile."""
        mock_db.execute = AsyncMock(return_value=FakeScalarResult(admin_user))

        resp = await client.get(
            "/api/v1/auth/me",
            headers=admin_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == "admin@example.com"
        assert data["role"] == "admin"

    async def test_me_unauthenticated(self, client, mock_db):
        """Missing auth token returns 401."""
        resp = await client.get("/api/v1/auth/me")

        assert resp.status_code == 401

    async def test_me_invalid_token(self, client, mock_db):
        """A malformed JWT returns 401."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer definitely.not.valid"},
        )

        assert resp.status_code == 401


# ===================================================================
# Revocation (jti denylist) — logout invalidates the access token
# ===================================================================


class TestRevocation:
    """A logged-out access token must be rejected for its remaining lifetime."""

    async def test_logout_revokes_access_token(self, client, mock_db, admin_user):
        """After /auth/logout the SAME bearer token is rejected by /auth/me.

        Exercises the real Redis denylist: logout denylists the token's jti and
        the subsequent /auth/me consults the denylist (fail-closed) and 401s.
        """
        from jose import jwt as _jwt
        from src.api.dependencies import create_access_token
        from src.cache import get_cache

        mock_db.execute = AsyncMock(return_value=FakeScalarResult(admin_user))

        token = create_access_token(str(USER_ADMIN_ID), "admin")
        headers = {"Authorization": f"Bearer {token}"}

        # 1) Token works before logout.
        ok = await client.get("/api/v1/auth/me", headers=headers)
        assert ok.status_code == 200

        # 2) Logout revokes it.
        out = await client.post("/api/v1/auth/logout", headers=headers)
        assert out.status_code == 204

        # 3) A REAL denylist entry now exists for this token's jti.
        jti = _jwt.get_unverified_claims(token)["jti"]
        assert await get_cache().is_denylisted(jti) is True

        # 4) The same token is now rejected.
        denied = await client.get("/api/v1/auth/me", headers=headers)
        assert denied.status_code == 401
        assert "revoked" in denied.json()["detail"].lower()
