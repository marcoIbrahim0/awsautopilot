from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class TenantIntegrationSetting(Base):
    """Tenant-scoped provider configuration and isolated secret payloads."""

    __tablename__ = "tenant_integration_settings"

    __table_args__ = (
        Index("ix_tenant_integration_settings_tenant_enabled", "tenant_id", "enabled"),
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_integration_settings_tenant_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    outbound_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    inbound_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    auto_create: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    reopen_on_regression: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    secret_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    webhook_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

