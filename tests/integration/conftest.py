"""Shared fixtures for API integration tests.

Provides a mock async DB session, test HTTP client, JWT auth helpers,
and sample data factories.  No real database connection is made.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure SECRET_KEY is set before importing the dependencies module,
# which validates the env var at import time.
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-that-is-at-least-32-characters-long-for-testing",
)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    get_db,
    get_current_user,
    check_rate_limit,
)

# ---------------------------------------------------------------------------
# Deterministic IDs for test data
# ---------------------------------------------------------------------------

USER_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER_EDITOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
USER_VIEWER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")

CAMPAIGN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
BRAND_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
ASSET_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
JOB_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fake ORM objects  (plain objects with the attributes routes read)
# ---------------------------------------------------------------------------


def _make_user(
    user_id: uuid.UUID = USER_ADMIN_ID,
    email: str = "admin@example.com",
    display_name: str = "Admin User",
    role: str = "admin",
    is_active: bool = True,
) -> MagicMock:
    """Return a mock that quacks like ``src.db.models.User``."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.password_hash = "$2b$12$placeholder_hash_value_for_testing"
    user.display_name = display_name
    user.role = role
    user.is_active = is_active
    user.created_at = NOW
    user.updated_at = NOW
    return user


def _make_campaign(
    campaign_uuid: uuid.UUID = CAMPAIGN_ID,
    campaign_id: str = "SUMMER2026",
    campaign_name: str = "Summer 2026 Launch",
    brand_name: str = "TechStyle",
    status: str = "draft",
    image_backend: str = "firefly",
    brand_guidelines_id: uuid.UUID | None = None,
    brief: dict | None = None,
    target_locales: list | None = None,
    aspect_ratios: list | None = None,
    created_by: uuid.UUID = USER_EDITOR_ID,
) -> MagicMock:
    """Return a mock that quacks like ``src.db.models.Campaign``."""
    c = MagicMock()
    c.id = campaign_uuid
    c.campaign_id = campaign_id
    c.campaign_name = campaign_name
    c.brand_name = brand_name
    c.status = status
    c.image_backend = image_backend
    c.brand_guidelines_id = brand_guidelines_id
    c.brief = brief or {"headline": "Summer Innovation"}
    c.target_locales = target_locales or ["en-US"]
    c.aspect_ratios = aspect_ratios or ["1:1", "16:9"]
    c.created_by = created_by
    c.created_at = NOW
    c.updated_at = NOW
    return c


def _make_asset(
    asset_id: uuid.UUID = ASSET_ID,
    campaign_id: uuid.UUID = CAMPAIGN_ID,
) -> MagicMock:
    """Return a mock that quacks like ``src.db.models.GeneratedAsset``."""
    a = MagicMock()
    a.id = asset_id
    a.campaign_id = campaign_id
    a.product_id = "PROD-001"
    a.locale = "en-US"
    a.aspect_ratio = "1:1"
    a.file_path = "/output/image.png"
    a.storage_key = "campaigns/SUMMER2026/image.png"
    a.file_size_bytes = 102400
    a.width = 1024
    a.height = 1024
    a.generation_method = "firefly"
    a.generation_time_ms = 1500.0
    a.created_at = NOW
    return a


def _make_brand(
    brand_id: uuid.UUID = BRAND_ID,
    name: str = "TechStyle",
    created_by: uuid.UUID = USER_EDITOR_ID,
) -> MagicMock:
    """Return a mock that quacks like ``src.db.models.BrandGuideline``."""
    b = MagicMock()
    b.id = brand_id
    b.name = name
    b.source_file_path = None
    b.primary_colors = ["#0066CC"]
    b.secondary_colors = ["#FFFFFF"]
    b.primary_font = "Montserrat"
    b.secondary_font = "Open Sans"
    b.brand_voice = "Professional"
    b.photography_style = "Clean"
    b.raw_extracted_data = None
    b.created_by = created_by
    b.created_at = NOW
    b.updated_at = NOW
    return b


