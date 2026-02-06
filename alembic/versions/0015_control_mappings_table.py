"""control_mappings table (Step 12.3)

Revision ID: 0015_control_mappings
Revises: 0014_pack_type
Create Date: 2026-02-02

Creates the control_mappings table for v1 mapping: control_id (e.g. S3.1, CloudTrail.1)
→ framework (SOC 2, CIS, ISO 27001) → control code and title. Seeds with minimal v1 data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0015_control_mappings"
down_revision: Union[str, None] = "0014_pack_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Minimal v1 seed data (same as compliance_pack_spec.CONTROL_MAPPING_V1)
SEED_ROWS = [
    ("S3.1", "CIS AWS Foundations Benchmark", "3.1", "Ensure S3 block public access", "S3 account-level block public access"),
    ("S3.1", "SOC 2", "CC6.1", "Logical access", "Logical and physical access controls"),
    ("CloudTrail.1", "CIS AWS Foundations Benchmark", "3.2", "Ensure CloudTrail in all regions", "CloudTrail multi-region"),
    ("CloudTrail.1", "SOC 2", "CC7.2", "System monitoring", "Monitoring of system operations"),
    ("CloudTrail.1", "ISO 27001", "A.12.4.1", "Event logging", "Event logs for audit"),
    ("GuardDuty.1", "CIS AWS Foundations Benchmark", "4.1", "Ensure GuardDuty enabled", "GuardDuty threat detection"),
    ("GuardDuty.1", "SOC 2", "CC7.2", "System monitoring", "Threat detection and monitoring"),
    ("SecurityHub.1", "CIS AWS Foundations Benchmark", "4.2", "Ensure Security Hub enabled", "Security Hub standards"),
]


def upgrade() -> None:
    op.create_table(
        "control_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column("framework_name", sa.String(length=128), nullable=False),
        sa.Column("framework_control_code", sa.String(length=64), nullable=False),
        sa.Column("control_title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_control_mappings_control_id", "control_mappings", ["control_id"])
    op.create_index("idx_control_mappings_framework", "control_mappings", ["framework_name"])
    op.create_unique_constraint(
        "uq_control_mappings_control_framework",
        "control_mappings",
        ["control_id", "framework_name"],
    )

    # Seed v1 mapping data
    conn = op.get_bind()
    for row in SEED_ROWS:
        control_id, framework_name, framework_control_code, control_title, description = row
        conn.execute(
            sa.text(
                """
                INSERT INTO control_mappings (id, control_id, framework_name, framework_control_code, control_title, description)
                VALUES (gen_random_uuid(), :control_id, :framework_name, :framework_control_code, :control_title, :description)
                """
            ),
            {
                "control_id": control_id,
                "framework_name": framework_name,
                "framework_control_code": framework_control_code,
                "control_title": control_title,
                "description": description,
            },
        )


def downgrade() -> None:
    op.drop_constraint("uq_control_mappings_control_framework", "control_mappings", type_="unique")
    op.drop_index("idx_control_mappings_framework", table_name="control_mappings")
    op.drop_index("idx_control_mappings_control_id", table_name="control_mappings")
    op.drop_table("control_mappings")
