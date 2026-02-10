"""control-plane events and shadow finding state tables

Revision ID: 0021_control_plane_shadow
Revises: 0020_run_executions
Create Date: 2026-02-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_control_plane_shadow"
down_revision: Union[str, None] = "0020_run_executions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "control_plane_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("detail_type", sa.String(length=128), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=True),
        sa.Column("event_category", sa.String(length=32), nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("drop_reason", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("intake_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queue_enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handler_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upsert_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_visible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cloudtrail_delivery_lag_ms", sa.Integer(), nullable=True),
        sa.Column("queue_lag_ms", sa.Integer(), nullable=True),
        sa.Column("handler_latency_ms", sa.Integer(), nullable=True),
        sa.Column("end_to_end_lag_ms", sa.Integer(), nullable=True),
        sa.Column("resolution_freshness_ms", sa.Integer(), nullable=True),
        sa.Column("raw_event", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "event_id",
            "account_id",
            "region",
            name="uq_control_plane_events_tenant_event_account_region",
        ),
    )
    op.create_index("ix_control_plane_events_tenant_time", "control_plane_events", ["tenant_id", "event_time"])
    op.create_index(
        "ix_control_plane_events_tenant_status",
        "control_plane_events",
        ["tenant_id", "processing_status", "event_time"],
    )
    op.create_index(
        "ix_control_plane_events_account_region",
        "control_plane_events",
        ["tenant_id", "account_id", "region", "event_time"],
    )
    op.create_index("ix_control_plane_events_tenant_id", "control_plane_events", ["tenant_id"])
    op.create_index("ix_control_plane_events_account_id", "control_plane_events", ["account_id"])

    op.create_table(
        "finding_shadow_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="event_monitor_shadow"),
        sa.Column("fingerprint", sa.String(length=1024), nullable=False),
        sa.Column("resource_id", sa.String(length=2048), nullable=False),
        sa.Column("resource_type", sa.String(length=256), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("evidence_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("state_confidence", sa.Integer(), nullable=True),
        sa.Column("first_observed_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observed_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "source",
            "fingerprint",
            name="uq_finding_shadow_states_tenant_source_fingerprint",
        ),
    )
    op.create_index(
        "ix_finding_shadow_states_tenant_status",
        "finding_shadow_states",
        ["tenant_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_finding_shadow_states_tenant_account_region",
        "finding_shadow_states",
        ["tenant_id", "account_id", "region"],
    )
    op.create_index(
        "ix_finding_shadow_states_event_time",
        "finding_shadow_states",
        ["tenant_id", "last_observed_event_time"],
    )
    op.create_index("ix_finding_shadow_states_tenant_id", "finding_shadow_states", ["tenant_id"])
    op.create_index("ix_finding_shadow_states_account_id", "finding_shadow_states", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_finding_shadow_states_account_id", table_name="finding_shadow_states")
    op.drop_index("ix_finding_shadow_states_tenant_id", table_name="finding_shadow_states")
    op.drop_index("ix_finding_shadow_states_event_time", table_name="finding_shadow_states")
    op.drop_index("ix_finding_shadow_states_tenant_account_region", table_name="finding_shadow_states")
    op.drop_index("ix_finding_shadow_states_tenant_status", table_name="finding_shadow_states")
    op.drop_table("finding_shadow_states")

    op.drop_index("ix_control_plane_events_account_id", table_name="control_plane_events")
    op.drop_index("ix_control_plane_events_tenant_id", table_name="control_plane_events")
    op.drop_index("ix_control_plane_events_account_region", table_name="control_plane_events")
    op.drop_index("ix_control_plane_events_tenant_status", table_name="control_plane_events")
    op.drop_index("ix_control_plane_events_tenant_time", table_name="control_plane_events")
    op.drop_table("control_plane_events")
