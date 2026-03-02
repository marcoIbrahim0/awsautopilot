from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import RootKeyExternalTaskStatus, RootKeyRemediationMode, RootKeyRemediationState

if TYPE_CHECKING:
    from backend.models.root_key_remediation_run import RootKeyRemediationRun


class RootKeyExternalTask(Base):
    """User-attention tasks required for manual root-key remediation flows."""

    __tablename__ = "root_key_external_tasks"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_id",
            "idempotency_key",
            name="uq_root_key_external_tasks_tenant_run_idempotency",
        ),
        CheckConstraint("retry_count >= 0", name="ck_root_key_external_tasks_retry_non_negative"),
        Index("ix_root_key_external_tasks_tenant_run", "tenant_id", "run_id"),
        Index("ix_root_key_external_tasks_tenant_status_due", "tenant_id", "status", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("root_key_remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    control_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[RootKeyRemediationState] = mapped_column(
        SAEnum(RootKeyRemediationState, name="root_key_remediation_state", create_type=False),
        nullable=False,
    )
    status: Mapped[RootKeyExternalTaskStatus] = mapped_column(
        SAEnum(RootKeyExternalTaskStatus, name="root_key_external_task_status", create_type=False),
        nullable=False,
        default=RootKeyExternalTaskStatus.open,
    )
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[RootKeyRemediationMode] = mapped_column(
        SAEnum(RootKeyRemediationMode, name="root_key_remediation_mode", create_type=False),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_payload: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    task_result: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rollback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exception_expiry: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    run: Mapped["RootKeyRemediationRun"] = relationship(
        "RootKeyRemediationRun",
        foreign_keys=[run_id],
        lazy="selectin",
        back_populates="external_tasks",
    )
