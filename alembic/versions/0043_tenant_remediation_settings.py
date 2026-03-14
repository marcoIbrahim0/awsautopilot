"""Add tenant remediation settings persistence and merge current heads.

Revision ID: 0043_tenant_remediation_settings
Revises: 0042_action_remediation_system_of_record, 0042_bidirectional_integrations
Create Date: 2026-03-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0043_tenant_remediation_settings"
down_revision: Union[str, Sequence[str], None] = (
    "0042_action_remediation_system_of_record",
    "0042_bidirectional_integrations",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "remediation_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("tenants", "remediation_settings", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "remediation_settings")
