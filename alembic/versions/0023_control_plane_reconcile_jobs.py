"""control-plane reconcile job history table

Revision ID: 0023_cp_reconcile_jobs
Revises: 0022_inventory_assets
Create Date: 2026-02-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_cp_reconcile_jobs"
down_revision: Union[str, None] = "0022_inventory_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "control_plane_reconcile_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("submitted_by_email", sa.String(length=320), nullable=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("queue_message_id", sa.String(length=256), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_control_plane_reconcile_jobs_tenant_id", "control_plane_reconcile_jobs", ["tenant_id"])
    op.create_index(
        "ix_cp_reconcile_jobs_tenant_submitted",
        "control_plane_reconcile_jobs",
        ["tenant_id", "submitted_at"],
    )
    op.create_index(
        "ix_cp_reconcile_jobs_tenant_status",
        "control_plane_reconcile_jobs",
        ["tenant_id", "status", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cp_reconcile_jobs_tenant_status", table_name="control_plane_reconcile_jobs")
    op.drop_index("ix_cp_reconcile_jobs_tenant_submitted", table_name="control_plane_reconcile_jobs")
    op.drop_index("ix_control_plane_reconcile_jobs_tenant_id", table_name="control_plane_reconcile_jobs")
    op.drop_table("control_plane_reconcile_jobs")
