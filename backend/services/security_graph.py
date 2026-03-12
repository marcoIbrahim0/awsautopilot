from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from sqlalchemy.orm import Session, selectinload

from backend.models import Action, ActionFinding, Finding, SecurityGraphEdge, SecurityGraphNode
from backend.services.canonicalization import build_resource_key
from backend.services.action_scoring import score_action_finding
from backend.services.risk_signals import signals_from_score_components

_IDENTITY_RESOURCE_TYPES = frozenset(
    {
        "AwsAccount",
        "AwsIamAccessKey",
        "AwsIamGroup",
        "AwsIamPolicy",
        "AwsIamRole",
        "AwsIamUser",
        "AwsIamInstanceProfile",
    }
)
_GRAPH_NODE_TYPES = frozenset({"resource", "identity", "exposure", "finding", "action"})


@dataclass(frozen=True)
class GraphNodeSpec:
    node_type: str
    node_key: str
    account_id: str
    region: str | None
    display_name: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class GraphEdgeSpec:
    edge_type: str
    edge_key: str
    source_node_key: str
    target_node_key: str
    account_id: str
    region: str | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class GraphSnapshot:
    nodes: tuple[GraphNodeSpec, ...]
    edges: tuple[GraphEdgeSpec, ...]


class _GraphBuilder:
    def __init__(self, tenant_id: uuid.UUID):
        self._tenant_id = tenant_id
        self._nodes: dict[str, GraphNodeSpec] = {}
        self._edges: dict[str, GraphEdgeSpec] = {}

    def add_action(self, action: Action) -> None:
        action_node = _action_node_spec(action)
        self._add_node(action_node)
        self._add_target_relationship(action, action_node)
        self._add_exposure_relationships(action, action_node, _entity_signals(action))
        for finding in _tenant_scoped_findings(action, self._tenant_id):
            self._add_finding(action_node, finding)

    def snapshot(self) -> GraphSnapshot:
        return GraphSnapshot(nodes=tuple(self._nodes.values()), edges=tuple(self._edges.values()))

    def _add_finding(self, action_node: GraphNodeSpec, finding: Finding) -> None:
        finding_node = _finding_node_spec(finding)
        self._add_node(finding_node)
        self._add_edge(_action_finding_edge(action_node, finding_node))
        self._add_target_relationship(finding, finding_node)
        self._add_exposure_relationships(finding, finding_node, _entity_signals(finding))

    def _add_target_relationship(self, entity: Any, source_node: GraphNodeSpec) -> None:
        target_node = _target_node_spec(entity)
        if target_node is None:
            return
        self._add_node(target_node)
        self._add_edge(_target_edge(source_node, target_node))

    def _add_exposure_relationships(
        self,
        entity: Any,
        source_node: GraphNodeSpec,
        signals: Iterable[str],
    ) -> None:
        for signal in sorted(set(signals)):
            exposure_node = _exposure_node_spec(entity, signal)
            self._add_node(exposure_node)
            self._add_edge(_exposure_edge(source_node, exposure_node, signal))

    def _add_node(self, spec: GraphNodeSpec) -> None:
        if spec.node_type not in _GRAPH_NODE_TYPES:
            raise ValueError(f"unsupported graph node type: {spec.node_type}")
        self._nodes[spec.node_key] = spec

    def _add_edge(self, spec: GraphEdgeSpec) -> None:
        self._edges[spec.edge_key] = spec


def build_security_graph_snapshot(actions: Sequence[Action], tenant_id: uuid.UUID) -> GraphSnapshot:
    builder = _GraphBuilder(tenant_id)
    for action in actions:
        builder.add_action(action)
    return builder.snapshot()


