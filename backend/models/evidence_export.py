"""EvidenceExport model: one row per evidence pack export job (Step 10.1).

Tracks who requested the export, status (pending → running → success/failed),
and where the result lives (S3 key). Enables the API to enqueue an export,
return an export id, and let the frontend poll for status and download.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import EvidenceExportStatus


class EvidenceExport(Base):
    """
    One row per evidence pack export request.
    Primary record for who requested, when, status, and result location (S3).
    """

    __tablename__ = "evidence_exports"

    __table_args__ = (
        Index("idx_evidence_exports_tenant", "tenant_id"),
        Index(
            "idx_evidence_exports_tenant_created",
            "tenant_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index("idx_evidence_exports_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[EvidenceExportStatus] = mapped_column(
        SAEnum(EvidenceExportStatus, name="evidence_export_status", create_type=False),
        nullable=False,
    )
    pack_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="evidence",
        server_default="evidence",
    )
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id], lazy="selectin")
    requested_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[requested_by_user_id], lazy="selectin"
    )
