from __future__ import annotations

import sys

from backend.services import database_failover as failover


def test_resolve_database_urls_prefers_primary_when_probe_succeeds(monkeypatch) -> None:
    probes: list[str] = []

    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover, "_should_skip_probe", lambda: False)
    monkeypatch.setattr(failover, "_probe_sync_url", lambda url: probes.append(url))
    failover.resolve_database_urls.cache_clear()

    resolved = failover.resolve_database_urls()

    assert resolved.source == "primary"
    assert resolved.sync_url == "postgresql://primary-host/app"
    assert resolved.async_url == "postgresql+asyncpg://primary-host/app"
    assert probes == ["postgresql://primary-host/app"]


def test_resolve_database_urls_falls_back_when_primary_probe_fails(monkeypatch) -> None:
    probes: list[str] = []

    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover, "_should_skip_probe", lambda: False)

    def _probe(url: str) -> None:
        probes.append(url)
        if "primary-host" in url:
            raise RuntimeError("quota blocked")

    monkeypatch.setattr(failover, "_probe_sync_url", _probe)
    failover.resolve_database_urls.cache_clear()

    resolved = failover.resolve_database_urls()

    assert resolved.source == "fallback"
    assert resolved.sync_url == "postgresql://fallback-host/app"
    assert resolved.async_url == "postgresql+asyncpg://fallback-host/app"
    assert probes == ["postgresql://primary-host/app", "postgresql://fallback-host/app"]


def test_resolve_database_urls_skips_probe_in_test_context(monkeypatch) -> None:
    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover, "_should_skip_probe", lambda: True)
    monkeypatch.setattr(
        failover,
        "_probe_sync_url",
        lambda url: (_ for _ in ()).throw(AssertionError("probe should be skipped")),
    )
    failover.resolve_database_urls.cache_clear()

    resolved = failover.resolve_database_urls()

    assert resolved.source == "primary"
    assert resolved.sync_url == "postgresql://primary-host/app"


def test_should_skip_probe_during_pytest_bootstrap(monkeypatch) -> None:
    monkeypatch.setattr(failover.settings, "ENV", "development")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setitem(sys.modules, "pytest", object())

    assert failover._should_skip_probe() is True


def test_record_primary_runtime_failure_suspends_primary(monkeypatch) -> None:
    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_PRIMARY_RETRY_SECONDS", 30)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_SYNC_ENABLED", True)
    monkeypatch.setattr(failover, "_ensure_sync_monitor", lambda: None)
    failover.reset_failover_state()

    switched = failover.record_primary_runtime_failure(RuntimeError("Your project has exceeded the data transfer quota"))

    assert switched is True
    assert failover._primary_suspended() is True
    assert failover.primary_sync_pending() is True


def test_candidate_urls_prefers_fallback_while_primary_suspended(monkeypatch) -> None:
    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_PRIMARY_RETRY_SECONDS", 30)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_SYNC_ENABLED", True)
    monkeypatch.setattr(failover, "_ensure_sync_monitor", lambda: None)
    failover.reset_failover_state()
    failover.record_primary_runtime_failure(RuntimeError("quota exceeded"))

    candidates = failover._candidate_urls()

    assert [candidate.source for candidate in candidates] == ["fallback", "primary"]


def test_primary_rejoins_candidates_after_cooldown(monkeypatch) -> None:
    now = {"value": 100.0}
    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_PRIMARY_RETRY_SECONDS", 1)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_SYNC_ENABLED", False)
    monkeypatch.setattr(failover.time, "monotonic", lambda: now["value"])
    monkeypatch.setattr(failover, "_ensure_sync_monitor", lambda: None)
    failover.reset_failover_state()
    failover.record_primary_runtime_failure(RuntimeError("quota exceeded"))
    now["value"] = 101.5

    candidates = failover._candidate_urls()

    assert [candidate.source for candidate in candidates] == ["primary", "fallback"]


def test_run_pending_primary_resync_once_clears_sync_pending(monkeypatch) -> None:
    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_SYNC_ENABLED", True)
    monkeypatch.setattr(failover, "_ensure_sync_monitor", lambda: None)
    monkeypatch.setattr(failover, "_probe_sync_url", lambda url: None)
    monkeypatch.setattr(failover, "sync_configured_databases", lambda **kwargs: True)
    failover.reset_failover_state()
    failover.record_primary_runtime_failure(RuntimeError("quota exceeded"))

    synced = failover._run_pending_primary_resync_once()

    assert synced is True
    assert failover.primary_sync_pending() is False
    assert [candidate.source for candidate in failover._candidate_urls()] == ["primary", "fallback"]


def test_run_pending_primary_resync_once_keeps_sync_pending_when_sync_skipped(monkeypatch) -> None:
    monkeypatch.setattr(failover.settings, "DATABASE_URL", "postgresql+asyncpg://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC", "postgresql://primary-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_FALLBACK", "postgresql://fallback-host/app")
    monkeypatch.setattr(failover.settings, "DATABASE_URL_SYNC_FALLBACK", None)
    monkeypatch.setattr(failover.settings, "DATABASE_FAILOVER_SYNC_ENABLED", True)
    monkeypatch.setattr(failover, "_ensure_sync_monitor", lambda: None)
    monkeypatch.setattr(failover, "_probe_sync_url", lambda url: None)
    monkeypatch.setattr(failover, "sync_configured_databases", lambda **kwargs: False)
    failover.reset_failover_state()
    failover.record_primary_runtime_failure(RuntimeError("quota exceeded"))

    synced = failover._run_pending_primary_resync_once()

    assert synced is False
    assert failover.primary_sync_pending() is True
    assert [candidate.source for candidate in failover._candidate_urls()] == ["fallback", "primary"]
