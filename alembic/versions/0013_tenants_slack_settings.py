"""tenants Slack settings (Step 11.4)

Revision ID: 0013_slack_settings
Revises: 0012_digest_preferences
Create Date: 2026-02-02

Adds slack_webhook_url and slack_digest_enabled to tenants for optional
weekly digest delivery to Slack. Webhook URL is secret; do not log in full.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_slack_settings"
down_revision: Union[str, None] = "0012_digest_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "slack_webhook_url",
            sa.Text(),
            nullable=True,
            comment="Slack incoming webhook URL; secret, do not log in full.",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "slack_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="If true and slack_webhook_url set, weekly digest is posted to Slack.",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "slack_digest_enabled")
    op.drop_column("tenants", "slack_webhook_url")
