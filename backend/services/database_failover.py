from __future__ import annotations

import logging
import os
import shutil
import ssl
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from threading import Lock
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine, text

from backend.config import settings

logger = logging.getLogger(__name__)

_FAILOVER_LOCK = Lock()
_CACHED_RESOLUTION: ResolvedDatabaseUrls | None = None
_PRIMARY_SUSPENDED_UNTIL_MONOTONIC = 0.0
_LAST_FAILOVER_REASON: str | None = None
_SYNC_PENDING = False
_SYNC_MONITOR_THREAD: threading.Thread | None = None
_SYNC_ADVISORY_LOCK_ID = 82240331
_QUOTA_MARKERS = (
    "exceeded the data transfer quota",
    "data transfer quota",
    "quota exceeded",
)
_FAILOVER_ERROR_MARKERS = (
    "connection refused",
    "could not connect",
    "connection reset",
    "server closed the connection unexpectedly",
    "timeout expired",
    "temporarily unavailable",
    "remaining connection slots are reserved",
)


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
    args: dict[str, object] = {}
    timeout_seconds = max(int(settings.DATABASE_FAILOVER_CONNECT_TIMEOUT_SECONDS or 0), 0)
    if timeout_seconds:
        args["timeout"] = timeout_seconds
    if "neon" not in lowered and "sslmode=require" not in lowered:
        return args
    try:
        context = ssl.create_default_context()
    except Exception:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    args["ssl"] = context
    return args


def build_sync_connect_args(url: str) -> dict[str, object]:
    args: dict[str, object] = {}
    timeout_seconds = max(int(settings.DATABASE_FAILOVER_CONNECT_TIMEOUT_SECONDS or 0), 0)
    if timeout_seconds:
        args["connect_timeout"] = timeout_seconds
    if "neon" in url.lower():
        args["sslmode"] = "require"
    return args


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


def _primary_retry_seconds() -> int:
    return max(int(settings.DATABASE_FAILOVER_PRIMARY_RETRY_SECONDS or 300), 1)


def _sync_enabled() -> bool:
    return bool(settings.DATABASE_FAILOVER_SYNC_ENABLED)


def _sync_poll_seconds() -> int:
    return max(int(settings.DATABASE_FAILOVER_SYNC_POLL_SECONDS or 60), 5)


def _primary_candidate() -> ResolvedDatabaseUrls:
    return ResolvedDatabaseUrls(
        async_url=normalize_async_url(settings.DATABASE_URL),
        sync_url=to_sync_url(settings.database_url_sync),
        source="primary",
    )


def _fallback_candidate() -> ResolvedDatabaseUrls | None:
    fallback_seed = (settings.DATABASE_URL_FALLBACK or "").strip()
    fallback_sync_seed = settings.database_url_sync_fallback
    if not fallback_seed and not fallback_sync_seed:
        return None
    fallback = ResolvedDatabaseUrls(
        async_url=normalize_async_url(to_async_url(fallback_seed or fallback_sync_seed or "")),
        sync_url=to_sync_url(fallback_sync_seed or fallback_seed or ""),
        source="fallback",
    )
    primary = _primary_candidate()
    return None if fallback.sync_url == primary.sync_url else fallback


def _has_fallback() -> bool:
    return _fallback_candidate() is not None


def _primary_suspended() -> bool:
    return time.monotonic() < _PRIMARY_SUSPENDED_UNTIL_MONOTONIC


def _candidate_urls() -> list[ResolvedDatabaseUrls]:
    primary = _primary_candidate()
    fallback = _fallback_candidate()
    if fallback is None:
        return [primary]
    if _primary_suspended() or _SYNC_PENDING:
        return [fallback, primary]
    return [primary, fallback]


def _probe_sync_url(url: str) -> None:
    engine = create_engine(url, pool_pre_ping=True, connect_args=build_sync_connect_args(url))
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def _describe_host(url: str) -> str:
    return urlparse(url).hostname or "<unknown>"


def _exception_text(exc: Exception) -> str:
    return " ".join(part for part in (type(exc).__name__, str(exc)) if part).lower()


def _is_quota_error(exc: Exception) -> bool:
    text_value = _exception_text(exc)
    return any(marker in text_value for marker in _QUOTA_MARKERS)


def _is_failover_eligible_exception(exc: Exception) -> bool:
    text_value = _exception_text(exc)
    if _is_quota_error(exc):
        return True
    return any(marker in text_value for marker in _FAILOVER_ERROR_MARKERS)


