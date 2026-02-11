"""findings in_scope flag and shadow overlay fields

Revision ID: 0027_findings_scope_shadow
Revises: 0026_canonical_keys
Create Date: 2026-02-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0027_findings_scope_shadow"
down_revision: Union[str, None] = "0026_canonical_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Frozen copy of backend.services.control_scope.IN_SCOPE_CONTROL_TOKENS (uppercased).
_IN_SCOPE_TOKENS: tuple[str, ...] = (
    "S3.1",
    "SECURITYHUB.1",
    "GUARDDUTY.1",
    "S3.2",
    "S3.4",
    "EC2.53",
    "CLOUDTRAIL.1",
    "CONFIG.1",
    "SSM.7",
    "EC2.182",
    "EC2.7",
    "S3.5",
    "IAM.4",
    "S3.9",
    "S3.11",
    "S3.15",
    # Aliases
    "S3.3",
    "S3.8",
    "S3.17",
    "EC2.13",
    "EC2.18",
    "EC2.19",
)


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("in_scope", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_findings_tenant_in_scope",
        "findings",
        ["tenant_id", "in_scope"],
    )

    # Denormalized shadow overlay fields (Phase 1/2 wiring).
    op.add_column("findings", sa.Column("shadow_status_raw", sa.String(length=32), nullable=True))
    op.add_column("findings", sa.Column("shadow_status_normalized", sa.String(length=32), nullable=True))
    op.add_column("findings", sa.Column("shadow_status_reason", sa.Text(), nullable=True))
    op.add_column(
        "findings",
        sa.Column("shadow_last_observed_event_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("shadow_last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("findings", sa.Column("shadow_fingerprint", sa.String(length=1024), nullable=True))
    op.add_column("findings", sa.Column("shadow_source", sa.String(length=32), nullable=True))

    # Backfill in_scope from existing control_id/canonical_control_id.
    tokens_sql = ", ".join(f"'{t}'" for t in _IN_SCOPE_TOKENS)
    op.execute(
        f"""
        UPDATE findings
        SET in_scope = true
        WHERE (
            canonical_control_id IS NOT NULL
            AND upper(canonical_control_id) IN ({tokens_sql})
        ) OR (
            canonical_control_id IS NULL
            AND control_id IS NOT NULL
            AND upper(substring(control_id, '([A-Za-z][A-Za-z0-9]*\\.[0-9]+)$')) IN ({tokens_sql})
        );
        """
    )


def downgrade() -> None:
    op.drop_index("ix_findings_tenant_in_scope", table_name="findings")
    op.drop_column("findings", "shadow_source")
    op.drop_column("findings", "shadow_fingerprint")
    op.drop_column("findings", "shadow_last_evaluated_at")
    op.drop_column("findings", "shadow_last_observed_event_time")
    op.drop_column("findings", "shadow_status_reason")
    op.drop_column("findings", "shadow_status_normalized")
    op.drop_column("findings", "shadow_status_raw")
    op.drop_column("findings", "in_scope")

