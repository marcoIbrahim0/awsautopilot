# backend/models/user_invite.py
"""
User invite model for email-based invitations to join a tenant.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class UserInvite(Base):
    """
    Pending invite for a user to join a tenant.
    
    Unique constraint on (tenant_id, email) ensures only one pending invite per email per tenant.
    Token is used in the invite link: /accept-invite?token={token}
    """
    __tablename__ = "user_invites"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_invites_tenant_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    
    # Token used in invite link (UUID for security)
    token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    
    # When the invite expires
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # User who created the invite (admin)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Allow null if inviter is deleted
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    tenant = relationship("Tenant")
    created_by_user = relationship("User", back_populates="created_invites", foreign_keys=[created_by_user_id])
