"""actions table (Step 5.1)

Revision ID: 0004_actions
Revises: 0003_auth_user_fields_invites
Create Date: 2026-01-31

Creates the actions table for aggregated, deduplicated units of work
derived from findings. One action per distinct (tenant, action_type, target_id, account_id, region).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_actions"
down_revision: Union[str, None] = "0003_auth_user_fields_invites"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=512), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=2048), nullable=True),
        sa.Column("resource_type", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_actions_tenant_status", "actions", ["tenant_id", "status"])
    op.create_index(
        "idx_actions_tenant_priority",
        "actions",
        ["tenant_id", "priority"],
        postgresql_ops={"priority": "DESC"},
    )
    op.create_index("idx_actions_tenant_account_region", "actions", ["tenant_id", "account_id", "region"])
    op.create_index("ix_actions_tenant_id", "actions", ["tenant_id"])
    # Dedupe: one action per distinct target per tenant (region NULL treated as '' for uniqueness)
    op.execute(
        "CREATE UNIQUE INDEX uq_actions_tenant_target ON actions "
        "(tenant_id, action_type, target_id, account_id, COALESCE(region, ''))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_actions_tenant_target")
    op.drop_index("idx_actions_tenant_account_region", table_name="actions")
    op.drop_index("idx_actions_tenant_priority", table_name="actions")
    op.drop_index("idx_actions_tenant_status", table_name="actions")
    op.drop_index("ix_actions_tenant_id", table_name="actions")
    op.drop_table("actions")
