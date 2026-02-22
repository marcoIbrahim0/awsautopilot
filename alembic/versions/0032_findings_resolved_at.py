"""add resolved_at to findings

Revision ID: 0032_findings_resolved_at
Revises: 0031_control_plane_token_hash
Create Date: 2026-02-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0032_findings_resolved_at"
down_revision: Union[str, None] = "0031_control_plane_token_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE findings
            SET resolved_at = COALESCE(last_observed_at, sh_updated_at, updated_at, NOW())
            WHERE status = 'RESOLVED' AND resolved_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("findings", "resolved_at")