def sync_security_graph_for_scope(
    session: Session,
    tenant_id: uuid.UUID,
    account_id: str | None = None,
    region: str | None = None,
) -> dict[str, int]:
    actions = _scoped_actions(session, tenant_id, account_id=account_id, region=region)
    snapshot = build_security_graph_snapshot(actions, tenant_id)
    node_counts, node_map = _upsert_nodes(session, tenant_id, snapshot.nodes)
    edge_counts = _upsert_edges(session, tenant_id, snapshot.edges, node_map)
    deleted_edges = _delete_stale_edges(session, tenant_id, snapshot.edges, account_id=account_id, region=region)
    deleted_nodes = _delete_stale_nodes(session, tenant_id, snapshot.nodes, account_id=account_id, region=region)
    return {
        **node_counts,
        **edge_counts,
        "graph_edges_deleted": deleted_edges,
        "graph_nodes_deleted": deleted_nodes,
    }


def _scoped_actions(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    account_id: str | None,
    region: str | None,
) -> list[Action]:
    query = session.query(Action).options(selectinload(Action.action_finding_links).selectinload(ActionFinding.finding))
    query = query.filter(Action.tenant_id == tenant_id)
    if account_id is not None:
        query = query.filter(Action.account_id == account_id)
    if region is not None:
        query = query.filter(Action.region == region)
    return query.all()


def _upsert_nodes(
    session: Session,
    tenant_id: uuid.UUID,
    node_specs: Sequence[GraphNodeSpec],
) -> tuple[dict[str, int], dict[str, SecurityGraphNode]]:
    existing = _existing_nodes_by_key(session, tenant_id, [node.node_key for node in node_specs])
    created = 0
    updated = 0
    for spec in node_specs:
        row = existing.get(spec.node_key)
        if row is None:
            row = _new_node_row(tenant_id, spec)
            session.add(row)
            existing[spec.node_key] = row
            created += 1
            continue
        _apply_node_spec(row, spec)
        updated += 1
    return {"graph_nodes_created": created, "graph_nodes_updated": updated}, existing


def _upsert_edges(
    session: Session,
    tenant_id: uuid.UUID,
    edge_specs: Sequence[GraphEdgeSpec],
    node_map: dict[str, SecurityGraphNode],
) -> dict[str, int]:
    existing = _existing_edges_by_key(session, tenant_id, [edge.edge_key for edge in edge_specs])
    created = 0
    updated = 0
    for spec in edge_specs:
        row = existing.get(spec.edge_key)
        if row is None:
            session.add(_new_edge_row(tenant_id, spec, node_map))
            created += 1
            continue
        _apply_edge_spec(row, spec, node_map)
        updated += 1
    return {"graph_edges_created": created, "graph_edges_updated": updated}


def _existing_nodes_by_key(
    session: Session,
    tenant_id: uuid.UUID,
    node_keys: Sequence[str],
) -> dict[str, SecurityGraphNode]:
    if not node_keys:
        return {}
    rows = (
        session.query(SecurityGraphNode)
        .filter(
            SecurityGraphNode.tenant_id == tenant_id,
            SecurityGraphNode.node_key.in_(list(node_keys)),
        )
        .all()
    )
    return {row.node_key: row for row in rows}


def _existing_edges_by_key(
    session: Session,
    tenant_id: uuid.UUID,
    edge_keys: Sequence[str],
) -> dict[str, SecurityGraphEdge]:
    if not edge_keys:
        return {}
    rows = (
        session.query(SecurityGraphEdge)
        .filter(
            SecurityGraphEdge.tenant_id == tenant_id,
            SecurityGraphEdge.edge_key.in_(list(edge_keys)),
        )
        .all()
    )
    return {row.edge_key: row for row in rows}


def _delete_stale_edges(
    session: Session,
    tenant_id: uuid.UUID,
    edge_specs: Sequence[GraphEdgeSpec],
    *,
    account_id: str | None,
    region: str | None,
) -> int:
    desired = {edge.edge_key for edge in edge_specs}
    removed = 0
    for row in _scoped_edges(session, tenant_id, account_id=account_id, region=region):
        if row.edge_key in desired:
            continue
        session.delete(row)
        removed += 1
    return removed


