# backend/models/aws_account.py
import uuid
from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import AwsAccountStatus


class AwsAccount(Base):
    __tablename__ = "aws_accounts"

    __table_args__ = (
        # Often useful: prevent duplicates per tenant.
        UniqueConstraint("tenant_id", "account_id", name="uq_aws_accounts_tenant_account"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    account_id: Mapped[str] = mapped_column(String(12), index=True, nullable=False)  # AWS account IDs are 12 digits

    role_read_arn: Mapped[str] = mapped_column(String(2048), nullable=False)
    role_write_arn: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Redundant copy (per your requirement). Your app should ensure it matches tenant.external_id.
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    regions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # e.g. ["us-east-1","eu-west-1"]

    status: Mapped[AwsAccountStatus] = mapped_column(
        Enum(AwsAccountStatus, name="aws_account_status"),
        nullable=False,
        default=AwsAccountStatus.pending,
    )

    last_validated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant = relationship("Tenant", back_populates="aws_accounts")
