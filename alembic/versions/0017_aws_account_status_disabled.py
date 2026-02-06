"""Add disabled status to aws_account_status enum

Revision ID: 0017_aws_account_disabled
Revises: 0016_baseline_reports
Create Date: 2026-02-04

Allows clients to "stop" an AWS account (set status to disabled) so ingestion
and remediation are skipped without removing the account.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017_aws_account_disabled"
down_revision: Union[str, None] = "0016_baseline_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE aws_account_status ADD VALUE IF NOT EXISTS 'disabled'")


def downgrade() -> None:
    # PostgreSQL does not support removing an enum value; existing rows with
    # 'disabled' would need to be updated first. No-op for safety.
    pass
