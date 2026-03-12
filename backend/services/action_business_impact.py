"""Business-impact matrix helpers for risk x criticality."""
from __future__ import annotations

import json
from typing import Any

from backend.services.control_scope import action_type_from_control

_UNKNOWN_STATUS = "unknown"
_KNOWN_STATUS = "known"
_UNKNOWN_TIER = "unknown"
_DIMENSION_SIGNAL_LIMIT = 3
_PARTIAL_MATCH_MULTIPLIER = 0.6
_CRITICALITY_DIMENSIONS = (
    {
        "name": "customer_facing",
        "label": "Customer-facing",
        "weight": 25,
        "keywords": (
            "api gateway",
            "cloudfront",
            "customer portal",
            "customer app",
            "external api",
            "frontend",
            "public website",
            "website",
        ),
        "resource_types": (),
        "action_types": (),
    },
    {
        "name": "revenue_path",
        "label": "Revenue-path",
        "weight": 25,
        "keywords": (
            "billing",
            "checkout",
            "commerce",
            "invoice",
            "order",
            "payment",
            "revenue",
            "subscription",
        ),
        "resource_types": (),
        "action_types": (),
    },
    {
        "name": "regulated_data",
        "label": "Regulated-data",
        "weight": 25,
        "keywords": (
            "cardholder",
            "financial",
            "gdpr",
            "hipaa",
            "pci",
            "phi",
            "pii",
            "sox",
        ),
        "resource_types": (),
        "action_types": ("s3_bucket_encryption", "s3_bucket_encryption_kms", "ebs_default_encryption"),
    },
    {
        "name": "identity_boundary",
        "label": "Identity-boundary",
        "weight": 15,
        "keywords": (
            "access key",
            "administrator",
            "assume role",
            "identity",
            "root user",
            "sts",
        ),
        "resource_types": ("AwsAccount", "AwsIamPolicy", "AwsIamRole", "AwsIamUser"),
        "action_types": ("iam_root_access_key_absent",),
    },
    {
        "name": "production_environment",
        "label": "Production-environment",
        "weight": 10,
        "keywords": ("customer-prod", "live", "prod-", "-prod", "production"),
        "resource_types": (),
        "action_types": (),
    },
)
_RISK_TIER_RULES = (
    ("critical", 85, 4),
    ("high", 65, 3),
    ("medium", 40, 2),
    ("low", 0, 1),
)
_CRITICALITY_TIER_RULES = (
    ("critical", 70, 4),
    ("high", 40, 3),
    ("medium", 1, 2),
)


def build_business_impact_for_finding(finding: Any, *, technical_score: int) -> dict[str, Any]:
    text = _criticality_text(finding)
    action_type = action_type_from_control(getattr(finding, "control_id", None))
    resource_type = str(getattr(finding, "resource_type", "") or "")
    dimensions = [_dimension_payload(rule, text, action_type, resource_type) for rule in _CRITICALITY_DIMENSIONS]
    criticality = _criticality_payload(dimensions)
    return _business_impact_payload(technical_score, criticality)


def build_business_impact_from_components(
    components: dict[str, Any] | None,
    *,
    stored_score: int | None = None,
) -> dict[str, Any]:
    score = _resolved_score(components, stored_score)
    stored = _stored_business_impact(components)
    criticality = _criticality_from_stored_payload(stored)
    return _business_impact_payload(score, criticality)


def business_impact_rank(components: dict[str, Any] | None, *, stored_score: int | None = None) -> int:
    payload = build_business_impact_from_components(components, stored_score=stored_score)
    matrix = payload.get("matrix_position") if isinstance(payload, dict) else {}
    return int((matrix or {}).get("rank") or 0)


