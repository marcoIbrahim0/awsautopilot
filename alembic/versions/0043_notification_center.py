"""Add persistent notification center tables.

Revision ID: 0043_notification_center
Revises: 0042_bidirectional_integrations
Create Date: 2026-03-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0043_notification_center"
down_revision: Union[str, None] = "0042_bidirectional_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("governance_notification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("action_url", sa.Text(), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_key", sa.String(length=191), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["governance_notification_id"], ["governance_notifications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "client_key", name="uq_app_notifications_tenant_client_key"),
        sa.UniqueConstraint(
            "tenant_id",
            "governance_notification_id",
            name="uq_app_notifications_tenant_governance_notification",
        ),
    )
    op.create_index("ix_app_notifications_tenant_actor", "app_notifications", ["tenant_id", "actor_user_id"])
    op.create_index("ix_app_notifications_tenant_created", "app_notifications", ["tenant_id", "created_at"])
    op.create_index("ix_app_notifications_tenant_source", "app_notifications", ["tenant_id", "source"])

    op.create_table(
        "app_notification_user_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["app_notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id",
            "user_id",
            name="uq_app_notification_user_states_notification_user",
        ),
    )
    op.create_index(
        "ix_app_notification_user_states_user_archived",
        "app_notification_user_states",
        ["user_id", "archived_at"],
    )

    op.execute(
        """
        INSERT INTO app_notifications (
            id,
            tenant_id,
            governance_notification_id,
            kind,
            source,
            severity,
            status,
            title,
            message,
            detail,
            action_url,
            target_type,
            target_id,
            created_at,
            updated_at
        )
        SELECT
            id,
            tenant_id,
            id,
            'governance',
            'governance',
            CASE
                WHEN status = 'failed' THEN 'error'
                WHEN stage = 'completion' THEN 'success'
                WHEN stage = 'action_required' THEN 'warning'
                ELSE 'info'
            END,
            CASE
                WHEN status IN ('failed', 'skipped') THEN status
                ELSE stage
            END,
            COALESCE(payload ->> 'title', initcap(replace(stage, '_', ' '))),
            COALESCE(payload ->> 'message', 'Governance notification'),
            NULLIF(payload #>> '{webhook,detail}', ''),
            NULLIF(payload #>> '{webhook,action_url}', ''),
            target_type,
            target_id,
            created_at,
            COALESCE(updated_at, created_at)
        FROM governance_notifications
        WHERE channel = 'in_app'
          AND created_at >= now() - interval '30 days'
        ON CONFLICT ON CONSTRAINT uq_app_notifications_tenant_governance_notification DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_app_notification_user_states_user_archived",
        table_name="app_notification_user_states",
    )
    op.drop_table("app_notification_user_states")
    op.drop_index("ix_app_notifications_tenant_source", table_name="app_notifications")
    op.drop_index("ix_app_notifications_tenant_created", table_name="app_notifications")
    op.drop_index("ix_app_notifications_tenant_actor", table_name="app_notifications")
    op.drop_table("app_notifications")
