"""Add attack path materialized read model tables.

Revision ID: 0046_attack_path_materialized_read_model
Revises: 0045_help_assistant_llm_threads
Create Date: 2026-03-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0046_attack_path_materialized_read_model"
down_revision: Union[str, Sequence[str], None] = "0045_help_assistant_llm_threads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attack_path_materialized_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path_id", sa.String(length=128), nullable=False),
        sa.Column("representative_action_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_id", sa.String(length=12), nullable=True),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("has_blast_radius", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_business_critical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_actively_exploited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_owners", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "summary_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_max_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stale_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_status", sa.String(length=32), nullable=True),
        sa.Column("refresh_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "path_id", name="uq_attack_path_materialized_summaries_tenant_path"),
    )
    op.create_index(
        "ix_attack_path_materialized_summaries_tenant_rank",
        "attack_path_materialized_summaries",
        ["tenant_id", "rank"],
    )
    op.create_index(
        "ix_attack_path_materialized_summaries_tenant_status_rank",
        "attack_path_materialized_summaries",
        ["tenant_id", "status", "rank"],
    )
    op.create_index(
        "ix_attack_path_materialized_summaries_tenant_account_rank",
        "attack_path_materialized_summaries",
        ["tenant_id", "account_id", "rank"],
    )
    op.create_index(
        "ix_attack_path_materialized_summaries_tenant_path",
        "attack_path_materialized_summaries",
        ["tenant_id", "path_id"],
    )

    op.create_table(
        "attack_path_materialized_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "detail_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("refresh_status", sa.Text(), nullable=True),
        sa.Column("refresh_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["summary_id"],
            ["attack_path_materialized_summaries.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_id"),
    )
    op.create_index(
        "ix_attack_path_materialized_details_tenant_summary",
        "attack_path_materialized_details",
        ["tenant_id", "summary_id"],
    )

    op.create_table(
        "attack_path_materialized_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path_id", sa.String(length=128), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=True),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("resource_id", sa.String(length=2048), nullable=True),
        sa.Column("owner_key", sa.String(length=255), nullable=True),
        sa.Column("owner_label", sa.String(length=255), nullable=True),
        sa.Column("action_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["summary_id"],
            ["attack_path_materialized_summaries.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "path_id",
            "action_id",
            name="uq_attack_path_materialized_memberships_tenant_path_action",
        ),
    )
    op.create_index(
        "ix_attack_path_materialized_memberships_tenant_path",
        "attack_path_materialized_memberships",
        ["tenant_id", "path_id"],
    )
    op.create_index(
        "ix_attack_path_materialized_memberships_tenant_action",
        "attack_path_materialized_memberships",
        ["tenant_id", "action_id"],
    )
    op.create_index(
        "ix_attack_path_materialized_memberships_tenant_owner",
        "attack_path_materialized_memberships",
        ["tenant_id", "owner_key"],
    )
    op.create_index(
        "ix_attack_path_materialized_memberships_tenant_account",
        "attack_path_materialized_memberships",
        ["tenant_id", "account_id"],
    )
    op.create_index(
        "ix_attack_path_materialized_memberships_tenant_resource",
        "attack_path_materialized_memberships",
        ["tenant_id", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_attack_path_materialized_memberships_tenant_resource",
        table_name="attack_path_materialized_memberships",
    )
    op.drop_index(
        "ix_attack_path_materialized_memberships_tenant_account",
        table_name="attack_path_materialized_memberships",
    )
    op.drop_index(
        "ix_attack_path_materialized_memberships_tenant_owner",
        table_name="attack_path_materialized_memberships",
    )
    op.drop_index(
        "ix_attack_path_materialized_memberships_tenant_action",
        table_name="attack_path_materialized_memberships",
    )
    op.drop_index(
        "ix_attack_path_materialized_memberships_tenant_path",
        table_name="attack_path_materialized_memberships",
    )
    op.drop_table("attack_path_materialized_memberships")

    op.drop_index(
        "ix_attack_path_materialized_details_tenant_summary",
        table_name="attack_path_materialized_details",
    )
    op.drop_table("attack_path_materialized_details")

    op.drop_index(
        "ix_attack_path_materialized_summaries_tenant_path",
        table_name="attack_path_materialized_summaries",
    )
    op.drop_index(
        "ix_attack_path_materialized_summaries_tenant_account_rank",
        table_name="attack_path_materialized_summaries",
    )
    op.drop_index(
        "ix_attack_path_materialized_summaries_tenant_status_rank",
        table_name="attack_path_materialized_summaries",
    )
    op.drop_index(
        "ix_attack_path_materialized_summaries_tenant_rank",
        table_name="attack_path_materialized_summaries",
    )
    op.drop_table("attack_path_materialized_summaries")
