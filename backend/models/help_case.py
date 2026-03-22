from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class HelpCase(Base):
    __tablename__ = "help_cases"

    __table_args__ = (
        Index("ix_help_cases_tenant_status", "tenant_id", "status"),
        Index("ix_help_cases_requester_created", "requester_user_id", "created_at"),
        Index("ix_help_cases_assignee_status", "assigned_saas_admin_user_id", "status"),
        Index("ix_help_cases_tenant_last_message", "tenant_id", "last_message_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_saas_admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default="new")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    current_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    referenced_entities: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    first_response_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    requester = relationship("User", foreign_keys=[requester_user_id], lazy="selectin")
    assignee = relationship("User", foreign_keys=[assigned_saas_admin_user_id], lazy="selectin")
    messages = relationship("HelpCaseMessage", back_populates="case", cascade="all, delete-orphan", lazy="selectin")
    attachments = relationship("HelpCaseAttachment", back_populates="case", cascade="all, delete-orphan", lazy="selectin")
