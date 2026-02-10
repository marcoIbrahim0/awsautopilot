"""support notes and files tables for SaaS admin dashboard

Revision ID: 0018_support_notes_files
Revises: 0017_aws_account_disabled
Create Date: 2026-02-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_support_notes_files"
down_revision: Union[str, None] = "0017_aws_account_disabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_support_notes_tenant_id", "support_notes", ["tenant_id"])
    op.create_index("idx_support_notes_tenant_created", "support_notes", ["tenant_id", "created_at"])

    op.create_table(
        "support_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("s3_bucket", sa.String(length=255), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending_upload", nullable=False),
        sa.Column("visible_to_tenant", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_support_files_tenant_id", "support_files", ["tenant_id"])
    op.create_index("idx_support_files_tenant_created", "support_files", ["tenant_id", "created_at"])
    op.create_index("idx_support_files_tenant_status", "support_files", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_support_files_tenant_status", table_name="support_files")
    op.drop_index("idx_support_files_tenant_created", table_name="support_files")
    op.drop_index("ix_support_files_tenant_id", table_name="support_files")
    op.drop_table("support_files")

    op.drop_index("idx_support_notes_tenant_created", table_name="support_notes")
    op.drop_index("ix_support_notes_tenant_id", table_name="support_notes")
    op.drop_table("support_notes")
