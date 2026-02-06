"""evidence_exports.pack_type (Step 12.2)

Revision ID: 0014_pack_type
Revises: 0013_slack_settings
Create Date: 2026-02-02

Adds pack_type to evidence_exports: "evidence" (Step 10 only) or "compliance"
(Step 10 + exception_attestations + control_mapping + auditor_summary).
Default "evidence" for backward compatibility.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_pack_type"
down_revision: Union[str, None] = "0013_slack_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evidence_exports",
        sa.Column(
            "pack_type",
            sa.String(length=32),
            nullable=False,
            server_default="evidence",
            comment="evidence = Step 10 only; compliance = Step 10 + attestations + control_mapping + auditor_summary",
        ),
    )


def downgrade() -> None:
    op.drop_column("evidence_exports", "pack_type")