def _set_primary_suspension(reason: str) -> None:
    global _CACHED_RESOLUTION, _LAST_FAILOVER_REASON, _PRIMARY_SUSPENDED_UNTIL_MONOTONIC
    _PRIMARY_SUSPENDED_UNTIL_MONOTONIC = time.monotonic() + _primary_retry_seconds()
    _LAST_FAILOVER_REASON = reason
    _CACHED_RESOLUTION = None


def _log_sync_guidance() -> None:
    logger.warning(
        "database_failover primary quota block detected; fallback stays authoritative until primary is "
        "writable again and the runtime resynchronizes fallback back into primary. Manual operator override: "
        "`python scripts/sync_failover_database.py --source fallback --target primary --allow-destructive-sync`."
    )


def _mark_sync_pending_locked(reason: str) -> None:
    global _SYNC_PENDING
    if not _has_fallback() or not _sync_enabled():
        return
    _SYNC_PENDING = True
    logger.warning(
        "database_failover marked primary host=%s for fallback-to-primary resync after failover: %s",
        _describe_host(_primary_candidate().sync_url),
        reason,
    )


def primary_sync_pending() -> bool:
    with _FAILOVER_LOCK:
        return _SYNC_PENDING


def build_database_sync_command(source_url: str, target_url: str) -> str:
    return (
        f'pg_dump --no-owner --no-privileges --clean --if-exists --format=plain "{source_url}" '
        f'| psql "{target_url}"'
    )


def _require_binary(name: str) -> None:
    if shutil.which(name):
        return
    raise RuntimeError(f"Missing required binary: {name}")


def _sync_pipeline_args(source_url: str, target_url: str) -> tuple[list[str], list[str]]:
    dump_cmd = [
        "pg_dump",
        "--no-owner",
        "--no-privileges",
        "--clean",
        "--if-exists",
        "--format=plain",
        source_url,
    ]
    restore_cmd = ["psql", target_url]
    return dump_cmd, restore_cmd


def _database_urls_for_sync(source: str, target: str) -> tuple[str, str]:
    urls = configured_database_urls()
    if source == target:
        raise ValueError("Source and target must differ.")
    if source not in urls or target not in urls:
        raise ValueError("Primary and fallback database URLs must both be configured.")
    return urls[source].sync_url, urls[target].sync_url


def _run_sync_pipeline(source_url: str, target_url: str) -> None:
    _require_binary("pg_dump")
    _require_binary("psql")
    dump_cmd, restore_cmd = _sync_pipeline_args(source_url, target_url)
    env = dict(os.environ)
    env.setdefault("PGCONNECT_TIMEOUT", "15")
    dump_proc = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, env=env)
    assert dump_proc.stdout is not None
    restore_proc = subprocess.Popen(restore_cmd, stdin=dump_proc.stdout, env=env)
    dump_proc.stdout.close()
    restore_code = restore_proc.wait()
    dump_code = dump_proc.wait()
    if dump_code != 0 or restore_code != 0:
        raise RuntimeError(
            "Fallback-to-primary sync failed "
            f"(pg_dump exit={dump_code}, psql exit={restore_code})."
        )


def sync_configured_databases(
    *,
    source: str = "fallback",
    target: str = "primary",
    allow_destructive_sync: bool = False,
    dry_run: bool = False,
) -> bool:
    source_url, target_url = _database_urls_for_sync(source, target)
    if dry_run:
        return False
    if not allow_destructive_sync:
        raise ValueError("Refusing to overwrite the target database without allow_destructive_sync=True.")

    target_engine = create_engine(
        target_url,
        pool_pre_ping=True,
        connect_args=build_sync_connect_args(target_url),
    )
    try:
        with target_engine.connect() as connection:
            locked = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": _SYNC_ADVISORY_LOCK_ID},
                ).scalar()
            )
            if not locked:
                logger.warning(
                    "database_failover sync already in progress for target host=%s",
                    _describe_host(target_url),
                )
                return False
            try:
                _run_sync_pipeline(source_url, target_url)
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": _SYNC_ADVISORY_LOCK_ID},
                )
    finally:
        target_engine.dispose()
    return True


def _clear_sync_pending_locked() -> None:
    global _CACHED_RESOLUTION, _LAST_FAILOVER_REASON, _PRIMARY_SUSPENDED_UNTIL_MONOTONIC, _SYNC_PENDING
    _SYNC_PENDING = False
    _CACHED_RESOLUTION = None
    _LAST_FAILOVER_REASON = None
    _PRIMARY_SUSPENDED_UNTIL_MONOTONIC = 0.0


