# backend/models/action.py
"""Action model: aggregated, deduplicated units of work derived from findings."""
from __future__ import annotations

import uuid
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.action_finding import ActionFinding
from backend.models.base import Base


class Action(Base):
    """
    One row per distinct actionable item: fix this resource for this control.
    Scoped by tenant, account, and optionally region.
    """

    __tablename__ = "actions"

    __table_args__ = (
        Index("idx_actions_tenant_status", "tenant_id", "status"),
        Index("idx_actions_tenant_priority", "tenant_id", "priority", postgresql_ops={"priority": "DESC"}),
        Index("idx_actions_tenant_account_region", "tenant_id", "account_id", "region"),
        # Dedupe: one action per distinct target per tenant (unique index with COALESCE in migration)
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(512), nullable=False)
    account_id: Mapped[str] = mapped_column(String(12), nullable=False)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)

    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Association to findings (many-to-many via action_findings)
    action_finding_links: Mapped[list["ActionFinding"]] = relationship(
        "ActionFinding",
        back_populates="action",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    findings: Mapped[list["Finding"]] = association_proxy(
        "action_finding_links",
        "finding",
        creator=lambda f: ActionFinding(finding=f),
    )