def _delete_stale_nodes(
    session: Session,
    tenant_id: uuid.UUID,
    node_specs: Sequence[GraphNodeSpec],
    *,
    account_id: str | None,
    region: str | None,
) -> int:
    desired = {node.node_key for node in node_specs}
    removed = 0
    for row in _scoped_nodes(session, tenant_id, account_id=account_id, region=region):
        if row.node_key in desired:
            continue
        session.delete(row)
        removed += 1
    return removed


def _scoped_nodes(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    account_id: str | None,
    region: str | None,
) -> list[SecurityGraphNode]:
    query = session.query(SecurityGraphNode).filter(SecurityGraphNode.tenant_id == tenant_id)
    if account_id is not None:
        query = query.filter(SecurityGraphNode.account_id == account_id)
    if region is not None:
        query = query.filter(SecurityGraphNode.region == region)
    return query.all()


def _scoped_edges(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    account_id: str | None,
    region: str | None,
) -> list[SecurityGraphEdge]:
    query = session.query(SecurityGraphEdge).filter(SecurityGraphEdge.tenant_id == tenant_id)
    if account_id is not None:
        query = query.filter(SecurityGraphEdge.account_id == account_id)
    if region is not None:
        query = query.filter(SecurityGraphEdge.region == region)
    return query.all()


def _new_node_row(tenant_id: uuid.UUID, spec: GraphNodeSpec) -> SecurityGraphNode:
    return SecurityGraphNode(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        account_id=spec.account_id,
        region=spec.region,
        node_type=spec.node_type,
        node_key=spec.node_key,
        display_name=spec.display_name,
        metadata_json=spec.metadata_json,
    )


def _new_edge_row(
    tenant_id: uuid.UUID,
    spec: GraphEdgeSpec,
    node_map: dict[str, SecurityGraphNode],
) -> SecurityGraphEdge:
    return SecurityGraphEdge(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        account_id=spec.account_id,
        region=spec.region,
        edge_type=spec.edge_type,
        edge_key=spec.edge_key,
        source_node_id=_node_id(node_map, spec.source_node_key),
        target_node_id=_node_id(node_map, spec.target_node_key),
        metadata_json=spec.metadata_json,
    )


def _apply_node_spec(row: SecurityGraphNode, spec: GraphNodeSpec) -> None:
    row.account_id = spec.account_id
    row.region = spec.region
    row.node_type = spec.node_type
    row.display_name = spec.display_name
    row.metadata_json = spec.metadata_json


def _apply_edge_spec(
    row: SecurityGraphEdge,
    spec: GraphEdgeSpec,
    node_map: dict[str, SecurityGraphNode],
) -> None:
    row.account_id = spec.account_id
    row.region = spec.region
    row.edge_type = spec.edge_type
    row.source_node_id = _node_id(node_map, spec.source_node_key)
    row.target_node_id = _node_id(node_map, spec.target_node_key)
    row.metadata_json = spec.metadata_json


def _node_id(node_map: dict[str, SecurityGraphNode], node_key: str) -> uuid.UUID:
    row = node_map.get(node_key)
    if row is None or row.id is None:
        raise ValueError(f"security graph node missing for key={node_key}")
    return row.id


def _action_node_spec(action: Action) -> GraphNodeSpec:
    return GraphNodeSpec(
        node_type="action",
        node_key=_stable_key("action", str(action.id)),
        account_id=action.account_id,
        region=action.region,
        display_name=_display_name(getattr(action, "title", None), fallback="Action"),
        metadata_json=_action_metadata(action),
    )


def _finding_node_spec(finding: Finding) -> GraphNodeSpec:
    return GraphNodeSpec(
        node_type="finding",
        node_key=_stable_key("finding", str(finding.id)),
        account_id=finding.account_id,
        region=finding.region,
        display_name=_display_name(getattr(finding, "title", None), fallback="Finding"),
        metadata_json=_finding_metadata(finding),
    )


