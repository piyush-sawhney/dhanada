"""Async database session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def get_async_engine(database_url: str, **kwargs: Any) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        database_url: PostgreSQL connection URL (asyncpg).
        **kwargs: Additional engine options.

    Returns:
        Configured AsyncEngine instance.
    """
    return create_async_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
        **kwargs,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: AsyncEngine instance.

    Returns:
        async_sessionmaker bound to the engine.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


class DatabaseSession:
    """Manages async database sessions with context manager support."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_async_engine(database_url)
        self._session_factory = create_session_factory(self._engine)

    async def close(self) -> None:
        """Dispose of the engine and all connections."""
        await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session.

        Yields:
            AsyncSession with automatic rollback on error.
        """
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()