"""Conservative toxic-combination score overlays for related action neighborhoods."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Sequence

from backend.config import settings

logger = logging.getLogger(__name__)

TOXIC_COMBINATIONS_COMPONENT = "toxic_combinations"
_TOXIC_EVIDENCE_SOURCE = "related action neighborhoods (same resource plus account-scoped context)"
_SIGNAL_COMPONENTS = {
    "internet_exposure": ("internet_exposure", 15),
    "privilege_weakness": ("privilege_level", 12),
    "sensitive_data": ("data_sensitivity", 12),
    "exploit_signals": ("exploit_signals", 10),
}
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
_MIN_RELATIONSHIP_CONFIDENCE = 0.75


@dataclass(frozen=True)
class ToxicCombinationRule:
    rule_id: str
    label: str
    required_signals: tuple[str, ...]
    boost_points: int
    anchor_signals: tuple[str, ...] = ()
    require_resource_anchor: bool = True
    allow_account_scope_support: bool = True


@dataclass(frozen=True)
class _ActionSignalView:
    action: Any
    account_id: str
    region: str | None
    resource_id: str | None
    signals: frozenset[str]
    account_scoped: bool
    relationship_context_complete: bool
    relationship_confidence: float


def apply_toxic_combination_overlays(actions: Sequence[Any]) -> int:
    if not actions:
        return 0
    rules = _load_rules()
    max_boost = max(0, int(settings.ACTIONS_TOXIC_COMBINATION_MAX_BOOST))
    views = [_signal_view(action) for action in actions]
    matched = 0
    for view in views:
        overlay = evaluate_toxic_combination_overlay(view.action, actions, rules=rules, max_boost=max_boost, views=views)
        matched += int(overlay.get("points", 0) > 0)
        _persist_overlay(view.action, overlay)
    return matched


def evaluate_toxic_combination_overlay(
    action: Any,
    related_actions: Sequence[Any],
    *,
    rules: Sequence[ToxicCombinationRule] | None = None,
    max_boost: int | None = None,
    views: Sequence[_ActionSignalView] | None = None,
) -> dict[str, Any]:
    resolved_rules = tuple(rules or _load_rules())
    resolved_views = tuple(views or [_signal_view(item) for item in related_actions])
    anchor = _find_anchor_view(action, resolved_views)
    return _build_overlay(anchor, resolved_views, resolved_rules, _resolved_max_boost(max_boost))


def _build_overlay(
    anchor: _ActionSignalView,
    views: Sequence[_ActionSignalView],
    rules: Sequence[ToxicCombinationRule],
    max_boost: int,
) -> dict[str, Any]:
    evaluations = [_evaluate_rule(rule, anchor, views) for rule in rules]
    matched = [item for item in evaluations if item["matched"]]
    incomplete = [item for item in evaluations if item["context_incomplete"]]
    boost = min(sum(int(item["boost_points"]) for item in matched), max_boost)
    return {
        "points": boost,
        "max_boost": max_boost,
        "context_incomplete": bool(incomplete),
        "matched_rule_ids": [item["rule_id"] for item in matched],
        "context_incomplete_rule_ids": [item["rule_id"] for item in incomplete],
        "missing_signals": _missing_signals(evaluations),
        "signals": _overlay_signals(matched, incomplete, evaluations),
        "evidence_source": _TOXIC_EVIDENCE_SOURCE,
        "explanation": _overlay_explanation(matched, incomplete, evaluations, boost),
    }


def _evaluate_rule(
    rule: ToxicCombinationRule,
    anchor: _ActionSignalView,
    views: Sequence[_ActionSignalView],
) -> dict[str, Any]:
    if rule.require_resource_anchor and (not anchor.resource_id or anchor.account_scoped):
        return _rule_result(rule, matched=False, context_incomplete=True, missing_signals=rule.required_signals)
    if rule.anchor_signals and not set(rule.anchor_signals).intersection(anchor.signals):
        return _rule_result(rule, matched=False, missing_signals=rule.anchor_signals)
    related_views = _related_views(rule, anchor, views)
    if not _relationship_context_ready(related_views):
        return _rule_result(rule, matched=False, context_incomplete=True, missing_signals=rule.required_signals)
    signals = _signals_for_views(related_views)
    missing = tuple(signal for signal in rule.required_signals if signal not in signals)
    return _rule_result(rule, matched=not missing, missing_signals=missing)


def _rule_result(
    rule: ToxicCombinationRule,
    *,
    matched: bool,
    missing_signals: Sequence[str] = (),
    context_incomplete: bool = False,
) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "label": rule.label,
        "matched": matched,
        "boost_points": rule.boost_points if matched else 0,
        "missing_signals": list(missing_signals),
        "context_incomplete": context_incomplete,
    }


def _related_views(
    rule: ToxicCombinationRule,
    anchor: _ActionSignalView,
    views: Sequence[_ActionSignalView],
) -> tuple[_ActionSignalView, ...]:
    return tuple(view for view in views if _related_to_anchor(rule, anchor, view))


def _relationship_context_ready(views: Sequence[_ActionSignalView]) -> bool:
    return bool(views) and all(view.relationship_context_complete for view in views)


def _signals_for_views(views: Sequence[_ActionSignalView]) -> set[str]:
    signals: set[str] = set()
    for view in views:
        signals.update(view.signals)
    return signals


def _related_to_anchor(rule: ToxicCombinationRule, anchor: _ActionSignalView, view: _ActionSignalView) -> bool:
    if anchor.account_id != view.account_id or not _regions_related(anchor.region, view.region):
        return False
    if view.action is anchor.action:
        return True
    if anchor.resource_id and anchor.resource_id == view.resource_id:
        return True
    return bool(rule.allow_account_scope_support and view.account_scoped)


def _regions_related(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right


def _persist_overlay(action: Any, overlay: dict[str, Any]) -> None:
    base_score = _base_score(action)
    final_score = _clamp_score(base_score + int(overlay.get("points") or 0))
    components = _components_copy(action)
    components["score_before_toxic_combinations"] = base_score
    components["score"] = final_score
    components["context_incomplete"] = bool(overlay.get("context_incomplete"))
    components[TOXIC_COMBINATIONS_COMPONENT] = overlay
    action.score_components = components
    action.score = final_score
    action.priority = final_score


def _base_score(action: Any) -> int:
    components = getattr(action, "score_components", None)
    if isinstance(components, dict) and "score_before_toxic_combinations" in components:
        return int(components.get("score_before_toxic_combinations") or 0)
    if isinstance(components, dict) and isinstance(components.get(TOXIC_COMBINATIONS_COMPONENT), dict):
        return int(components.get("score") or 0) - int(components[TOXIC_COMBINATIONS_COMPONENT].get("points") or 0)
    raw = getattr(action, "score", None)
    if raw is None:
        raw = getattr(action, "priority", 0)
    return int(raw or 0)


def _components_copy(action: Any) -> dict[str, Any]:
    payload = getattr(action, "score_components", None)
    return dict(payload) if isinstance(payload, dict) else {}


def _signal_view(action: Any) -> _ActionSignalView:
    resource_id = _normalized_resource_id(action)
    relationship_complete, relationship_confidence = _relationship_context_state(action)
    return _ActionSignalView(
        action=action,
        account_id=str(getattr(action, "account_id", "") or ""),
        region=getattr(action, "region", None),
        resource_id=resource_id,
        signals=frozenset(_signals_from_components(getattr(action, "score_components", None))),
        account_scoped=_is_account_scoped_action(action, resource_id),
        relationship_context_complete=relationship_complete,
        relationship_confidence=relationship_confidence,
    )


def _relationship_context_state(action: Any) -> tuple[bool, float]:
    payload = _relationship_context_payload(action)
    if payload is None:
        return False, 0.0
    confidence = _relationship_confidence(payload)
    return _relationship_context_complete(payload) and confidence >= _MIN_RELATIONSHIP_CONFIDENCE, confidence


def _relationship_context_payload(action: Any) -> dict[str, Any] | None:
    payload = _coerce_mapping((getattr(action, "score_components", None) or {}).get("relationship_context"))
    if payload is not None:
        return payload
    return _linked_finding_relationship_context(action)


def _linked_finding_relationship_context(action: Any) -> dict[str, Any] | None:
    best_payload = None
    best_confidence = -1.0
    for link in getattr(action, "action_finding_links", []) or []:
        payload = _raw_relationship_context(getattr(getattr(link, "finding", None), "raw_json", None))
        if payload is None:
            continue
        confidence = _relationship_confidence(payload)
        if _relationship_context_complete(payload) and confidence >= _MIN_RELATIONSHIP_CONFIDENCE:
            return payload
        if confidence > best_confidence:
            best_payload = payload
            best_confidence = confidence
    return best_payload


def _raw_relationship_context(raw_json: Any) -> dict[str, Any] | None:
    raw = raw_json if isinstance(raw_json, dict) else {}
    for key in _RELATIONSHIP_CONTEXT_KEYS:
        payload = _coerce_mapping(raw.get(key))
        if payload is not None:
            return payload
    product_fields = raw.get("ProductFields")
    if isinstance(product_fields, dict):
        for key in _RELATIONSHIP_CONTEXT_PRODUCT_FIELD_KEYS:
            payload = _coerce_mapping(product_fields.get(key))
            if payload is not None:
                return payload
    return None


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _relationship_confidence(payload: dict[str, Any]) -> float:
    for key in ("confidence", "confidence_score", "relationship_confidence"):
        normalized = _normalize_confidence(payload.get(key))
        if normalized is not None:
            return normalized
    return 0.0


def _normalize_confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric > 1:
        numeric = numeric / 100
    return max(0.0, min(1.0, numeric))


def _relationship_context_complete(payload: dict[str, Any]) -> bool:
    for key in ("complete", "is_complete", "context_complete"):
        coerced = _coerce_bool(payload.get(key))
        if coerced is not None:
            return coerced
    status = str(payload.get("status", "") or "").strip().lower()
    return status in {"complete", "ready"}


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    return None


def _signals_from_components(components: dict[str, Any] | None) -> set[str]:
    signals: set[str] = set()
    for signal_name, (component_name, minimum_points) in _SIGNAL_COMPONENTS.items():
        if _component_points(components, component_name) >= minimum_points:
            signals.add(signal_name)
    return signals


def _component_points(components: dict[str, Any] | None, key: str) -> int:
    payload = components.get(key) if isinstance(components, dict) else None
    if not isinstance(payload, dict):
        return 0
    return int(payload.get("points") or 0)


def _is_account_scoped_action(action: Any, resource_id: str | None) -> bool:
    if not resource_id:
        return True
    account_id = str(getattr(action, "account_id", "") or "")
    resource_type = str(getattr(action, "resource_type", "") or "")
    return resource_id == account_id or resource_type == "AwsAccount"


def _normalized_resource_id(action: Any) -> str | None:
    value = str(getattr(action, "resource_id", "") or "").strip()
    return value or None


def _find_anchor_view(action: Any, views: Sequence[_ActionSignalView]) -> _ActionSignalView:
    for view in views:
        if view.action is action:
            return view
    return _signal_view(action)


def _missing_signals(evaluations: Sequence[dict[str, Any]]) -> list[str]:
    signals: list[str] = []
    for item in evaluations:
        for signal in item.get("missing_signals", []):
            if signal not in signals:
                signals.append(str(signal))
    return signals[:3]


def _overlay_signals(
    matched: Sequence[dict[str, Any]],
    incomplete: Sequence[dict[str, Any]],
    evaluations: Sequence[dict[str, Any]],
) -> list[str]:
    if matched:
        return [f"rule:{item['rule_id']}" for item in matched][:3]
    if incomplete:
        return ["status:context_incomplete"] + [f"rule:{item['rule_id']}" for item in incomplete[:2]]
    return [f"missing:{signal}" for signal in _missing_signals(evaluations)]


def _overlay_explanation(
    matched: Sequence[dict[str, Any]],
    incomplete: Sequence[dict[str, Any]],
    evaluations: Sequence[dict[str, Any]],
    boost: int,
) -> str:
    if matched:
        labels = ", ".join(item["label"] for item in matched)
        return f"Toxic combinations added {boost} points after related findings matched: {labels}."
    if incomplete:
        labels = ", ".join(item["label"] for item in incomplete)
        return f"Related context is incomplete for toxic-combination evaluation ({labels}); no boost was applied."
    missing = ", ".join(_missing_signals(evaluations)) or "required signals"
    return f"Toxic-combination boost not applied because related findings were missing: {missing}."


def _load_rules() -> tuple[ToxicCombinationRule, ...]:
    if not settings.ACTIONS_TOXIC_COMBINATIONS_ENABLED:
        return ()
    configured = _configured_rules()
    return configured or _default_rules()


def _configured_rules() -> tuple[ToxicCombinationRule, ...]:
    raw = (settings.ACTIONS_TOXIC_COMBINATION_RULES_JSON or "").strip()
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid ACTIONS_TOXIC_COMBINATION_RULES_JSON; falling back to defaults")
        return ()
    if not isinstance(payload, list):
        return ()
    rules = [_rule_from_raw(item) for item in payload]
    return tuple(rule for rule in rules if rule is not None)


def _rule_from_raw(raw: Any) -> ToxicCombinationRule | None:
    if not isinstance(raw, dict):
        return None
    required = tuple(str(item).strip() for item in raw.get("required_signals", []) if str(item).strip())
    if not raw.get("rule_id") or not raw.get("label") or not required:
        return None
    return ToxicCombinationRule(
        rule_id=str(raw["rule_id"]).strip(),
        label=str(raw["label"]).strip(),
        required_signals=required,
        boost_points=max(0, int(raw.get("boost_points") or 0)),
        anchor_signals=tuple(str(item).strip() for item in raw.get("anchor_signals", []) if str(item).strip()),
        require_resource_anchor=bool(raw.get("require_resource_anchor", True)),
        allow_account_scope_support=bool(raw.get("allow_account_scope_support", True)),
    )


def _default_rules() -> tuple[ToxicCombinationRule, ...]:
    return (
        ToxicCombinationRule(
            rule_id="public_exposure_privilege_sensitive_data",
            label="Public exposure plus privilege weakness plus sensitive data",
            required_signals=("internet_exposure", "privilege_weakness", "sensitive_data"),
            boost_points=15,
            anchor_signals=("internet_exposure", "sensitive_data"),
        ),
    )


def _resolved_max_boost(value: int | None) -> int:
    if value is not None:
        return max(0, int(value))
    return max(0, int(settings.ACTIONS_TOXIC_COMBINATION_MAX_BOOST))


def _clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))
