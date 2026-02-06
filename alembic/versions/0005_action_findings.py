"""action_findings association table (Step 5.2)

Revision ID: 0005_action_findings
Revises: 0004_actions
Create Date: 2026-01-31

Creates the action_findings many-to-many table linking actions to findings.
Supports drill-down from action to source findings and evidence.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_action_findings"
down_revision: Union[str, None] = "0004_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "action_findings",
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_action_findings_action",
        "action_findings",
        ["action_id"],
    )
    op.create_index(
        "idx_action_findings_finding",
        "action_findings",
        ["finding_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_action_findings_finding", table_name="action_findings")
    op.drop_index("idx_action_findings_action", table_name="action_findings")
    op.drop_table("action_findings")
