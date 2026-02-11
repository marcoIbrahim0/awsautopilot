from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class TenantReconcileRunShard(Base):
    """Per-shard execution records for a tenant reconciliation run."""

    __tablename__ = "tenant_reconcile_run_shards"

    __table_args__ = (
        Index("ix_tenant_reconcile_run_shards_run_status", "run_id", "status"),
        Index(
            "ix_tenant_reconcile_run_shards_tenant_account_status",
            "tenant_id",
            "account_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_reconcile_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    service: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    queue_message_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
