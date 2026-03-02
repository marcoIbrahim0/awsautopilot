"""communication + governance layer schema

Revision ID: 0037_comm_governance_layer
Revises: 0036_secret_migration_conn
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0037_comm_governance_layer"
down_revision: Union[str, None] = "0036_secret_migration_conn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("governance_webhook_url", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "governance_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column("exceptions", sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "exceptions",
        sa.Column("approval_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("exceptions", sa.Column("reminder_interval_days", sa.Integer(), nullable=True))
    op.add_column("exceptions", sa.Column("next_reminder_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exceptions", sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exceptions", sa.Column("revalidation_interval_days", sa.Integer(), nullable=True))
    op.add_column("exceptions", sa.Column("next_revalidation_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exceptions", sa.Column("last_revalidated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_exceptions_owner_user_id_users",
        "exceptions",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index("idx_exceptions_owner", "exceptions", ["tenant_id", "owner_user_id"])
    op.create_index("idx_exceptions_reminder_due", "exceptions", ["tenant_id", "next_reminder_at"])
    op.create_index("idx_exceptions_revalidation_due", "exceptions", ["tenant_id", "next_revalidation_at"])

    op.create_table(
        "governance_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notification_key", sa.String(length=160), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "notification_key",
            "channel",
            name="uq_governance_notifications_tenant_key_channel",
        ),
    )

    op.create_index("ix_governance_notifications_tenant", "governance_notifications", ["tenant_id"])
    op.create_index(
        "ix_governance_notifications_tenant_created",
        "governance_notifications",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_governance_notifications_tenant_status",
        "governance_notifications",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_governance_notifications_tenant_target",
        "governance_notifications",
        ["tenant_id", "target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_governance_notifications_tenant_target", table_name="governance_notifications")
    op.drop_index("ix_governance_notifications_tenant_status", table_name="governance_notifications")
    op.drop_index("ix_governance_notifications_tenant_created", table_name="governance_notifications")
    op.drop_index("ix_governance_notifications_tenant", table_name="governance_notifications")
    op.drop_table("governance_notifications")

    op.drop_index("idx_exceptions_revalidation_due", table_name="exceptions")
    op.drop_index("idx_exceptions_reminder_due", table_name="exceptions")
    op.drop_index("idx_exceptions_owner", table_name="exceptions")
    op.drop_constraint("fk_exceptions_owner_user_id_users", "exceptions", type_="foreignkey")

    op.drop_column("exceptions", "last_revalidated_at")
    op.drop_column("exceptions", "next_revalidation_at")
    op.drop_column("exceptions", "revalidation_interval_days")
    op.drop_column("exceptions", "last_reminded_at")
    op.drop_column("exceptions", "next_reminder_at")
    op.drop_column("exceptions", "reminder_interval_days")
    op.drop_column("exceptions", "approval_metadata")
    op.drop_column("exceptions", "owner_user_id")

    op.drop_column("tenants", "governance_notifications_enabled")
    op.drop_column("tenants", "governance_webhook_url")
