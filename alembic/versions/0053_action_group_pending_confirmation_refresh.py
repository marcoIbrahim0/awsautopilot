"""Add refresh bookkeeping for pending-confirmation action-group states.

Revision ID: 0053_action_group_pending_confirmation_refresh
Revises: 0052_action_group_run_shared_execution_results
Create Date: 2026-03-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0053_action_group_pending_confirmation_refresh"
down_revision: Union[str, Sequence[str], None] = "0052_action_group_run_shared_execution_results"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "action_group_action_state",
        sa.Column("confirmation_refresh_last_enqueued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "action_group_action_state",
        sa.Column("confirmation_refresh_next_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "action_group_action_state",
        sa.Column(
            "confirmation_refresh_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_action_group_action_state_pending_refresh_due",
        "action_group_action_state",
        ["latest_run_status_bucket", "confirmation_refresh_next_due_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_action_group_action_state_pending_refresh_due",
        table_name="action_group_action_state",
    )
    op.drop_column("action_group_action_state", "confirmation_refresh_attempt_count")
    op.drop_column("action_group_action_state", "confirmation_refresh_next_due_at")
    op.drop_column("action_group_action_state", "confirmation_refresh_last_enqueued_at")
