"""audit_log table (Step 7.5)

Revision ID: 0008_audit_log
Revises: 0007_remediation_runs
Create Date: 2026-02-02

Creates the audit_log table for one-line summary events (e.g. remediation_run_completed).
Optional denormalized log for compliance dashboards; remediation_runs remains the primary audit record.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008_audit_log"
down_revision: Union[str, None] = "0007_remediation_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
    )
    op.create_index("idx_audit_log_tenant", "audit_log", ["tenant_id"])
    op.create_index(
        "idx_audit_log_tenant_timestamp",
        "audit_log",
        ["tenant_id", "timestamp"],
        postgresql_ops={"timestamp": "DESC"},
    )
    op.create_index("idx_audit_log_event_type", "audit_log", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_audit_log_event_type", table_name="audit_log")
    op.drop_index("idx_audit_log_tenant_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_log_tenant", table_name="audit_log")
    op.drop_table("audit_log")
