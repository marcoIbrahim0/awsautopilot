# backend/models/finding.py
from __future__ import annotations

import uuid
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.action_finding import ActionFinding
from backend.models.base import Base


def _severity_normalized(label: str | None) -> int:
    m = {
        "CRITICAL": 100,
        "HIGH": 75,
        "MEDIUM": 50,
        "LOW": 25,
        "INFORMATIONAL": 0,
        "UNTRIAGED": 25,  # Inspector v2: vendor has not assigned severity yet
    }
    return m.get((label or "").upper(), 0)


class Finding(Base):
    __tablename__ = "findings"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "finding_id",
            "account_id",
            "region",
            "source",
            name="uq_findings_tenant_finding_id_account_region_source",
        ),
        Index("ix_findings_tenant_account_region", "tenant_id", "account_id", "region"),
        Index("ix_findings_tenant_severity_status", "tenant_id", "severity_label", "status"),
        Index("ix_findings_tenant_updated", "tenant_id", "updated_at"),
        Index("ix_findings_tenant_source", "tenant_id", "source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    finding_id: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="security_hub", index=True
    )

    severity_label: Mapped[str] = mapped_column(String(32), nullable=False)
    severity_normalized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    control_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    standard_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False)

    first_observed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sh_updated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_json: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Association to actions (many-to-many via action_findings)
    action_finding_links: Mapped[list["ActionFinding"]] = relationship(
        "ActionFinding",
        back_populates="finding",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    actions: Mapped[list["Action"]] = association_proxy(
        "action_finding_links",
        "action",
        creator=lambda a: ActionFinding(action=a),
    )

    @staticmethod
    def severity_to_int(label: str | None) -> int:
        return _severity_normalized(label)
