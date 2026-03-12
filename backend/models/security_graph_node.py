from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class SecurityGraphNode(Base):
    __tablename__ = "security_graph_nodes"

    __table_args__ = (
        UniqueConstraint("tenant_id", "node_key", name="uq_security_graph_nodes_tenant_key"),
        Index(
            "ix_security_graph_nodes_tenant_type_account_region",
            "tenant_id",
            "node_type",
            "account_id",
            "region",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    node_key: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_json: Mapped[dict | list] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    outgoing_edges: Mapped[list["SecurityGraphEdge"]] = relationship(
        "SecurityGraphEdge",
        back_populates="source_node",
        cascade="all, delete-orphan",
        foreign_keys="SecurityGraphEdge.source_node_id",
        lazy="selectin",
    )
    incoming_edges: Mapped[list["SecurityGraphEdge"]] = relationship(
        "SecurityGraphEdge",
        back_populates="target_node",
        cascade="all, delete-orphan",
        foreign_keys="SecurityGraphEdge.target_node_id",
        lazy="selectin",
    )
