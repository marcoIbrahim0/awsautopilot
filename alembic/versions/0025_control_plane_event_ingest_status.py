"""control-plane event ingest status

Revision ID: 0025_cp_event_status
Revises: 0024_tenant_cp_token
Create Date: 2026-02-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_cp_event_status"
down_revision: Union[str, None] = "0024_tenant_cp_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "control_plane_event_ingest_status",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), primary_key=True, nullable=False),
        sa.Column("region", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("last_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_intake_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_cp_event_ingest_status_tenant",
        "control_plane_event_ingest_status",
        ["tenant_id"],
    )
    op.create_index(
        "ix_cp_event_ingest_status_tenant_account",
        "control_plane_event_ingest_status",
        ["tenant_id", "account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_cp_event_ingest_status_tenant_account", table_name="control_plane_event_ingest_status")
    op.drop_index("ix_cp_event_ingest_status_tenant", table_name="control_plane_event_ingest_status")
    op.drop_table("control_plane_event_ingest_status")

