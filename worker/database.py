"""
Sync SQLAlchemy engine and session for the worker (blocking loop).
Uses backend config database_url_sync (psycopg2). Shared metadata with backend models.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.models.base import Base

_sync_url = settings.database_url_sync
_connect_args: dict = {}
if "neon" in _sync_url.lower():
    # psycopg2 only accepts DSN-style options in connect(); sslcontext is not valid.
    # Use sslmode=require so Neon gets SSL without putting sslcontext in the DSN.
    _connect_args["sslmode"] = "require"

_engine = create_engine(
    _sync_url,
    echo=settings.LOG_LEVEL.upper() == "DEBUG",
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=_connect_args if _connect_args else {},
)
SessionLocal = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Session:
    """Return a new sync session. Caller must close or use as context manager."""
    return SessionLocal()


@contextmanager
def session_scope():
    """Context manager that yields a session and commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
