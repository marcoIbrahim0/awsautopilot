"""exceptions table (Step 6.1)

Revision ID: 0006_exceptions
Revises: 0005_action_findings
Create Date: 2026-02-01

Creates the exceptions table for suppressions with reason, approver, and expiry.
One exception per distinct (tenant, entity_type, entity_id).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_exceptions"
down_revision: Union[str, None] = "0005_action_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create entity_type enum
    op.execute("CREATE TYPE entity_type AS ENUM ('finding', 'action')")
    
    # Create exceptions table
    op.create_table(
        "exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            postgresql.ENUM("finding", "action", name="entity_type", create_type=False),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticket_link", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    
    # Create indexes
    op.create_index("idx_exceptions_tenant", "exceptions", ["tenant_id"])
    op.create_index("idx_exceptions_entity", "exceptions", ["tenant_id", "entity_type", "entity_id"])
    op.create_index("idx_exceptions_expires_at", "exceptions", ["tenant_id", "expires_at"])
    
    # Create unique constraint
    op.create_unique_constraint(
        "uq_exceptions_tenant_entity",
        "exceptions",
        ["tenant_id", "entity_type", "entity_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_exceptions_tenant_entity", "exceptions", type_="unique")
    op.drop_index("idx_exceptions_expires_at", table_name="exceptions")
    op.drop_index("idx_exceptions_entity", table_name="exceptions")
    op.drop_index("idx_exceptions_tenant", table_name="exceptions")
    op.drop_table("exceptions")
    op.execute("DROP TYPE entity_type")
