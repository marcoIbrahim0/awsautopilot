"""secret migration connectors schema

Revision ID: 0036_secret_migration_conn
Revises: 0035_rootkey_remediation_orch
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0036_secret_migration_conn"
down_revision: Union[str, None] = "0035_rootkey_remediation_orch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "secret_migration_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_connector", sa.String(length=64), nullable=False),
        sa.Column("source_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("target_connector", sa.String(length=64), nullable=False),
        sa.Column("target_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rollback_on_failure", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("request_signature", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("total_targets", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("succeeded_targets", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_targets", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rolled_back_targets", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_secret_migration_runs_tenant_idempotency"),
        sa.CheckConstraint(
            "status in ('queued','running','success','partial_failed','failed','rolled_back')",
            name="ck_secret_migration_runs_status_valid",
        ),
        sa.CheckConstraint("total_targets >= 0", name="ck_secret_migration_runs_total_non_negative"),
        sa.CheckConstraint("succeeded_targets >= 0", name="ck_secret_migration_runs_succeeded_non_negative"),
        sa.CheckConstraint("failed_targets >= 0", name="ck_secret_migration_runs_failed_non_negative"),
        sa.CheckConstraint("rolled_back_targets >= 0", name="ck_secret_migration_runs_rolled_back_non_negative"),
    )
    op.create_index("ix_secret_migration_runs_tenant_id", "secret_migration_runs", ["tenant_id"])
    op.create_index("ix_secret_migration_runs_tenant_status", "secret_migration_runs", ["tenant_id", "status"])
    op.create_index(
        "ix_secret_migration_runs_tenant_created",
        "secret_migration_runs",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_table(
        "secret_migration_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("secret_migration_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_ref", sa.String(length=1024), nullable=False),
        sa.Column("target_ref", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rollback_supported", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("target_version", sa.String(length=256), nullable=True),
        sa.Column("rollback_token", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "target_ref",
            name="uq_secret_migration_transactions_tenant_run_target",
        ),
        sa.CheckConstraint(
            "status in ('pending','success','failed','rolled_back','rollback_failed','skipped')",
            name="ck_secret_migration_tx_status_valid",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_secret_migration_tx_attempt_non_negative"),
    )
    op.create_index("ix_secret_migration_tx_tenant_id", "secret_migration_transactions", ["tenant_id"])
    op.create_index("ix_secret_migration_tx_tenant_status", "secret_migration_transactions", ["tenant_id", "status"])
    op.create_index("ix_secret_migration_tx_tenant_run", "secret_migration_transactions", ["tenant_id", "run_id"])


def downgrade() -> None:
    op.drop_index("ix_secret_migration_tx_tenant_run", table_name="secret_migration_transactions")
    op.drop_index("ix_secret_migration_tx_tenant_status", table_name="secret_migration_transactions")
    op.drop_index("ix_secret_migration_tx_tenant_id", table_name="secret_migration_transactions")
    op.drop_table("secret_migration_transactions")

    op.drop_index("ix_secret_migration_runs_tenant_created", table_name="secret_migration_runs")
    op.drop_index("ix_secret_migration_runs_tenant_status", table_name="secret_migration_runs")
    op.drop_index("ix_secret_migration_runs_tenant_id", table_name="secret_migration_runs")
    op.drop_table("secret_migration_runs")
