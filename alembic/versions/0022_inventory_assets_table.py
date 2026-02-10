"""inventory assets table for phase-2 reconciliation

Revision ID: 0022_inventory_assets
Revises: 0021_control_plane_shadow
Create Date: 2026-02-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_inventory_assets"
down_revision: Union[str, None] = "0021_control_plane_shadow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=2048), nullable=False),
        sa.Column("resource_type", sa.String(length=256), nullable=True),
        sa.Column("key_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("state_size_bytes", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reconcile_mode", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            "region",
            "service",
            "resource_id",
            name="uq_inventory_assets_tenant_account_region_service_resource",
        ),
    )
    op.create_index("ix_inventory_assets_tenant_id", "inventory_assets", ["tenant_id"])
    op.create_index("ix_inventory_assets_account_id", "inventory_assets", ["account_id"])
    op.create_index(
        "ix_inventory_assets_tenant_service_region",
        "inventory_assets",
        ["tenant_id", "service", "region", "last_seen_at"],
    )
    op.create_index(
        "ix_inventory_assets_tenant_reconcile_mode",
        "inventory_assets",
        ["tenant_id", "last_reconcile_mode", "last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_assets_tenant_reconcile_mode", table_name="inventory_assets")
    op.drop_index("ix_inventory_assets_tenant_service_region", table_name="inventory_assets")
    op.drop_index("ix_inventory_assets_account_id", table_name="inventory_assets")
    op.drop_index("ix_inventory_assets_tenant_id", table_name="inventory_assets")
    op.drop_table("inventory_assets")
