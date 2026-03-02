from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import SecretMigrationRunStatus


class SecretMigrationRun(Base):
    """Tenant-scoped secret migration execution record."""

    __tablename__ = "secret_migration_runs"

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_secret_migration_runs_tenant_idempotency"),
        CheckConstraint("total_targets >= 0", name="ck_secret_migration_runs_total_non_negative"),
        CheckConstraint("succeeded_targets >= 0", name="ck_secret_migration_runs_succeeded_non_negative"),
        CheckConstraint("failed_targets >= 0", name="ck_secret_migration_runs_failed_non_negative"),
        CheckConstraint("rolled_back_targets >= 0", name="ck_secret_migration_runs_rolled_back_non_negative"),
        Index("ix_secret_migration_runs_tenant_status", "tenant_id", "status"),
        Index("ix_secret_migration_runs_tenant_created", "tenant_id", "created_at", postgresql_ops={"created_at": "DESC"}),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_connector: Mapped[str] = mapped_column(String(64), nullable=False)
    source_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    target_connector: Mapped[str] = mapped_column(String(64), nullable=False)
    target_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    rollback_on_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SecretMigrationRunStatus.queued.value,
        server_default=SecretMigrationRunStatus.queued.value,
    )
    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    total_targets: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    succeeded_targets: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_targets: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rolled_back_targets: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    transactions = relationship(
        "SecretMigrationTransaction",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
