"""
AuditLog model (Step 7.5): one-line summary events for compliance dashboards.

Optional denormalized log; remediation_runs remains the primary audit record
for remediation runs. Use for search and dashboards (e.g. "remediation_run_completed").
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AuditLog(Base):
    """
    One row per audit event: tenant, event_type, entity, user, timestamp, summary.

    Used for compliance dashboards and operational visibility. Write-once;
    no updates or deletes.
    """

    __tablename__ = "audit_log"

    __table_args__ = (
        Index("idx_audit_log_tenant", "tenant_id"),
        Index("idx_audit_log_tenant_timestamp", "tenant_id", "timestamp", postgresql_ops={"timestamp": "DESC"}),
        Index("idx_audit_log_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
