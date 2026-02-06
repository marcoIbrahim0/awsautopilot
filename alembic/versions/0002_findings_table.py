"""findings table

Revision ID: 0002_findings
Revises: 0001_initial_models
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_findings"
down_revision = "0001_initial_models"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("finding_id", sa.String(length=512), nullable=False),
        sa.Column("severity_label", sa.String(length=32), nullable=False),
        sa.Column("severity_normalized", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.String(length=2048), nullable=True),
        sa.Column("resource_type", sa.String(length=256), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=True),
        sa.Column("standard_name", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sh_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("finding_id", "account_id", "region", name="uq_findings_finding_id_account_region"),
    )
    op.create_index("ix_findings_tenant_id", "findings", ["tenant_id"])
    op.create_index("ix_findings_account_id", "findings", ["account_id"])
    op.create_index("ix_findings_tenant_account_region", "findings", ["tenant_id", "account_id", "region"])
    op.create_index("ix_findings_tenant_severity_status", "findings", ["tenant_id", "severity_label", "status"])
    op.create_index("ix_findings_tenant_updated", "findings", ["tenant_id", "updated_at"])


def downgrade():
    op.drop_index("ix_findings_tenant_updated", table_name="findings")
    op.drop_index("ix_findings_tenant_severity_status", table_name="findings")
    op.drop_index("ix_findings_tenant_account_region", table_name="findings")
    op.drop_index("ix_findings_account_id", table_name="findings")
    op.drop_index("ix_findings_tenant_id", table_name="findings")
    op.drop_table("findings")
