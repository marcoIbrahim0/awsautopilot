"""findings.source column (Step 2B.1)

Revision ID: 0010_findings_source
Revises: 0009_evidence_exports
Create Date: 2026-02-02

Adds source column to findings for optional data sources (e.g. security_hub, access_analyzer).
Updates unique constraint to (finding_id, account_id, region, source) so findings from
different sources can coexist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_findings_source"
down_revision: Union[str, None] = "0009_evidence_exports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="security_hub"),
    )
    op.drop_constraint(
        "uq_findings_finding_id_account_region",
        "findings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_findings_finding_id_account_region_source",
        "findings",
        ["finding_id", "account_id", "region", "source"],
    )
    op.create_index(
        "ix_findings_tenant_source",
        "findings",
        ["tenant_id", "source"],
    )


def downgrade() -> None:
    op.drop_index("ix_findings_tenant_source", table_name="findings")
    op.drop_constraint(
        "uq_findings_finding_id_account_region_source",
        "findings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_findings_finding_id_account_region",
        "findings",
        ["finding_id", "account_id", "region"],
    )
    op.drop_column("findings", "source")
