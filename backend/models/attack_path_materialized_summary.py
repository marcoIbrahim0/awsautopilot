from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AttackPathMaterializedSummary(Base):
    """Tenant-scoped read model row for one shared attack path summary."""

    __tablename__ = "attack_path_materialized_summaries"

    __table_args__ = (
        UniqueConstraint("tenant_id", "path_id", name="uq_attack_path_materialized_summaries_tenant_path"),
        Index("ix_attack_path_materialized_summaries_tenant_rank", "tenant_id", "rank"),
        Index("ix_attack_path_materialized_summaries_tenant_status_rank", "tenant_id", "status", "rank"),
        Index("ix_attack_path_materialized_summaries_tenant_account_rank", "tenant_id", "account_id", "rank"),
        Index("ix_attack_path_materialized_summaries_tenant_path", "tenant_id", "path_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path_id: Mapped[str] = mapped_column(String(128), nullable=False)
    representative_action_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    has_blast_radius: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_business_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_actively_exploited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    has_owners: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    summary_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_max_updated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    computed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    stale_after: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    refresh_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