def _criticality_text(finding: Any) -> str:
    raw = getattr(finding, "raw_json", None)
    payload = raw if isinstance(raw, dict) else {}
    subset = {
        "product_fields": payload.get("ProductFields"),
        "resource_tags": payload.get("ResourceTags"),
        "resources": payload.get("Resources"),
        "tags": payload.get("Tags"),
    }
    parts = [
        str(getattr(finding, "title", "") or ""),
        str(getattr(finding, "description", "") or ""),
        str(getattr(finding, "resource_id", "") or ""),
        str(getattr(finding, "resource_type", "") or ""),
        json.dumps(subset, sort_keys=True, default=str),
    ]
    return " ".join(parts).lower()


def _dimension_payload(rule: dict[str, Any], text: str, action_type: str, resource_type: str) -> dict[str, Any]:
    signals = _dimension_signals(rule, text, action_type, resource_type)
    contribution = _dimension_contribution(int(rule["weight"]), len(signals))
    return {
        "dimension": rule["name"],
        "label": rule["label"],
        "weight": int(rule["weight"]),
        "matched": bool(signals),
        "contribution": contribution,
        "signals": signals,
        "explanation": _dimension_explanation(rule["label"], signals, contribution),
    }


def _dimension_signals(rule: dict[str, Any], text: str, action_type: str, resource_type: str) -> list[str]:
    signals = _hint_signals(rule, action_type, resource_type)
    signals.extend(_keyword_signals(text, tuple(rule["keywords"])))
    return signals[:_DIMENSION_SIGNAL_LIMIT]


def _hint_signals(rule: dict[str, Any], action_type: str, resource_type: str) -> list[str]:
    signals: list[str] = []
    if action_type and action_type in tuple(rule["action_types"]):
        signals.append(f"action_type:{action_type}")
    if resource_type and resource_type in tuple(rule["resource_types"]):
        signals.append(f"resource_type:{resource_type}")
    return signals


