"""Add action remediation sync state and event tables.

Revision ID: 0042_action_remediation_system_of_record
Revises: 0041_security_graph_foundation
Create Date: 2026-03-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0042_action_remediation_system_of_record"
down_revision: Union[str, None] = "0041_security_graph_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "action_remediation_sync_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("external_status", sa.String(length=128), nullable=True),
        sa.Column("mapped_internal_status", sa.String(length=32), nullable=True),
        sa.Column("canonical_internal_status", sa.String(length=32), nullable=False),
        sa.Column("preferred_external_status", sa.String(length=128), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False, server_default=sa.text("'in_sync'")),
        sa.Column("last_source", sa.String(length=32), nullable=False, server_default=sa.text("'internal'")),
        sa.Column("resolution_decision", sa.String(length=64), nullable=True),
        sa.Column("conflict_reason", sa.Text(), nullable=True),
        sa.Column("sync_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "action_id",
            "provider",
            name="uq_action_remediation_sync_states_tenant_action_provider",
        ),
    )
    op.create_index(
        "ix_action_remediation_sync_states_tenant_action",
        "action_remediation_sync_states",
        ["tenant_id", "action_id"],
    )
    op.create_index(
        "ix_action_remediation_sync_states_tenant_sync_status",
        "action_remediation_sync_states",
        ["tenant_id", "sync_status"],
    )
    op.create_index(
        "ix_action_remediation_sync_states_tenant_provider",
        "action_remediation_sync_states",
        ["tenant_id", "provider"],
    )
    op.alter_column("action_remediation_sync_states", "sync_status", server_default=None)
    op.alter_column("action_remediation_sync_states", "last_source", server_default=None)

    op.create_table(
        "action_remediation_sync_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sync_state_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("internal_status_before", sa.String(length=32), nullable=True),
        sa.Column("internal_status_after", sa.String(length=32), nullable=True),
        sa.Column("external_status", sa.String(length=128), nullable=True),
        sa.Column("mapped_internal_status", sa.String(length=32), nullable=True),
        sa.Column("preferred_external_status", sa.String(length=128), nullable=True),
        sa.Column("resolution_decision", sa.String(length=64), nullable=True),
        sa.Column("decision_detail", sa.Text(), nullable=True),
        sa.Column("event_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sync_state_id"], ["action_remediation_sync_states.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "action_id",
            "idempotency_key",
            name="uq_action_remediation_sync_events_tenant_action_idempotency",
        ),
    )
    op.create_index(
        "ix_action_remediation_sync_events_tenant_action",
        "action_remediation_sync_events",
        ["tenant_id", "action_id"],
    )
    op.create_index(
        "ix_action_remediation_sync_events_tenant_provider",
        "action_remediation_sync_events",
        ["tenant_id", "provider"],
    )
    op.create_index(
        "ix_action_remediation_sync_events_tenant_created",
        "action_remediation_sync_events",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_remediation_sync_events_tenant_created", table_name="action_remediation_sync_events")
    op.drop_index("ix_action_remediation_sync_events_tenant_provider", table_name="action_remediation_sync_events")
    op.drop_index("ix_action_remediation_sync_events_tenant_action", table_name="action_remediation_sync_events")
    op.drop_table("action_remediation_sync_events")
    op.drop_index("ix_action_remediation_sync_states_tenant_provider", table_name="action_remediation_sync_states")
    op.drop_index("ix_action_remediation_sync_states_tenant_sync_status", table_name="action_remediation_sync_states")
    op.drop_index("ix_action_remediation_sync_states_tenant_action", table_name="action_remediation_sync_states")
    op.drop_table("action_remediation_sync_states")
