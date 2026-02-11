"""canonical control/resource keys for overlay and promotion

Revision ID: 0026_canonical_keys
Revises: 0025_cp_event_status
Create Date: 2026-02-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0026_canonical_keys"
down_revision: Union[str, None] = "0025_cp_event_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("canonical_control_id", sa.String(length=64), nullable=True))
    op.add_column("findings", sa.Column("resource_key", sa.String(length=512), nullable=True))
    op.create_index(
        "ix_findings_tenant_canonical_key",
        "findings",
        ["tenant_id", "canonical_control_id", "resource_key"],
    )

    op.add_column("finding_shadow_states", sa.Column("canonical_control_id", sa.String(length=64), nullable=True))
    op.add_column("finding_shadow_states", sa.Column("resource_key", sa.String(length=512), nullable=True))
    op.create_index(
        "ix_finding_shadow_states_tenant_canonical_key",
        "finding_shadow_states",
        ["tenant_id", "canonical_control_id", "resource_key", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_finding_shadow_states_tenant_canonical_key", table_name="finding_shadow_states")
    op.drop_column("finding_shadow_states", "resource_key")
    op.drop_column("finding_shadow_states", "canonical_control_id")

    op.drop_index("ix_findings_tenant_canonical_key", table_name="findings")
    op.drop_column("findings", "resource_key")
    op.drop_column("findings", "canonical_control_id")

