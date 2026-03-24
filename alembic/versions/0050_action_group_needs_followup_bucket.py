"""Add grouped member successful-needs-followup status bucket.

Revision ID: 0050_action_group_needs_followup_bucket
Revises: 0049_action_group_metadata_only_bucket
Create Date: 2026-03-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0050_action_group_needs_followup_bucket"
down_revision: Union[str, Sequence[str], None] = "0049_action_group_metadata_only_bucket"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE action_group_status_bucket "
        "ADD VALUE IF NOT EXISTS 'run_successful_needs_followup'"
    )


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally omitted; downgrade is a no-op.
    pass
