"""
Async SQLAlchemy 2.0 engine and session. All engine/session creation lives here.
Everywhere else: import get_db (dependency) and Base (for models). No duplicate engines.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.config import settings
from backend.models.base import Base
from backend.services.database_failover import build_async_connect_args, resolve_database_urls

_resolved_urls = resolve_database_urls()
_db_url = _resolved_urls.async_url
_connect_args = build_async_connect_args(_db_url)

async_engine: AsyncEngine = create_async_engine(
    _db_url,
    echo=settings.LOG_LEVEL.upper() == "DEBUG",
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


def build_async_session_factory(*, isolated: bool = False) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = async_engine
    if isolated:
        engine = create_async_engine(
            _db_url,
            echo=settings.LOG_LEVEL.upper() == "DEBUG",
            pool_pre_ping=True,
            connect_args=dict(_connect_args),
            poolclass=NullPool,
        )
    return (
        engine,
        async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        ),
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def ping_db() -> bool:
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
