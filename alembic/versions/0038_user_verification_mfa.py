"""Add user contact verification and MFA fields.

Revision ID: 0038_user_verification_mfa
Revises: 0037_comm_governance_layer
Create Date: 2026-03-02

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0038_user_verification_mfa"
down_revision: Union[str, None] = "0037_comm_governance_layer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(length=32), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("mfa_method", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("email_verification_code_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("phone_verification_code_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("phone_verification_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("mfa_challenge_code_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("mfa_challenge_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("mfa_challenge_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_users_mfa_challenge_token_hash",
        "users",
        ["mfa_challenge_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_users_mfa_challenge_token_hash", table_name="users")
    op.drop_column("users", "mfa_challenge_expires_at")
    op.drop_column("users", "mfa_challenge_token_hash")
    op.drop_column("users", "mfa_challenge_code_hash")
    op.drop_column("users", "phone_verification_expires_at")
    op.drop_column("users", "phone_verification_code_hash")
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_code_hash")
    op.drop_column("users", "mfa_method")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "phone_verified")
    op.drop_column("users", "phone_number")
