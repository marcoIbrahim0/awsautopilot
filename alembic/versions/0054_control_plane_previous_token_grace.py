"""Add bounded grace support for the previous control-plane token.

Revision ID: 0054_control_plane_previous_token_grace
Revises: 0053_action_group_pending_confirmation_refresh
Create Date: 2026-03-30
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0054_control_plane_previous_token_grace"
down_revision: Union[str, Sequence[str], None] = "0053_action_group_pending_confirmation_refresh"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("control_plane_previous_token", sa.String(length=255), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("control_plane_previous_token_fingerprint", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("control_plane_previous_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "control_plane_previous_token_expires_at")
    op.drop_column("tenants", "control_plane_previous_token_fingerprint")
    op.drop_column("tenants", "control_plane_previous_token")
