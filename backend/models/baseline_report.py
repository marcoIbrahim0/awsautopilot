"""
BaselineReport model (Step 13.2).

One row per baseline report request. Tracks status (pending → running → success/failed),
S3 result location, and optional failure outcome. Tenant-scoped; used by API to enqueue
report generation and return status/download link.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import BaselineReportStatus


class BaselineReport(Base):
    """
    One row per baseline report request.
    Status: pending → running → success/failed. On success: s3_key, file_size_bytes.
    On failure: outcome (error message).
    """

    __tablename__ = "baseline_reports"

    __table_args__ = (
        Index("idx_baseline_reports_tenant", "tenant_id"),
        Index(
            "idx_baseline_reports_tenant_created",
            "tenant_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index("idx_baseline_reports_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[BaselineReportStatus] = mapped_column(
        SAEnum(BaselineReportStatus, name="baseline_report_status", create_type=False),
        nullable=False,
    )
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)

    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    account_ids: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id], lazy="selectin")
    requested_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[requested_by_user_id], lazy="selectin"
    )
