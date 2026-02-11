from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import ActionGroupExecutionStatus


class ActionGroupRunResult(Base):
    """Per-action execution outcome for one action-group run."""

    __tablename__ = "action_group_run_results"

    __table_args__ = (
        UniqueConstraint("group_run_id", "action_id", name="uq_action_group_run_results_run_action"),
        Index("ix_action_group_run_results_group_run", "group_run_id"),
        Index("ix_action_group_run_results_tenant_action", "tenant_id", "action_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_group_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_status: Mapped[ActionGroupExecutionStatus] = mapped_column(
        SAEnum(ActionGroupExecutionStatus, name="action_group_execution_status", create_type=False),
        nullable=False,
        default=ActionGroupExecutionStatus.unknown,
    )
    execution_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    execution_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    group_run: Mapped["ActionGroupRun"] = relationship(
        "ActionGroupRun",
        foreign_keys=[group_run_id],
        lazy="selectin",
        back_populates="results",
    )
    action: Mapped["Action"] = relationship(
        "Action",
        foreign_keys=[action_id],
        lazy="selectin",
    )
