from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ActionExternalLink(Base):
    """Tenant-scoped link between an action and an external ticket or chat thread."""

    __tablename__ = "action_external_links"

    __table_args__ = (
        Index("ix_action_external_links_tenant_action", "tenant_id", "action_id"),
        Index("ix_action_external_links_tenant_provider", "tenant_id", "provider"),
        UniqueConstraint("tenant_id", "action_id", "provider", name="uq_action_external_links_tenant_action_provider"),
        UniqueConstraint("tenant_id", "provider", "external_id", name="uq_action_external_links_tenant_provider_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_assignee_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_assignee_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_outbound_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_outbound_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_inbound_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_inbound_event_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

