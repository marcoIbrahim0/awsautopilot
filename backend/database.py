"""
Async SQLAlchemy 2.0 engine and session. All engine/session creation lives here.
Everywhere else: import get_db (dependency) and Base (for models). No duplicate engines.
"""
from __future__ import annotations

from threading import Lock
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.config import settings
from backend.models.base import Base
from backend.services.database_failover import (
    build_async_connect_args,
    record_primary_runtime_failure,
    resolve_database_urls,
)

_ENGINE_LOCK = Lock()


def _build_engine(url: str, *, isolated: bool = False) -> AsyncEngine:
    kwargs = {
        "echo": settings.LOG_LEVEL.upper() == "DEBUG",
        "pool_pre_ping": True,
        "connect_args": build_async_connect_args(url),
    }
    if isolated:
        kwargs["poolclass"] = NullPool
    return create_async_engine(url, **kwargs)


def _build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


_resolved_urls = resolve_database_urls()
_db_url = _resolved_urls.async_url
async_engine: AsyncEngine = _build_engine(_db_url)
_session_factory = _build_session_factory(async_engine)


def _refresh_engine_if_needed() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global _db_url, _resolved_urls, async_engine, _session_factory
    resolved = resolve_database_urls()
    if resolved.async_url == _db_url:
        return async_engine, _session_factory
    with _ENGINE_LOCK:
        resolved = resolve_database_urls()
        if resolved.async_url == _db_url:
            return async_engine, _session_factory
        async_engine = _build_engine(resolved.async_url)
        _session_factory = _build_session_factory(async_engine)
        _resolved_urls = resolved
        _db_url = resolved.async_url
    return async_engine, _session_factory


class _AsyncSessionFactoryProxy:
    def __call__(self, *args, **kwargs):
        _, session_factory = _refresh_engine_if_needed()
        return session_factory(*args, **kwargs)


AsyncSessionLocal = _AsyncSessionFactoryProxy()


def build_async_session_factory(*, isolated: bool = False) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine, session_factory = _refresh_engine_if_needed()
    if not isolated:
        return engine, session_factory
    isolated_engine = _build_engine(_db_url, isolated=True)
    return isolated_engine, _build_session_factory(isolated_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception as exc:
        record_primary_runtime_failure(exc)
        raise
    finally:
        await session.close()


async def ping_db() -> bool:
    try:
        engine, _ = _refresh_engine_if_needed()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        record_primary_runtime_failure(exc)
        return False
