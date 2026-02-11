from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class FindingShadowState(Base):
    """
    Shadow finding state written by the near-real-time control-plane pipeline.

    This table is intentionally separate from findings for phase-1 shadow mode.
    """

    __tablename__ = "finding_shadow_states"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source",
            "fingerprint",
            name="uq_finding_shadow_states_tenant_source_fingerprint",
        ),
        Index(
            "ix_finding_shadow_states_tenant_status",
            "tenant_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_finding_shadow_states_tenant_account_region",
            "tenant_id",
            "account_id",
            "region",
        ),
        Index(
            "ix_finding_shadow_states_event_time",
            "tenant_id",
            "last_observed_event_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="event_monitor_shadow")

    fingerprint: Mapped[str] = mapped_column(String(1024), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(2048), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    control_id: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_control_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ref: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    state_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    first_observed_event_time: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_event_time: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_evaluated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
