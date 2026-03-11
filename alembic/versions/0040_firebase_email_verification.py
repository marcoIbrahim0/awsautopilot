"""Add Firebase-backed email verification fields and merge current heads.

Revision ID: 0040_firebase_email_verification
Revises: 0039_action_owner_queues, 0039_action_scoring_metadata
Create Date: 2026-03-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0040_firebase_email_verification"
down_revision: Union[str, Sequence[str], None] = (
    "0039_action_owner_queues",
    "0039_action_scoring_metadata",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("firebase_uid", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verification_sync_token_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_sync_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_firebase_uid", table_name="users")
    op.drop_column("users", "email_verification_sync_expires_at")
    op.drop_column("users", "email_verification_sync_token_hash")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "firebase_uid")
