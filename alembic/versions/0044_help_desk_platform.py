"""Add help desk platform tables.

Revision ID: 0044_help_desk_platform
Revises: 0043_notification_center, 0043_tenant_remediation_settings
Create Date: 2026-03-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0044_help_desk_platform"
down_revision: Union[str, Sequence[str], None] = (
    "0043_notification_center",
    "0043_tenant_remediation_settings",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "help_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=32), nullable=False, server_default="customer"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("related_routes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_help_articles_slug", "help_articles", ["slug"])

    op.create_table(
        "help_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_saas_admin_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("current_path", sa.Text(), nullable=True),
        sa.Column("referenced_entities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_saas_admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_help_cases_tenant_status", "help_cases", ["tenant_id", "status"])
    op.create_index("ix_help_cases_requester_created", "help_cases", ["requester_user_id", "created_at"])
    op.create_index("ix_help_cases_assignee_status", "help_cases", ["assigned_saas_admin_user_id", "status"])
    op.create_index("ix_help_cases_tenant_last_message", "help_cases", ["tenant_id", "last_message_at"])

    op.create_table(
        "help_case_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("internal_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["help_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_help_case_messages_case_created", "help_case_messages", ["case_id", "created_at"])
    op.create_index("ix_help_case_messages_tenant_created", "help_case_messages", ["tenant_id", "created_at"])

    op.create_table(
        "help_case_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("s3_bucket", sa.String(length=255), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("internal_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["help_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["help_case_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_help_case_attachments_case_created", "help_case_attachments", ["case_id", "created_at"])
    op.create_index("ix_help_case_attachments_message", "help_case_attachments", ["message_id"])

    op.create_table(
        "help_assistant_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("escalated_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("current_path", sa.Text(), nullable=True),
        sa.Column("request_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cited_article_slugs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("referenced_entities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("suggested_case", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("helpful", sa.Boolean(), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["escalated_case_id"], ["help_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_help_assistant_interactions_tenant_created", "help_assistant_interactions", ["tenant_id", "created_at"])
    op.create_index("ix_help_assistant_interactions_user_created", "help_assistant_interactions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_help_assistant_interactions_user_created", table_name="help_assistant_interactions")
    op.drop_index("ix_help_assistant_interactions_tenant_created", table_name="help_assistant_interactions")
    op.drop_table("help_assistant_interactions")
    op.drop_index("ix_help_case_attachments_message", table_name="help_case_attachments")
    op.drop_index("ix_help_case_attachments_case_created", table_name="help_case_attachments")
    op.drop_table("help_case_attachments")
    op.drop_index("ix_help_case_messages_tenant_created", table_name="help_case_messages")
    op.drop_index("ix_help_case_messages_case_created", table_name="help_case_messages")
    op.drop_table("help_case_messages")
    op.drop_index("ix_help_cases_tenant_last_message", table_name="help_cases")
    op.drop_index("ix_help_cases_assignee_status", table_name="help_cases")
    op.drop_index("ix_help_cases_requester_created", table_name="help_cases")
    op.drop_index("ix_help_cases_tenant_status", table_name="help_cases")
    op.drop_table("help_cases")
    op.drop_index("ix_help_articles_slug", table_name="help_articles")
    op.drop_table("help_articles")
