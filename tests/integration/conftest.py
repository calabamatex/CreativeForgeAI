"""Shared fixtures for API integration tests.

Provides a mock async DB session, test HTTP client, JWT auth helpers,
and sample data factories.  No real database connection is made.

P3-T0 schema-build decision: the future end-to-end integration test (P3-T0)
MUST build its schema via ``alembic upgrade head`` against a real (ephemeral)
Postgres, NOT via ``Base.metadata.create_all``. Running the real migration
path is what exercises the production schema-provisioning code and catches
migration drift. ``create_all`` is only acceptable in narrowly isolated,
per-test fixtures and must never become the schema source of truth.
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
# Real Redis for the JWT revocation denylist  (P4-T1)
# ---------------------------------------------------------------------------
#
# The revocation check (``assert_not_revoked``) fails CLOSED when Redis is
# unreachable, so the integration suite must connect the module-level cache
# singleton to the Compose Redis once per session. Without this every protected
# endpoint would 401 ("revocation status unavailable"). This genuinely exercises
# the real denylist (no no-op cache); the revoke/rotation tests assert real
# denylist entries against this same connection.


@pytest_asyncio.fixture(autouse=True)
async def _connect_revocation_cache():
    """Connect the cache singleton to real Redis for the CURRENT test's loop.

    pytest-asyncio runs each test on a fresh function-scoped event loop, and the
    redis.asyncio client binds to the loop it was created on. So we (re)connect
    per test — creating a client on this test's loop — and close it at teardown,
    avoiding "Event loop is closed" errors from a stale cross-test connection.
    """
    from src.cache import get_cache

    cache = get_cache()
    await cache.connect()
    yield
    await cache.close()


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


# ===========================================================================
# REAL integration harness (P3-T0a)
# ===========================================================================
#
# Everything ABOVE this banner is the pre-existing, fully-mocked path that the
# 8 ``test_api_*.py`` files rely on. It is left untouched. The fixtures below
# are NEW (new names) and opt-in: they stand up a real Postgres test database,
# a recording/controllable fake ARQ pool, and an in-memory storage backend so
# the end-to-end tests can assert real inserts, the ``uq_asset_variant``
# constraint, and enqueue side-effects.
#
# Schema is built with ``alembic upgrade head`` against a DEDICATED database
# (``genai_platform_test``) on the Compose Postgres server — never the dev DB.
# ---------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)

from tests.integration.harness import (  # noqa: E402
    FakeArqPool,
    FakeStorageBackend,
    ensure_test_database,
    drop_test_database,
    make_image_backend_mock,
    run_alembic_upgrade_on,
    tiny_png_bytes as _tiny_png_bytes,
)


@pytest.fixture(scope="session")
def _test_db_url() -> str:
    """Session-scoped: ensure the dedicated TEST database exists + is migrated.

    Creates ``genai_platform_test`` if missing (on the Compose Postgres server,
    with the dev creds — only the db *name* is swapped) and builds its schema
    via ``alembic upgrade head``. Drops it again at the end of the test session
    so the dev DB is never polluted and the test DB is re-creatable. Returns the
    async DATABASE_URL for the test DB.

    Synchronous fixture (uses ``asyncio.run`` for the asyncpg admin work) so it
    is independent of any per-test event loop.
    """
    if "DATABASE_URL" not in os.environ:
        pytest.skip("DATABASE_URL not set; real-DB harness unavailable")

    import asyncio

    test_url = asyncio.run(ensure_test_database())
    run_alembic_upgrade_on(test_url)
    try:
        yield test_url
    finally:
        asyncio.run(drop_test_database())


@pytest_asyncio.fixture
async def real_db_engine(_test_db_url):
    """Function-scoped async engine bound to the TEST database.

    Created per test so it lives on the test's own event loop (pytest-asyncio
    uses a function-scoped loop in auto mode); disposed at teardown. The DB
    itself is created/migrated/dropped once per session by ``_test_db_url``.
    """
    engine = create_async_engine(_test_db_url, echo=False, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def real_db_session(real_db_engine):
    """Function-scoped real ``AsyncSession`` with PER-TEST ISOLATION.

    Isolation mechanism: a single connection is opened and an OUTER
    transaction begun; the session is bound to that connection and runs inside
    a SAVEPOINT (nested transaction). Every ``session.commit()`` the app code
    issues commits only to the savepoint — a new savepoint is started
    automatically after each commit via the ``after_transaction_end`` event —
    so writes are visible within the test but never reach the database. At
    teardown the OUTER transaction is rolled back, discarding everything. A row
    inserted in one test is therefore invisible in the next.
    """
    connection = await real_db_engine.connect()
    trans = await connection.begin()

    session_maker = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = session_maker()

    # ``join_transaction_mode="create_savepoint"`` makes the session run inside
    # a SAVEPOINT on the externally-managed connection transaction and restart
    # a fresh savepoint after each ``commit()``/``rollback()`` automatically, so
    # the app's commits never escape the outer transaction.
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def real_app_client(real_db_session):
    """Yield ``(client, real_db_session)`` wired to the REAL test DB.

    Overrides ``get_db`` to yield the isolated ``real_db_session`` so API
    routes execute against real Postgres. Rate limiting is disabled; auth is
    NOT overridden (use the ``auth_header``/``admin_headers`` helpers, or layer
    your own ``get_current_user`` override per-test).
    """
    from src.api.main import create_app

    app = create_app()

    async def _override_db():
        yield real_db_session

    async def _no_rate_limit():
        pass

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[check_rate_limit] = _no_rate_limit

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, real_db_session

    app.dependency_overrides.clear()


@pytest.fixture
def fake_storage_backend() -> FakeStorageBackend:
    """In-memory storage backend implementing ``StorageBackend``."""
    return FakeStorageBackend()


@pytest.fixture
def tiny_png() -> bytes:
    """A minimal valid 1x1 PNG (bytes)."""
    return _tiny_png_bytes()


@pytest.fixture
def image_backend_mock():
    """Mocked image-generation backend; ``generate_image`` returns a tiny PNG."""
    return make_image_backend_mock()


@pytest.fixture
def fake_arq_pool(real_db_session, fake_storage_backend, image_backend_mock):
    """Recording, controllable fake ARQ pool wired to the real harness.

    ``enqueue_job`` records calls (dedupe by ``_job_id`` observable). ``drive``
    runs the real ``process_campaign_job`` in-process against the real DB
    session, the fake storage backend, and the mocked image backend.
    """
    return FakeArqPool(
        session_factory=lambda: real_db_session,
        storage_backend=fake_storage_backend,
        image_backend=image_backend_mock,
    )


@pytest.fixture
def patch_storage_factory(fake_storage_backend):
    """Patch the storage factory so any code resolving the default backend
    (``get_default_storage_backend`` / ``get_storage_backend``) gets the
    in-memory fake. Yields the fake so the test can inspect what was written.
    """
    from unittest.mock import patch as _patch

    import src.storage_factory as sf

    sf.get_default_storage_backend.cache_clear()
    with _patch.object(
        sf, "get_storage_backend", return_value=fake_storage_backend
    ), _patch.object(
        sf, "get_default_storage_backend", return_value=fake_storage_backend
    ):
        yield fake_storage_backend
    sf.get_default_storage_backend.cache_clear()