def _target_node_spec(entity: Any) -> GraphNodeSpec | None:
    account_id = _account_id(entity)
    resource_key = _resource_key(entity)
    node_type = _target_node_type(entity, resource_key)
    if node_type is None:
        return None
    return GraphNodeSpec(
        node_type=node_type,
        node_key=_stable_key(node_type, account_id, resource_key or _resource_id(entity)),
        account_id=account_id,
        region=_target_region(entity, node_type, resource_key),
        display_name=_display_name(_resource_id(entity), fallback=resource_key or account_id),
        metadata_json=_target_metadata(entity, resource_key, node_type),
    )


def _exposure_node_spec(entity: Any, signal: str) -> GraphNodeSpec:
    account_id = _account_id(entity)
    region = _region(entity)
    scope_token = _resource_key(entity) or _resource_id(entity) or account_id
    return GraphNodeSpec(
        node_type="exposure",
        node_key=_stable_key("exposure", account_id, region or "global", scope_token, signal),
        account_id=account_id,
        region=region,
        display_name=_signal_label(signal),
        metadata_json=_exposure_metadata(entity, signal, scope_token),
    )


def _action_finding_edge(action_node: GraphNodeSpec, finding_node: GraphNodeSpec) -> GraphEdgeSpec:
    return _edge_spec(
        "action_derived_from_finding",
        action_node,
        finding_node,
        {"source": "action_findings"},
    )


def _target_edge(source_node: GraphNodeSpec, target_node: GraphNodeSpec) -> GraphEdgeSpec:
    return _edge_spec(
        f"{source_node.node_type}_targets_{target_node.node_type}",
        source_node,
        target_node,
        {"source_node_type": source_node.node_type, "target_node_type": target_node.node_type},
    )


def _exposure_edge(source_node: GraphNodeSpec, target_node: GraphNodeSpec, signal: str) -> GraphEdgeSpec:
    return _edge_spec(
        f"{source_node.node_type}_indicates_exposure",
        source_node,
        target_node,
        {"signal": signal},
    )


def _edge_spec(
    edge_type: str,
    source_node: GraphNodeSpec,
    target_node: GraphNodeSpec,
    metadata_json: dict[str, Any],
) -> GraphEdgeSpec:
    return GraphEdgeSpec(
        edge_type=edge_type,
        edge_key=_stable_key(edge_type, source_node.node_key, target_node.node_key, limit=1024),
        source_node_key=source_node.node_key,
        target_node_key=target_node.node_key,
        account_id=source_node.account_id,
        region=source_node.region,
        metadata_json=metadata_json,
    )


def _tenant_scoped_findings(action: Action, tenant_id: uuid.UUID) -> list[Finding]:
    findings: list[Finding] = []
    for link in getattr(action, "action_finding_links", []) or []:
        finding = getattr(link, "finding", None)
        if not _finding_in_scope(action, finding, tenant_id):
            continue
        findings.append(finding)
    return findings


def _finding_in_scope(action: Action, finding: Finding | None, tenant_id: uuid.UUID) -> bool:
    if finding is None or getattr(finding, "tenant_id", None) != tenant_id:
        return False
    if str(getattr(finding, "account_id", "") or "") != str(getattr(action, "account_id", "") or ""):
        return False
    return _regions_related(getattr(action, "region", None), getattr(finding, "region", None))


