from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class ActionGroupMembership(Base):
    """Immutable append-only link between one action and one persistent group."""

    __tablename__ = "action_group_memberships"

    __table_args__ = (
        UniqueConstraint("action_id", name="uq_action_group_memberships_action_id"),
        Index("ix_action_group_memberships_group_id", "group_id"),
        Index("ix_action_group_memberships_tenant_group", "tenant_id", "group_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="ingest")

    group: Mapped["ActionGroup"] = relationship(
        "ActionGroup",
        foreign_keys=[group_id],
        lazy="selectin",
        back_populates="memberships",
    )
    action: Mapped["Action"] = relationship(
        "Action",
        foreign_keys=[action_id],
        lazy="selectin",
    )
