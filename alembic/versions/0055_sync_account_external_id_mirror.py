"""sync aws account external_id mirror to tenant canonical external_id

Revision ID: 0055_sync_account_external_id_mirror
Revises: 0054_control_plane_previous_token_grace
Create Date: 2026-04-01 22:30:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0055_sync_account_external_id_mirror"
down_revision = "0054_control_plane_previous_token_grace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE aws_accounts AS account
        SET external_id = tenant.external_id
        FROM tenants AS tenant
        WHERE tenant.id = account.tenant_id
          AND account.external_id IS DISTINCT FROM tenant.external_id
        """
    )


def downgrade() -> None:
    # Data backfill only; no safe downgrade.
    pass
