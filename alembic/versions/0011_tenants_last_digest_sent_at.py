"""tenants.last_digest_sent_at (Step 11.1)

Revision ID: 0011_last_digest_sent_at
Revises: 0010_findings_source
Create Date: 2026-02-02

Adds last_digest_sent_at to tenants for weekly digest idempotency:
duplicate cron invocations do not send twice per tenant per week.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_last_digest_sent_at"
down_revision: Union[str, None] = "0010_findings_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "last_digest_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "last_digest_sent_at")
