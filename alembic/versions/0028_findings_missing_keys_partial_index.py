"""partial index for in-scope findings missing canonical/resource keys

Revision ID: 0028_findings_missing_keys_index
Revises: 0027_findings_scope_shadow
Create Date: 2026-02-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0028_findings_missing_keys_index"
down_revision: Union[str, None] = "0027_findings_scope_shadow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_findings_in_scope_missing_keys",
        "findings",
        ["tenant_id", "account_id", "region", "updated_at"],
        unique=False,
        postgresql_where=sa.text(
            "source = 'security_hub' AND in_scope IS TRUE "
            "AND (canonical_control_id IS NULL OR resource_key IS NULL)"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_findings_in_scope_missing_keys", table_name="findings")