def _run_pending_primary_resync_once() -> bool:
    fallback = _fallback_candidate()
    if fallback is None or not _sync_enabled():
        return False
    with _FAILOVER_LOCK:
        if not _SYNC_PENDING:
            return False
    primary = _primary_candidate()
    try:
        _probe_sync_url(primary.sync_url)
    except Exception as exc:
        if _is_failover_eligible_exception(exc):
            with _FAILOVER_LOCK:
                _set_primary_suspension(_exception_text(exc))
        return False

    synced = sync_configured_databases(source="fallback", target="primary", allow_destructive_sync=True)
    if not synced:
        return False
    with _FAILOVER_LOCK:
        _clear_sync_pending_locked()
    logger.warning(
        "database_failover completed fallback-to-primary resync for host=%s; primary is eligible again",
        _describe_host(primary.sync_url),
    )
    return True


def _sync_monitor_loop() -> None:
    global _SYNC_MONITOR_THREAD
    current = threading.current_thread()
    try:
        while True:
            with _FAILOVER_LOCK:
                if not _SYNC_PENDING:
                    return
            try:
                if _run_pending_primary_resync_once():
                    return
            except Exception as exc:
                logger.warning("database_failover background resync attempt failed: %s", exc)
            time.sleep(_sync_poll_seconds())
    finally:
        with _FAILOVER_LOCK:
            if _SYNC_MONITOR_THREAD is current:
                _SYNC_MONITOR_THREAD = None


def _ensure_sync_monitor() -> None:
    global _SYNC_MONITOR_THREAD
    if not _sync_enabled() or _should_skip_probe():
        return
    with _FAILOVER_LOCK:
        if _SYNC_MONITOR_THREAD is not None and _SYNC_MONITOR_THREAD.is_alive():
            return
        _SYNC_MONITOR_THREAD = threading.Thread(
            target=_sync_monitor_loop,
            name="database-failover-sync-monitor",
            daemon=True,
        )
        _SYNC_MONITOR_THREAD.start()


def record_primary_runtime_failure(exc: Exception) -> bool:
    if not _has_fallback() or not _is_failover_eligible_exception(exc):
        return False
    with _FAILOVER_LOCK:
        _set_primary_suspension(_exception_text(exc))
        _mark_sync_pending_locked(_exception_text(exc))
    logger.warning(
        "database_failover suspended primary host=%s for %ss after runtime failure: %s",
        _describe_host(_primary_candidate().sync_url),
        _primary_retry_seconds(),
        type(exc).__name__,
    )
    _ensure_sync_monitor()
    if _is_quota_error(exc):
        _log_sync_guidance()
    return True


def current_database_source() -> str | None:
    resolved = resolve_database_urls()
    return resolved.source


def configured_database_urls() -> dict[str, ResolvedDatabaseUrls]:
    urls = {"primary": _primary_candidate()}
    fallback = _fallback_candidate()
    if fallback is not None:
        urls["fallback"] = fallback
    return urls


def resolve_database_urls(*, force_refresh: bool = False) -> ResolvedDatabaseUrls:
    global _CACHED_RESOLUTION
    with _FAILOVER_LOCK:
        if not force_refresh and _CACHED_RESOLUTION is not None:
            return _CACHED_RESOLUTION

    candidates = _candidate_urls()
    if _should_skip_probe():
        chosen = candidates[0]
    else:
        chosen = _resolve_by_probe(candidates)

    with _FAILOVER_LOCK:
        _CACHED_RESOLUTION = chosen
    return chosen


def _resolve_by_probe(candidates: list[ResolvedDatabaseUrls]) -> ResolvedDatabaseUrls:
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
                _ensure_sync_monitor()
                if _LAST_FAILOVER_REASON and "quota" in _LAST_FAILOVER_REASON:
                    _log_sync_guidance()
            return candidate
        except Exception as exc:
            failures.append(f"{candidate.source}@{_describe_host(candidate.sync_url)}: {exc}")
            if candidate.source == "primary" and _is_failover_eligible_exception(exc):
                with _FAILOVER_LOCK:
                    _set_primary_suspension(_exception_text(exc))
                    _mark_sync_pending_locked(_exception_text(exc))
    details = "; ".join(failures) or "no configured database candidates"
    raise RuntimeError(f"Unable to connect to any configured database candidate. {details}")


def reset_failover_state() -> None:
    global _CACHED_RESOLUTION, _LAST_FAILOVER_REASON, _PRIMARY_SUSPENDED_UNTIL_MONOTONIC, _SYNC_PENDING
    with _FAILOVER_LOCK:
        _CACHED_RESOLUTION = None
        _LAST_FAILOVER_REASON = None
        _PRIMARY_SUSPENDED_UNTIL_MONOTONIC = 0.0
        _SYNC_PENDING = False


resolve_database_urls.cache_clear = reset_failover_state  # type: ignore[attr-defined]
