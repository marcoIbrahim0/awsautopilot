from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ControlPlaneEvent(Base):
    """
    Ingested control-plane event record with lifecycle/latency telemetry.

    This table is phase-1 source-of-truth for event freshness measurement,
    de-duplication accounting, and replay/audit support.
    """

    __tablename__ = "control_plane_events"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "event_id",
            "account_id",
            "region",
            name="uq_control_plane_events_tenant_event_account_region",
        ),
        Index(
            "ix_control_plane_events_tenant_time",
            "tenant_id",
            "event_time",
        ),
        Index(
            "ix_control_plane_events_tenant_status",
            "tenant_id",
            "processing_status",
            "event_time",
        ),
        Index(
            "ix_control_plane_events_account_region",
            "tenant_id",
            "account_id",
            "region",
            "event_time",
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

    # Event identity
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    detail_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_category: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Lifecycle and outcome
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing fields used for SLO metrics
    event_time: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    intake_time: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queue_enqueued_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handler_started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    upsert_completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    api_visible_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Pre-computed metrics for cheap percentile queries.
    cloudtrail_delivery_lag_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_lag_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    handler_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_to_end_lag_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_freshness_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_event: Mapped[dict | list] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
