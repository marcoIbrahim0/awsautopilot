from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AwsAccountReconcileSettings(Base):
    """Tenant-managed reconciliation defaults and schedule settings per AWS account."""

    __tablename__ = "aws_account_reconcile_settings"

    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", name="uq_aws_account_reconcile_settings_tenant_account"),
        Index("ix_aws_account_reconcile_settings_tenant_enabled", "tenant_id", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=360)
    services: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    regions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    max_resources: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sweep_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    last_enqueued_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_reconcile_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
