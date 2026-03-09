"""Deterministic context-driven action scoring for findings and action groups."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.services.control_scope import action_type_from_control

_SCORE_WEIGHTS = {
    "severity": 35,
    "internet_exposure": 20,
    "privilege_level": 15,
    "data_sensitivity": 15,
    "exploit_signals": 15,
    "compensating_controls": 15,
}

_HIGH_EXPOSURE_ACTIONS = {
    "ebs_snapshot_block_public_access": 0.85,
    "s3_block_public_access": 0.75,
    "s3_bucket_block_public_access": 0.9,
    "s3_bucket_require_ssl": 0.6,
    "sg_restrict_public_ports": 0.95,
    "ssm_block_public_sharing": 0.8,
}
_PRIVILEGE_ACTIONS = {
    "iam_root_access_key_absent": 1.0,
    "sg_restrict_public_ports": 0.8,
    "s3_bucket_require_ssl": 0.3,
}
_DATA_SENSITIVITY_ACTIONS = {
    "aws_config_enabled": 0.45,
    "cloudtrail_enabled": 0.55,
    "ebs_default_encryption": 0.7,
    "ebs_snapshot_block_public_access": 0.8,
    "iam_root_access_key_absent": 0.6,
    "s3_block_public_access": 0.75,
    "s3_bucket_access_logging": 0.65,
    "s3_bucket_block_public_access": 0.8,
    "s3_bucket_encryption": 0.85,
    "s3_bucket_encryption_kms": 0.95,
    "s3_bucket_lifecycle_configuration": 0.55,
    "s3_bucket_require_ssl": 0.8,
    "sg_restrict_public_ports": 0.45,
}
_EXPLOIT_ACTIONS = {
    "ebs_snapshot_block_public_access": 0.7,
    "iam_root_access_key_absent": 0.85,
    "s3_block_public_access": 0.65,
    "s3_bucket_block_public_access": 0.75,
    "sg_restrict_public_ports": 0.9,
    "ssm_block_public_sharing": 0.65,
}

_HIGH_EXPOSURE_KEYWORDS = (
    "0.0.0.0/0",
    "::/0",
    "internet-facing",
    "open to the world",
    "public endpoint",
    "publicly accessible",
    "publicly exposed",
    "unrestricted",
)
_MEDIUM_EXPOSURE_KEYWORDS = ("internet", "public", "world-accessible")
_HIGH_PRIVILEGE_KEYWORDS = (
    "access key",
    "administrator",
    "admin access",
    "admin port",
    "elevated privileges",
    "root",
)
_MEDIUM_PRIVILEGE_KEYWORDS = ("iam", "policy", "privilege", "rdp", "role", "ssh")
_HIGH_DATA_KEYWORDS = (
    "customer data",
    "database",
    "financial",
    "kms",
    "pci",
    "phi",
    "pii",
    "secret",
    "sensitive",
)
_MEDIUM_DATA_KEYWORDS = ("audit", "bucket", "encryption", "log", "snapshot", "tls")
_HIGH_EXPLOIT_KEYWORDS = (
    "actively exploited",
    "cisa kev",
    "cve-",
    "exploit",
    "public rdp",
    "public ssh",
    "root access key",
)
_MEDIUM_EXPLOIT_KEYWORDS = ("exposed", "internet", "open port", "public", "unrestricted")
_COMPENSATING_CONTROL_KEYWORDS = (
    "allowlist",
    "approved exception",
    "cloudfront origin access control",
    "internal only",
    "oac",
    "private link",
    "private subnet",
    "trusted principal",
    "vpc only",
)
_FACTOR_ORDER = (
    "severity",
    "internet_exposure",
    "privilege_level",
    "data_sensitivity",
    "exploit_signals",
    "compensating_controls",
)
_TOXIC_COMBINATIONS_FACTOR = "toxic_combinations"
_FACTOR_LABELS = {
    "severity": "Severity",
    "internet_exposure": "Internet exposure",
    "privilege_level": "Privilege level",
    "data_sensitivity": "Data sensitivity",
    "exploit_signals": "Exploit signals",
    "compensating_controls": "Compensating controls",
    _TOXIC_COMBINATIONS_FACTOR: "Toxic combinations",
}
_FACTOR_EVIDENCE_SOURCES = {
    "severity": "finding.severity_label + finding.severity_normalized",
    "internet_exposure": "finding.title + finding.description + selected raw_json exposure metadata",
    "privilege_level": "finding.title + finding.description + selected raw_json identity metadata",
    "data_sensitivity": "finding.title + finding.description + selected raw_json data-impact metadata",
    "exploit_signals": "finding.title + finding.description + selected raw_json exploit metadata",
    "compensating_controls": "finding.title + finding.description + selected raw_json mitigating-control metadata",
    _TOXIC_COMBINATIONS_FACTOR: "related action neighborhoods (same resource plus account-scoped context)",
}


@dataclass(frozen=True)
class ActionScore:
    score: int
    components: dict[str, Any]
    representative_finding: Any | None = None


@dataclass(frozen=True)
class _ComponentScore:
    normalized: float
    points: int
    signals: tuple[str, ...]


@dataclass(frozen=True)
class _ScoredFinding:
    finding: Any
    score: ActionScore
    tie_breaker: tuple[Any, ...]


def score_action_finding(finding: Any) -> ActionScore:
    action_type = action_type_from_control(getattr(finding, "control_id", None))
    text = _finding_text(finding)
    severity = _severity_component(finding)
    exposure = _internet_exposure_component(action_type, text)
    privilege = _privilege_component(action_type, text)
    data_sensitivity = _data_sensitivity_component(action_type, text)
    exploit = _exploit_component(action_type, text)
    compensating = _compensating_controls_component(text)
    score = _clamp_score(
        severity.points + exposure.points + privilege.points + data_sensitivity.points + exploit.points - compensating.points
    )
    components = _build_components(score, finding, severity, exposure, privilege, data_sensitivity, exploit, compensating)
    return ActionScore(score=score, components=components, representative_finding=finding)


def score_action_group(findings: list[Any]) -> ActionScore:
    if not findings:
        return ActionScore(score=0, components=_empty_components(), representative_finding=None)
    scored = [_score_entry(finding) for finding in findings]
    scored.sort(key=lambda item: item.tie_breaker, reverse=True)
    return scored[0].score


def _score_entry(finding: Any) -> _ScoredFinding:
    score = score_action_finding(finding)
    tie_breaker = (
        score.score,
        _component_points(score.components, "severity"),
        _finding_recency_token(finding),
        str(getattr(finding, "finding_id", "") or ""),
        str(getattr(finding, "id", "") or ""),
    )
    return _ScoredFinding(finding=finding, score=score, tie_breaker=tie_breaker)


def _finding_text(finding: Any) -> str:
    raw = getattr(finding, "raw_json", None)
    raw_subset = raw if isinstance(raw, dict) else {}
    payload = {
        "compliance": raw_subset.get("Compliance"),
        "network_path": raw_subset.get("NetworkPath"),
        "product_fields": raw_subset.get("ProductFields"),
        "resources": raw_subset.get("Resources"),
        "status_branch": raw_subset.get("status_branch"),
        "types": raw_subset.get("Types"),
        "vulnerabilities": raw_subset.get("Vulnerabilities"),
    }
    base = [
        str(getattr(finding, "title", "") or ""),
        str(getattr(finding, "description", "") or ""),
        str(getattr(finding, "resource_type", "") or ""),
        str(getattr(finding, "resource_id", "") or ""),
        str(getattr(finding, "control_id", "") or ""),
        json.dumps(payload, sort_keys=True, default=str),
    ]
    return " ".join(base).lower()


def _severity_component(finding: Any) -> _ComponentScore:
    normalized = _clamp_normalized((int(getattr(finding, "severity_normalized", 0) or 0)) / 100)
    label = str(getattr(finding, "severity_label", "") or "INFORMATIONAL").upper()
    return _component_score(normalized, _SCORE_WEIGHTS["severity"], (f"severity:{label}",))


def _internet_exposure_component(action_type: str, text: str) -> _ComponentScore:
    return _keyword_or_action_component(
        action_type,
        text,
        _HIGH_EXPOSURE_KEYWORDS,
        _MEDIUM_EXPOSURE_KEYWORDS,
        _HIGH_EXPOSURE_ACTIONS,
        "internet_exposure",
    )


def _privilege_component(action_type: str, text: str) -> _ComponentScore:
    return _keyword_or_action_component(
        action_type,
        text,
        _HIGH_PRIVILEGE_KEYWORDS,
        _MEDIUM_PRIVILEGE_KEYWORDS,
        _PRIVILEGE_ACTIONS,
        "privilege_level",
    )


def _data_sensitivity_component(action_type: str, text: str) -> _ComponentScore:
    return _keyword_or_action_component(
        action_type,
        text,
        _HIGH_DATA_KEYWORDS,
        _MEDIUM_DATA_KEYWORDS,
        _DATA_SENSITIVITY_ACTIONS,
        "data_sensitivity",
    )


def _exploit_component(action_type: str, text: str) -> _ComponentScore:
    return _keyword_or_action_component(
        action_type,
        text,
        _HIGH_EXPLOIT_KEYWORDS,
        _MEDIUM_EXPLOIT_KEYWORDS,
        _EXPLOIT_ACTIONS,
        "exploit_signals",
    )


def _compensating_controls_component(text: str) -> _ComponentScore:
    signals = _matched_signals(text, _COMPENSATING_CONTROL_KEYWORDS)
    if len(signals) >= 2:
        return _component_score(0.8, _SCORE_WEIGHTS["compensating_controls"], tuple(signals))
    if signals:
        return _component_score(0.5, _SCORE_WEIGHTS["compensating_controls"], tuple(signals))
    return _component_score(0.0, _SCORE_WEIGHTS["compensating_controls"], ())


def _keyword_or_action_component(
    action_type: str,
    text: str,
    high_keywords: tuple[str, ...],
    medium_keywords: tuple[str, ...],
    action_defaults: dict[str, float],
    name: str,
) -> _ComponentScore:
    default = _clamp_normalized(action_defaults.get(action_type, 0.0))
    default_signals = (f"action_type:{action_type}",) if default > 0 else ()
    high_signals = _matched_signals(text, high_keywords)
    if high_signals:
        return _component_score(1.0, _SCORE_WEIGHTS[name], tuple(high_signals))
    medium_signals = _matched_signals(text, medium_keywords)
    if medium_signals and default < 0.6:
        return _component_score(0.6, _SCORE_WEIGHTS[name], tuple(medium_signals))
    if medium_signals and default >= 0.6:
        return _component_score(default, _SCORE_WEIGHTS[name], default_signals + tuple(medium_signals))
    return _component_score(default, _SCORE_WEIGHTS[name], default_signals)


def _matched_signals(text: str, keywords: tuple[str, ...]) -> list[str]:
    matches = [f"keyword:{keyword}" for keyword in keywords if keyword in text]
    return matches[:3]


def _component_score(normalized: float, weight: int, signals: tuple[str, ...]) -> _ComponentScore:
    clamped = _clamp_normalized(normalized)
    points = int((clamped * weight) + 0.5)
    return _ComponentScore(normalized=round(clamped, 4), points=points, signals=signals)


def _build_components(
    score: int,
    finding: Any,
    severity: _ComponentScore,
    exposure: _ComponentScore,
    privilege: _ComponentScore,
    data_sensitivity: _ComponentScore,
    exploit: _ComponentScore,
    compensating: _ComponentScore,
) -> dict[str, Any]:
    return {
        "version": 1,
        "representative_finding_id": str(getattr(finding, "finding_id", "") or ""),
        "representative_finding_db_id": str(getattr(finding, "id", "") or ""),
        "severity": _component_payload(severity),
        "internet_exposure": _component_payload(exposure),
        "privilege_level": _component_payload(privilege),
        "data_sensitivity": _component_payload(data_sensitivity),
        "exploit_signals": _component_payload(exploit),
        "compensating_controls": _component_payload(compensating, negative=True),
        "score": score,
        "total_positive_points": severity.points + exposure.points + privilege.points + data_sensitivity.points + exploit.points,
        "total_compensating_points": compensating.points,
    }


def _component_payload(component: _ComponentScore, *, negative: bool = False) -> dict[str, Any]:
    points = -component.points if negative else component.points
    return {"normalized": component.normalized, "points": points, "signals": list(component.signals)}


def _component_points(components: dict[str, Any], key: str) -> int:
    payload = components.get(key) if isinstance(components, dict) else None
    if not isinstance(payload, dict):
        return 0
    return int(payload.get("points") or 0)


def _finding_recency_token(finding: Any) -> str:
    for attr in ("sh_updated_at", "last_observed_at", "updated_at", "created_at"):
        value = getattr(finding, attr, None)
        if value is None:
            continue
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    return ""


def _empty_components() -> dict[str, Any]:
    return {
        "version": 1,
        "representative_finding_id": "",
        "representative_finding_db_id": "",
        "severity": _component_payload(_component_score(0.0, _SCORE_WEIGHTS["severity"], ())),
        "internet_exposure": _component_payload(_component_score(0.0, _SCORE_WEIGHTS["internet_exposure"], ())),
        "privilege_level": _component_payload(_component_score(0.0, _SCORE_WEIGHTS["privilege_level"], ())),
        "data_sensitivity": _component_payload(_component_score(0.0, _SCORE_WEIGHTS["data_sensitivity"], ())),
        "exploit_signals": _component_payload(_component_score(0.0, _SCORE_WEIGHTS["exploit_signals"], ())),
        "compensating_controls": _component_payload(
            _component_score(0.0, _SCORE_WEIGHTS["compensating_controls"], ()),
            negative=True,
        ),
        "score": 0,
        "total_positive_points": 0,
        "total_compensating_points": 0,
    }


def _clamp_normalized(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))


def build_score_factors(
    components: dict[str, Any] | None,
    *,
    stored_score: int | None = None,
    legacy_source: str = "stored action.score",
) -> list[dict[str, Any]]:
    score = _resolved_stored_score(components, stored_score)
    if not _has_structured_components(components):
        return [_legacy_score_factor(score, legacy_source)]
    factors = [_factor_payload(name, components) for name in _factor_names(components)]
    return _append_adjustment_factor(factors, score)


def _resolved_stored_score(components: dict[str, Any] | None, stored_score: int | None) -> int:
    if stored_score is not None:
        return int(stored_score)
    if isinstance(components, dict):
        return int(components.get("score") or 0)
    return 0


def _has_structured_components(components: dict[str, Any] | None) -> bool:
    if not isinstance(components, dict):
        return False
    return all(isinstance(components.get(name), dict) for name in _FACTOR_ORDER)


def _legacy_score_factor(score: int, evidence_source: str) -> dict[str, Any]:
    return {
        "factor_name": "legacy_score",
        "weight": 0,
        "contribution": score,
        "evidence_source": evidence_source,
        "signals": [],
        "explanation": "Stored score is available, but granular factor evidence has not been persisted for this action.",
    }


def _factor_payload(name: str, components: dict[str, Any]) -> dict[str, Any]:
    if name == _TOXIC_COMBINATIONS_FACTOR:
        return _toxic_combination_factor_payload(components)
    payload = components.get(name) if isinstance(components, dict) else {}
    contribution = int((payload or {}).get("points") or 0)
    signals = _safe_signals((payload or {}).get("signals"))
    return {
        "factor_name": name,
        "weight": _SCORE_WEIGHTS[name],
        "contribution": contribution,
        "evidence_source": _FACTOR_EVIDENCE_SOURCES[name],
        "signals": signals,
        "explanation": _factor_explanation(name, contribution, signals),
    }


def _factor_names(components: dict[str, Any] | None) -> tuple[str, ...]:
    names = list(_FACTOR_ORDER)
    payload = components.get(_TOXIC_COMBINATIONS_FACTOR) if isinstance(components, dict) else None
    if isinstance(payload, dict):
        names.append(_TOXIC_COMBINATIONS_FACTOR)
    return tuple(names)


def _toxic_combination_factor_payload(components: dict[str, Any]) -> dict[str, Any]:
    payload = components.get(_TOXIC_COMBINATIONS_FACTOR) if isinstance(components, dict) else {}
    contribution = int((payload or {}).get("points") or 0)
    signals = _safe_signals((payload or {}).get("signals"))
    evidence_source = str((payload or {}).get("evidence_source") or _FACTOR_EVIDENCE_SOURCES[_TOXIC_COMBINATIONS_FACTOR])
    explanation = str((payload or {}).get("explanation") or _factor_explanation(_TOXIC_COMBINATIONS_FACTOR, contribution, signals))
    return {
        "factor_name": _TOXIC_COMBINATIONS_FACTOR,
        "weight": int((payload or {}).get("max_boost") or 0),
        "contribution": contribution,
        "evidence_source": evidence_source,
        "signals": signals,
        "explanation": explanation,
    }


def _safe_signals(raw_signals: Any) -> list[str]:
    if not isinstance(raw_signals, (list, tuple)):
        return []
    return [str(signal).strip()[:120] for signal in raw_signals if str(signal).strip()][:3]


def _factor_explanation(name: str, contribution: int, signals: list[str]) -> str:
    label = _FACTOR_LABELS[name]
    if contribution < 0:
        return f"{label} reduced the score by {abs(contribution)} points using: {_signal_summary(signals)}."
    return f"{label} contributed {contribution} points using: {_signal_summary(signals)}."


def _signal_summary(signals: list[str]) -> str:
    if not signals:
        return "no matched signals"
    return ", ".join(signals)


def _append_adjustment_factor(factors: list[dict[str, Any]], score: int) -> list[dict[str, Any]]:
    delta = score - sum(int(factor.get("contribution") or 0) for factor in factors)
    if delta == 0:
        return factors
    return factors + [_score_adjustment_factor(delta)]


def _score_adjustment_factor(delta: int) -> dict[str, Any]:
    verb = "added" if delta > 0 else "removed"
    return {
        "factor_name": "score_bounds_adjustment",
        "weight": 0,
        "contribution": delta,
        "evidence_source": "score clamp to the persisted 0-100 action score",
        "signals": [],
        "explanation": f"Score bounds enforcement {verb} {abs(delta)} points to match the persisted action score.",
    }
