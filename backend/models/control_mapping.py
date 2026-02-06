# backend/models/control_mapping.py
"""Control mapping model (Step 12.3): maps Security Hub control_id to audit frameworks."""
from __future__ import annotations

import uuid
from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ControlMapping(Base):
    """
    One row per (control_id, framework_name): maps a Security Hub control
    (e.g. S3.1, CloudTrail.1) to an audit framework control (SOC 2, CIS, ISO 27001).
    Global v1 mapping; tenant_id can be added later for overrides.
    """

    __tablename__ = "control_mappings"

    __table_args__ = (
        UniqueConstraint(
            "control_id",
            "framework_name",
            name="uq_control_mappings_control_framework",
        ),
        Index("idx_control_mappings_control_id", "control_id"),
        Index("idx_control_mappings_framework", "framework_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    control_id: Mapped[str] = mapped_column(String(64), nullable=False)
    framework_name: Mapped[str] = mapped_column(String(128), nullable=False)
    framework_control_code: Mapped[str] = mapped_column(String(64), nullable=False)
    control_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
