"""baseline_reports table (Step 13.2)

Revision ID: 0016_baseline_reports
Revises: 0015_control_mappings
Create Date: 2026-02-03

Creates the baseline_reports table for 48h baseline report jobs.
One row per report request: status (pending/running/success/failed), S3 result, optional outcome.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_baseline_reports"
down_revision: Union[str, None] = "0015_control_mappings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE baseline_report_status AS ENUM "
        "('pending', 'running', 'success', 'failed')"
    )

    op.create_table(
        "baseline_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "running", "success", "failed",
                name="baseline_report_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("s3_bucket", sa.String(length=255), nullable=True),
        sa.Column("s3_key", sa.String(length=512), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("account_ids", postgresql.JSONB(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_baseline_reports_tenant",
        "baseline_reports",
        ["tenant_id"],
    )
    op.create_index(
        "idx_baseline_reports_tenant_created",
        "baseline_reports",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_baseline_reports_status",
        "baseline_reports",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_baseline_reports_status", table_name="baseline_reports")
    op.drop_index("idx_baseline_reports_tenant_created", table_name="baseline_reports")
    op.drop_index("idx_baseline_reports_tenant", table_name="baseline_reports")
    op.drop_table("baseline_reports")
    op.execute("DROP TYPE baseline_report_status")
