# backend/models/action_finding.py
"""Association model linking actions to findings (many-to-many with metadata)."""
from __future__ import annotations

import uuid
from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class ActionFinding(Base):
    """
    Association table: many-to-many between Action and Finding.
    One action can group multiple findings; one finding can map to one or more
    actions when account-scoped findings are expanded into resource targets.
    Supports drill-down from action to source findings and evidence.
    """

    __tablename__ = "action_findings"

    __table_args__ = (
        Index("idx_action_findings_action", "action_id"),
        Index("idx_action_findings_finding", "finding_id"),
    )

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actions.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships (lazy so that models can be loaded in any order)
    action: Mapped["Action"] = relationship("Action", back_populates="action_finding_links")
    finding: Mapped["Finding"] = relationship("Finding", back_populates="action_finding_links")
