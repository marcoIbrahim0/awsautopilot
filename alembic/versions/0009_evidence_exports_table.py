"""evidence_exports table (Step 10.1)

Revision ID: 0009_evidence_exports
Revises: 0008_audit_log
Create Date: 2026-02-02

Creates the evidence_exports table for evidence pack export jobs.
One row per export request: status (pending/running/success/failed), S3 result location.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009_evidence_exports"
down_revision: Union[str, None] = "0008_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE evidence_export_status AS ENUM "
        "('pending', 'running', 'success', 'failed')"
    )

    op.create_table(
        "evidence_exports",
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
                name="evidence_export_status",
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
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("s3_bucket", sa.String(length=255), nullable=True),
        sa.Column("s3_key", sa.String(length=512), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("idx_evidence_exports_tenant", "evidence_exports", ["tenant_id"])
    op.create_index(
        "idx_evidence_exports_tenant_created",
        "evidence_exports",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index("idx_evidence_exports_status", "evidence_exports", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_evidence_exports_status", table_name="evidence_exports")
    op.drop_index("idx_evidence_exports_tenant_created", table_name="evidence_exports")
    op.drop_index("idx_evidence_exports_tenant", table_name="evidence_exports")
    op.drop_table("evidence_exports")
    op.execute("DROP TYPE evidence_export_status")
