"""Add action ownership fields for owner-based queues.

Revision ID: 0039_action_owner_queues
Revises: 0038_user_verification_mfa
Create Date: 2026-03-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0039_action_owner_queues"
down_revision: Union[str, None] = "0038_user_verification_mfa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "actions",
        sa.Column("owner_type", sa.String(length=32), nullable=False, server_default=sa.text("'unassigned'")),
    )
    op.add_column(
        "actions",
        sa.Column("owner_key", sa.String(length=255), nullable=False, server_default=sa.text("'unassigned'")),
    )
    op.add_column(
        "actions",
        sa.Column("owner_label", sa.String(length=255), nullable=False, server_default=sa.text("'Unassigned'")),
    )
    op.create_index("idx_actions_tenant_owner", "actions", ["tenant_id", "owner_type", "owner_key"])


def downgrade() -> None:
    op.drop_index("idx_actions_tenant_owner", table_name="actions")
    op.drop_column("actions", "owner_label")
    op.drop_column("actions", "owner_key")
    op.drop_column("actions", "owner_type")
