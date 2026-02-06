"""initial models

Revision ID: 0001_initial_models
Revises:
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_models"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enum type: create once, then use postgresql.ENUM with create_type=False in table
    aws_account_status = sa.Enum("pending", "validated", "error", name="aws_account_status")
    aws_account_status.create(op.get_bind(), checkfirst=True)
    status_col = postgresql.ENUM("pending", "validated", "error", name="aws_account_status", create_type=False)

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tenants_external_id", "tenants", ["external_id"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "aws_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("role_read_arn", sa.String(length=2048), nullable=False),
        sa.Column("role_write_arn", sa.String(length=2048), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", status_col, nullable=False, server_default="pending"),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "account_id", name="uq_aws_accounts_tenant_account"),
    )
    op.create_index("ix_aws_accounts_tenant_id", "aws_accounts", ["tenant_id"])
    op.create_index("ix_aws_accounts_account_id", "aws_accounts", ["account_id"])


def downgrade():
    op.drop_index("ix_aws_accounts_account_id", table_name="aws_accounts")
    op.drop_index("ix_aws_accounts_tenant_id", table_name="aws_accounts")
    op.drop_table("aws_accounts")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_tenants_external_id", table_name="tenants")
    op.drop_table("tenants")

    sa.Enum(name="aws_account_status").drop(op.get_bind(), checkfirst=True)