def _make_job(
    job_id: uuid.UUID = JOB_ID,
    campaign_id: uuid.UUID = CAMPAIGN_ID,
    status: str = "queued",
) -> MagicMock:
    j = MagicMock()
    j.id = job_id
    j.campaign_id = campaign_id
    j.status = status
    j.progress_percent = 0
    j.current_stage = None
    j.result = None
    j.error_message = None
    j.started_at = None
    j.completed_at = None
    j.created_at = NOW
    return j


# ---------------------------------------------------------------------------
# Public fixtures: sample data
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user():
    return _make_user(USER_ADMIN_ID, "admin@example.com", "Admin User", "admin")


@pytest.fixture
def editor_user():
    return _make_user(USER_EDITOR_ID, "editor@example.com", "Editor User", "editor")


@pytest.fixture
def viewer_user():
    return _make_user(USER_VIEWER_ID, "viewer@example.com", "Viewer User", "viewer")


@pytest.fixture
def sample_campaign():
    return _make_campaign()


@pytest.fixture
def sample_asset():
    return _make_asset()


@pytest.fixture
def sample_brand():
    return _make_brand()


@pytest.fixture
def sample_job():
    return _make_job()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def auth_header(user_id: uuid.UUID, role: str) -> dict[str, str]:
    """Return an ``Authorization: Bearer <jwt>`` header dict for the given user."""
    token = create_access_token(str(user_id), role)
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict[str, str]:
    return auth_header(USER_ADMIN_ID, "admin")


def editor_headers() -> dict[str, str]:
    return auth_header(USER_EDITOR_ID, "editor")


def viewer_headers() -> dict[str, str]:
    return auth_header(USER_VIEWER_ID, "viewer")


def make_refresh_token(user_id: uuid.UUID) -> str:
    return create_refresh_token(str(user_id))


# ---------------------------------------------------------------------------
# Mock DB session
# ---------------------------------------------------------------------------


class FakeScalarResult:
    """Wraps a single value to mimic ``result.scalar_one_or_none()`` / ``.scalar_one()``.

    Also supports ``result.all()`` for queries that return full rows (tuples).
    Pass a list to get it back from ``.all()``.  Pass a non-list value for
    the scalar helpers.
    """

    def __init__(self, value: Any = None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        if self._value is None:
            raise Exception("No row found")
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return [self._value] if self._value is not None else []


@pytest.fixture
def mock_db():
    """Return an ``AsyncMock`` that behaves like an ``AsyncSession``.

    Tests should configure ``mock_db.execute.return_value`` with a
    ``FakeScalarResult`` to control what the route sees.
    """
    session = AsyncMock()
    session.execute = AsyncMock(return_value=FakeScalarResult(None))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Test HTTP client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(mock_db) -> AsyncGenerator[AsyncClient, None]:
    """Yield an ``httpx.AsyncClient`` wired to the FastAPI app with
    the DB session and rate-limiter dependencies overridden.
    """
    from src.api.main import create_app

    app = create_app()

    # Override the DB dependency so no real connection is attempted
    async def _override_db():
        yield mock_db

    # Disable rate limiting in tests
    async def _no_rate_limit():
        pass

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[check_rate_limit] = _no_rate_limit

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client(mock_db, admin_user) -> AsyncGenerator[tuple[AsyncClient, MagicMock], None]:
    """Yield ``(client, mock_db)`` with the current-user dependency
    also overridden to return *admin_user* directly (skip JWT + DB lookup).
    """
    from src.api.main import create_app

    app = create_app()

    async def _override_db():
        yield mock_db

    async def _no_rate_limit():
        pass

    async def _override_user():
        return admin_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[check_rate_limit] = _no_rate_limit
    app.dependency_overrides[get_current_user] = _override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, mock_db

    app.dependency_overrides.clear()
