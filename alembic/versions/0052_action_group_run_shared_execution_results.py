"""Add shared execution diagnostics to action_group_runs.

Revision ID: 0052_action_group_run_shared_execution_results
Revises: 0051_findings_group_actions_ack_fields
Create Date: 2026-03-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0052_action_group_run_shared_execution_results"
down_revision: Union[str, Sequence[str], None] = "0051_findings_group_actions_ack_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "action_group_runs",
        sa.Column("shared_execution_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("action_group_runs", "shared_execution_results")
