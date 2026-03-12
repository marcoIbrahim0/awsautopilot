from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ActionRemediationSyncState(Base):
    """Current external-sync snapshot for one action/provider pair."""

    __tablename__ = "action_remediation_sync_states"

    __table_args__ = (
        Index("ix_action_remediation_sync_states_tenant_action", "tenant_id", "action_id"),
        Index("ix_action_remediation_sync_states_tenant_sync_status", "tenant_id", "sync_status"),
        Index("ix_action_remediation_sync_states_tenant_provider", "tenant_id", "provider"),
        UniqueConstraint(
            "tenant_id",
            "action_id",
            "provider",
            name="uq_action_remediation_sync_states_tenant_action_provider",
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
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mapped_internal_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    canonical_internal_status: Mapped[str] = mapped_column(String(32), nullable=False)
    preferred_external_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="in_sync")
    last_source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="internal")
    resolution_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conflict_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_event_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconciled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
