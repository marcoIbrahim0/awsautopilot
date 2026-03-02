from __future__ import annotations

from pathlib import Path


_MIGRATION_PATH = Path("alembic/versions/0035_root_key_remediation_orchestration.py")


def test_root_key_migration_upgrade_contains_required_entities_and_fields() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")

    required_tables = [
        "root_key_remediation_runs",
        "root_key_remediation_events",
        "root_key_dependency_fingerprints",
        "root_key_remediation_artifacts",
        "root_key_external_tasks",
    ]
    for table in required_tables:
        assert f'"{table}"' in text

    required_fields = [
        '"tenant_id"',
        '"account_id"',
        '"region"',
        '"control_id"',
        '"action_id"',
        '"finding_id"',
        '"strategy_id"',
        '"mode"',
        '"correlation_id"',
        '"started_at"',
        '"updated_at"',
        '"completed_at"',
        '"retry_count"',
        '"rollback_reason"',
        '"exception_expiry"',
        '"actor_metadata"',
    ]
    for field in required_fields:
        assert field in text

    assert "idempotency_key" in text
    assert "lock_version" in text


def test_root_key_migration_upgrade_and_downgrade_cover_all_enums() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")

    enum_types = [
        "root_key_remediation_state",
        "root_key_remediation_mode",
        "root_key_remediation_run_status",
        "root_key_dependency_status",
        "root_key_artifact_status",
        "root_key_external_task_status",
    ]
    for enum_type in enum_types:
        assert f"CREATE TYPE {enum_type} AS ENUM" in text
        assert f"DROP TYPE IF EXISTS {enum_type}" in text



def test_root_key_migration_downgrade_drops_all_tables() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'op.drop_table("root_key_external_tasks")' in text
    assert 'op.drop_table("root_key_remediation_artifacts")' in text
    assert 'op.drop_table("root_key_dependency_fingerprints")' in text
    assert 'op.drop_table("root_key_remediation_events")' in text
    assert 'op.drop_table("root_key_remediation_runs")' in text
