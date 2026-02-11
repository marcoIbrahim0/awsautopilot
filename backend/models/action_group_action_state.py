from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import ActionGroupConfirmationSource, ActionGroupStatusBucket


class ActionGroupActionState(Base):
    """
    Denormalized latest state projection for action membership inside a group.

    Buckets are derived from run attempts and trusted AWS confirmations.
    """

    __tablename__ = "action_group_action_state"

    __table_args__ = (
        UniqueConstraint("tenant_id", "group_id", "action_id", name="uq_action_group_action_state_scope"),
        Index("ix_action_group_action_state_group_bucket", "group_id", "latest_run_status_bucket"),
        Index("ix_action_group_action_state_tenant_group", "tenant_id", "group_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_groups.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    latest_run_status_bucket: Mapped[ActionGroupStatusBucket] = mapped_column(
        SAEnum(ActionGroupStatusBucket, name="action_group_status_bucket", create_type=False),
        nullable=False,
        default=ActionGroupStatusBucket.not_run_yet,
    )
    latest_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_group_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_attempt_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_confirmed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_confirmation_source: Mapped[ActionGroupConfirmationSource | None] = mapped_column(
        SAEnum(ActionGroupConfirmationSource, name="action_group_confirmation_source", create_type=False),
        nullable=True,
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    group: Mapped["ActionGroup"] = relationship(
        "ActionGroup",
        foreign_keys=[group_id],
        lazy="selectin",
        back_populates="action_states",
    )
    action: Mapped["Action"] = relationship(
        "Action",
        foreign_keys=[action_id],
        lazy="selectin",
    )
    latest_run: Mapped["ActionGroupRun | None"] = relationship(
        "ActionGroupRun",
        foreign_keys=[latest_run_id],
        lazy="selectin",
    )
