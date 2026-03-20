"""
SQLAlchemy asyncio engine and session factory for the Forest application.

The engine is constructed at import time from :func:`forest.config.get_settings`.
Use :func:`session_scope` for request- or job-scoped transactions with commit/rollback.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from forest.config import get_settings

_settings = get_settings()
engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Provide a transactional scope around a series of operations.

    Yields
    ------
    AsyncSession
        Database session bound to the shared async engine.

    Notes
    -----
    On success, commits the transaction. On any exception, rolls back and re-raises.
    Prefer one scope per logical unit of work (e.g. one ingest cue, one slash command).

    Examples
    --------
    Typical usage::

        async with session_scope() as session:
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
