"""tenants digest preferences (Step 11.3)

Revision ID: 0012_digest_preferences
Revises: 0011_last_digest_sent_at
Create Date: 2026-02-02

Adds digest_enabled and digest_recipients to tenants for optional weekly digest
preferences: only send if enabled; use custom recipients or default to admin users.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_digest_preferences"
down_revision: Union[str, None] = "0011_last_digest_sent_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "digest_recipients",
            sa.Text(),
            nullable=True,
            comment="Comma-separated email addresses; if null, digest goes to tenant admins.",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "digest_recipients")
    op.drop_column("tenants", "digest_enabled")
