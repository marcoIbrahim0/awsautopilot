"""findings unique constraint scoped by tenant

Revision ID: 0019_findings_unique_tenant
Revises: 0018_support_notes_files
Create Date: 2026-02-08

Fixes findings uniqueness so different tenants can ingest the same AWS account
without cross-tenant collisions.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0019_findings_unique_tenant"
down_revision: Union[str, None] = "0018_support_notes_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_findings_finding_id_account_region_source",
        "findings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_findings_tenant_finding_id_account_region_source",
        "findings",
        ["tenant_id", "finding_id", "account_id", "region", "source"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_findings_tenant_finding_id_account_region_source",
        "findings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_findings_finding_id_account_region_source",
        "findings",
        ["finding_id", "account_id", "region", "source"],
    )

