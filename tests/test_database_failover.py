from __future__ import annotations

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
