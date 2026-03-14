"""Graph-backed action detail context built from persisted finding and inventory data."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.action import Action
from backend.models.finding import Finding
from backend.models.inventory_asset import InventoryAsset
from backend.services.canonicalization import build_resource_key

GRAPH_CONTEXT_MAX_RELATED_FINDINGS = 24
GRAPH_CONTEXT_MAX_RELATED_ACTIONS = 24
GRAPH_CONTEXT_MAX_INVENTORY_ASSETS = 24
GRAPH_CONTEXT_MAX_CONNECTED_ASSETS = 6
GRAPH_CONTEXT_MAX_IDENTITY_NODES = 6
GRAPH_CONTEXT_MAX_BLAST_RADIUS_NEIGHBORS = 6

_GRAPH_CONTEXT_SOURCE = "finding_relationship_context+inventory_assets"
_MIN_RELATIONSHIP_CONFIDENCE = 0.75
_RELATIONSHIP_CONTEXT_KEYS = (
    "relationship_context",
    "RelationshipContext",
    "graph_context",
    "GraphContext",
)
_RELATIONSHIP_CONTEXT_PRODUCT_FIELD_KEYS = (
    "aws/autopilot/relationship_context",
    "aws/autopilot/graph_context",
    "relationship_context",
)


@dataclass(frozen=True)
class _GraphAnchor:
    account_id: str
    region: str | None
    resource_id: str | None
    resource_type: str | None
    resource_key: str
    self_resolved: bool = False


async def build_action_graph_context(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: Action,
) -> dict[str, Any]:
    anchor = _graph_anchor(action)
    if anchor is None:
        return _unavailable_graph_context("relationship_context_unavailable")

    related_findings, findings_truncated = await load_related_graph_findings(db, tenant_id=tenant_id, anchor=anchor)
    related_actions, actions_truncated = await load_related_graph_actions(db, tenant_id=tenant_id, anchor=anchor)
    inventory_assets, inventory_truncated = await load_graph_inventory_assets(db, tenant_id=tenant_id, anchor=anchor)
    connected_assets, assets_truncated = _build_connected_assets(
        action,
        anchor=anchor,
        related_findings=related_findings,
        related_actions=related_actions,
        inventory_assets=inventory_assets,
    )
    identity_path, identity_truncated = _build_identity_path(action)
    blast_radius, blast_truncated = _build_blast_radius_neighborhood(
        anchor=anchor,
        related_findings=related_findings,
        related_actions=related_actions,
        inventory_assets=inventory_assets,
    )
    return {
        "status": "available",
        "availability_reason": None,
        "source": _GRAPH_CONTEXT_SOURCE,
        "self_resolved": anchor.self_resolved,
        "connected_assets": connected_assets,
        "identity_path": identity_path,
        "blast_radius_neighborhood": blast_radius,
        "truncated_sections": _truncated_sections(
            connected_assets=assets_truncated or findings_truncated or actions_truncated or inventory_truncated,
            identity_path=identity_truncated,
            blast_radius_neighborhood=blast_truncated or findings_truncated or actions_truncated or inventory_truncated,
        ),
        "limits": _graph_limits_payload(),
    }


async def load_related_graph_findings(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    anchor: _GraphAnchor,
) -> tuple[list[Finding], bool]:
    stmt = (
        select(Finding)
        .where(
            Finding.tenant_id == tenant_id,
            Finding.account_id == anchor.account_id,
            Finding.resource_key.in_(sorted(_neighbor_resource_keys(anchor))),
        )
        .order_by(Finding.updated_at.desc())
        .limit(GRAPH_CONTEXT_MAX_RELATED_FINDINGS + 1)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return _bounded_rows(rows, GRAPH_CONTEXT_MAX_RELATED_FINDINGS)


async def load_related_graph_actions(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    anchor: _GraphAnchor,
) -> tuple[list[Action], bool]:
    stmt = (
        select(Action)
        .where(
            Action.tenant_id == tenant_id,
            Action.account_id == anchor.account_id,
            _related_action_filter(anchor),
        )
        .order_by(Action.updated_at.desc())
        .limit(GRAPH_CONTEXT_MAX_RELATED_ACTIONS + 1)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return _bounded_rows(rows, GRAPH_CONTEXT_MAX_RELATED_ACTIONS)


async def load_graph_inventory_assets(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    anchor: _GraphAnchor,
) -> tuple[list[InventoryAsset], bool]:
    stmt = (
        select(InventoryAsset)
        .where(
            InventoryAsset.tenant_id == tenant_id,
            InventoryAsset.account_id == anchor.account_id,
            _inventory_asset_filter(anchor),
        )
        .order_by(InventoryAsset.last_seen_at.desc())
        .limit(GRAPH_CONTEXT_MAX_INVENTORY_ASSETS + 1)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return _bounded_rows(rows, GRAPH_CONTEXT_MAX_INVENTORY_ASSETS)


def _graph_anchor(action: Action) -> _GraphAnchor | None:
    relationship = _relationship_context_payload(action)
    provider_complete = _relationship_context_complete(relationship)
    account_id = _normalized_text((relationship or {}).get("account_id")) or _normalized_text(getattr(action, "account_id", None))
    region = _normalized_text((relationship or {}).get("region")) or _normalized_text(getattr(action, "region", None))
    resource_id = _normalized_text((relationship or {}).get("resource_id")) or _normalized_text(getattr(action, "resource_id", None))
    resource_type = _normalized_text((relationship or {}).get("resource_type")) or _normalized_text(getattr(action, "resource_type", None))
    resource_key = _normalized_text((relationship or {}).get("resource_key")) or _build_resource_key_for_action(
        account_id=account_id,
        region=region,
        resource_id=resource_id,
        resource_type=resource_type,
    )
    if account_id is None:
        return None
    if resource_key is None:
        # Last-resort: anchor to the account (optionally scoped by region).
        resource_key = f"account:{account_id}:region:{region}" if region else f"account:{account_id}"
    return _GraphAnchor(
        account_id=account_id,
        region=region,
        resource_id=resource_id,
        resource_type=resource_type,
        resource_key=resource_key,
        self_resolved=not provider_complete,
    )


def _build_connected_assets(
    action: Action,
    *,
    anchor: _GraphAnchor,
    related_findings: list[Finding],
    related_actions: list[Action],
    inventory_assets: list[InventoryAsset],
) -> tuple[list[dict[str, Any]], bool]:
    assets: dict[str, dict[str, Any]] = {}
    _record_asset(
        assets,
        resource_key=anchor.resource_key,
        resource_id=anchor.resource_id,
        resource_type=anchor.resource_type,
        relationship="anchor",
    )
    for finding in related_findings:
        _record_asset_from_finding(assets, anchor=anchor, finding=finding)
        for resource in _finding_resources(finding):
            _record_asset(assets, relationship="linked_resource", **resource)
    for inventory in inventory_assets:
        _record_asset_from_inventory(assets, anchor=anchor, inventory=inventory)
    for related_action in related_actions:
        _increment_asset_action_count(assets, action=related_action, anchor=anchor)
    ordered = sorted(assets.values(), key=_asset_sort_key)
    return _bounded_rows(_finalize_assets(ordered), GRAPH_CONTEXT_MAX_CONNECTED_ASSETS)


def _build_identity_path(action: Action) -> tuple[list[dict[str, Any]], bool]:
    nodes = _identity_hint_nodes(action)
    if not nodes:
        return [], False
    tail = _identity_tail_nodes(action)
    budget = max(0, GRAPH_CONTEXT_MAX_IDENTITY_NODES - len(tail))
    ordered = nodes[:budget] + tail
    return _bounded_rows(ordered, GRAPH_CONTEXT_MAX_IDENTITY_NODES)


def _build_blast_radius_neighborhood(
    *,
    anchor: _GraphAnchor,
    related_findings: list[Finding],
    related_actions: list[Action],
    inventory_assets: list[InventoryAsset],
) -> tuple[list[dict[str, Any]], bool]:
    neighbors: dict[str, dict[str, Any]] = {}
    for finding in related_findings:
        _increment_neighbor_finding(neighbors, anchor=anchor, finding=finding)
    for action in related_actions:
        _increment_neighbor_action(neighbors, anchor=anchor, action=action)
    for inventory in inventory_assets:
        _increment_neighbor_inventory(neighbors, anchor=anchor, inventory=inventory)
    ordered = sorted(neighbors.values(), key=_neighbor_sort_key)
    return _bounded_rows(ordered, GRAPH_CONTEXT_MAX_BLAST_RADIUS_NEIGHBORS)


def _record_asset_from_finding(
    assets: dict[str, dict[str, Any]],
    *,
    anchor: _GraphAnchor,
    finding: Finding,
) -> None:
    relationship = "anchor" if _finding_resource_key(finding) == anchor.resource_key else "account_support"
    _record_asset(
        assets,
        resource_key=_finding_resource_key(finding),
        resource_id=_normalized_text(getattr(finding, "resource_id", None)),
        resource_type=_normalized_text(getattr(finding, "resource_type", None)),
        relationship=relationship,
        finding_count=1,
    )


def _record_asset_from_inventory(
    assets: dict[str, dict[str, Any]],
    *,
    anchor: _GraphAnchor,
    inventory: InventoryAsset,
) -> None:
    relationship = "anchor" if _inventory_resource_key(inventory) == anchor.resource_key else "inventory_support"
    _record_asset(
        assets,
        resource_key=_inventory_resource_key(inventory),
        resource_id=_normalized_text(inventory.resource_id),
        resource_type=_normalized_text(inventory.resource_type),
        relationship=relationship,
        inventory_service=str(inventory.service),
    )


def _increment_asset_action_count(
    assets: dict[str, dict[str, Any]],
    *,
    action: Action,
    anchor: _GraphAnchor,
) -> None:
    resource_key = _action_resource_key(action)
    if resource_key is None:
        return
    relationship = "anchor" if resource_key == anchor.resource_key else "account_support"
    _record_asset(
        assets,
        resource_key=resource_key,
        resource_id=_normalized_text(getattr(action, "resource_id", None)),
        resource_type=_normalized_text(getattr(action, "resource_type", None)),
        relationship=relationship,
        action_count=1,
    )


def _record_asset(
    assets: dict[str, dict[str, Any]],
    *,
    resource_key: str | None,
    resource_id: str | None,
    resource_type: str | None,
    relationship: str,
    finding_count: int = 0,
    action_count: int = 0,
    inventory_service: str | None = None,
) -> None:
    if resource_key is None and resource_id is None and resource_type is None:
        return
    key = _asset_identity_key(resource_key, resource_id, resource_type)
    asset = assets.setdefault(
        key,
        {
            "resource_key": resource_key,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "relationship": relationship,
            "label": _asset_label(resource_type, resource_id, resource_key),
            "finding_count": 0,
            "action_count": 0,
            "inventory_services": set(),
        },
    )
    asset["finding_count"] += finding_count
    asset["action_count"] += action_count
    asset["relationship"] = _preferred_relationship(asset["relationship"], relationship)
    if inventory_service:
        asset["inventory_services"].add(inventory_service)


def _increment_neighbor_finding(
    neighbors: dict[str, dict[str, Any]],
    *,
    anchor: _GraphAnchor,
    finding: Finding,
) -> None:
    _record_neighbor(
        neighbors,
        anchor=anchor,
        resource_key=_finding_resource_key(finding),
        resource_id=_normalized_text(getattr(finding, "resource_id", None)),
        resource_type=_normalized_text(getattr(finding, "resource_type", None)),
        control_id=_normalized_text(getattr(finding, "control_id", None)),
        finding_count=1,
    )


def _increment_neighbor_action(
    neighbors: dict[str, dict[str, Any]],
    *,
    anchor: _GraphAnchor,
    action: Action,
) -> None:
    _record_neighbor(
        neighbors,
        anchor=anchor,
        resource_key=_action_resource_key(action),
        resource_id=_normalized_text(getattr(action, "resource_id", None)),
        resource_type=_normalized_text(getattr(action, "resource_type", None)),
        control_id=_normalized_text(getattr(action, "control_id", None)),
        action_count=1,
    )


def _increment_neighbor_inventory(
    neighbors: dict[str, dict[str, Any]],
    *,
    anchor: _GraphAnchor,
    inventory: InventoryAsset,
) -> None:
    _record_neighbor(
        neighbors,
        anchor=anchor,
        resource_key=_inventory_resource_key(inventory),
        resource_id=_normalized_text(inventory.resource_id),
        resource_type=_normalized_text(inventory.resource_type),
        control_id=None,
        inventory_service=inventory.service,
    )


def _record_neighbor(
    neighbors: dict[str, dict[str, Any]],
    *,
    anchor: _GraphAnchor,
    resource_key: str | None,
    resource_id: str | None,
    resource_type: str | None,
    control_id: str | None,
    finding_count: int = 0,
    action_count: int = 0,
    inventory_service: str | None = None,
) -> None:
    if resource_key is None and resource_id is None:
        return
    key = _asset_identity_key(resource_key, resource_id, resource_type)
    neighbor = neighbors.setdefault(
        key,
        {
            "scope": _neighbor_scope(anchor, resource_key),
            "label": _asset_label(resource_type, resource_id, resource_key),
            "resource_key": resource_key,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "finding_count": 0,
            "open_action_count": 0,
            "inventory_service_count": 0,
            "controls": set(),
        },
    )
    neighbor["finding_count"] += finding_count
    neighbor["open_action_count"] += action_count
    if control_id:
        neighbor["controls"].add(control_id)
    if inventory_service:
        neighbor["inventory_service_count"] += 1


def _identity_hint_nodes(action: Action) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    for raw in _linked_raw_payloads(action):
        nodes.extend(_identity_nodes_from_principal(raw.get("principal")))
        nodes.extend(_identity_nodes_from_resources(raw.get("Resources")))
        nodes.extend(_identity_nodes_from_product_fields(raw.get("ProductFields")))
    return _dedupe_nodes(nodes)


def _identity_nodes_from_principal(value: Any) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    for item in _flatten_identity_values(value):
        nodes.append({"node_type": "principal", "label": item, "value": item, "source": "finding.raw_json.principal"})
    return nodes


def _identity_nodes_from_resources(value: Any) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    for resource in value if isinstance(value, list) else []:
        if not isinstance(resource, dict):
            continue
        resource_id = _normalized_text(resource.get("Id"))
        resource_type = _normalized_text(resource.get("Type"))
        if not _looks_like_identity_resource(resource_id, resource_type):
            continue
        label = _asset_label(resource_type, resource_id, resource_id)
        nodes.append({"node_type": "principal", "label": label, "value": resource_id or label, "source": "finding.raw_json.Resources"})
    return nodes


def _identity_nodes_from_product_fields(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    nodes: list[dict[str, str]] = []
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip().lower()
        text = _normalized_text(raw_value)
        if not key or text is None or not _looks_like_identity_value(text):
            continue
        if any(token in key for token in ("principal", "role", "user", "arn")):
            nodes.append({"node_type": "principal", "label": text, "value": text, "source": f"finding.raw_json.ProductFields.{raw_key}"})
    return nodes


def _identity_tail_nodes(action: Action) -> list[dict[str, str]]:
    account_id = _normalized_text(getattr(action, "account_id", None))
    resource_id = _normalized_text(getattr(action, "resource_id", None))
    resource_type = _normalized_text(getattr(action, "resource_type", None))
    tail: list[dict[str, str]] = []
    if account_id:
        tail.append({"node_type": "account", "label": account_id, "value": account_id, "source": "action.account_id"})
    if resource_id and resource_id != account_id:
        tail.append(
            {
                "node_type": "resource",
                "label": _asset_label(resource_type, resource_id, resource_id),
                "value": resource_id,
                "source": "action.resource_id",
            }
        )
    return tail


def _finding_resources(finding: Finding) -> list[dict[str, str | None]]:
    resources = getattr(finding, "raw_json", None)
    if not isinstance(resources, dict):
        return []
    items = resources.get("Resources")
    if not isinstance(items, list):
        return []
    output: list[dict[str, str | None]] = []
    for resource in items:
        if not isinstance(resource, dict):
            continue
        resource_id = _normalized_text(resource.get("Id"))
        resource_type = _normalized_text(resource.get("Type"))
        resource_key = _build_resource_key_from_resource(resource_id=resource_id, resource_type=resource_type, finding=finding)
        output.append(
            {
                "resource_id": resource_id,
                "resource_type": resource_type,
                "resource_key": resource_key,
            }
        )
    return output


def _linked_raw_payloads(action: Action) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for link in getattr(action, "action_finding_links", None) or []:
        raw = getattr(getattr(link, "finding", None), "raw_json", None)
        if isinstance(raw, dict):
            payloads.append(raw)
    return payloads


def _relationship_context_payload(action: Action) -> dict[str, Any] | None:
    payload = _mapping((getattr(action, "score_components", None) or {}).get("relationship_context"))
    if payload:
        return payload
    for raw in _linked_raw_payloads(action):
        payload = _raw_relationship_context(raw)
        if payload:
            return payload
    return None


def _raw_relationship_context(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    for key in _RELATIONSHIP_CONTEXT_KEYS:
        payload = _mapping(raw.get(key))
        if payload:
            return payload
    product_fields = raw.get("ProductFields")
    if isinstance(product_fields, dict):
        for key in _RELATIONSHIP_CONTEXT_PRODUCT_FIELD_KEYS:
            payload = _mapping(product_fields.get(key))
            if payload:
                return payload
    return None


def _mapping(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _relationship_context_complete(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    confidence = _float_value(payload.get("confidence"))
    return bool(payload.get("complete")) and confidence >= _MIN_RELATIONSHIP_CONFIDENCE


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _neighbor_resource_keys(anchor: _GraphAnchor) -> set[str]:
    keys = {anchor.resource_key, f"account:{anchor.account_id}"}
    if anchor.region:
        keys.add(f"account:{anchor.account_id}:region:{anchor.region}")
    return keys


def _related_action_filter(anchor: _GraphAnchor) -> Any:
    account_scope = and_(
        Action.resource_id == anchor.account_id,
        Action.resource_type == "AwsAccount",
        _region_support_filter(anchor.region),
    )
    if not anchor.resource_id or anchor.resource_id == anchor.account_id:
        return account_scope
    return or_(
        and_(Action.resource_id == anchor.resource_id, Action.resource_type == anchor.resource_type),
        account_scope,
    )


def _inventory_asset_filter(anchor: _GraphAnchor) -> Any:
    account_scope = and_(InventoryAsset.resource_id == anchor.account_id, _region_inventory_filter(anchor.region))
    if not anchor.resource_id or anchor.resource_id == anchor.account_id:
        return account_scope
    return or_(InventoryAsset.resource_id == anchor.resource_id, account_scope)


def _region_support_filter(region: str | None) -> Any:
    if region is None:
        return True
    return or_(Action.region == region, Action.region.is_(None))


def _region_inventory_filter(region: str | None) -> Any:
    if region is None:
        return True
    return InventoryAsset.region == region


def _action_resource_key(action: Action) -> str | None:
    return _build_resource_key_for_action(
        account_id=_normalized_text(getattr(action, "account_id", None)),
        region=_normalized_text(getattr(action, "region", None)),
        resource_id=_normalized_text(getattr(action, "resource_id", None)),
        resource_type=_normalized_text(getattr(action, "resource_type", None)),
    )


def _inventory_resource_key(inventory: InventoryAsset) -> str | None:
    return build_resource_key(
        account_id=str(inventory.account_id),
        region=_normalized_text(inventory.region),
        resource_id=_normalized_text(inventory.resource_id),
        resource_type=_normalized_text(inventory.resource_type),
    )


def _finding_resource_key(finding: Finding) -> str | None:
    existing = _normalized_text(getattr(finding, "resource_key", None))
    if existing:
        return existing
    return _build_resource_key_from_resource(
        resource_id=_normalized_text(getattr(finding, "resource_id", None)),
        resource_type=_normalized_text(getattr(finding, "resource_type", None)),
        finding=finding,
    )


def _build_resource_key_from_resource(
    *,
    resource_id: str | None,
    resource_type: str | None,
    finding: Finding,
) -> str | None:
    return build_resource_key(
        account_id=str(getattr(finding, "account_id", "") or ""),
        region=_normalized_text(getattr(finding, "region", None)),
        resource_id=resource_id,
        resource_type=resource_type,
    )


def _build_resource_key_for_action(
    *,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
) -> str | None:
    if account_id is None:
        return None
    return build_resource_key(
        account_id=account_id,
        region=region,
        resource_id=resource_id,
        resource_type=resource_type,
    )


def _flatten_identity_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if _looks_like_identity_value(value) else []
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_identity_values(item))
        return flattened
    if isinstance(value, dict):
        flattened: list[str] = []
        for item in value.values():
            flattened.extend(_flatten_identity_values(item))
        return flattened
    return []


def _looks_like_identity_resource(resource_id: str | None, resource_type: str | None) -> bool:
    if resource_type and resource_type.startswith("AwsIam"):
        return True
    return bool(resource_id and "arn:aws:iam::" in resource_id)


def _looks_like_identity_value(value: str) -> bool:
    text = value.strip().lower()
    return "arn:aws:iam::" in text or text.endswith(".amazonaws.com") or text.endswith(":root")


def _dedupe_nodes(nodes: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, str]] = []
    for node in nodes:
        identity = (node["node_type"], node["label"], node["source"])
        if identity in seen:
            continue
        seen.add(identity)
        output.append(node)
    return output


def _asset_identity_key(resource_key: str | None, resource_id: str | None, resource_type: str | None) -> str:
    return resource_key or f"{resource_type or 'unknown'}:{resource_id or 'unknown'}"


def _asset_label(resource_type: str | None, resource_id: str | None, resource_key: str | None) -> str:
    if resource_id:
        return resource_id
    if resource_key:
        return resource_key
    return resource_type or "resource"


def _preferred_relationship(current: str, incoming: str) -> str:
    ranking = {"anchor": 0, "linked_resource": 1, "account_support": 2, "inventory_support": 3}
    return current if ranking.get(current, 99) <= ranking.get(incoming, 99) else incoming


def _neighbor_scope(anchor: _GraphAnchor, resource_key: str | None) -> str:
    if resource_key == anchor.resource_key:
        return "anchor"
    if resource_key == f"account:{anchor.account_id}":
        return "account"
    return "related"


def _asset_sort_key(asset: dict[str, Any]) -> tuple[int, int, int, str]:
    ranking = {"anchor": 0, "linked_resource": 1, "account_support": 2, "inventory_support": 3}
    return (
        ranking.get(str(asset.get("relationship")), 99),
        -int(asset.get("action_count", 0) or 0),
        -int(asset.get("finding_count", 0) or 0),
        str(asset.get("label") or ""),
    )


def _neighbor_sort_key(neighbor: dict[str, Any]) -> tuple[int, int, int, str]:
    ranking = {"anchor": 0, "account": 1, "related": 2}
    return (
        ranking.get(str(neighbor.get("scope")), 99),
        -int(neighbor.get("open_action_count", 0) or 0),
        -int(neighbor.get("finding_count", 0) or 0),
        str(neighbor.get("label") or ""),
    )


def _finalize_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    for asset in assets:
        finalized.append(
            {
                **asset,
                "inventory_services": sorted(asset.get("inventory_services", set())),
            }
        )
    return finalized


def _bounded_rows(rows: list[Any], limit: int) -> tuple[list[Any], bool]:
    return rows[:limit], len(rows) > limit


def _graph_limits_payload() -> dict[str, int]:
    return {
        "max_related_findings": GRAPH_CONTEXT_MAX_RELATED_FINDINGS,
        "max_related_actions": GRAPH_CONTEXT_MAX_RELATED_ACTIONS,
        "max_inventory_assets": GRAPH_CONTEXT_MAX_INVENTORY_ASSETS,
        "max_connected_assets": GRAPH_CONTEXT_MAX_CONNECTED_ASSETS,
        "max_identity_nodes": GRAPH_CONTEXT_MAX_IDENTITY_NODES,
        "max_blast_radius_neighbors": GRAPH_CONTEXT_MAX_BLAST_RADIUS_NEIGHBORS,
    }


def _truncated_sections(**flags: bool) -> list[str]:
    return [name for name, enabled in flags.items() if enabled]


def _unavailable_graph_context(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "availability_reason": reason,
        "source": _GRAPH_CONTEXT_SOURCE,
        "self_resolved": False,
        "connected_assets": [],
        "identity_path": [],
        "blast_radius_neighborhood": [],
        "truncated_sections": [],
        "limits": _graph_limits_payload(),
    }


def _normalized_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
