"""Add per-account Help Hub live IAM lookup controls.

Revision ID: 0047_help_assistant_live_iam_lookup
Revises: 0046_attack_path_materialized_read_model
Create Date: 2026-03-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0047_help_assistant_live_iam_lookup"
down_revision: Union[str, Sequence[str], None] = "0046_attack_path_materialized_read_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aws_accounts",
        sa.Column("ai_live_lookup_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "aws_accounts",
        sa.Column("ai_live_lookup_scope", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "aws_accounts",
        sa.Column("ai_live_lookup_enabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "aws_accounts",
        sa.Column("ai_live_lookup_enabled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "aws_accounts",
        sa.Column("ai_live_lookup_notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_aws_accounts_ai_live_lookup_enabled_by_user_id",
        "aws_accounts",
        "users",
        ["ai_live_lookup_enabled_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_aws_accounts_ai_live_lookup_enabled_by_user_id",
        "aws_accounts",
        type_="foreignkey",
    )
    op.drop_column("aws_accounts", "ai_live_lookup_notes")
    op.drop_column("aws_accounts", "ai_live_lookup_enabled_by_user_id")
    op.drop_column("aws_accounts", "ai_live_lookup_enabled_at")
    op.drop_column("aws_accounts", "ai_live_lookup_scope")
    op.drop_column("aws_accounts", "ai_live_lookup_enabled")
