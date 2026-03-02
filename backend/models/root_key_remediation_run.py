from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import RootKeyRemediationMode, RootKeyRemediationRunStatus, RootKeyRemediationState

if TYPE_CHECKING:
    from backend.models.root_key_dependency_fingerprint import RootKeyDependencyFingerprint
    from backend.models.root_key_external_task import RootKeyExternalTask
    from backend.models.root_key_remediation_artifact import RootKeyRemediationArtifact
    from backend.models.root_key_remediation_event import RootKeyRemediationEvent


class RootKeyRemediationRun(Base):
    """Root-key remediation orchestration run with tenant-scoped idempotency keys."""

    __tablename__ = "root_key_remediation_runs"

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_root_key_runs_tenant_idempotency"),
        CheckConstraint("retry_count >= 0", name="ck_root_key_runs_retry_non_negative"),
        CheckConstraint("lock_version > 0", name="ck_root_key_runs_lock_version_positive"),
        Index("ix_root_key_runs_tenant_state_status", "tenant_id", "state", "status"),
        Index("ix_root_key_runs_tenant_scope", "tenant_id", "account_id", "region"),
        Index("ix_root_key_runs_correlation", "tenant_id", "correlation_id"),
        Index(
            "ix_root_key_runs_tenant_updated",
            "tenant_id",
            "updated_at",
            postgresql_ops={"updated_at": "DESC"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    control_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[RootKeyRemediationState] = mapped_column(
        SAEnum(RootKeyRemediationState, name="root_key_remediation_state", create_type=False),
        nullable=False,
        default=RootKeyRemediationState.discovery,
    )
    status: Mapped[RootKeyRemediationRunStatus] = mapped_column(
        SAEnum(RootKeyRemediationRunStatus, name="root_key_remediation_run_status", create_type=False),
        nullable=False,
        default=RootKeyRemediationRunStatus.queued,
    )
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[RootKeyRemediationMode] = mapped_column(
        SAEnum(RootKeyRemediationMode, name="root_key_remediation_mode", create_type=False),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rollback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exception_expiry: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    events: Mapped[list["RootKeyRemediationEvent"]] = relationship(
        "RootKeyRemediationEvent",
        foreign_keys="RootKeyRemediationEvent.run_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="run",
    )
    dependency_fingerprints: Mapped[list["RootKeyDependencyFingerprint"]] = relationship(
        "RootKeyDependencyFingerprint",
        foreign_keys="RootKeyDependencyFingerprint.run_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="run",
    )
    artifacts: Mapped[list["RootKeyRemediationArtifact"]] = relationship(
        "RootKeyRemediationArtifact",
        foreign_keys="RootKeyRemediationArtifact.run_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="run",
    )
    external_tasks: Mapped[list["RootKeyExternalTask"]] = relationship(
        "RootKeyExternalTask",
        foreign_keys="RootKeyExternalTask.run_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="run",
    )
