"""add unique active-run guard for remediation_runs

Revision ID: 0034_remrun_active_unique_guard
Revises: 0033_user_auth_reset_fields
Create Date: 2026-03-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0034_remrun_active_unique_guard"
down_revision: Union[str, None] = "0033_user_auth_reset_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_remediation_runs_action_active",
        "remediation_runs",
        ["tenant_id", "action_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending','running','awaiting_approval')"),
    )


def downgrade() -> None:
    op.drop_index("uq_remediation_runs_action_active", table_name="remediation_runs")
