from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ActionRemediationSyncEvent(Base):
    """Immutable audit trail for action remediation sync decisions."""

    __tablename__ = "action_remediation_sync_events"

    __table_args__ = (
        Index("ix_action_remediation_sync_events_tenant_action", "tenant_id", "action_id"),
        Index("ix_action_remediation_sync_events_tenant_provider", "tenant_id", "provider"),
        Index("ix_action_remediation_sync_events_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint(
            "tenant_id",
            "action_id",
            "idempotency_key",
            name="uq_action_remediation_sync_events_tenant_action_idempotency",
        ),
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
    sync_state_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_remediation_sync_states.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    internal_status_before: Mapped[str | None] = mapped_column(String(32), nullable=True)
    internal_status_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mapped_internal_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_external_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
