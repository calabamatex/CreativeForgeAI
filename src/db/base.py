"""SQLAlchemy async engine, session factory, and declarative base."""

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
import structlog

logger = structlog.get_logger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/adobe_genai",
)


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, rolling back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Project root (…/CreativeForgeAI) and the alembic.ini that lives there.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"


def _run_alembic_upgrade() -> None:
    """Run ``alembic upgrade head`` synchronously.

    Migrations are the single source of truth for the schema. We invoke
    Alembic programmatically (rather than relying on ``Base.metadata.create_all``)
    so application startup applies the exact, version-controlled migration
    history. ``env.py`` reads ``DATABASE_URL`` from the environment, so the
    upgrade targets the same database this module is configured against.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    # Make script_location absolute so the upgrade works regardless of CWD.
    cfg.set_main_option(
        "script_location", str(_PROJECT_ROOT / "src" / "db" / "migrations")
    )
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Apply database migrations (``alembic upgrade head``) at startup.

    Note: migrations are the schema source of truth. We deliberately do NOT
    use ``Base.metadata.create_all`` here — see ``_run_alembic_upgrade``.
    Alembic's ``command.upgrade`` is synchronous and drives its own (sync)
    engine via ``env.py``, so we run it in a worker thread to avoid blocking
    the event loop.
    """
    import asyncio

    logger.info("db.init.migrate", url=DATABASE_URL)
    await asyncio.to_thread(_run_alembic_upgrade)
    logger.info("db.init.complete")


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    logger.info("db.close")
    await engine.dispose()
