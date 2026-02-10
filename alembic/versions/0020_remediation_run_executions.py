"""remediation run executions table for SaaS bundle executor

Revision ID: 0020_run_executions
Revises: 0019_findings_unique_tenant
Create Date: 2026-02-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_run_executions"
down_revision: Union[str, None] = "0019_findings_unique_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE remediation_run_status "
        "ADD VALUE IF NOT EXISTS 'awaiting_approval'"
    )
    op.execute(
        "CREATE TYPE remediation_run_execution_phase "
        "AS ENUM ('plan', 'apply')"
    )
    op.execute(
        "CREATE TYPE remediation_run_execution_status "
        "AS ENUM ('queued', 'running', 'awaiting_approval', 'success', 'failed', 'cancelled')"
    )

    op.create_table(
        "remediation_run_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("remediation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "phase",
            postgresql.ENUM("plan", "apply", name="remediation_run_execution_phase", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "awaiting_approval",
                "success",
                "failed",
                "cancelled",
                name="remediation_run_execution_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("workspace_manifest", postgresql.JSONB(), nullable=True),
        sa.Column("results", postgresql.JSONB(), nullable=True),
        sa.Column("logs_ref", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_run_exec_tenant", "remediation_run_executions", ["tenant_id"])
    op.create_index("idx_run_exec_run", "remediation_run_executions", ["run_id"])
    op.create_index("idx_run_exec_status", "remediation_run_executions", ["tenant_id", "status"])
    op.create_index(
        "idx_run_exec_tenant_created",
        "remediation_run_executions",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_run_exec_tenant_created", table_name="remediation_run_executions")
    op.drop_index("idx_run_exec_status", table_name="remediation_run_executions")
    op.drop_index("idx_run_exec_run", table_name="remediation_run_executions")
    op.drop_index("idx_run_exec_tenant", table_name="remediation_run_executions")
    op.drop_table("remediation_run_executions")
    op.execute("DROP TYPE remediation_run_execution_status")
    op.execute("DROP TYPE remediation_run_execution_phase")
