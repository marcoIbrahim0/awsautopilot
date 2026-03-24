"""Add grouped metadata-only terminal status bucket.

Revision ID: 0049_action_group_metadata_only_bucket
Revises: 0048_action_group_pending_confirmation_bucket
Create Date: 2026-03-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0049_action_group_metadata_only_bucket"
down_revision: Union[str, Sequence[str], None] = "0048_action_group_pending_confirmation_bucket"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE action_group_status_bucket "
        "ADD VALUE IF NOT EXISTS 'run_finished_metadata_only'"
    )


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally omitted; downgrade is a no-op.
    pass
