from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class HelpAssistantInteraction(Base):
    __tablename__ = "help_assistant_interactions"

    __table_args__ = (
        Index("ix_help_assistant_interactions_tenant_created", "tenant_id", "created_at"),
        Index("ix_help_assistant_interactions_user_created", "user_id", "created_at"),
        Index("ix_help_assistant_interactions_thread_created", "thread_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    escalated_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("help_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    current_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cited_article_slugs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    citations: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    referenced_entities: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    suggested_case: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    follow_up_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    context_gaps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reasoning_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)
    usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", lazy="selectin")
    escalated_case = relationship("HelpCase", lazy="selectin")
