"""tenant control-plane token

Revision ID: 0024_tenant_cp_token
Revises: 0023_cp_reconcile_jobs
Create Date: 2026-02-10
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_tenant_cp_token"
down_revision: Union[str, None] = "0023_cp_reconcile_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("control_plane_token", sa.String(length=255), nullable=True),
    )

    # Backfill existing tenants with a unique per-tenant token.
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM tenants WHERE control_plane_token IS NULL")).fetchall()
    for (tenant_id,) in rows:
        token = f"cptok-{uuid.uuid4().hex}"
        bind.execute(
            sa.text("UPDATE tenants SET control_plane_token = :token WHERE id = :tenant_id"),
            {"token": token, "tenant_id": tenant_id},
        )

    op.alter_column(
        "tenants",
        "control_plane_token",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.create_index(
        "ix_tenants_control_plane_token",
        "tenants",
        ["control_plane_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_control_plane_token", table_name="tenants")
    op.drop_column("tenants", "control_plane_token")

