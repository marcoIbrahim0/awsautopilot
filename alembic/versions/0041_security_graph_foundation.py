"""Add tenant-scoped security graph foundation tables.

Revision ID: 0041_security_graph_foundation
Revises: 0040_firebase_email_verification
Create Date: 2026-03-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0041_security_graph_foundation"
down_revision: Union[str, None] = "0040_firebase_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_graph_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("node_type", sa.String(length=32), nullable=False),
        sa.Column("node_key", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "node_key", name="uq_security_graph_nodes_tenant_key"),
    )
    op.create_index(
        "ix_security_graph_nodes_tenant_type_account_region",
        "security_graph_nodes",
        ["tenant_id", "node_type", "account_id", "region"],
    )
    op.create_index("ix_security_graph_nodes_tenant_id", "security_graph_nodes", ["tenant_id"])
    op.create_index("ix_security_graph_nodes_account_id", "security_graph_nodes", ["account_id"])
    op.alter_column("security_graph_nodes", "metadata_json", server_default=None)

    op.create_table(
        "security_graph_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("edge_key", sa.String(length=1024), nullable=False),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_node_id"], ["security_graph_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["security_graph_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "edge_key", name="uq_security_graph_edges_tenant_key"),
    )
    op.create_index(
        "ix_security_graph_edges_tenant_type_account_region",
        "security_graph_edges",
        ["tenant_id", "edge_type", "account_id", "region"],
    )
    op.create_index("ix_security_graph_edges_tenant_source", "security_graph_edges", ["tenant_id", "source_node_id"])
    op.create_index("ix_security_graph_edges_tenant_target", "security_graph_edges", ["tenant_id", "target_node_id"])
    op.create_index("ix_security_graph_edges_tenant_id", "security_graph_edges", ["tenant_id"])
    op.create_index("ix_security_graph_edges_account_id", "security_graph_edges", ["account_id"])
    op.alter_column("security_graph_edges", "metadata_json", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_security_graph_edges_account_id", table_name="security_graph_edges")
    op.drop_index("ix_security_graph_edges_tenant_id", table_name="security_graph_edges")
    op.drop_index("ix_security_graph_edges_tenant_target", table_name="security_graph_edges")
    op.drop_index("ix_security_graph_edges_tenant_source", table_name="security_graph_edges")
    op.drop_index("ix_security_graph_edges_tenant_type_account_region", table_name="security_graph_edges")
    op.drop_table("security_graph_edges")
    op.drop_index("ix_security_graph_nodes_account_id", table_name="security_graph_nodes")
    op.drop_index("ix_security_graph_nodes_tenant_id", table_name="security_graph_nodes")
    op.drop_index("ix_security_graph_nodes_tenant_type_account_region", table_name="security_graph_nodes")
    op.drop_table("security_graph_nodes")
