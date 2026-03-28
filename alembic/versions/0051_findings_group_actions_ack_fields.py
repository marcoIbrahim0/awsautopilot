"""Add findings risk-acknowledgement fields for grouped actions.

Revision ID: 0051_findings_group_actions_ack_fields
Revises: 0050_action_group_needs_followup_bucket
Create Date: 2026-03-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0051_findings_group_actions_ack_fields"
down_revision: Union[str, Sequence[str], None] = "0050_action_group_needs_followup_bucket"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("risk_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("findings", sa.Column("risk_acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "findings",
        sa.Column("risk_acknowledged_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("findings", sa.Column("risk_acknowledged_group_key", sa.String(length=512), nullable=True))

    op.create_foreign_key(
        "fk_findings_risk_acknowledged_by_user_id_users",
        "findings",
        "users",
        ["risk_acknowledged_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_findings_tenant_risk_acknowledged",
        "findings",
        ["tenant_id", "risk_acknowledged"],
    )


def downgrade() -> None:
    op.drop_index("ix_findings_tenant_risk_acknowledged", table_name="findings")
    op.drop_constraint("fk_findings_risk_acknowledged_by_user_id_users", "findings", type_="foreignkey")
    op.drop_column("findings", "risk_acknowledged_group_key")
    op.drop_column("findings", "risk_acknowledged_by_user_id")
    op.drop_column("findings", "risk_acknowledged_at")
    op.drop_column("findings", "risk_acknowledged")
