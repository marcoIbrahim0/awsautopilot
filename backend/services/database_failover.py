from __future__ import annotations

import logging
import os
import ssl
import sys
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine, text

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedDatabaseUrls:
    async_url: str
    sync_url: str
    source: str


def to_sync_url(url: str) -> str:
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql", 1)
    if "+psycopg2" in url:
        return url.replace("postgresql+psycopg2", "postgresql", 1)
    return url


def to_async_url(url: str) -> str:
    if "+asyncpg" in url:
        return url
    if "+psycopg2" in url:
        return url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def normalize_async_url(url: str) -> str:
    if "+asyncpg" not in url or ("sslmode=" not in url and "channel_binding=" not in url):
        return url
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    query_params.pop("sslmode", None)
    query_params.pop("channel_binding", None)
    return urlunparse(parsed._replace(query=urlencode(query_params, doseq=True)))


def build_async_connect_args(url: str) -> dict[str, object]:
    lowered = url.lower()
    if "neon" not in lowered and "sslmode=require" not in lowered:
        return {}
    try:
        context = ssl.create_default_context()
    except Exception:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}


def build_sync_connect_args(url: str) -> dict[str, object]:
    return {"sslmode": "require"} if "neon" in url.lower() else {}


def _running_under_pytest() -> bool:
    argv0 = os.path.basename(sys.argv[0]).lower() if sys.argv else ""
    return (
        "pytest" in sys.modules
        or argv0.endswith("pytest")
        or argv0.endswith("py.test")
        or bool(os.getenv("PYTEST_CURRENT_TEST"))
    )


def _should_skip_probe() -> bool:
    return settings.ENV.lower() == "test" or _running_under_pytest()


def _candidate_urls() -> list[ResolvedDatabaseUrls]:
    primary = ResolvedDatabaseUrls(
        async_url=normalize_async_url(settings.DATABASE_URL),
        sync_url=to_sync_url(settings.database_url_sync),
        source="primary",
    )
    fallback_seed = (settings.DATABASE_URL_FALLBACK or "").strip()
    fallback_sync_seed = settings.database_url_sync_fallback
    if not fallback_seed and not fallback_sync_seed:
        return [primary]
    fallback = ResolvedDatabaseUrls(
        async_url=normalize_async_url(to_async_url(fallback_seed or fallback_sync_seed or "")),
        sync_url=to_sync_url(fallback_sync_seed or fallback_seed or ""),
        source="fallback",
    )
    return [primary] if fallback.sync_url == primary.sync_url else [primary, fallback]


def _probe_sync_url(url: str) -> None:
    engine = create_engine(url, pool_pre_ping=True, connect_args=build_sync_connect_args(url))
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def _describe_host(url: str) -> str:
    return urlparse(url).hostname or "<unknown>"


@lru_cache(maxsize=1)
def resolve_database_urls() -> ResolvedDatabaseUrls:
    candidates = _candidate_urls()
    if _should_skip_probe():
        return candidates[0]
    failures: list[str] = []
    for candidate in candidates:
        try:
            _probe_sync_url(candidate.sync_url)
            if candidate.source != "primary":
                logger.warning(
                    "database_failover selected source=%s host=%s after primary probe failure",
                    candidate.source,
                    _describe_host(candidate.sync_url),
                )
            return candidate
        except Exception as exc:
            failures.append(f"{candidate.source}@{_describe_host(candidate.sync_url)}: {exc}")
    details = "; ".join(failures) or "no configured database candidates"
    raise RuntimeError(f"Unable to connect to any configured database candidate. {details}")
