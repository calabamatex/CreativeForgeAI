"""Repository for User CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models import User
from src.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


class UserRepository:
    """Async CRUD operations for the users table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        email: str,
        password_hash: str,
        display_name: str,
        role: str = "viewer",
    ) -> User:
        """Create a new user and flush to the database.

        Args:
            email: Unique email address.
            password_hash: Pre-hashed password string.
            display_name: Human-readable display name.
            role: Authorization role (default ``"viewer"``).

        Returns:
            The newly created ``User`` instance.
        """
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        logger.info("user.created", user_id=str(user.id), email=email)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return a user by primary key, or ``None`` if not found."""
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Return a user by email address, or ``None`` if not found."""
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, user_id: uuid.UUID, **kwargs: object) -> User:
        """Update an existing user.

        Args:
            user_id: Primary key of the user to update.
            **kwargs: Column names and their new values.

        Returns:
            The updated ``User`` instance.

        Raises:
            NotFoundError: If the user does not exist.
        """
        user = await self.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        user.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        logger.info("user.updated", user_id=str(user_id), fields=list(kwargs.keys()))
        return user

    async def list_users(
        self, limit: int = 20, offset: int = 0
    ) -> list[User]:
        """Return a paginated list of users ordered by creation date (desc).

        Args:
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.

        Returns:
            A list of ``User`` instances.
        """
        stmt = (
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
