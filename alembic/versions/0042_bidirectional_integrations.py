"""Add tenant-scoped bi-directional integration persistence.

Revision ID: 0042_bidirectional_integrations
Revises: 0041_security_graph_foundation
Create Date: 2026-03-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0042_bidirectional_integrations"
down_revision: Union[str, None] = "0041_security_graph_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_integration_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("outbound_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("inbound_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_create", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reopen_on_regression", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("secret_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("webhook_token_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_tenant_integration_settings_tenant_provider"),
    )
    op.create_index(
        "ix_tenant_integration_settings_tenant_enabled",
        "tenant_integration_settings",
        ["tenant_id", "enabled"],
    )
    op.create_index(
        "ix_tenant_integration_settings_webhook_token_hash",
        "tenant_integration_settings",
        ["webhook_token_hash"],
    )
    op.alter_column("tenant_integration_settings", "config_json", server_default=None)

    op.create_table(
        "action_external_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("external_key", sa.String(length=255), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("external_status", sa.String(length=128), nullable=True),
        sa.Column("external_assignee_key", sa.String(length=255), nullable=True),
        sa.Column("external_assignee_label", sa.String(length=255), nullable=True),
        sa.Column("last_outbound_signature", sa.String(length=64), nullable=True),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_inbound_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "action_id",
            "provider",
            name="uq_action_external_links_tenant_action_provider",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_id",
            name="uq_action_external_links_tenant_provider_external",
        ),
    )
    op.create_index("ix_action_external_links_tenant_action", "action_external_links", ["tenant_id", "action_id"])
    op.create_index("ix_action_external_links_tenant_provider", "action_external_links", ["tenant_id", "provider"])
    op.alter_column("action_external_links", "metadata_json", server_default=None)

    op.create_table(
        "integration_sync_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("trigger", sa.String(length=64), nullable=False),
        sa.Column("request_signature", sa.String(length=64), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_integration_sync_tasks_attempt_count_non_negative",
        ),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["link_id"], ["action_external_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "request_signature", name="uq_integration_sync_tasks_tenant_signature"),
    )
    op.create_index("ix_integration_sync_tasks_tenant_status", "integration_sync_tasks", ["tenant_id", "status"])
    op.create_index("ix_integration_sync_tasks_tenant_action", "integration_sync_tasks", ["tenant_id", "action_id"])
    op.alter_column("integration_sync_tasks", "payload_json", server_default=None)

    op.create_table(
        "integration_event_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("receipt_key", sa.String(length=255), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'processed'")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "receipt_key",
            name="uq_integration_event_receipts_tenant_provider_key",
        ),
    )
    op.create_index(
        "ix_integration_event_receipts_tenant_provider",
        "integration_event_receipts",
        ["tenant_id", "provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_event_receipts_tenant_provider", table_name="integration_event_receipts")
    op.drop_table("integration_event_receipts")
    op.drop_index("ix_integration_sync_tasks_tenant_action", table_name="integration_sync_tasks")
    op.drop_index("ix_integration_sync_tasks_tenant_status", table_name="integration_sync_tasks")
    op.drop_table("integration_sync_tasks")
    op.drop_index("ix_action_external_links_tenant_provider", table_name="action_external_links")
    op.drop_index("ix_action_external_links_tenant_action", table_name="action_external_links")
    op.drop_table("action_external_links")
    op.drop_index(
        "ix_tenant_integration_settings_webhook_token_hash",
        table_name="tenant_integration_settings",
    )
    op.drop_index(
        "ix_tenant_integration_settings_tenant_enabled",
        table_name="tenant_integration_settings",
    )
    op.drop_table("tenant_integration_settings")
