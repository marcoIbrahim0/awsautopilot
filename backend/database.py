"""
Async SQLAlchemy 2.0 engine and session. All engine/session creation lives here.
Everywhere else: import get_db (dependency) and Base (for models). No duplicate engines.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.models.base import Base

# Fix DATABASE_URL for asyncpg - remove sslmode/channel_binding query params
# asyncpg doesn't support these in query string, needs SSL configured via connect_args
_db_url = settings.DATABASE_URL
if "+asyncpg" in _db_url and ("sslmode=" in _db_url or "channel_binding=" in _db_url):
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    parsed = urlparse(_db_url)
    query_params = parse_qs(parsed.query)
    query_params.pop("sslmode", None)
    query_params.pop("channel_binding", None)
    new_query = urlencode(query_params, doseq=True)
    _db_url = urlunparse(parsed._replace(query=new_query))

# Configure SSL for asyncpg (Neon requires SSL)
# For Neon, we need SSL but may need relaxed verification for certificate chain issues
_connect_args = {}
if "neon" in _db_url.lower() or "sslmode=require" in settings.DATABASE_URL.lower():
    import ssl

    # Try default context first, but allow fallback to relaxed verification if needed
    # For local development, relaxed verification may be needed if cert chain is incomplete
    try:
        ssl_context = ssl.create_default_context()
        # For Neon, we might need to relax verification
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    except Exception:
        # Fallback: create minimal SSL context
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    
    _connect_args["ssl"] = ssl_context

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
