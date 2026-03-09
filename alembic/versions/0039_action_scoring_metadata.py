"""action scoring metadata

Revision ID: 0039_action_scoring_metadata
Revises: 0038_user_verification_mfa
Create Date: 2026-03-09
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0039_action_scoring_metadata"
down_revision: Union[str, None] = "0038_user_verification_mfa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "actions",
        sa.Column("score", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "actions",
        sa.Column(
            "score_components",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute("UPDATE actions SET score = COALESCE(priority, 0)")
    op.create_index(
        "idx_actions_tenant_score",
        "actions",
        ["tenant_id", "score"],
        postgresql_ops={"score": "DESC"},
    )
    op.alter_column("actions", "score", server_default=None)
    op.alter_column("actions", "score_components", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_actions_tenant_score", table_name="actions")
    op.drop_column("actions", "score_components")
    op.drop_column("actions", "score")
