"""
Database connection and session management for external data database.
This is completely separate from the main app database.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from external_db.config import get_external_db_settings

# Base class for external models (separate from main app)
Base = declarative_base()

# Lazy-initialized engines and session factories
_external_engine: Optional[AsyncEngine] = None
_local_engine: Optional[AsyncEngine] = None
_external_session_factory: Optional[async_sessionmaker] = None
_local_session_factory: Optional[async_sessionmaker] = None


def _get_external_engine() -> AsyncEngine:
    """Get or create external database engine (lazy initialization)."""
    global _external_engine
    if _external_engine is None:
        settings = get_external_db_settings()
        _external_engine = create_async_engine(
            settings.external_database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _external_engine


def _get_local_engine() -> AsyncEngine:
    """Get or create local database engine (lazy initialization)."""
    global _local_engine
    if _local_engine is None:
        settings = get_external_db_settings()
        _local_engine = create_async_engine(
            settings.local_database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _local_engine


def _get_external_session_factory() -> async_sessionmaker:
    """Get or create external session factory (lazy initialization)."""
    global _external_session_factory
    if _external_session_factory is None:
        _external_session_factory = async_sessionmaker(
            _get_external_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _external_session_factory


def _get_local_session_factory() -> async_sessionmaker:
    """Get or create local session factory (lazy initialization)."""
    global _local_session_factory
    if _local_session_factory is None:
        _local_session_factory = async_sessionmaker(
            _get_local_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _local_session_factory


async def get_external_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting external database sessions (remote source)."""
    factory = _get_external_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_local_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting local database sessions."""
    factory = _get_local_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_external_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for external database sessions."""
    factory = _get_external_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_local_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for local database sessions."""
    factory = _get_local_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_local_db() -> None:
    """Initialize local database tables."""
    engine = _get_local_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_all_connections() -> None:
    """Close all database connections."""
    global _external_engine, _local_engine
    if _external_engine:
        await _external_engine.dispose()
    if _local_engine:
        await _local_engine.dispose()
