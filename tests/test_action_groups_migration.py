from __future__ import annotations

from pathlib import Path


def test_action_groups_migration_contains_immutable_constraints() -> None:
    migration_path = Path("alembic/versions/0030_action_groups_persistent.py")
    text = migration_path.read_text(encoding="utf-8")

    assert "uq_action_group_memberships_action_id" in text
    assert "uq_action_groups_group_key" in text
    assert "CREATE UNIQUE INDEX uq_action_groups_tenant_type_account_region_norm" in text
    assert "action_group_status_bucket" in text
    assert "run_successful_confirmed" in text


def test_pending_confirmation_bucket_migration_exists() -> None:
    migration_path = Path("alembic/versions/0048_action_group_pending_confirmation_bucket.py")
    text = migration_path.read_text(encoding="utf-8")

    assert "ALTER TYPE action_group_status_bucket" in text
    assert "run_successful_pending_confirmation" in text


def test_metadata_only_bucket_migration_exists() -> None:
    migration_path = Path("alembic/versions/0049_action_group_metadata_only_bucket.py")
    text = migration_path.read_text(encoding="utf-8")

    assert "ALTER TYPE action_group_status_bucket" in text
    assert "run_finished_metadata_only" in text
