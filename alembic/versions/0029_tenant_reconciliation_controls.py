"""tenant-facing reconciliation run tracking and schedules

Revision ID: 0029_tenant_reconcile_controls
Revises: 0028_findings_missing_keys_index
Create Date: 2026-02-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0029_tenant_reconcile_controls"
down_revision: Union[str, None] = "0028_findings_missing_keys_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_reconcile_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_by_email", sa.String(length=320), nullable=True),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("services", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sweep_mode", sa.String(length=32), nullable=False, server_default=sa.text("'global'")),
        sa.Column("max_resources", sa.Integer(), nullable=True),
        sa.Column("total_shards", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("enqueued_shards", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("running_shards", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("succeeded_shards", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_shards", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tenant_reconcile_runs_tenant_id", "tenant_reconcile_runs", ["tenant_id"])
    op.create_index("ix_tenant_reconcile_runs_account_id", "tenant_reconcile_runs", ["account_id"])
    op.create_index(
        "ix_tenant_reconcile_runs_tenant_created_at",
        "tenant_reconcile_runs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_tenant_reconcile_runs_tenant_account_status",
        "tenant_reconcile_runs",
        ["tenant_id", "account_id", "status"],
    )

    op.create_table(
        "tenant_reconcile_run_shards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_reconcile_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("queue_message_id", sa.String(length=256), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tenant_reconcile_run_shards_run_id", "tenant_reconcile_run_shards", ["run_id"])
    op.create_index("ix_tenant_reconcile_run_shards_tenant_id", "tenant_reconcile_run_shards", ["tenant_id"])
    op.create_index("ix_tenant_reconcile_run_shards_account_id", "tenant_reconcile_run_shards", ["account_id"])
    op.create_index(
        "ix_tenant_reconcile_run_shards_run_status",
        "tenant_reconcile_run_shards",
        ["run_id", "status"],
    )
    op.create_index(
        "ix_tenant_reconcile_run_shards_tenant_account_status",
        "tenant_reconcile_run_shards",
        ["tenant_id", "account_id", "status"],
    )

    op.create_table(
        "aws_account_reconcile_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default=sa.text("360")),
        sa.Column("services", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("max_resources", sa.Integer(), nullable=True),
        sa.Column("sweep_mode", sa.String(length=32), nullable=False, server_default=sa.text("'global'")),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("last_enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_reconcile_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "account_id", name="uq_aws_account_reconcile_settings_tenant_account"),
    )
    op.create_index(
        "ix_aws_account_reconcile_settings_tenant_id",
        "aws_account_reconcile_settings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_aws_account_reconcile_settings_account_id",
        "aws_account_reconcile_settings",
        ["account_id"],
    )
    op.create_index(
        "ix_aws_account_reconcile_settings_tenant_enabled",
        "aws_account_reconcile_settings",
        ["tenant_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aws_account_reconcile_settings_tenant_enabled",
        table_name="aws_account_reconcile_settings",
    )
    op.drop_index(
        "ix_aws_account_reconcile_settings_account_id",
        table_name="aws_account_reconcile_settings",
    )
    op.drop_index(
        "ix_aws_account_reconcile_settings_tenant_id",
        table_name="aws_account_reconcile_settings",
    )
    op.drop_table("aws_account_reconcile_settings")

    op.drop_index(
        "ix_tenant_reconcile_run_shards_tenant_account_status",
        table_name="tenant_reconcile_run_shards",
    )
    op.drop_index(
        "ix_tenant_reconcile_run_shards_run_status",
        table_name="tenant_reconcile_run_shards",
    )
    op.drop_index(
        "ix_tenant_reconcile_run_shards_account_id",
        table_name="tenant_reconcile_run_shards",
    )
    op.drop_index(
        "ix_tenant_reconcile_run_shards_tenant_id",
        table_name="tenant_reconcile_run_shards",
    )
    op.drop_index(
        "ix_tenant_reconcile_run_shards_run_id",
        table_name="tenant_reconcile_run_shards",
    )
    op.drop_table("tenant_reconcile_run_shards")

    op.drop_index(
        "ix_tenant_reconcile_runs_tenant_account_status",
        table_name="tenant_reconcile_runs",
    )
    op.drop_index(
        "ix_tenant_reconcile_runs_tenant_created_at",
        table_name="tenant_reconcile_runs",
    )
    op.drop_index(
        "ix_tenant_reconcile_runs_account_id",
        table_name="tenant_reconcile_runs",
    )
    op.drop_index(
        "ix_tenant_reconcile_runs_tenant_id",
        table_name="tenant_reconcile_runs",
    )
    op.drop_table("tenant_reconcile_runs")
