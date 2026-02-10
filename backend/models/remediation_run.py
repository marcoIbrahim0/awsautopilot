# backend/models/remediation_run.py
"""RemediationRun model: one row per remediation attempt (PR-only or direct fix) with audit trail."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import RemediationRunMode, RemediationRunStatus


class RemediationRun(Base):
    """
    One row per remediation run: PR bundle generation or direct fix.
    Primary audit record for who, when, what action, outcome, logs, and artifacts.
    """

    __tablename__ = "remediation_runs"

    __table_args__ = (
        Index("idx_remediation_runs_tenant", "tenant_id"),
        Index("idx_remediation_runs_action", "action_id"),
        Index("idx_remediation_runs_tenant_created", "tenant_id", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_remediation_runs_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )

    mode: Mapped[RemediationRunMode] = mapped_column(
        SAEnum(RemediationRunMode, name="remediation_run_mode", create_type=False),
        nullable=False,
    )
    status: Mapped[RemediationRunStatus] = mapped_column(
        SAEnum(RemediationRunStatus, name="remediation_run_status", create_type=False),
        nullable=False,
    )

    outcome: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    artifacts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    action: Mapped["Action"] = relationship("Action", foreign_keys=[action_id], lazy="selectin")
    approved_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approved_by_user_id], lazy="selectin"
    )
    executions: Mapped[list["RemediationRunExecution"]] = relationship(
        "RemediationRunExecution",
        foreign_keys="RemediationRunExecution.run_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="run",
    )