def _keyword_signals(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [f"keyword:{keyword}" for keyword in keywords if _keyword_present(text, keyword)][: _DIMENSION_SIGNAL_LIMIT]


def _keyword_present(text: str, keyword: str) -> bool:
    if " " in keyword or "-" in keyword or "_" in keyword or ":" in keyword:
        return keyword in text
    return f" {keyword} " in f" {text} "


def _dimension_contribution(weight: int, signal_count: int) -> int:
    if signal_count <= 0:
        return 0
    if signal_count == 1:
        return int((weight * _PARTIAL_MATCH_MULTIPLIER) + 0.5)
    return weight


def _dimension_explanation(label: str, signals: list[str], contribution: int) -> str:
    if not signals:
        return f"{label} is explicit unknown for this action."
    joined = ", ".join(signals)
    return f"{label} contributed {contribution} criticality points using: {joined}."


def _criticality_payload(dimensions: list[dict[str, Any]]) -> dict[str, Any]:
    score = min(100, sum(int(item.get("contribution") or 0) for item in dimensions))
    status = _KNOWN_STATUS if score > 0 else _UNKNOWN_STATUS
    tier, weight = _criticality_tier(score, status)
    return {
        "status": status,
        "score": score,
        "tier": tier,
        "weight": weight,
        "dimensions": dimensions,
        "explanation": _criticality_explanation(status, score, dimensions),
    }


def _criticality_tier(score: int, status: str) -> tuple[str, int]:
    if status != _KNOWN_STATUS:
        return _UNKNOWN_TIER, 1
    for tier, threshold, weight in _CRITICALITY_TIER_RULES:
        if score >= threshold:
            return tier, weight
    return _UNKNOWN_TIER, 1


def _criticality_explanation(status: str, score: int, dimensions: list[dict[str, Any]]) -> str:
    if status != _KNOWN_STATUS:
        return (
            "Criticality remains explicit unknown because no customer-facing, revenue-path, "
            "regulated-data, identity-boundary, or production-environment signals were detected."
        )
    matched = [str(item.get("label") or "") for item in dimensions if item.get("matched")]
    return f"Criticality scored {score} points from: {', '.join(matched)}."


def _business_impact_payload(technical_score: int, criticality: dict[str, Any]) -> dict[str, Any]:
    risk_tier, risk_weight = _risk_tier(technical_score)
    matrix = _matrix_position(technical_score, risk_tier, risk_weight, criticality)
    return {
        "technical_risk_score": int(technical_score),
        "technical_risk_tier": risk_tier,
        "criticality": criticality,
        "matrix_position": matrix,
        "summary": _business_impact_summary(risk_tier, criticality, matrix),
    }


def _risk_tier(score: int) -> tuple[str, int]:
    for tier, threshold, weight in _RISK_TIER_RULES:
        if score >= threshold:
            return tier, weight
    return "low", 1


def _matrix_position(
    technical_score: int,
    risk_tier: str,
    risk_weight: int,
    criticality: dict[str, Any],
) -> dict[str, Any]:
    criticality_tier = str(criticality.get("tier") or _UNKNOWN_TIER)
    criticality_weight = int(criticality.get("weight") or 1)
    rank = (risk_weight * 10000) + (criticality_weight * 100) + int(technical_score)
    return {
        "row": risk_tier,
        "column": criticality_tier,
        "cell": f"{risk_tier}:{criticality_tier}",
        "risk_weight": risk_weight,
        "criticality_weight": criticality_weight,
        "rank": rank,
        "explanation": _matrix_explanation(risk_tier, technical_score, criticality_tier),
    }


def _matrix_explanation(risk_tier: str, technical_score: int, criticality_tier: str) -> str:
    return (
        f"Matrix row uses technical risk tier {risk_tier} from score {technical_score}; "
        f"matrix column uses business criticality tier {criticality_tier}."
    )


def _business_impact_summary(risk_tier: str, criticality: dict[str, Any], matrix: dict[str, Any]) -> str:
    tier = str(criticality.get("tier") or _UNKNOWN_TIER)
    if str(criticality.get("status") or _UNKNOWN_STATUS) != _KNOWN_STATUS:
        return (
            f"{_title_case(risk_tier)} technical risk intersects with explicit unknown criticality "
            f"in matrix cell {matrix['cell']}."
        )
    return f"{_title_case(risk_tier)} technical risk intersects with {_title_case(tier)} business criticality."


def _stored_business_impact(components: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(components, dict):
        return None
    payload = components.get("business_impact")
    return payload if isinstance(payload, dict) else None


def _criticality_from_stored_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _unknown_criticality()
    criticality = payload.get("criticality")
    if not isinstance(criticality, dict):
        return _unknown_criticality()
    dimensions = criticality.get("dimensions")
    if not isinstance(dimensions, list):
        return _unknown_criticality()
    normalized = [_normalize_dimension(item) for item in dimensions]
    return _criticality_payload(normalized)


def _normalize_dimension(payload: Any) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    signals = _safe_signals(raw.get("signals"))
    return {
        "dimension": str(raw.get("dimension") or "unknown"),
        "label": str(raw.get("label") or "Unknown"),
        "weight": int(raw.get("weight") or 0),
        "matched": bool(raw.get("matched")),
        "contribution": int(raw.get("contribution") or 0),
        "signals": signals,
        "explanation": str(raw.get("explanation") or _dimension_explanation(str(raw.get("label") or "Unknown"), signals, int(raw.get("contribution") or 0))),
    }


def _safe_signals(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(item).strip()[:120] for item in raw if str(item).strip()][: _DIMENSION_SIGNAL_LIMIT]


def _unknown_criticality() -> dict[str, Any]:
    dimensions = [_unknown_dimension(rule) for rule in _CRITICALITY_DIMENSIONS]
    return _criticality_payload(dimensions)


def _unknown_dimension(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "dimension": rule["name"],
        "label": rule["label"],
        "weight": int(rule["weight"]),
        "matched": False,
        "contribution": 0,
        "signals": [],
        "explanation": _dimension_explanation(rule["label"], [], 0),
    }


def _resolved_score(components: dict[str, Any] | None, stored_score: int | None) -> int:
    if stored_score is not None:
        return int(stored_score)
    if isinstance(components, dict):
        return int(components.get("score") or 0)
    return 0


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()
