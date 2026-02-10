# backend/models/control_plane_event_ingest_status.py
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ControlPlaneEventIngestStatus(Base):
    """
    Per-tenant/account/region status tracking for control-plane event forwarding.

    This is used for tenant-facing validation ("are we receiving events?") and operational
    troubleshooting. It is updated at intake time.
    """

    __tablename__ = "control_plane_event_ingest_status"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(String(12), primary_key=True, nullable=False)
    region: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)

    last_event_time: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_intake_time: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

