from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class TenantReconcileRun(Base):
    """Tenant-visible reconciliation run state and aggregate progress counters."""

    __tablename__ = "tenant_reconcile_runs"

    __table_args__ = (
        Index("ix_tenant_reconcile_runs_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_tenant_reconcile_runs_tenant_account_status", "tenant_id", "account_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")

    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    regions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    services: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sweep_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    max_resources: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_shards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enqueued_shards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    running_shards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded_shards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_shards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
