from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import SecretMigrationTransactionStatus


class SecretMigrationTransaction(Base):
    """Per-target log row for a secret migration run."""

    __tablename__ = "secret_migration_transactions"

    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "target_ref", name="uq_secret_migration_transactions_tenant_run_target"),
        CheckConstraint("attempt_count >= 0", name="ck_secret_migration_tx_attempt_non_negative"),
        Index("ix_secret_migration_tx_tenant_status", "tenant_id", "status"),
        Index("ix_secret_migration_tx_tenant_run", "tenant_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("secret_migration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SecretMigrationTransactionStatus.pending.value,
        server_default=SecretMigrationTransactionStatus.pending.value,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rollback_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    target_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rollback_token: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    run = relationship("SecretMigrationRun", back_populates="transactions", lazy="selectin")
