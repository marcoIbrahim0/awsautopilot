from __future__ import annotations

from pathlib import Path


_MIGRATION_PATH = Path("alembic/versions/0036_secret_migration_connectors.py")


def test_secret_migration_migration_creates_required_tables_and_fields() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert '"secret_migration_runs"' in text
    assert '"secret_migration_transactions"' in text
    required_fields = [
        '"tenant_id"',
        '"source_connector"',
        '"source_config"',
        '"target_connector"',
        '"target_config"',
        '"dry_run"',
        '"rollback_on_failure"',
        '"status"',
        '"idempotency_key"',
        '"correlation_id"',
        '"total_targets"',
        '"succeeded_targets"',
        '"failed_targets"',
        '"rolled_back_targets"',
        '"source_ref"',
        '"target_ref"',
        '"rollback_token"',
    ]
    for field in required_fields:
        assert field in text


def test_secret_migration_migration_downgrade_drops_tables() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'op.drop_table("secret_migration_transactions")' in text
    assert 'op.drop_table("secret_migration_runs")' in text
