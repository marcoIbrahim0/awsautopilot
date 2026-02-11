"""persistent immutable action groups and run tracking

Revision ID: 0030_action_groups_persistent
Revises: 0029_tenant_reconcile_controls
Create Date: 2026-02-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0030_action_groups_persistent"
down_revision: Union[str, None] = "0029_tenant_reconcile_controls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE action_group_run_status "
        "AS ENUM ('queued', 'started', 'finished', 'failed', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE action_group_execution_status "
        "AS ENUM ('success', 'failed', 'cancelled', 'unknown')"
    )
    op.execute(
        "CREATE TYPE action_group_status_bucket "
        "AS ENUM ('not_run_yet', 'run_not_successful', 'run_successful_confirmed')"
    )
    op.execute(
        "CREATE TYPE action_group_confirmation_source "
        "AS ENUM ('security_hub', 'control_plane_reconcile')"
    )

    op.create_table(
        "action_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("group_key", sa.String(length=512), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("group_key", name="uq_action_groups_group_key"),
    )
    op.create_index("ix_action_groups_tenant_id", "action_groups", ["tenant_id"])
    op.create_index(
        "ix_action_groups_tenant_created",
        "action_groups",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_action_groups_tenant_scope",
        "action_groups",
        ["tenant_id", "action_type", "account_id", "region"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_action_groups_tenant_type_account_region_norm "
        "ON action_groups (tenant_id, action_type, account_id, COALESCE(region, ''))"
    )

    op.create_table(
        "action_group_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("action_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'ingest'")),
        sa.UniqueConstraint("action_id", name="uq_action_group_memberships_action_id"),
    )
    op.create_index("ix_action_group_memberships_tenant_id", "action_group_memberships", ["tenant_id"])
    op.create_index("ix_action_group_memberships_group_id", "action_group_memberships", ["group_id"])
    op.create_index(
        "ix_action_group_memberships_tenant_group",
        "action_group_memberships",
        ["tenant_id", "group_id"],
    )

    op.create_table(
        "action_group_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("action_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "remediation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("remediation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "initiated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "started",
                "finished",
                "failed",
                "cancelled",
                name="action_group_run_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reporting_source", sa.String(length=64), nullable=False, server_default=sa.text("'system'")),
        sa.Column("report_token_jti", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("report_token_jti", name="uq_action_group_runs_report_token_jti"),
    )
    op.create_index("ix_action_group_runs_tenant_id", "action_group_runs", ["tenant_id"])
    op.create_index("ix_action_group_runs_tenant_group", "action_group_runs", ["tenant_id", "group_id"])
    op.create_index("ix_action_group_runs_group_status", "action_group_runs", ["group_id", "status"])
    op.create_index(
        "ix_action_group_runs_tenant_created",
        "action_group_runs",
        ["tenant_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_table(
        "action_group_run_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("action_group_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execution_status",
            postgresql.ENUM(
                "success",
                "failed",
                "cancelled",
                "unknown",
                name="action_group_execution_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("execution_error_code", sa.String(length=128), nullable=True),
        sa.Column("execution_error_message", sa.Text(), nullable=True),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("group_run_id", "action_id", name="uq_action_group_run_results_run_action"),
    )
    op.create_index("ix_action_group_run_results_tenant_id", "action_group_run_results", ["tenant_id"])
    op.create_index("ix_action_group_run_results_group_run", "action_group_run_results", ["group_run_id"])
    op.create_index(
        "ix_action_group_run_results_tenant_action",
        "action_group_run_results",
        ["tenant_id", "action_id"],
    )

    op.create_table(
        "action_group_action_state",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("action_groups.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "latest_run_status_bucket",
            postgresql.ENUM(
                "not_run_yet",
                "run_not_successful",
                "run_successful_confirmed",
                name="action_group_status_bucket",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'not_run_yet'"),
        ),
        sa.Column(
            "latest_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("action_group_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_confirmation_source",
            postgresql.ENUM(
                "security_hub",
                "control_plane_reconcile",
                name="action_group_confirmation_source",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "group_id",
            "action_id",
            name="uq_action_group_action_state_scope",
        ),
    )
    op.create_index(
        "ix_action_group_action_state_group_bucket",
        "action_group_action_state",
        ["group_id", "latest_run_status_bucket"],
    )
    op.create_index(
        "ix_action_group_action_state_tenant_group",
        "action_group_action_state",
        ["tenant_id", "group_id"],
    )

    # Backfill existing actions into immutable groups + memberships and initialize
    # projection rows to not_run_yet.
    op.execute(
        """
        WITH grouped AS (
            SELECT
                a.tenant_id,
                a.action_type,
                a.account_id,
                a.region,
                (a.tenant_id::text || '|' || a.action_type || '|' || a.account_id || '|' || COALESCE(a.region, 'global')) AS group_key
            FROM actions a
            GROUP BY a.tenant_id, a.action_type, a.account_id, a.region
        )
        INSERT INTO action_groups (
            id,
            tenant_id,
            action_type,
            account_id,
            region,
            group_key,
            metadata,
            created_at,
            updated_at
        )
        SELECT
            (
                SUBSTRING(md5(g.group_key), 1, 8) || '-' ||
                SUBSTRING(md5(g.group_key), 9, 4) || '-' ||
                SUBSTRING(md5(g.group_key), 13, 4) || '-' ||
                SUBSTRING(md5(g.group_key), 17, 4) || '-' ||
                SUBSTRING(md5(g.group_key), 21, 12)
            )::uuid AS id,
            g.tenant_id,
            g.action_type,
            g.account_id,
            g.region,
            g.group_key,
            jsonb_build_object('source', 'migration_backfill'),
            now(),
            now()
        FROM grouped g
        ON CONFLICT (group_key) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO action_group_memberships (
            id,
            tenant_id,
            group_id,
            action_id,
            assigned_at,
            source
        )
        SELECT
            (
                SUBSTRING(md5(a.id::text || '|membership'), 1, 8) || '-' ||
                SUBSTRING(md5(a.id::text || '|membership'), 9, 4) || '-' ||
                SUBSTRING(md5(a.id::text || '|membership'), 13, 4) || '-' ||
                SUBSTRING(md5(a.id::text || '|membership'), 17, 4) || '-' ||
                SUBSTRING(md5(a.id::text || '|membership'), 21, 12)
            )::uuid AS id,
            a.tenant_id,
            g.id,
            a.id,
            now(),
            'backfill'
        FROM actions a
        JOIN action_groups g
          ON g.group_key = (a.tenant_id::text || '|' || a.action_type || '|' || a.account_id || '|' || COALESCE(a.region, 'global'))
        LEFT JOIN action_group_memberships m
          ON m.action_id = a.id
        WHERE m.action_id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO action_group_action_state (
            tenant_id,
            group_id,
            action_id,
            latest_run_status_bucket,
            updated_at
        )
        SELECT
            m.tenant_id,
            m.group_id,
            m.action_id,
            'not_run_yet'::action_group_status_bucket,
            now()
        FROM action_group_memberships m
        LEFT JOIN action_group_action_state s
          ON s.tenant_id = m.tenant_id
         AND s.group_id = m.group_id
         AND s.action_id = m.action_id
        WHERE s.action_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_action_group_action_state_tenant_group", table_name="action_group_action_state")
    op.drop_index("ix_action_group_action_state_group_bucket", table_name="action_group_action_state")
    op.drop_table("action_group_action_state")

    op.drop_index("ix_action_group_run_results_tenant_action", table_name="action_group_run_results")
    op.drop_index("ix_action_group_run_results_group_run", table_name="action_group_run_results")
    op.drop_index("ix_action_group_run_results_tenant_id", table_name="action_group_run_results")
    op.drop_table("action_group_run_results")

    op.drop_index("ix_action_group_runs_tenant_created", table_name="action_group_runs")
    op.drop_index("ix_action_group_runs_group_status", table_name="action_group_runs")
    op.drop_index("ix_action_group_runs_tenant_group", table_name="action_group_runs")
    op.drop_index("ix_action_group_runs_tenant_id", table_name="action_group_runs")
    op.drop_table("action_group_runs")

    op.drop_index("ix_action_group_memberships_tenant_group", table_name="action_group_memberships")
    op.drop_index("ix_action_group_memberships_group_id", table_name="action_group_memberships")
    op.drop_index("ix_action_group_memberships_tenant_id", table_name="action_group_memberships")
    op.drop_table("action_group_memberships")

    op.drop_index("uq_action_groups_tenant_type_account_region_norm", table_name="action_groups")
    op.drop_index("ix_action_groups_tenant_scope", table_name="action_groups")
    op.drop_index("ix_action_groups_tenant_created", table_name="action_groups")
    op.drop_index("ix_action_groups_tenant_id", table_name="action_groups")
    op.drop_table("action_groups")

    op.execute("DROP TYPE action_group_confirmation_source")
    op.execute("DROP TYPE action_group_status_bucket")
    op.execute("DROP TYPE action_group_execution_status")
    op.execute("DROP TYPE action_group_run_status")
