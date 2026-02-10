from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class InventoryAsset(Base):
    """
    Current inventory snapshot for one resource within a shard.

    Stores hash + key fields to keep storage compact while allowing quick
    change detection for reconciliation sweeps.
    """

    __tablename__ = "inventory_assets"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "account_id",
            "region",
            "service",
            "resource_id",
            name="uq_inventory_assets_tenant_account_region_service_resource",
        ),
        Index(
            "ix_inventory_assets_tenant_service_region",
            "tenant_id",
            "service",
            "region",
            "last_seen_at",
        ),
        Index(
            "ix_inventory_assets_tenant_reconcile_mode",
            "tenant_id",
            "last_reconcile_mode",
            "last_seen_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(2048), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(256), nullable=True)

    key_fields: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)

    first_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconcile_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