def _regions_related(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right


def _entity_signals(entity: Any) -> set[str]:
    if isinstance(entity, Finding):
        return signals_from_score_components(score_action_finding(entity).components)
    return signals_from_score_components(getattr(entity, "score_components", None))


def _target_node_type(entity: Any, resource_key: str | None) -> str | None:
    resource_type = str(getattr(entity, "resource_type", "") or "")
    if resource_type in _IDENTITY_RESOURCE_TYPES:
        return "identity"
    if resource_key and resource_key.startswith("account:"):
        return "identity"
    if _resource_id(entity) or resource_key:
        return "resource"
    return None


def _target_region(entity: Any, node_type: str, resource_key: str | None) -> str | None:
    if node_type != "identity":
        return _region(entity)
    if resource_key and resource_key.startswith("account:"):
        return None
    return _region(entity)


def _action_metadata(action: Action) -> dict[str, Any]:
    return {
        "action_id": str(getattr(action, "id", "") or ""),
        "action_type": str(getattr(action, "action_type", "") or ""),
        "control_id": str(getattr(action, "control_id", "") or ""),
        "resource_id": _resource_id(action),
        "resource_type": str(getattr(action, "resource_type", "") or ""),
        "score": int(getattr(action, "score", 0) or 0),
        "status": str(getattr(action, "status", "") or ""),
        "target_id": str(getattr(action, "target_id", "") or ""),
    }


def _finding_metadata(finding: Finding) -> dict[str, Any]:
    return {
        "finding_db_id": str(getattr(finding, "id", "") or ""),
        "finding_id": str(getattr(finding, "finding_id", "") or ""),
        "control_id": str(getattr(finding, "control_id", "") or ""),
        "resource_id": _resource_id(finding),
        "resource_type": str(getattr(finding, "resource_type", "") or ""),
        "severity_label": str(getattr(finding, "severity_label", "") or ""),
        "status": str(getattr(finding, "status", "") or ""),
    }


def _target_metadata(entity: Any, resource_key: str | None, node_type: str) -> dict[str, Any]:
    return {
        "node_type": node_type,
        "resource_id": _resource_id(entity),
        "resource_key": resource_key,
        "resource_type": str(getattr(entity, "resource_type", "") or ""),
    }


def _exposure_metadata(entity: Any, signal: str, scope_token: str) -> dict[str, Any]:
    return {
        "signal": signal,
        "scope_token": scope_token,
        "resource_key": _resource_key(entity),
        "resource_type": str(getattr(entity, "resource_type", "") or ""),
    }


def _resource_key(entity: Any) -> str | None:
    relationship = _relationship_context(entity)
    if relationship.get("resource_key"):
        return str(relationship["resource_key"])
    account_id = _account_id(entity)
    if not account_id:
        return None
    return build_resource_key(
        account_id=account_id,
        region=_region(entity),
        resource_id=_resource_id(entity),
        resource_type=str(getattr(entity, "resource_type", "") or "") or None,
    )


def _relationship_context(entity: Any) -> dict[str, Any]:
    if isinstance(entity, Finding):
        raw_json = getattr(entity, "raw_json", None)
        if isinstance(raw_json, dict):
            payload = raw_json.get("relationship_context")
            if isinstance(payload, dict):
                return payload
    payload = getattr(entity, "score_components", None)
    if isinstance(payload, dict):
        relationship = payload.get("relationship_context")
        if isinstance(relationship, dict):
            return relationship
    return {}


def _account_id(entity: Any) -> str:
    return str(getattr(entity, "account_id", "") or "")


def _region(entity: Any) -> str | None:
    value = str(getattr(entity, "region", "") or "").strip()
    return value or None


def _resource_id(entity: Any) -> str | None:
    value = str(getattr(entity, "resource_id", "") or "").strip()
    return value or None


def _display_name(value: str | None, *, fallback: str) -> str:
    text = str(value or "").strip()
    return (text or fallback)[:512]


def _signal_label(signal: str) -> str:
    return signal.replace("_", " ").title()[:512]


def _stable_key(prefix: str, *parts: Any, limit: int = 512) -> str:
    raw = "|".join(str(part or "") for part in parts if str(part or ""))
    candidate = f"{prefix}:{raw}" if raw else prefix
    if len(candidate) <= limit:
        return candidate
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    head = candidate[: max(0, limit - len(digest) - 1)]
    return f"{head}:{digest}"
