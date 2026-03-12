"""Bounded attack-path view built from existing action-detail contracts."""
from __future__ import annotations

from typing import Any

_ENTRY_POINT_LIMIT = 2
_TARGET_ASSET_LIMIT = 3
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


def build_action_attack_path_view(
    action: Any,
    *,
    graph_context: dict[str, Any] | None,
    business_impact: dict[str, Any],
    recommendation: dict[str, Any],
    score_factors: list[dict[str, Any]],
    execution_guidance: list[dict[str, Any]],
    sla: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph = _graph_payload(graph_context)
    entry_points = _entry_points(action, graph, score_factors)
    target_assets = _target_assets(action, graph, business_impact)
    status = _status(action, graph, entry_points, target_assets)
    path_nodes = _visible_path_nodes(status, graph, business_impact, recommendation, execution_guidance, entry_points, target_assets)
    return {
        "status": status,
        "summary": _summary(status, business_impact, recommendation, execution_guidance, entry_points, target_assets, sla, graph),
        "path_nodes": path_nodes,
        "path_edges": _path_edges(path_nodes),
        "entry_points": entry_points if status in {"available", "partial"} else [],
        "target_assets": target_assets if status in {"available", "partial"} else [],
        "business_impact_summary": _string(business_impact.get("summary")),
        "risk_reasons": _risk_reasons(score_factors, sla),
        "recommendation_summary": _recommendation_summary(recommendation, execution_guidance),
        "confidence": _confidence(action, status, graph),
        "truncated": _is_truncated(graph),
        "availability_reason": _availability_reason(status, graph, entry_points, target_assets),
    }


def _graph_payload(graph_context: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(graph_context, dict):
        return graph_context
    return {
        "status": "unavailable",
        "availability_reason": "graph_context_unavailable",
        "connected_assets": [],
        "identity_path": [],
        "blast_radius_neighborhood": [],
        "truncated_sections": [],
    }


def _status(
    action: Any,
    graph: dict[str, Any],
    entry_points: list[dict[str, Any]],
    target_assets: list[dict[str, Any]],
) -> str:
    if _context_incomplete(action):
        return "context_incomplete"
    if _string(graph.get("status")) != "available":
        return "unavailable"
    if _is_truncated(graph) or not entry_points or not target_assets:
        return "partial"
    return "available"


def _entry_points(
    action: Any,
    graph: dict[str, Any],
    score_factors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = _factor_entry_points(score_factors)
    if candidates:
        return candidates[:_ENTRY_POINT_LIMIT]
    identity_node = _primary_identity_node(graph)
    if identity_node is None:
        return _action_entry_fallback(action)
    return [_item("entry-identity", "entry_point", identity_node["label"], identity_node["source"], [])]


def _factor_entry_points(score_factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    exploit = _factor(score_factors, "exploit_signals")
    exposure = _factor(score_factors, "internet_exposure")
    privilege = _factor(score_factors, "privilege_level")
    if _positive_factor(exploit):
        items.append(_exploit_entry_point(exploit))
    if _positive_factor(exposure):
        items.append(_item("entry-exposure", "entry_point", "Public exposure", _string(exposure.get("explanation")), []))
    if not items and _positive_factor(privilege):
        items.append(_item("entry-privilege", "entry_point", "Privileged identity path", _string(privilege.get("explanation")), []))
    return items


def _exploit_entry_point(factor: dict[str, Any]) -> dict[str, Any]:
    badges = ["actively_exploited"] if _has_threat_provenance(factor) else []
    label = "Actively exploited path" if badges else "Exploitable path"
    return _item("entry-exploit", "entry_point", label, _string(factor.get("explanation")), badges)


def _target_assets(
    action: Any,
    graph: dict[str, Any],
    business_impact: dict[str, Any],
) -> list[dict[str, Any]]:
    items = [_target_asset_item(asset, business_impact) for asset in _connected_assets(graph)]
    if items:
        return items[:_TARGET_ASSET_LIMIT]
    fallback = _action_target_asset(action, business_impact)
    return [fallback] if fallback is not None else []


def _target_asset_item(asset: dict[str, Any], business_impact: dict[str, Any]) -> dict[str, Any]:
    detail = _join_parts(_string(asset.get("resource_type")), _string(asset.get("relationship")))
    return _item(
        f"target-{_string(asset.get('resource_key')) or _string(asset.get('label'))}",
        "target_asset",
        _string(asset.get("label")) or "Target asset",
        detail,
        _business_badges(business_impact),
    )


def _action_target_asset(action: Any, business_impact: dict[str, Any]) -> dict[str, Any] | None:
    label = _string(getattr(action, "resource_id", None)) or _string(getattr(action, "target_id", None))
    if not label:
        return None
    detail = _string(getattr(action, "resource_type", None))
    return _item("target-action", "target_asset", label, detail, _business_badges(business_impact))


def _path_nodes(
    graph: dict[str, Any],
    business_impact: dict[str, Any],
    recommendation: dict[str, Any],
    execution_guidance: list[dict[str, Any]],
    entry_points: list[dict[str, Any]],
    target_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    nodes = _primary_nodes(entry_points, graph, target_assets)
    nodes.append(_impact_node(business_impact))
    nodes.append(_next_step_node(recommendation, execution_guidance))
    return [node for node in nodes if node is not None]


def _visible_path_nodes(
    status: str,
    graph: dict[str, Any],
    business_impact: dict[str, Any],
    recommendation: dict[str, Any],
    execution_guidance: list[dict[str, Any]],
    entry_points: list[dict[str, Any]],
    target_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if status in {"unavailable", "context_incomplete"}:
        return []
    return _path_nodes(graph, business_impact, recommendation, execution_guidance, entry_points, target_assets)


def _primary_nodes(
    entry_points: list[dict[str, Any]],
    graph: dict[str, Any],
    target_assets: list[dict[str, Any]],
) -> list[dict[str, Any] | None]:
    identity = _identity_step_node(graph, entry_points)
    return [
        entry_points[0] if entry_points else None,
        identity,
        target_assets[0] if target_assets else None,
    ]


def _identity_step_node(
    graph: dict[str, Any],
    entry_points: list[dict[str, Any]],
) -> dict[str, Any] | None:
    identity_node = _primary_identity_node(graph)
    if identity_node is None:
        return None
    entry_label = _string(entry_points[0].get("label")) if entry_points else None
    if identity_node["label"] == entry_label:
        return None
    return _item("identity-primary", "identity", identity_node["label"], identity_node["source"], [])


def _impact_node(business_impact: dict[str, Any]) -> dict[str, Any]:
    cell = _string(((business_impact.get("matrix_position") or {}).get("cell")))
    detail = _join_parts(_string(business_impact.get("summary")), cell)
    return _item("impact-business", "business_impact", "Business impact", detail, _business_badges(business_impact))


def _next_step_node(
    recommendation: dict[str, Any],
    execution_guidance: list[dict[str, Any]],
) -> dict[str, Any]:
    guidance = _recommended_guidance(execution_guidance)
    if guidance is None:
        label = _mode_label(_string(recommendation.get("mode")) or "recommended_action")
        detail = _string(recommendation.get("rationale"))
        return _item("next-step-mode", "next_step", label, detail, ["recommended"])
    return _item(
        "next-step-guidance",
        "next_step",
        _string(guidance.get("label")) or "Recommended next step",
        _string(guidance.get("blast_radius_summary")) or _string(recommendation.get("rationale")),
        ["recommended"],
    )


def _path_edges(path_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for left, right in zip(path_nodes, path_nodes[1:]):
        edges.append(
            {
                "source_node_id": _string(left.get("node_id")),
                "target_node_id": _string(right.get("node_id")),
                "label": _edge_label(_string(left.get("kind")), _string(right.get("kind"))),
            }
        )
    return edges


def _summary(
    status: str,
    business_impact: dict[str, Any],
    recommendation: dict[str, Any],
    execution_guidance: list[dict[str, Any]],
    entry_points: list[dict[str, Any]],
    target_assets: list[dict[str, Any]],
    sla: dict[str, Any] | None,
    graph: dict[str, Any],
) -> str:
    if status == "unavailable":
        return "Attack path view is unavailable because bounded graph context is not available for this action."
    if status == "context_incomplete":
        return "Relationship context is incomplete, so the attack story stays fail-closed and bounded to directly observed evidence."
    entry = _string(entry_points[0].get("label")) if entry_points else "Local risk context"
    target = _string(target_assets[0].get("label")) if target_assets else "the affected target"
    urgency = _urgency_fragment(business_impact, sla)
    next_step = _recommendation_summary(recommendation, execution_guidance)
    if status == "partial":
        return f"{entry} can reach {target} in the current bounded view, but some path context is truncated or unresolved. {urgency} {next_step}"
    return f"{entry} can reach {target}. {urgency} {next_step}{_truncation_suffix(graph)}"


def _urgency_fragment(business_impact: dict[str, Any], sla: dict[str, Any] | None) -> str:
    base = _string(business_impact.get("summary")) or "Business impact remains significant."
    state = _string((sla or {}).get("state"))
    if state == "overdue":
        return f"{base} The action is already overdue."
    if state == "expiring":
        return f"{base} The action is nearing its SLA deadline."
    return base


def _truncation_suffix(graph: dict[str, Any]) -> str:
    if not _is_truncated(graph):
        return ""
    return " Some related context is truncated to keep the view bounded."


def _risk_reasons(score_factors: list[dict[str, Any]], sla: dict[str, Any] | None) -> list[str]:
    factors = sorted(_positive_factors(score_factors), key=_factor_sort_key, reverse=True)
    reasons = [_string(factor.get("explanation")) for factor in factors[:3] if _string(factor.get("explanation"))]
    sla_reason = _sla_reason(sla)
    if sla_reason:
        reasons.append(sla_reason)
    return reasons


def _positive_factors(score_factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        factor
        for factor in score_factors
        if int(factor.get("contribution") or 0) > 0 and _string(factor.get("factor_name")) != "score_bounds_adjustment"
    ]


def _sla_reason(sla: dict[str, Any] | None) -> str | None:
    state = _string((sla or {}).get("state"))
    if state == "overdue":
        return "SLA routing marks this action overdue."
    if state == "expiring":
        return "SLA routing marks this action as expiring soon."
    return None


def _recommendation_summary(
    recommendation: dict[str, Any],
    execution_guidance: list[dict[str, Any]],
) -> str:
    guidance = _recommended_guidance(execution_guidance)
    if guidance is None:
        mode = _mode_label(_string(recommendation.get("mode")) or "recommended_action")
        return f"Safest next step: {mode}."
    mode = _mode_label(_string(guidance.get("mode")) or "recommended")
    label = _string(guidance.get("label")) or "Recommended next step"
    return f"Safest next step: {label} via {mode}."


def _recommended_guidance(execution_guidance: list[dict[str, Any]]) -> dict[str, Any] | None:
    for guidance in execution_guidance:
        if guidance.get("recommended"):
            return guidance
    return execution_guidance[0] if execution_guidance else None


def _availability_reason(
    status: str,
    graph: dict[str, Any],
    entry_points: list[dict[str, Any]],
    target_assets: list[dict[str, Any]],
) -> str | None:
    if status == "available":
        return None
    if status == "context_incomplete":
        return _string(graph.get("availability_reason")) or "relationship_context_incomplete"
    if status == "unavailable":
        return _string(graph.get("availability_reason")) or "graph_context_unavailable"
    if _is_truncated(graph):
        return "bounded_context_truncated"
    if not entry_points:
        return "entry_point_unresolved"
    if not target_assets:
        return "target_assets_unresolved"
    return "partial_attack_story"


def _confidence(action: Any, status: str, graph: dict[str, Any]) -> float:
    base = _relationship_confidence(action)
    if status == "available":
        return round(max(base, _MIN_RELATIONSHIP_CONFIDENCE), 2)
    if status == "partial":
        return round(max(0.5, base), 2)
    return round(base, 2)


def _relationship_confidence(action: Any) -> float:
    payload = _relationship_context_payload(action)
    return round(_float_value((payload or {}).get("confidence")), 2)


def _relationship_context_payload(action: Any) -> dict[str, Any] | None:
    payload = _mapping((getattr(action, "score_components", None) or {}).get("relationship_context"))
    if payload:
        return payload
    for raw in _linked_raw_payloads(action):
        payload = _raw_relationship_context(raw)
        if payload:
            return payload
    return None


def _linked_raw_payloads(action: Any) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for link in getattr(action, "action_finding_links", None) or []:
        raw = getattr(getattr(link, "finding", None), "raw_json", None)
        if isinstance(raw, dict):
            payloads.append(raw)
    return payloads


def _raw_relationship_context(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    for key in _RELATIONSHIP_CONTEXT_KEYS:
        payload = _mapping(raw.get(key))
        if payload:
            return payload
    product_fields = raw.get("ProductFields")
    if not isinstance(product_fields, dict):
        return None
    for key in _RELATIONSHIP_CONTEXT_PRODUCT_FIELD_KEYS:
        payload = _mapping(product_fields.get(key))
        if payload:
            return payload
    return None


def _connected_assets(graph: dict[str, Any]) -> list[dict[str, Any]]:
    assets = graph.get("connected_assets")
    if not isinstance(assets, list):
        return []
    ordered = sorted(assets, key=_target_sort_key)
    return [asset for asset in ordered if isinstance(asset, dict)]


def _primary_identity_node(graph: dict[str, Any]) -> dict[str, str] | None:
    nodes = graph.get("identity_path")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, dict) and _string(node.get("label")):
            return {"label": _string(node.get("label")) or "Identity path", "source": _string(node.get("source")) or ""}
    return None


def _factor(score_factors: list[dict[str, Any]], factor_name: str) -> dict[str, Any]:
    for factor in score_factors:
        if _string(factor.get("factor_name")) == factor_name:
            return factor
    return {}


def _positive_factor(factor: dict[str, Any]) -> bool:
    return int(factor.get("contribution") or 0) > 0


def _has_threat_provenance(factor: dict[str, Any]) -> bool:
    provenance = factor.get("provenance")
    return isinstance(provenance, list) and bool(provenance)


def _action_entry_fallback(action: Any) -> list[dict[str, Any]]:
    if not _string(getattr(action, "title", None)):
        return []
    detail = _string(getattr(action, "description", None))
    return [_item("entry-action", "entry_point", "Observed finding path", detail, [])]


def _edge_label(source_kind: str | None, target_kind: str | None) -> str:
    mapping = {
        ("entry_point", "identity"): "uses",
        ("entry_point", "target_asset"): "reaches",
        ("identity", "target_asset"): "reaches",
        ("target_asset", "business_impact"): "puts at risk",
        ("business_impact", "next_step"): "prioritize with",
    }
    return mapping.get((source_kind, target_kind), "leads to")


def _context_incomplete(action: Any) -> bool:
    components = getattr(action, "score_components", None)
    if not isinstance(components, dict):
        return False
    marker = components.get("context_incomplete")
    if isinstance(marker, bool):
        return marker
    toxic = components.get("toxic_combinations")
    return isinstance(toxic, dict) and bool(toxic.get("context_incomplete"))


def _is_truncated(graph: dict[str, Any]) -> bool:
    sections = graph.get("truncated_sections")
    return isinstance(sections, list) and bool(sections)


def _business_badges(business_impact: dict[str, Any]) -> list[str]:
    criticality = _string(((business_impact.get("criticality") or {}).get("tier")))
    return ["business_critical"] if criticality in {"critical", "high"} else []


def _factor_sort_key(factor: dict[str, Any]) -> tuple[int, int]:
    return int(factor.get("contribution") or 0), len(_string(factor.get("explanation")) or "")


def _target_sort_key(asset: dict[str, Any]) -> tuple[int, int, int, str]:
    ranking = {"anchor": 0, "linked_resource": 1, "account_support": 2, "inventory_support": 3}
    return (
        ranking.get(_string(asset.get("relationship")) or "", 99),
        -int(asset.get("action_count") or 0),
        -int(asset.get("finding_count") or 0),
        _string(asset.get("label")) or "",
    )


def _item(
    node_id: str,
    kind: str,
    label: str,
    detail: str | None,
    badges: list[str],
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "kind": kind,
        "label": label,
        "detail": detail,
        "badges": badges,
    }


def _mapping(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _join_parts(*parts: str | None) -> str | None:
    values = [part for part in parts if part]
    return " · ".join(values) if values else None


def _string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()


def _mode_label(value: str) -> str:
    if value == "pr_only":
        return "PR only"
    if value == "direct_fix":
        return "Direct fix"
    return _title_case(value)
