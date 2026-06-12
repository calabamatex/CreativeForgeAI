"""Real-DB / fake-pool / fake-storage integration harness (P3-T0a).

This module provides the building blocks that the conftest fixtures wire
together so the upcoming end-to-end tests (P3-T0/T1/T2) can assert REAL row
inserts, the ``uq_asset_variant`` unique constraint, and enqueue side-effects.

Nothing here touches the dev database: a dedicated ``genai_platform_test``
database is created on the same Compose Postgres server and its schema is built
via ``alembic upgrade head`` (the P0-T4 decision — exercise the real migration
path, not ``Base.metadata.create_all``).

Contents:

* :func:`tiny_png_bytes` -- a minimal valid 1x1 PNG.
* :class:`FakeStorageBackend` -- in-memory :class:`StorageBackend`.
* :class:`FakeArqPool` -- records enqueued jobs and can drive the real task
  coroutine in-process against the real DB session + fakes.
* DB helpers (:func:`build_test_database_url`, :func:`ensure_test_database`,
  :func:`drop_test_database`, :func:`run_alembic_upgrade_on`).
"""

from __future__ import annotations

import os
import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import structlog
from src.storage_backend import StorageBackend, validate_storage_key

logger = structlog.get_logger(__name__)

# Name of the dedicated, throwaway test database. NEVER the dev DB
# (``genai_platform``).
TEST_DB_NAME = "genai_platform_test"


# ---------------------------------------------------------------------------
# Tiny valid PNG
# ---------------------------------------------------------------------------


