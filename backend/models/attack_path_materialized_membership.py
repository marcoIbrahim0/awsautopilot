from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AttackPathMaterializedMembership(Base):
    """Linked-action membership rows for shared attack paths."""

    __tablename__ = "attack_path_materialized_memberships"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "path_id",
            "action_id",
            name="uq_attack_path_materialized_memberships_tenant_path_action",
        ),
        Index("ix_attack_path_materialized_memberships_tenant_path", "tenant_id", "path_id"),
        Index("ix_attack_path_materialized_memberships_tenant_action", "tenant_id", "action_id"),
        Index("ix_attack_path_materialized_memberships_tenant_owner", "tenant_id", "owner_key"),
        Index("ix_attack_path_materialized_memberships_tenant_account", "tenant_id", "account_id"),
        Index("ix_attack_path_materialized_memberships_tenant_resource", "tenant_id", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attack_path_materialized_summaries.id", ondelete="CASCADE"),
        nullable=False,
    )
    path_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    owner_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
