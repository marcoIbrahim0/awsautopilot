"""remediation_runs table (Step 7.1)

Revision ID: 0007_remediation_runs
Revises: 0006_exceptions
Create Date: 2026-02-02

Creates the remediation_runs table for remediation attempt audit trail.
One row per run: mode (pr_only | direct_fix), status, outcome, logs, artifacts.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_remediation_runs"
down_revision: Union[str, None] = "0006_exceptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums for mode and status
    op.execute("CREATE TYPE remediation_run_mode AS ENUM ('pr_only', 'direct_fix')")
    op.execute(
        "CREATE TYPE remediation_run_status AS ENUM "
        "('pending', 'running', 'success', 'failed', 'cancelled')"
    )

    op.create_table(
        "remediation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mode",
            postgresql.ENUM("pr_only", "direct_fix", name="remediation_run_mode", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "running", "success", "failed", "cancelled",
                name="remediation_run_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(length=500), nullable=True),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column("artifacts", postgresql.JSONB(), nullable=True),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("idx_remediation_runs_tenant", "remediation_runs", ["tenant_id"])
    op.create_index("idx_remediation_runs_action", "remediation_runs", ["action_id"])
    op.create_index(
        "idx_remediation_runs_tenant_created",
        "remediation_runs",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index("idx_remediation_runs_status", "remediation_runs", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_remediation_runs_status", table_name="remediation_runs")
    op.drop_index("idx_remediation_runs_tenant_created", table_name="remediation_runs")
    op.drop_index("idx_remediation_runs_action", table_name="remediation_runs")
    op.drop_index("idx_remediation_runs_tenant", table_name="remediation_runs")
    op.drop_table("remediation_runs")
    op.execute("DROP TYPE remediation_run_status")
    op.execute("DROP TYPE remediation_run_mode")
