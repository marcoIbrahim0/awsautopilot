from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class SecurityGraphEdge(Base):
    __tablename__ = "security_graph_edges"

    __table_args__ = (
        UniqueConstraint("tenant_id", "edge_key", name="uq_security_graph_edges_tenant_key"),
        Index(
            "ix_security_graph_edges_tenant_type_account_region",
            "tenant_id",
            "edge_type",
            "account_id",
            "region",
        ),
        Index("ix_security_graph_edges_tenant_source", "tenant_id", "source_node_id"),
        Index("ix_security_graph_edges_tenant_target", "tenant_id", "target_node_id"),
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
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    edge_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    metadata_json: Mapped[dict | list] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    source_node: Mapped["SecurityGraphNode"] = relationship(
        "SecurityGraphNode",
        back_populates="outgoing_edges",
        foreign_keys=[source_node_id],
    )
    target_node: Mapped["SecurityGraphNode"] = relationship(
        "SecurityGraphNode",
        back_populates="incoming_edges",
        foreign_keys=[target_node_id],
    )
