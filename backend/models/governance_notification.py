"""Governance notification event model (communication layer)."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class GovernanceNotification(Base):
    """Tenant-scoped, idempotent communication events for governance notifications."""

    __tablename__ = "governance_notifications"

    __table_args__ = (
        Index("ix_governance_notifications_tenant", "tenant_id"),
        Index(
            "ix_governance_notifications_tenant_created",
            "tenant_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index("ix_governance_notifications_tenant_status", "tenant_id", "status"),
        Index("ix_governance_notifications_tenant_target", "tenant_id", "target_type", "target_id"),
        UniqueConstraint(
            "tenant_id",
            "notification_key",
            "channel",
            name="uq_governance_notifications_tenant_key_channel",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    notification_key: Mapped[str] = mapped_column(String(160), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
