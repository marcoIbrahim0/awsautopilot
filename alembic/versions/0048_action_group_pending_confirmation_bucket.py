"""Add grouped member pending-confirmation status bucket.

Revision ID: 0048_action_group_pending_confirmation_bucket
Revises: 0047_help_assistant_live_iam_lookup
Create Date: 2026-03-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0048_action_group_pending_confirmation_bucket"
down_revision: Union[str, Sequence[str], None] = "0047_help_assistant_live_iam_lookup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE action_group_status_bucket "
        "ADD VALUE IF NOT EXISTS 'run_successful_pending_confirmation'"
    )


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally omitted; downgrade is a no-op.
    pass
