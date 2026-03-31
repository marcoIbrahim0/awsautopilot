"""
Sync SQLAlchemy engine and session for the worker (blocking loop).
Uses backend config database_url_sync (psycopg2). Shared metadata with backend models.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.models.base import Base
from backend.services.database_failover import (
    build_sync_connect_args,
    record_primary_runtime_failure,
    resolve_database_urls,
)

_ENGINE_LOCK = Lock()


def _build_engine(url: str):
    connect_args = build_sync_connect_args(url)
    return create_engine(
        url,
        echo=settings.LOG_LEVEL.upper() == "DEBUG",
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args if connect_args else {},
    )


def _build_session_factory(engine):
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


_resolved_urls = resolve_database_urls()
_sync_url = _resolved_urls.sync_url
_engine = _build_engine(_sync_url)
_session_factory = _build_session_factory(_engine)


def _refresh_engine_if_needed():
    global _resolved_urls, _sync_url, _engine, _session_factory
    resolved = resolve_database_urls()
    if resolved.sync_url == _sync_url:
        return _engine, _session_factory
    with _ENGINE_LOCK:
        resolved = resolve_database_urls()
        if resolved.sync_url == _sync_url:
            return _engine, _session_factory
        _engine = _build_engine(resolved.sync_url)
        _session_factory = _build_session_factory(_engine)
        _resolved_urls = resolved
        _sync_url = resolved.sync_url
    return _engine, _session_factory


class _SessionFactoryProxy:
    def __call__(self, *args, **kwargs):
        _, session_factory = _refresh_engine_if_needed()
        return session_factory(*args, **kwargs)


SessionLocal = _SessionFactoryProxy()


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
    except Exception as exc:
        session.rollback()
        record_primary_runtime_failure(exc)
        raise
    finally:
        session.close()
