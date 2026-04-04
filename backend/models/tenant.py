# backend/models/tenant.py
import uuid
from sqlalchemy import Boolean, DateTime, String, Text, func, inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.models.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Used as sts:ExternalId in AssumeRole. Must be unique per tenant.
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Per-tenant control-plane token hash (never store plaintext).
    # Hash is validated against incoming X-Control-Plane-Token.
    control_plane_token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Non-secret token fingerprint safe for settings/audit visibility.
    control_plane_token_fingerprint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    control_plane_token_created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    control_plane_token_revoked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    control_plane_previous_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    control_plane_previous_token_fingerprint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    control_plane_previous_token_expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Idempotency for weekly digest (Step 11.1): skip if digest already sent this week
    last_digest_sent_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional preferences (Step 11.3): only send if digest_enabled; use digest_recipients or tenant admins
    digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    digest_recipients: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Slack delivery (Step 11.4): webhook URL is secret; do not log in full
    slack_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Communication/governance layer settings (default-off rollout).
    governance_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    governance_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    remediation_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    aws_accounts = relationship("AwsAccount", back_populates="tenant", cascade="all, delete-orphan")

    @validates("external_id")
    def _validate_external_id(self, key: str, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Tenant.external_id cannot be empty.")
        state = inspect(self)
        current = str(getattr(self, key, "") or "").strip()
        if state.persistent and current and current != normalized:
            raise ValueError("Tenant.external_id is immutable after tenant creation.")
        return normalized
