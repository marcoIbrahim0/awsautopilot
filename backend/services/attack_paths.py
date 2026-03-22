"""Graph-native attack-path helpers built from persisted security graph rows."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.action import Action
from backend.models.security_graph_edge import SecurityGraphEdge
from backend.models.security_graph_node import SecurityGraphNode

_ENTRY_POINT_LIMIT = 2
_CONNECTED_ASSET_LIMIT = 6
_IDENTITY_PATH_LIMIT = 6
_MIN_RELATIONSHIP_CONFIDENCE = 0.75
_STATUS_ORDER = {
    "available": 0,
    "partial": 1,
    "context_incomplete": 2,
    "unavailable": 3,
}


@dataclass(slots=True)
class AttackPathActionProjection:
    path_id: str
    action: Action
    graph_context: dict[str, Any]
    confidence: float
    freshness_score: float
    freshness_observed_at: str | None
    evidence: list[dict[str, Any]]
    provenance: list[dict[str, Any]]
    rank_inputs: dict[str, float]


async def build_attack_path_graph_context(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: Action,
) -> dict[str, Any]:
    relationship = _relationship_context_payload(action)
    if not _relationship_context_complete(relationship):
        return _unavailable_graph("relationship_context_unavailable")
    action_node = await _load_action_node(db, tenant_id=tenant_id, action=action)
    if action_node is None:
        return _unavailable_graph("graph_path_unavailable")
    action_edges, target_nodes = await _load_action_edges(db, tenant_id=tenant_id, action_node=action_node)
    finding_nodes = [node for node in target_nodes if node.node_type == "finding"]
    finding_edges, finding_target_nodes = await _load_finding_edges(db, tenant_id=tenant_id, finding_nodes=finding_nodes)
    nodes = _nodes_by_id(action_node, target_nodes, finding_target_nodes)
    target_nodes = _target_nodes(action_edges, finding_edges, nodes)
    exposure_nodes = _exposure_nodes(action_edges, finding_edges, nodes)
    primary_target = _primary_target_node(target_nodes, action=action, relationship=relationship)
    connected_assets = _connected_assets(primary_target, target_nodes)
    identity_path = _identity_path(primary_target, target_nodes)
    entry_points = _entry_points(exposure_nodes, identity_path)
    truncated = _truncated_sections(exposure_nodes, connected_assets, identity_path)
    status = "available" if primary_target is not None else "unavailable"
    return {
        "status": status,
        "availability_reason": None if status == "available" else "target_assets_unresolved",
        "source": "security_graph_nodes+security_graph_edges",
        "connected_assets": connected_assets,
        "identity_path": identity_path,
        "blast_radius_neighborhood": [],
        "truncated_sections": truncated,
        "limits": {
            "max_related_findings": 24,
            "max_related_actions": 24,
            "max_inventory_assets": 24,
            "max_connected_assets": _CONNECTED_ASSET_LIMIT,
            "max_identity_nodes": _IDENTITY_PATH_LIMIT,
            "max_blast_radius_neighbors": 6,
        },
        "entry_points": entry_points,
        "path_signature": _path_signature(entry_points, identity_path, connected_assets, action),
    }


async def build_shared_attack_path_records(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actions: list[Action],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[AttackPathActionProjection]] = {}
    for action in actions:
        graph_context = await build_attack_path_graph_context(db, tenant_id=tenant_id, action=action)
        projection = _action_projection(action, graph_context)
        grouped.setdefault(projection.path_id, []).append(projection)
    records = [_grouped_record(path_id, projections) for path_id, projections in grouped.items()]
    return sorted(records, key=_record_sort_key)


def build_attack_path_detail_record(
    record: dict[str, Any],
    *,
    path_nodes: list[dict[str, Any]],
    path_edges: list[dict[str, Any]],
    entry_points: list[dict[str, Any]],
    target_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": record["id"],
        "status": record["status"],
        "rank": record["rank"],
        "rank_factors": record["rank_factors"],
        "confidence": record["confidence"],
        "freshness": record["freshness"],
        "path_nodes": path_nodes,
        "path_edges": path_edges,
        "entry_points": entry_points,
        "target_assets": target_assets,
        "business_impact": record["business_impact"],
        "risk_reasons": record["risk_reasons"],
        "owners": record["owners"],
        "recommended_fix": record["recommended_fix"],
        "linked_actions": record["linked_actions"],
        "evidence": record["evidence"],
        "provenance": record["provenance"],
        "remediation_summary": record.get("remediation_summary"),
        "truncated": bool(record.get("truncated")),
        "availability_reason": record.get("availability_reason"),
    }


def attack_path_id_for_graph_context(graph_context: dict[str, Any], action: Action) -> str:
    signature = graph_context.get("path_signature")
    if isinstance(signature, str) and signature:
        return signature
    return f"action:{action.id}"


def _action_projection(action: Action, graph_context: dict[str, Any]) -> AttackPathActionProjection:
    freshness_score, freshness_observed_at = _freshness_payload(action)
    return AttackPathActionProjection(
        path_id=attack_path_id_for_graph_context(graph_context, action),
        action=action,
        graph_context=graph_context,
        confidence=_relationship_confidence(action),
        freshness_score=freshness_score,
        freshness_observed_at=freshness_observed_at,
        evidence=_evidence_payload(action),
        provenance=_provenance_payload(action),
        rank_inputs=_rank_inputs(action, graph_context, freshness_score=freshness_score),
    )


def _grouped_record(path_id: str, projections: list[AttackPathActionProjection]) -> dict[str, Any]:
    representative = max(
        projections,
        key=lambda item: (
            -_STATUS_ORDER.get(_text(item.graph_context.get("status")) or "unavailable", 99),
            int(getattr(item.action, "priority", 0) or getattr(item.action, "score", 0) or 0),
            item.path_id,
            str(item.action.id),
        ),
    )
    linked_actions = sorted(projections, key=lambda item: (-int(item.action.priority or 0), str(item.action.id)))
    owners = sorted({(item.action.owner_label or "Unassigned").strip() or "Unassigned" for item in projections})
    unique_targets = {
        _text(asset.get("resource_key")) or _text(asset.get("resource_id")) or _text(asset.get("label"))
        for item in projections
        for asset in item.graph_context.get("connected_assets", [])
    }
    unique_targets.discard(None)
    factor_inputs = {
        "exploitability": max(item.rank_inputs["exploitability"] for item in projections),
        "internet_reachability": max(item.rank_inputs["internet_reachability"] for item in projections),
        "effective_privilege": max(item.rank_inputs["effective_privilege"] for item in projections),
        "reachable_sensitive_data": max(item.rank_inputs["reachable_sensitive_data"] for item in projections),
        "business_criticality": max(item.rank_inputs["business_criticality"] for item in projections),
        "compensating_controls": max(item.rank_inputs["compensating_controls"] for item in projections),
        "confidence_penalty": 1.0 - max(item.confidence for item in projections),
        "freshness_penalty": 1.0 - max(item.freshness_score for item in projections),
        "blast_radius": min(1.0, max(0.0, ((len(projections) - 1) * 0.25) + ((len(unique_targets) - 1) * 0.2))),
    }
    rank_factors = _rank_factors(factor_inputs)
    rank = _overall_rank(rank_factors)
    confidence = round(max(item.confidence for item in projections), 2)
    freshness_score = max(item.freshness_score for item in projections)
    freshest = max(projections, key=lambda item: (item.freshness_observed_at or "", str(item.action.id)))
    business_impact = _business_impact_summary_payload(representative.action)
    remediation_summary = _remediation_summary(linked_actions)
    return {
        "id": path_id,
        "status": _combined_status(projections),
        "rank": rank,
        "rank_factors": rank_factors,
        "confidence": confidence,
        "freshness": {
            "score": round(freshness_score, 2),
            "observed_at": freshest.freshness_observed_at,
        },
        "business_impact": business_impact,
        "risk_reasons": _risk_reasons(linked_actions[0].action),
        "owners": [
            {
                "key": _text(action.action.owner_key),
                "label": action.action.owner_label or "Unassigned",
            }
            for action in linked_actions
        ],
        "linked_actions": [
            {
                "id": str(item.action.id),
                "title": item.action.title,
                "priority": int(item.action.priority or 0),
                "status": item.action.status,
                "owner_label": item.action.owner_label or "Unassigned",
            }
            for item in linked_actions
        ],
        "linked_action_ids": [str(item.action.id) for item in linked_actions],
        "owner_labels": owners,
        "recommended_fix": _recommended_fix_payload(representative.action),
        "summary": _shared_summary(representative.action, business_impact),
        "business_impact_summary": _text(business_impact.get("summary")),
        "recommended_fix_summary": _recommended_fix_payload(representative.action).get("summary"),
        "remediation_summary": remediation_summary,
        "availability_reason": representative.graph_context.get("availability_reason"),
        "truncated": bool(representative.graph_context.get("truncated_sections")),
        "representative_action": representative.action,
        "representative_graph_context": representative.graph_context,
        "evidence": _merge_unique_dicts(item for projection in projections for item in projection.evidence),
        "provenance": _merge_unique_dicts(item for projection in projections for item in projection.provenance),
    }


def _remediation_summary(linked_actions: list[AttackPathActionProjection]) -> dict[str, Any]:
    open_total = sum(1 for item in linked_actions if item.action.status == "open")
    in_progress_total = sum(1 for item in linked_actions if item.action.status == "in_progress")
    resolved_total = sum(1 for item in linked_actions if item.action.status == "resolved")
    highest_priority_open = max(
        (
            int(item.action.priority or 0)
            for item in linked_actions
            if item.action.status in {"open", "in_progress"}
        ),
        default=None,
    )
    return {
        "linked_actions_total": len(linked_actions),
        "open_actions": open_total,
        "in_progress_actions": in_progress_total,
        "resolved_actions": resolved_total,
        "highest_priority_open": highest_priority_open,
        "coverage_summary": _coverage_summary(
            linked_total=len(linked_actions),
            open_total=open_total,
            in_progress_total=in_progress_total,
            resolved_total=resolved_total,
        ),
    }


def _coverage_summary(*, linked_total: int, open_total: int, in_progress_total: int, resolved_total: int) -> str:
    if linked_total == 0:
        return "No linked remediation actions are attached to this path yet."
    if resolved_total == linked_total:
        return "All linked actions are resolved; keep monitoring for drift or reopen."
    if in_progress_total:
        return f"{in_progress_total} linked actions in progress and {open_total} still open."
    return f"{open_total} linked actions remain open and {resolved_total} already resolved."


def _record_sort_key(record: dict[str, Any]) -> tuple[int, float, str]:
    return (-int(record["rank"]), -float(record["confidence"]), str(record["id"]))


def _combined_status(projections: list[AttackPathActionProjection]) -> str:
    statuses = [_text(item.graph_context.get("status")) or "unavailable" for item in projections]
    if "available" in statuses:
        return "available"
    if "partial" in statuses:
        return "partial"
    if "context_incomplete" in statuses:
        return "context_incomplete"
    return "unavailable"


def _rank_factors(inputs: dict[str, float]) -> list[dict[str, Any]]:
    factors = [
        _rank_factor("exploitability", "Exploitability", inputs["exploitability"], 0.22, "positive", "Exploit-factor and threat-intelligence signals increase urgency."),
        _rank_factor("internet_reachability", "Internet reachability", inputs["internet_reachability"], 0.18, "positive", "Exposure nodes and public-reachability signals increase path risk."),
        _rank_factor("effective_privilege", "Effective privilege", inputs["effective_privilege"], 0.14, "positive", "Privileged identity context increases path impact."),
        _rank_factor("reachable_sensitive_data", "Sensitive data reachability", inputs["reachable_sensitive_data"], 0.14, "positive", "Data-sensitivity signals increase consequence if the path succeeds."),
        _rank_factor("blast_radius", "Blast radius", inputs["blast_radius"], 0.12, "positive", "More linked actions or assets broaden the path neighborhood."),
        _rank_factor("business_criticality", "Business criticality", inputs["business_criticality"], 0.16, "positive", "Business-impact criticality raises prioritization."),
        _rank_factor("compensating_controls", "Compensating controls", inputs["compensating_controls"], 0.12, "negative", "Documented mitigating controls lower the path rank."),
        _rank_factor("freshness_penalty", "Freshness penalty", inputs["freshness_penalty"], 0.06, "negative", "Older evidence slightly reduces urgency."),
        _rank_factor("confidence_penalty", "Confidence penalty", inputs["confidence_penalty"], 0.08, "negative", "Lower relationship confidence reduces rank certainty."),
    ]
    return sorted(factors, key=lambda item: (-abs(float(item["weighted_impact"])), item["name"]))


def _rank_factor(
    name: str,
    label: str,
    value: float,
    weight: float,
    direction: str,
    explanation: str,
) -> dict[str, Any]:
    normalized = round(_clamp(value), 2)
    weighted = round(normalized * weight, 4)
    impact = -weighted if direction == "negative" else weighted
    return {
        "name": name,
        "label": label,
        "direction": direction,
        "score": normalized,
        "weight": weight,
        "weighted_impact": round(impact, 4),
        "explanation": explanation,
    }


def _overall_rank(rank_factors: list[dict[str, Any]]) -> int:
    total = 0.0
    for factor in rank_factors:
        total += float(factor.get("weighted_impact") or 0.0)
    return max(0, min(100, int(round(total * 100))))


def _rank_inputs(action: Action, graph_context: dict[str, Any], *, freshness_score: float) -> dict[str, float]:
    components = _mapping(getattr(action, "score_components", None)) or {}
    return {
        "exploitability": max(
            _normalized_component(components.get("exploit_signals")),
            _signal_present(graph_context.get("entry_points"), "actively_exploited"),
        ),
        "internet_reachability": max(
            _normalized_component(components.get("internet_exposure")),
            _signal_present(graph_context.get("entry_points"), "Public exposure"),
        ),
        "effective_privilege": max(
            _normalized_component(components.get("privilege_level")),
            1.0 if graph_context.get("identity_path") else 0.0,
        ),
        "reachable_sensitive_data": _normalized_component(components.get("data_sensitivity")),
        "business_criticality": _business_criticality_score(components),
        "compensating_controls": _normalized_component(components.get("compensating_controls")),
        "freshness_score": freshness_score,
    }


def _normalized_component(value: Any) -> float:
    payload = _mapping(value) or {}
    normalized = payload.get("normalized")
    if normalized is not None:
        try:
            return _clamp(float(normalized))
        except (TypeError, ValueError):
            return 0.0
    points = payload.get("points")
    max_points = payload.get("factor_max_points") or payload.get("weight") or 20
    try:
        return _clamp(float(points or 0.0) / max(float(max_points or 1.0), 1.0))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _business_criticality_score(components: dict[str, Any]) -> float:
    business = _mapping(components.get("business_impact")) or {}
    criticality = _mapping(business.get("criticality")) or {}
    try:
        return _clamp(float(criticality.get("score") or 0.0) / 100.0)
    except (TypeError, ValueError):
        return 0.0


def _signal_present(items: Any, expected: str) -> float:
    for item in items or []:
        if _text((item or {}).get("label")) == expected:
            return 1.0
    return 0.0


def _freshness_payload(action: Action) -> tuple[float, str | None]:
    timestamps: list[datetime] = []
    exploit = _mapping((_mapping(getattr(action, "score_components", None)) or {}).get("exploit_signals")) or {}
    for signal in exploit.get("applied_threat_signals", []) or []:
        parsed = _parse_datetime((signal or {}).get("timestamp"))
        if parsed is not None:
            timestamps.append(parsed)
    updated = _parse_datetime(getattr(action, "updated_at", None))
    if updated is not None:
        timestamps.append(updated)
    if not timestamps:
        return 0.0, None
    observed_at = max(timestamps)
    age_days = max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds() / 86400.0)
    score = max(0.0, min(1.0, 1.0 - min(age_days, 90.0) / 90.0))
    return round(score, 2), observed_at.isoformat()


def _evidence_payload(action: Action) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for link in getattr(action, "action_finding_links", []) or []:
        finding = getattr(link, "finding", None)
        if finding is None:
            continue
        items.append(
            {
                "type": "finding",
                "id": _text(getattr(finding, "finding_id", None)) or str(getattr(finding, "id", "")),
                "label": _text(getattr(finding, "title", None)) or "Linked finding",
                "updated_at": _isoformat(getattr(finding, "updated_at", None)),
            }
        )
    components = _mapping(getattr(action, "score_components", None)) or {}
    exploit = _mapping(components.get("exploit_signals")) or {}
    for signal in exploit.get("applied_threat_signals", []) or []:
        items.append(
            {
                "type": "threat_signal",
                "id": _text((signal or {}).get("identifier")) or _text((signal or {}).get("cve_id")) or "threat-intel",
                "label": _text((signal or {}).get("source")) or "threat_intel",
                "updated_at": _text((signal or {}).get("timestamp")),
            }
        )
    return _merge_unique_dicts(items)


def _provenance_payload(action: Action) -> list[dict[str, Any]]:
    items = [
        {"source": "security_graph_nodes+security_graph_edges", "kind": "graph"},
        {"source": "action.score_components", "kind": "scoring"},
    ]
    if getattr(action, "action_finding_links", None):
        items.append({"source": "action_finding_links.finding.raw_json", "kind": "finding"})
    return items


def _merge_unique_dicts(items: Any) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = repr(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _business_impact_summary_payload(action: Action) -> dict[str, Any]:
    components = _mapping(getattr(action, "score_components", None)) or {}
    business = _mapping(components.get("business_impact")) or {}
    criticality = _mapping(business.get("criticality")) or {}
    summary = _text(business.get("summary"))
    if summary is None:
        tier = _text(criticality.get("tier")) or "unknown"
        summary = f"Business criticality is {tier} for the linked action set."
    return {
        "summary": summary,
        "criticality_tier": _text(criticality.get("tier")),
        "criticality_score": criticality.get("score"),
    }


def _recommended_fix_payload(action: Action) -> dict[str, Any]:
    title = _text(getattr(action, "title", None)) or "Review linked remediation"
    return {
        "summary": title,
        "action_type": _text(getattr(action, "action_type", None)),
    }


def _shared_summary(action: Action, business_impact: dict[str, Any]) -> str:
    title = _text(getattr(action, "title", None))
    if title:
        return title
    impact = _text(business_impact.get("summary"))
    if impact:
        return impact
    return "Graph-native attack path"


def _risk_reasons(action: Action) -> list[str]:
    components = _mapping(getattr(action, "score_components", None)) or {}
    items: list[str] = []
    if _normalized_component(components.get("exploit_signals")) > 0:
        items.append("Exploit signals increase likelihood of path execution.")
    if _normalized_component(components.get("internet_exposure")) > 0:
        items.append("Internet exposure increases initial reachability.")
    if _normalized_component(components.get("privilege_level")) > 0:
        items.append("Privilege context increases downstream impact.")
    if _normalized_component(components.get("data_sensitivity")) > 0:
        items.append("Sensitive data reachability raises business consequence.")
    return items


def _relationship_confidence(action: Action) -> float:
    payload = _relationship_context_payload(action) or {}
    try:
        return round(_clamp(float(payload.get("confidence") or 0.0)), 2)
    except (TypeError, ValueError):
        return 0.0


async def _load_action_node(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: Action,
) -> SecurityGraphNode | None:
    node_key = f"action:{action.id}"
    result = await db.execute(
        select(SecurityGraphNode).where(
            SecurityGraphNode.tenant_id == tenant_id,
            SecurityGraphNode.node_key == node_key,
        )
    )
    return result.scalar_one_or_none()


async def _load_action_edges(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action_node: SecurityGraphNode,
) -> tuple[list[SecurityGraphEdge], list[SecurityGraphNode]]:
    edge_result = await db.execute(
        select(SecurityGraphEdge).where(
            SecurityGraphEdge.tenant_id == tenant_id,
            SecurityGraphEdge.source_node_id == action_node.id,
        )
    )
    edges = list(edge_result.scalars().all())
    target_ids = [edge.target_node_id for edge in edges]
    return edges, await _load_nodes(db, tenant_id=tenant_id, node_ids=target_ids)


async def _load_finding_edges(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    finding_nodes: list[SecurityGraphNode],
) -> tuple[list[SecurityGraphEdge], list[SecurityGraphNode]]:
    if not finding_nodes:
        return [], []
    result = await db.execute(
        select(SecurityGraphEdge).where(
            SecurityGraphEdge.tenant_id == tenant_id,
            SecurityGraphEdge.source_node_id.in_([node.id for node in finding_nodes]),
        )
    )
    edges = list(result.scalars().all())
    target_ids = [edge.target_node_id for edge in edges]
    nodes = await _load_nodes(db, tenant_id=tenant_id, node_ids=target_ids)
    return edges, nodes


async def _load_nodes(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    node_ids: list[uuid.UUID],
) -> list[SecurityGraphNode]:
    if not node_ids:
        return []
    result = await db.execute(
        select(SecurityGraphNode).where(
            SecurityGraphNode.tenant_id == tenant_id,
            SecurityGraphNode.id.in_(node_ids),
        )
    )
    return list(result.scalars().all())


def _nodes_by_id(
    action_node: SecurityGraphNode,
    action_target_nodes: list[SecurityGraphNode],
    finding_target_nodes: list[SecurityGraphNode],
) -> dict[uuid.UUID, SecurityGraphNode]:
    nodes = [action_node]
    nodes.extend(action_target_nodes)
    nodes.extend(finding_target_nodes)
    return {node.id: node for node in nodes}


def _target_nodes(
    action_edges: list[SecurityGraphEdge],
    finding_edges: list[SecurityGraphEdge],
    seed_nodes: dict[uuid.UUID, SecurityGraphNode],
) -> list[SecurityGraphNode]:
    return _edge_target_nodes(action_edges + finding_edges, seed_nodes, suffix="_targets_resource") + _edge_target_nodes(
        action_edges + finding_edges,
        seed_nodes,
        suffix="_targets_identity",
    )


def _exposure_nodes(
    action_edges: list[SecurityGraphEdge],
    finding_edges: list[SecurityGraphEdge],
    seed_nodes: dict[uuid.UUID, SecurityGraphNode],
) -> list[SecurityGraphNode]:
    return _edge_target_nodes(action_edges + finding_edges, seed_nodes, suffix="_indicates_exposure")


def _edge_target_nodes(
    edges: list[SecurityGraphEdge],
    seed_nodes: dict[uuid.UUID, SecurityGraphNode],
    *,
    suffix: str,
) -> list[SecurityGraphNode]:
    items: list[SecurityGraphNode] = []
    for edge in edges:
        if not edge.edge_type.endswith(suffix):
            continue
        node = seed_nodes.get(edge.target_node_id)
        if node is not None:
            items.append(node)
    return _unique_nodes(items)


def _primary_target_node(
    target_nodes: list[SecurityGraphNode],
    *,
    action: Action,
    relationship: dict[str, Any] | None,
) -> SecurityGraphNode | None:
    resource_key = _text((relationship or {}).get("resource_key"))
    resource_id = _text(getattr(action, "resource_id", None))
    for node in target_nodes:
        metadata = _metadata(node)
        if resource_key and _text(metadata.get("resource_key")) == resource_key:
            return node
        if resource_id and _text(metadata.get("resource_id")) == resource_id:
            return node
    return target_nodes[0] if target_nodes else None


def _connected_assets(
    primary_target: SecurityGraphNode | None,
    target_nodes: list[SecurityGraphNode],
) -> list[dict[str, Any]]:
    ordered = list(target_nodes)
    if primary_target is not None:
        ordered = [primary_target] + [node for node in ordered if node.id != primary_target.id]
    items = [_asset_payload(node, "anchor" if index == 0 else "linked_resource") for index, node in enumerate(ordered)]
    return items[:_CONNECTED_ASSET_LIMIT]


def _identity_path(
    primary_target: SecurityGraphNode | None,
    target_nodes: list[SecurityGraphNode],
) -> list[dict[str, Any]]:
    nodes = [node for node in target_nodes if node.node_type == "identity"]
    if primary_target is not None and primary_target.node_type == "identity":
        nodes = [primary_target] + [node for node in nodes if node.id != primary_target.id]
    items = [_identity_payload(node) for node in nodes]
    return items[:_IDENTITY_PATH_LIMIT]


def _entry_points(
    exposure_nodes: list[SecurityGraphNode],
    identity_path: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = [_entry_payload(node) for node in exposure_nodes]
    if items:
        return items[:_ENTRY_POINT_LIMIT]
    if not identity_path:
        return []
    first = identity_path[0]
    return [
        {
            "node_id": f"entry:{_text(first.get('value'))}",
            "kind": "entry_point",
            "label": "Privileged identity path",
            "detail": _text(first.get("label")),
            "badges": [],
        }
    ]


def _entry_payload(node: SecurityGraphNode) -> dict[str, Any]:
    signal = _text(_metadata(node).get("signal")) or "exposure"
    label = _entry_label(signal)
    badges = ["actively_exploited"] if signal == "exploit_signals" else []
    return {
        "node_id": f"entry:{node.node_key}",
        "kind": "entry_point",
        "label": label,
        "detail": node.display_name,
        "badges": badges,
    }


def _entry_label(signal: str) -> str:
    if signal == "exploit_signals":
        return "Actively exploited path"
    if signal == "internet_exposure":
        return "Public exposure"
    if signal == "privilege_weakness":
        return "Privileged identity path"
    if signal == "sensitive_data":
        return "Sensitive data path"
    return signal.replace("_", " ").title()


def _asset_payload(node: SecurityGraphNode, relationship: str) -> dict[str, Any]:
    metadata = _metadata(node)
    return {
        "label": node.display_name,
        "resource_id": _text(metadata.get("resource_id")),
        "resource_type": _text(metadata.get("resource_type")),
        "resource_key": _text(metadata.get("resource_key")),
        "relationship": relationship,
        "finding_count": 0,
        "action_count": 0,
        "inventory_services": [],
    }


def _identity_payload(node: SecurityGraphNode) -> dict[str, Any]:
    metadata = _metadata(node)
    resource_id = _text(metadata.get("resource_id")) or node.display_name
    node_type = "account" if (_text(metadata.get("resource_type")) == "AwsAccount" or resource_id.isdigit()) else "principal"
    return {
        "node_type": node_type,
        "label": node.display_name,
        "value": resource_id,
        "source": "security_graph_nodes",
    }


def _truncated_sections(
    exposure_nodes: list[SecurityGraphNode],
    connected_assets: list[dict[str, Any]],
    identity_path: list[dict[str, Any]],
) -> list[str]:
    items: list[str] = []
    if len(exposure_nodes) > _ENTRY_POINT_LIMIT:
        items.append("entry_points")
    if len(connected_assets) >= _CONNECTED_ASSET_LIMIT:
        items.append("connected_assets")
    if len(identity_path) >= _IDENTITY_PATH_LIMIT:
        items.append("identity_path")
    return items


def _path_signature(
    entry_points: list[dict[str, Any]],
    identity_path: list[dict[str, Any]],
    connected_assets: list[dict[str, Any]],
    action: Action,
) -> str:
    parts = [item.get("node_id") for item in entry_points[:_ENTRY_POINT_LIMIT]]
    if identity_path:
        parts.append(identity_path[0].get("value"))
    if connected_assets:
        parts.append(connected_assets[0].get("resource_key") or connected_assets[0].get("label"))
    normalized = "|".join(_text(part) for part in parts if _text(part))
    if not normalized:
        normalized = f"action:{action.id}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return f"path:{digest}"


def _unavailable_graph(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "availability_reason": reason,
        "source": "security_graph_nodes+security_graph_edges",
        "connected_assets": [],
        "identity_path": [],
        "blast_radius_neighborhood": [],
        "truncated_sections": [],
        "limits": {
            "max_related_findings": 24,
            "max_related_actions": 24,
            "max_inventory_assets": 24,
            "max_connected_assets": _CONNECTED_ASSET_LIMIT,
            "max_identity_nodes": _IDENTITY_PATH_LIMIT,
            "max_blast_radius_neighbors": 6,
        },
        "entry_points": [],
        "path_signature": None,
    }


def _relationship_context_payload(action: Any) -> dict[str, Any] | None:
    payload = _mapping((getattr(action, "score_components", None) or {}).get("relationship_context"))
    if payload is not None:
        return payload
    for link in getattr(action, "action_finding_links", []) or []:
        raw_json = getattr(getattr(link, "finding", None), "raw_json", None)
        payload = _mapping((raw_json or {}).get("relationship_context"))
        if payload is not None:
            return payload
    return None


def _relationship_context_complete(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    confidence = float(payload.get("confidence") or 0.0)
    return bool(payload.get("complete")) and confidence >= _MIN_RELATIONSHIP_CONFIDENCE


def _metadata(node: SecurityGraphNode) -> dict[str, Any]:
    payload = getattr(node, "metadata_json", None)
    if isinstance(payload, dict):
        return payload
    return {}


def _mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _isoformat(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _unique_nodes(nodes: list[SecurityGraphNode]) -> list[SecurityGraphNode]:
    seen: set[uuid.UUID] = set()
    items: list[SecurityGraphNode] = []
    for node in nodes:
        if node.id in seen:
            continue
        seen.add(node.id)
        items.append(node)
    return items
