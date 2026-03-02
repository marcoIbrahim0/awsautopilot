# backend/models/exception.py
"""Exception model: suppressions for findings or actions with reason, approver, and expiry."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import EntityType

if TYPE_CHECKING:
    from backend.models.user import User


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
        Index("idx_exceptions_owner", "tenant_id", "owner_user_id"),
        Index("idx_exceptions_reminder_due", "tenant_id", "next_reminder_at"),
        Index("idx_exceptions_revalidation_due", "tenant_id", "next_revalidation_at"),
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
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ticket_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    reminder_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_reminder_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reminded_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revalidation_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_revalidation_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_revalidated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    approved_by: Mapped["User"] = relationship("User", foreign_keys=[approved_by_user_id], lazy="selectin")
    owner: Mapped["User | None"] = relationship("User", foreign_keys=[owner_user_id], lazy="selectin")
