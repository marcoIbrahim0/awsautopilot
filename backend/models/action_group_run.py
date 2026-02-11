from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import ActionGroupRunStatus


class ActionGroupRun(Base):
    """Execution attempt scoped to a persistent action group."""

    __tablename__ = "action_group_runs"

    __table_args__ = (
        UniqueConstraint("report_token_jti", name="uq_action_group_runs_report_token_jti"),
        Index("ix_action_group_runs_tenant_group", "tenant_id", "group_id"),
        Index("ix_action_group_runs_group_status", "group_id", "status"),
        Index("ix_action_group_runs_tenant_created", "tenant_id", "created_at", postgresql_ops={"created_at": "DESC"}),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    remediation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("remediation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    mode: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ActionGroupRunStatus] = mapped_column(
        SAEnum(ActionGroupRunStatus, name="action_group_run_status", create_type=False),
        nullable=False,
        default=ActionGroupRunStatus.queued,
    )
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reporting_source: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    report_token_jti: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    group: Mapped["ActionGroup"] = relationship(
        "ActionGroup",
        foreign_keys=[group_id],
        lazy="selectin",
        back_populates="runs",
    )
    results: Mapped[list["ActionGroupRunResult"]] = relationship(
        "ActionGroupRunResult",
        foreign_keys="ActionGroupRunResult.group_run_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="group_run",
    )
    remediation_run: Mapped["RemediationRun | None"] = relationship(
        "RemediationRun",
        foreign_keys=[remediation_run_id],
        lazy="selectin",
    )
