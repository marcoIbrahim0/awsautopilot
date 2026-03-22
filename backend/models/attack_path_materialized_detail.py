from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AttackPathMaterializedDetail(Base):
    """Tenant-scoped extended shared attack path payload."""

    __tablename__ = "attack_path_materialized_details"

    __table_args__ = (
        Index("ix_attack_path_materialized_details_tenant_summary", "tenant_id", "summary_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attack_path_materialized_summaries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    detail_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    refresh_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
