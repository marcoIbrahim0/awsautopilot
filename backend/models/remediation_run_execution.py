"""Remediation run execution model for SaaS-managed PR bundle runner."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import RemediationRunExecutionPhase, RemediationRunExecutionStatus


class RemediationRunExecution(Base):
    """One row per plan/apply execution attempt for a remediation run."""

    __tablename__ = "remediation_run_executions"

    __table_args__ = (
        Index("idx_run_exec_tenant", "tenant_id"),
        Index("idx_run_exec_run", "run_id"),
        Index("idx_run_exec_status", "tenant_id", "status"),
        Index(
            "idx_run_exec_tenant_created",
            "tenant_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    phase: Mapped[RemediationRunExecutionPhase] = mapped_column(
        SAEnum(RemediationRunExecutionPhase, name="remediation_run_execution_phase", create_type=False),
        nullable=False,
    )
    status: Mapped[RemediationRunExecutionStatus] = mapped_column(
        SAEnum(RemediationRunExecutionStatus, name="remediation_run_execution_status", create_type=False),
        nullable=False,
    )

    workspace_manifest: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    logs_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    started_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    run: Mapped["RemediationRun"] = relationship(
        "RemediationRun",
        foreign_keys=[run_id],
        lazy="selectin",
        back_populates="executions",
    )
