# backend/models/exception.py
"""Exception model: suppressions for findings or actions with reason, approver, and expiry."""
from __future__ import annotations

import uuid
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import EntityType


class Exception(Base):
    """
    One row per suppressed finding or action.
    Records include reason, approver, expiry date, and optional ticket link.
    At most one active exception per (tenant, entity_type, entity_id).
    """

    __tablename__ = "exceptions"

    __table_args__ = (
        Index("idx_exceptions_tenant", "tenant_id"),
        Index("idx_exceptions_entity", "tenant_id", "entity_type", "entity_id"),
        Index("idx_exceptions_expires_at", "tenant_id", "expires_at"),
        UniqueConstraint("tenant_id", "entity_type", "entity_id", name="uq_exceptions_tenant_entity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType, name="entity_type", create_type=False),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticket_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    approved_by: Mapped["User"] = relationship("User", foreign_keys=[approved_by_user_id], lazy="selectin")
