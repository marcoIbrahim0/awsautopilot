"""root-key remediation orchestration schema

Revision ID: 0035_rootkey_remediation_orch
Revises: 0034_remrun_active_unique_guard
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0035_rootkey_remediation_orch"
down_revision: Union[str, None] = "0034_remrun_active_unique_guard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_enums() -> None:
    op.execute(
        "CREATE TYPE root_key_remediation_state AS ENUM ("
        "'discovery','migration','validation','disable_window','delete_window',"
        "'completed','needs_attention','rolled_back','failed'"
        ")"
    )
    op.execute("CREATE TYPE root_key_remediation_mode AS ENUM ('auto','manual')")
    op.execute(
        "CREATE TYPE root_key_remediation_run_status AS ENUM ("
        "'queued','running','waiting_for_user','completed','failed','cancelled'"
        ")"
    )
    op.execute("CREATE TYPE root_key_dependency_status AS ENUM ('pass','warn','unknown','fail')")
    op.execute("CREATE TYPE root_key_artifact_status AS ENUM ('pending','available','redacted','failed')")
    op.execute(
        "CREATE TYPE root_key_external_task_status AS ENUM ("
        "'open','in_progress','completed','cancelled','failed'"
        ")"
    )


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "root_key_remediation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "discovery",
                "migration",
                "validation",
                "disable_window",
                "delete_window",
                "completed",
                "needs_attention",
                "rolled_back",
                "failed",
                name="root_key_remediation_state",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'discovery'"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "waiting_for_user",
                "completed",
                "failed",
                "cancelled",
                name="root_key_remediation_run_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM(
                "auto",
                "manual",
                name="root_key_remediation_mode",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Column("exception_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_root_key_runs_tenant_idempotency"),
        sa.CheckConstraint("retry_count >= 0", name="ck_root_key_runs_retry_non_negative"),
        sa.CheckConstraint("lock_version > 0", name="ck_root_key_runs_lock_version_positive"),
    )
    op.create_index("ix_root_key_runs_tenant_id", "root_key_remediation_runs", ["tenant_id"])
    op.create_index("ix_root_key_runs_tenant_state_status", "root_key_remediation_runs", ["tenant_id", "state", "status"])
    op.create_index("ix_root_key_runs_tenant_scope", "root_key_remediation_runs", ["tenant_id", "account_id", "region"])
    op.create_index("ix_root_key_runs_correlation", "root_key_remediation_runs", ["tenant_id", "correlation_id"])
    op.create_index(
        "ix_root_key_runs_tenant_updated",
        "root_key_remediation_runs",
        ["tenant_id", "updated_at"],
        postgresql_ops={"updated_at": "DESC"},
    )

    op.create_table(
        "root_key_remediation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("root_key_remediation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "discovery",
                "migration",
                "validation",
                "disable_window",
                "delete_window",
                "completed",
                "needs_attention",
                "rolled_back",
                "failed",
                name="root_key_remediation_state",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "waiting_for_user",
                "completed",
                "failed",
                "cancelled",
                name="root_key_remediation_run_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM("auto", "manual", name="root_key_remediation_mode", create_type=False),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Column("exception_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "idempotency_key",
            name="uq_root_key_events_tenant_run_idempotency",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_root_key_events_retry_non_negative"),
    )
    op.create_index("ix_root_key_events_tenant_id", "root_key_remediation_events", ["tenant_id"])
    op.create_index("ix_root_key_events_tenant_run", "root_key_remediation_events", ["tenant_id", "run_id"])
    op.create_index(
        "ix_root_key_events_tenant_created",
        "root_key_remediation_events",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_table(
        "root_key_dependency_fingerprints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("root_key_remediation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "discovery",
                "migration",
                "validation",
                "disable_window",
                "delete_window",
                "completed",
                "needs_attention",
                "rolled_back",
                "failed",
                name="root_key_remediation_state",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pass",
                "warn",
                "unknown",
                "fail",
                name="root_key_dependency_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM("auto", "manual", name="root_key_remediation_mode", create_type=False),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("fingerprint_type", sa.String(length=64), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=128), nullable=False),
        sa.Column("fingerprint_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unknown_dependency", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("unknown_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Column("exception_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "fingerprint_type",
            "fingerprint_hash",
            name="uq_root_key_dependency_fingerprint",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_root_key_dependency_retry_non_negative"),
    )
    op.create_index("ix_root_key_dependency_tenant_id", "root_key_dependency_fingerprints", ["tenant_id"])
    op.create_index(
        "ix_root_key_dependency_tenant_run",
        "root_key_dependency_fingerprints",
        ["tenant_id", "run_id"],
    )
    op.create_index(
        "ix_root_key_dependency_tenant_unknown",
        "root_key_dependency_fingerprints",
        ["tenant_id", "unknown_dependency", "status"],
    )

    op.create_table(
        "root_key_remediation_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("root_key_remediation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "discovery",
                "migration",
                "validation",
                "disable_window",
                "delete_window",
                "completed",
                "needs_attention",
                "rolled_back",
                "failed",
                name="root_key_remediation_state",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "available",
                "redacted",
                "failed",
                name="root_key_artifact_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM("auto", "manual", name="root_key_remediation_mode", create_type=False),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_ref", sa.String(length=512), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=128), nullable=True),
        sa.Column("redaction_applied", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Column("exception_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "idempotency_key",
            name="uq_root_key_artifacts_tenant_run_idempotency",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_root_key_artifacts_retry_non_negative"),
    )
    op.create_index("ix_root_key_artifacts_tenant_id", "root_key_remediation_artifacts", ["tenant_id"])
    op.create_index(
        "ix_root_key_artifacts_tenant_run",
        "root_key_remediation_artifacts",
        ["tenant_id", "run_id"],
    )
    op.create_index(
        "ix_root_key_artifacts_tenant_type",
        "root_key_remediation_artifacts",
        ["tenant_id", "artifact_type"],
    )

    op.create_table(
        "root_key_external_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("root_key_remediation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "discovery",
                "migration",
                "validation",
                "disable_window",
                "delete_window",
                "completed",
                "needs_attention",
                "rolled_back",
                "failed",
                name="root_key_remediation_state",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open",
                "in_progress",
                "completed",
                "cancelled",
                "failed",
                name="root_key_external_task_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM("auto", "manual", name="root_key_remediation_mode", create_type=False),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("task_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("task_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "assigned_to_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.Column("exception_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "idempotency_key",
            name="uq_root_key_external_tasks_tenant_run_idempotency",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_root_key_external_tasks_retry_non_negative"),
    )
    op.create_index("ix_root_key_external_tasks_tenant_id", "root_key_external_tasks", ["tenant_id"])
    op.create_index(
        "ix_root_key_external_tasks_tenant_run",
        "root_key_external_tasks",
        ["tenant_id", "run_id"],
    )
    op.create_index(
        "ix_root_key_external_tasks_tenant_status_due",
        "root_key_external_tasks",
        ["tenant_id", "status", "due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_root_key_external_tasks_tenant_status_due", table_name="root_key_external_tasks")
    op.drop_index("ix_root_key_external_tasks_tenant_run", table_name="root_key_external_tasks")
    op.drop_index("ix_root_key_external_tasks_tenant_id", table_name="root_key_external_tasks")
    op.drop_table("root_key_external_tasks")

    op.drop_index("ix_root_key_artifacts_tenant_type", table_name="root_key_remediation_artifacts")
    op.drop_index("ix_root_key_artifacts_tenant_run", table_name="root_key_remediation_artifacts")
    op.drop_index("ix_root_key_artifacts_tenant_id", table_name="root_key_remediation_artifacts")
    op.drop_table("root_key_remediation_artifacts")

    op.drop_index("ix_root_key_dependency_tenant_unknown", table_name="root_key_dependency_fingerprints")
    op.drop_index("ix_root_key_dependency_tenant_run", table_name="root_key_dependency_fingerprints")
    op.drop_index("ix_root_key_dependency_tenant_id", table_name="root_key_dependency_fingerprints")
    op.drop_table("root_key_dependency_fingerprints")

    op.drop_index("ix_root_key_events_tenant_created", table_name="root_key_remediation_events")
    op.drop_index("ix_root_key_events_tenant_run", table_name="root_key_remediation_events")
    op.drop_index("ix_root_key_events_tenant_id", table_name="root_key_remediation_events")
    op.drop_table("root_key_remediation_events")

    op.drop_index("ix_root_key_runs_tenant_updated", table_name="root_key_remediation_runs")
    op.drop_index("ix_root_key_runs_correlation", table_name="root_key_remediation_runs")
    op.drop_index("ix_root_key_runs_tenant_scope", table_name="root_key_remediation_runs")
    op.drop_index("ix_root_key_runs_tenant_state_status", table_name="root_key_remediation_runs")
    op.drop_index("ix_root_key_runs_tenant_id", table_name="root_key_remediation_runs")
    op.drop_table("root_key_remediation_runs")

    op.execute("DROP TYPE IF EXISTS root_key_external_task_status")
    op.execute("DROP TYPE IF EXISTS root_key_artifact_status")
    op.execute("DROP TYPE IF EXISTS root_key_dependency_status")
    op.execute("DROP TYPE IF EXISTS root_key_remediation_run_status")
    op.execute("DROP TYPE IF EXISTS root_key_remediation_mode")
    op.execute("DROP TYPE IF EXISTS root_key_remediation_state")
