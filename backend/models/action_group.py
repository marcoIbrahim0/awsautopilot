from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class ActionGroup(Base):
    """Persistent immutable grouping boundary for actions."""

    __tablename__ = "action_groups"

    __table_args__ = (
        UniqueConstraint("group_key", name="uq_action_groups_group_key"),
        Index("ix_action_groups_tenant_created", "tenant_id", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("ix_action_groups_tenant_scope", "tenant_id", "action_type", "account_id", "region"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(12), nullable=False)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    group_key: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    memberships: Mapped[list["ActionGroupMembership"]] = relationship(
        "ActionGroupMembership",
        foreign_keys="ActionGroupMembership.group_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="group",
    )
    runs: Mapped[list["ActionGroupRun"]] = relationship(
        "ActionGroupRun",
        foreign_keys="ActionGroupRun.group_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="group",
    )
    action_states: Mapped[list["ActionGroupActionState"]] = relationship(
        "ActionGroupActionState",
        foreign_keys="ActionGroupActionState.group_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="group",
    )