def tiny_png_bytes(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Return the bytes of a minimal, VALID 1x1 PNG.

    Hand-built (no Pillow needed) so the harness has no heavy dependency just
    to produce a decodable image. Pillow CAN still open the result.
    """

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    # 1x1, 8-bit, RGB (color type 2)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    # One scanline: filter byte 0 + the RGB pixel.
    raw = bytes([0, color[0], color[1], color[2]])
    idat = zlib.compress(raw)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


# ---------------------------------------------------------------------------
# In-memory fake storage backend
# ---------------------------------------------------------------------------


class FakeStorageBackend(StorageBackend):
    """In-memory :class:`StorageBackend` backed by a dict.

    Implements the full abstract interface (``save``/``get``/``delete``/
    ``get_url``/``list_keys``) plus a convenience ``exists`` helper. Stores raw
    bytes keyed by the (validated) storage key. No network, no disk.
    """

    def __init__(self) -> None:
        # key -> (data, content_type)
        self._store: dict[str, tuple[bytes, str]] = {}

    async def save(self, key: str, data: bytes, content_type: str) -> str:
        validate_storage_key(key)
        self._store[key] = (bytes(data), content_type)
        logger.info("fake_storage.save", key=key, size=len(data))
        return key

    async def get(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(f"Key not found in fake storage: {key}")
        return self._store[key][0]

    async def delete(self, key: str) -> None:
        # Idempotent per the ABC contract.
        self._store.pop(key, None)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        return f"memory://{key}"

    async def list_keys(self, prefix: str) -> list[str]:
        return sorted(k for k in self._store if k.startswith(prefix))

    # -- test convenience (not part of the ABC) ---------------------------

    def exists(self, key: str) -> bool:
        return key in self._store

    @property
    def keys(self) -> list[str]:
        return sorted(self._store)

    def __len__(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Controllable, recording fake ARQ pool
# ---------------------------------------------------------------------------


@dataclass
class EnqueuedJob:
    """A single recorded enqueue call."""

    function_name: str
    args: tuple
    kwargs: dict
    job_id: str | None
    # True when an enqueue with the same _job_id was already recorded; ARQ
    # would return None (no new job) in that case. Mirrors that behaviour so
    # tests can assert dedupe.
    deduped: bool = False


class FakeArqPool:
    """A fake ARQ pool that RECORDS enqueues and can DRIVE the real task.

    Mirrors ``arq.ArqRedis.enqueue_job(function, *args, _job_id=..., **kwargs)``:

    * Every call is appended to :attr:`enqueued`.
    * ``_job_id`` dedupe is observable: enqueueing a second job with a
      ``_job_id`` that was already used returns ``None`` and marks the record
      ``deduped=True`` (the original is still the only "live" job). Tests can
      assert "exactly one job enqueued with this job_id, no duplicates".

    Driving:

    * :meth:`drive` runs the REAL registered task coroutine
      ``process_campaign_job(ctx, campaign_id, job_id)`` in-process. The task
      module imports its session factory and pipeline lazily, so ``drive``
      patches ``src.jobs.tasks.async_session_factory`` to hand the task the
      provided real DB session, and patches
      ``src.jobs.tasks.CreativeAutomationPipeline`` with a fake pipeline whose
      ``process_campaign`` is supplied by the caller (default: a no-op stub
      returning a minimal output). The worker ``ctx`` dict carries the real DB
      session, the fake storage backend, and a mocked image backend.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
        storage_backend: StorageBackend | None = None,
        image_backend: Any | None = None,
    ) -> None:
        self.enqueued: list[EnqueuedJob] = []
        self._seen_job_ids: set[str] = set()
        # Resources made available to driven tasks via ctx / patching.
        self.session_factory = session_factory
        self.storage_backend = storage_backend
        self.image_backend = image_backend

    # -- enqueue (recording) ----------------------------------------------

    async def enqueue_job(
        self,
        function_name: str,
        *args: Any,
        _job_id: str | None = None,
        **kwargs: Any,
    ) -> EnqueuedJob | None:
        deduped = _job_id is not None and _job_id in self._seen_job_ids
        record = EnqueuedJob(
            function_name=function_name,
            args=args,
            kwargs=kwargs,
            job_id=_job_id,
            deduped=deduped,
        )
        self.enqueued.append(record)
        if _job_id is not None:
            self._seen_job_ids.add(_job_id)
        if deduped:
            logger.info("fake_pool.enqueue.deduped", function=function_name, job_id=_job_id)
            return None
        logger.info("fake_pool.enqueue", function=function_name, job_id=_job_id)
        return record

    # -- introspection helpers --------------------------------------------

    def jobs_for(self, function_name: str) -> list[EnqueuedJob]:
        return [j for j in self.enqueued if j.function_name == function_name]

    def live_job_ids(self) -> list[str]:
        """Job ids that resulted in an actual (non-deduped) enqueue."""
        return [j.job_id for j in self.enqueued if j.job_id is not None and not j.deduped]

    def count_for_job_id(self, job_id: str) -> int:
        """Total enqueue attempts (incl. deduped) recorded for a job id."""
        return sum(1 for j in self.enqueued if j.job_id == job_id)

    # -- driving the real task --------------------------------------------

    async def drive(
        self,
        campaign_id: str,
        job_id: str,
        *,
        session,
        process_campaign: Callable[..., Any] | None = None,
    ) -> Any:
        """Run the real ``process_campaign_job`` coroutine in-process.

        Args:
            campaign_id: Campaign PK (str of UUID), as the API would enqueue.
            job_id: Job PK (str of UUID).
            session: The real (test) ``AsyncSession`` the task should use. The
                task opens ``async_session_factory()`` as an async context
                manager, so it is patched to yield this session WITHOUT closing
                it (the harness owns the session lifecycle / rollback).
            process_campaign: Optional async callable used as the pipeline's
                ``process_campaign``. Receives the ``CampaignBrief``. Defaults
                to a stub returning a minimal valid ``CampaignOutput``.

        Returns:
            The task's return value (currently ``None``).
        """
        from src.jobs.tasks import process_campaign_job

        ctx = {
            "db_session": session,
            "storage_backend": self.storage_backend,
            "image_backend": self.image_backend,
            "job_id": job_id,
        }

        # The task does ``async with async_session_factory() as session:`` and
        # commits inside. We want it to use OUR session (bound to the rollback
        # connection) and NOT close it on exit.
        factory = _SessionFactoryProxy(session)

        fake_pipeline_cls = _make_fake_pipeline_cls(process_campaign)

        # ``process_campaign_job`` imports these lazily from their source
        # modules, so patch them at the source (not on src.jobs.tasks).
        with (
            patch("src.db.base.async_session_factory", factory),
            patch("src.pipeline.CreativeAutomationPipeline", fake_pipeline_cls),
        ):
            return await process_campaign_job(ctx, campaign_id, job_id)


class _SessionFactoryProxy:
    """Callable that returns an async-context-manager yielding a fixed session.

    Used to make ``async with async_session_factory() as s`` hand back the
    harness-owned session without closing it (so the outer rollback stays in
    control of isolation).
    """

    def __init__(self, session) -> None:
        self._session = session

    def __call__(self):
        return _NoCloseSessionCM(self._session)


class _NoCloseSessionCM:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        # Deliberately do NOT close: the harness owns lifecycle.
        return False


