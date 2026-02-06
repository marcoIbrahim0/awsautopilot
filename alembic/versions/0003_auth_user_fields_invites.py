"""Add auth fields to users table and create user_invites table.

Step 4.1: Support passwords, roles, and onboarding state on User;
support invite-by-email with a token.

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_auth_user_fields_invites"
down_revision: Union[str, None] = "0002_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_role enum type
    user_role_enum = postgresql.ENUM("admin", "member", name="user_role", create_type=False)
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # Add new columns to users table
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Enum("admin", "member", name="user_role", create_type=False),
            nullable=False,
            server_default="member",
        ),
    )
    op.add_column(
        "users",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create user_invites table
    op.create_table(
        "user_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("token", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Unique constraint: one pending invite per email per tenant
        sa.UniqueConstraint("tenant_id", "email", name="uq_user_invites_tenant_email"),
    )


def downgrade() -> None:
    # Drop user_invites table
    op.drop_table("user_invites")

    # Remove columns from users table
    op.drop_column("users", "onboarding_completed_at")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")

    # Drop enum type
    user_role_enum = postgresql.ENUM("admin", "member", name="user_role", create_type=False)
    user_role_enum.drop(op.get_bind(), checkfirst=True)
