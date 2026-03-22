"""Add Help Hub LLM thread metadata.

Revision ID: 0045_help_assistant_llm_threads
Revises: 0044_help_desk_platform
Create Date: 2026-03-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0045_help_assistant_llm_threads"
down_revision: Union[str, Sequence[str], None] = "0044_help_desk_platform"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "help_assistant_interactions",
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "help_assistant_interactions",
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "help_assistant_interactions",
        sa.Column(
            "follow_up_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "help_assistant_interactions",
        sa.Column(
            "context_gaps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("help_assistant_interactions", sa.Column("provider_name", sa.String(length=64), nullable=True))
    op.add_column("help_assistant_interactions", sa.Column("model_name", sa.String(length=128), nullable=True))
    op.add_column("help_assistant_interactions", sa.Column("reasoning_effort", sa.String(length=16), nullable=True))
    op.add_column(
        "help_assistant_interactions",
        sa.Column(
            "usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "help_assistant_interactions",
        sa.Column(
            "response_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("help_assistant_interactions", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column("help_assistant_interactions", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.execute("UPDATE help_assistant_interactions SET thread_id = id WHERE thread_id IS NULL")
    op.alter_column("help_assistant_interactions", "thread_id", nullable=False)
    op.create_index(
        "ix_help_assistant_interactions_thread_created",
        "help_assistant_interactions",
        ["thread_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_help_assistant_interactions_thread_created", table_name="help_assistant_interactions")
    op.drop_column("help_assistant_interactions", "error_code")
    op.drop_column("help_assistant_interactions", "latency_ms")
    op.drop_column("help_assistant_interactions", "response_payload")
    op.drop_column("help_assistant_interactions", "usage")
    op.drop_column("help_assistant_interactions", "reasoning_effort")
    op.drop_column("help_assistant_interactions", "model_name")
    op.drop_column("help_assistant_interactions", "provider_name")
    op.drop_column("help_assistant_interactions", "context_gaps")
    op.drop_column("help_assistant_interactions", "follow_up_questions")
    op.drop_column("help_assistant_interactions", "citations")
    op.drop_column("help_assistant_interactions", "thread_id")