def _make_fake_pipeline_cls(process_campaign: Callable[..., Any] | None):
    """Build a stand-in for ``CreativeAutomationPipeline``.

    The real pipeline reaches out to image backends, Claude, and disk. For the
    harness we replace it with a class whose ``process_campaign`` is the
    supplied coroutine (or a minimal stub) and whose ``close`` is a no-op.
    """

    async def _default_process_campaign(brief, brief_path=None):
        from datetime import datetime

        from src.models import CampaignOutput

        return CampaignOutput(
            campaign_id=brief.campaign_id,
            campaign_name=brief.campaign_name,
            generated_assets=[],
            total_assets=0,
            locales_processed=list(getattr(brief, "target_locales", []) or []),
            products_processed=[p.product_id for p in getattr(brief, "products", [])],
            processing_time_seconds=0.0,
            success_rate=1.0,
            errors=[],
            generation_timestamp=datetime.now(),
            technical_metrics={},
        )

    impl = process_campaign or _default_process_campaign

    class _FakePipeline:
        def __init__(self, image_backend: str | None = None) -> None:
            self.image_backend = image_backend

        async def process_campaign(self, brief, brief_path=None):
            return await impl(brief, brief_path=brief_path)

        async def close(self):
            return None

    return _FakePipeline


def make_image_backend_mock(png: bytes | None = None) -> AsyncMock:
    """Return a mocked image-generation backend.

    ``generate_image(...)`` returns the supplied PNG (default
    :func:`tiny_png_bytes`). No network, no paid calls. ``get_backend_name``
    and ``close`` are stubbed so it can stand in for a real backend.
    """
    png = png if png is not None else tiny_png_bytes()
    backend = AsyncMock()
    backend.generate_image = AsyncMock(return_value=png)
    backend.get_backend_name = lambda: "fake"
    backend.close = AsyncMock(return_value=None)
    return backend


# ---------------------------------------------------------------------------
# Test-database lifecycle (asyncpg + alembic)
# ---------------------------------------------------------------------------


def build_test_database_url(dev_url: str | None = None) -> str:
    """Return the async DATABASE_URL for the dedicated test database.

    Derived from the dev ``DATABASE_URL`` by swapping the database name to
    :data:`TEST_DB_NAME`, so it points at the SAME Compose Postgres server with
    the SAME credentials but a separate database.
    """
    dev_url = dev_url or os.environ["DATABASE_URL"]
    base, _, _dbname = dev_url.rpartition("/")
    # Preserve any query string on the db component (none expected locally).
    return f"{base}/{TEST_DB_NAME}"


def _asyncpg_dsn(async_url: str) -> str:
    """Convert a SQLAlchemy ``postgresql+asyncpg://`` URL to a plain DSN."""
    return async_url.replace("postgresql+asyncpg://", "postgresql://")


async def ensure_test_database(dev_url: str | None = None) -> str:
    """Create the test database if missing; return its async URL.

    Connects to the server's default ``postgres`` maintenance DB with the dev
    credentials and issues ``CREATE DATABASE`` when absent.
    """
    import asyncpg

    dev_url = dev_url or os.environ["DATABASE_URL"]
    test_url = build_test_database_url(dev_url)

    base, _, _ = dev_url.rpartition("/")
    admin_dsn = _asyncpg_dsn(f"{base}/postgres")

    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            # asyncpg can't parametrise an identifier; TEST_DB_NAME is a fixed
            # constant, not user input.
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
            logger.info("test_db.created", name=TEST_DB_NAME)
    finally:
        await conn.close()

    return test_url


async def drop_test_database(dev_url: str | None = None) -> None:
    """Drop the test database (terminating any lingering connections)."""
    import asyncpg

    dev_url = dev_url or os.environ["DATABASE_URL"]
    base, _, _ = dev_url.rpartition("/")
    admin_dsn = _asyncpg_dsn(f"{base}/postgres")

    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            TEST_DB_NAME,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
        logger.info("test_db.dropped", name=TEST_DB_NAME)
    finally:
        await conn.close()


def run_alembic_upgrade_on(test_url: str) -> None:
    """Build the test DB schema via ``alembic upgrade head``.

    Exercises the real migration path (P0-T4 decision). Alembic's ``env.py``
    reads ``DATABASE_URL`` from the environment, so we point it at the test DB
    for the duration of the upgrade.
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    project_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "src" / "db" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", test_url)

    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    try:
        command.upgrade(cfg, "head")
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev
