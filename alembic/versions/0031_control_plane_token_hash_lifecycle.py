"""control-plane token hash lifecycle metadata

Revision ID: 0031_control_plane_token_hash
Revises: 0030_action_groups_persistent
Create Date: 2026-02-17
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0031_control_plane_token_hash"
down_revision: Union[str, None] = "0030_action_groups_persistent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_fingerprint(token: str) -> str:
    if len(token) <= 12:
        return token
    return f"{token[:8]}...{token[-4:]}"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("control_plane_token_fingerprint", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("control_plane_token_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("control_plane_token_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, control_plane_token, created_at FROM tenants"),
    ).fetchall()

    now = datetime.now(timezone.utc)
    for tenant_id, raw_token, tenant_created_at in rows:
        normalized = str(raw_token or "").strip() or f"legacy-{tenant_id}"
        bind.execute(
            sa.text(
                "UPDATE tenants "
                "SET control_plane_token = :token_hash, "
                "control_plane_token_fingerprint = :token_fingerprint, "
                "control_plane_token_created_at = :token_created_at "
                "WHERE id = :tenant_id"
            ),
            {
                "tenant_id": tenant_id,
                "token_hash": _token_hash(normalized),
                "token_fingerprint": _token_fingerprint(normalized),
                "token_created_at": tenant_created_at or now,
            },
        )


def downgrade() -> None:
    op.drop_column("tenants", "control_plane_token_revoked_at")
    op.drop_column("tenants", "control_plane_token_created_at")
    op.drop_column("tenants", "control_plane_token_fingerprint")
