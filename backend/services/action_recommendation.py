"""Recommendation-mode derivation from matrix position."""
from __future__ import annotations

from typing import Any, Literal, TypedDict

from backend.services.action_sla import risk_tier_from_score
from backend.services.root_credentials_workflow import is_root_credentials_required_action

RecommendationMode = Literal["direct_fix_candidate", "pr_only", "exception_review"]
MatrixRiskTier = Literal["low", "medium", "high"]
BusinessCriticalityTier = Literal["low", "medium", "high"]

_HIGH_CRITICALITY_ACTIONS = {
    "aws_config_enabled": 0.85,
    "cloudtrail_enabled": 0.9,
    "ebs_default_encryption": 0.7,
    "iam_root_access_key_absent": 1.0,
    "s3_bucket_access_logging": 0.7,
    "s3_bucket_encryption": 0.8,
    "s3_bucket_encryption_kms": 0.95,
    "s3_bucket_require_ssl": 0.7,
}
_MEDIUM_CRITICALITY_ACTIONS = {
    "ebs_snapshot_block_public_access": 0.65,
    "enable_guardduty": 0.45,
    "enable_security_hub": 0.45,
    "s3_block_public_access": 0.55,
    "s3_bucket_block_public_access": 0.6,
    "sg_restrict_public_ports": 0.6,
    "ssm_block_public_sharing": 0.5,
}
_HIGH_CRITICALITY_KEYWORDS = (
    "auth",
    "billing",
    "checkout",
    "customer",
    "payment",
    "pci",
    "phi",
    "pii",
    "prod",
    "production",
    "regulated",
    "revenue",
)
_MEDIUM_CRITICALITY_KEYWORDS = (
    "audit",
    "compliance",
    "internal",
    "log",
    "shared",
)
_MATRIX_MODE_MAP: dict[tuple[MatrixRiskTier, BusinessCriticalityTier], RecommendationMode] = {
    ("low", "low"): "direct_fix_candidate",
    ("medium", "low"): "direct_fix_candidate",
    ("high", "low"): "direct_fix_candidate",
    ("low", "medium"): "direct_fix_candidate",
    ("medium", "medium"): "pr_only",
    ("high", "medium"): "pr_only",
    ("low", "high"): "pr_only",
    ("medium", "high"): "pr_only",
    ("high", "high"): "exception_review",
}


class RecommendationMatrixPosition(TypedDict):
    risk_tier: MatrixRiskTier
    business_criticality: BusinessCriticalityTier
    cell: str


class RecommendationEvidence(TypedDict):
    score: int
    context_incomplete: bool
    data_sensitivity: float
    internet_exposure: float
    privilege_level: float
    exploit_signals: float
    matched_signals: list[str]


class ActionRecommendation(TypedDict):
    mode: RecommendationMode
    default_mode: RecommendationMode
    advisory: bool
    enforced_by_policy: str | None
    rationale: str
    matrix_position: RecommendationMatrixPosition
    evidence: RecommendationEvidence


def build_action_recommendation(
    action: Any,
    *,
    mode_options: list[str] | None = None,
    manual_high_risk: bool = False,
) -> ActionRecommendation:
    evidence = _build_evidence(action)
    position = _matrix_position(action, evidence)
    default_mode = _MATRIX_MODE_MAP[(position["risk_tier"], position["business_criticality"])]
    mode, advisory, enforced_by_policy = _effective_mode(
        action,
        default_mode=default_mode,
        manual_high_risk=manual_high_risk,
    )
    rationale = _build_rationale(
        action,
        position=position,
        evidence=evidence,
        default_mode=default_mode,
        mode=mode,
        advisory=advisory,
        enforced_by_policy=enforced_by_policy,
        mode_options=mode_options or [],
    )
    return {
        "mode": mode,
        "default_mode": default_mode,
        "advisory": advisory,
        "enforced_by_policy": enforced_by_policy,
        "rationale": rationale,
        "matrix_position": position,
        "evidence": evidence,
    }


def _build_evidence(action: Any) -> RecommendationEvidence:
    components = _components(action)
    return {
        "score": _score(action),
        "context_incomplete": _context_incomplete(components),
        "data_sensitivity": _normalized_component(components, "data_sensitivity"),
        "internet_exposure": _normalized_component(components, "internet_exposure"),
        "privilege_level": _normalized_component(components, "privilege_level"),
        "exploit_signals": _normalized_component(components, "exploit_signals"),
        "matched_signals": _business_signals(action),
    }


def _matrix_position(action: Any, evidence: RecommendationEvidence) -> RecommendationMatrixPosition:
    risk_tier = _matrix_risk_tier(evidence["score"])
    criticality = _business_criticality_tier(action, evidence)
    return {
        "risk_tier": risk_tier,
        "business_criticality": criticality,
        "cell": f"risk_{risk_tier}__criticality_{criticality}",
    }


def _effective_mode(
    action: Any,
    *,
    default_mode: RecommendationMode,
    manual_high_risk: bool,
) -> tuple[RecommendationMode, bool, str | None]:
    if _action_type(action) == "pr_only":
        return "exception_review", False, "unsupported_pr_only_action"
    if manual_high_risk or is_root_credentials_required_action(_action_type(action)):
        return "exception_review", False, "manual_high_risk_root_credentials_required"
    return default_mode, True, None


def _build_rationale(
    action: Any,
    *,
    position: RecommendationMatrixPosition,
    evidence: RecommendationEvidence,
    default_mode: RecommendationMode,
    mode: RecommendationMode,
    advisory: bool,
    enforced_by_policy: str | None,
    mode_options: list[str],
) -> str:
    summary = _matrix_summary(position, default_mode)
    criticality = _criticality_summary(evidence)
    context = _context_summary(evidence["context_incomplete"])
    capability = _capability_summary(mode, advisory, mode_options)
    policy = _policy_summary(action, enforced_by_policy)
    return " ".join(part for part in (summary, criticality, context, capability, policy) if part)


def _matrix_risk_tier(score: int) -> MatrixRiskTier:
    tier = risk_tier_from_score(score)
    if tier in {"critical", "high"}:
        return "high"
    if tier == "medium":
        return "medium"
    return "low"


def _business_criticality_tier(
    action: Any,
    evidence: RecommendationEvidence,
) -> BusinessCriticalityTier:
    score = _business_criticality_score(action, evidence)
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _business_criticality_score(action: Any, evidence: RecommendationEvidence) -> float:
    signals = evidence["matched_signals"]
    keyword_score = 1.0 if _has_high_keyword(signals) else 0.6 if signals else 0.0
    action_score = _action_criticality_default(_action_type(action))
    signal_score = max(evidence["data_sensitivity"], evidence["privilege_level"] * 0.85)
    return round(max(keyword_score, action_score, signal_score), 4)


def _action_criticality_default(action_type: str) -> float:
    if action_type in _HIGH_CRITICALITY_ACTIONS:
        return _HIGH_CRITICALITY_ACTIONS[action_type]
    return _MEDIUM_CRITICALITY_ACTIONS.get(action_type, 0.0)


def _business_signals(action: Any) -> list[str]:
    text = _action_text(action)
    high = [f"keyword:{word}" for word in _HIGH_CRITICALITY_KEYWORDS if word in text]
    medium = [f"keyword:{word}" for word in _MEDIUM_CRITICALITY_KEYWORDS if word in text]
    return (high or medium)[:3]


def _matrix_summary(
    position: RecommendationMatrixPosition,
    default_mode: RecommendationMode,
) -> str:
    return (
        f"Matrix cell {position['cell']} maps to default recommendation "
        f"'{default_mode}'. Risk is {position['risk_tier']} and business criticality is "
        f"{position['business_criticality']}."
    )


def _criticality_summary(evidence: RecommendationEvidence) -> str:
    signals = ", ".join(evidence["matched_signals"]) if evidence["matched_signals"] else "none"
    return (
        "Criticality evidence: "
        f"data_sensitivity={evidence['data_sensitivity']:.2f}, "
        f"privilege_level={evidence['privilege_level']:.2f}, "
        f"internet_exposure={evidence['internet_exposure']:.2f}, "
        f"matched_signals={signals}."
    )


def _context_summary(context_incomplete: bool) -> str:
    if not context_incomplete:
        return "Relationship context is complete enough for advisory matrix placement."
    return "Relationship context is incomplete, so the recommendation remains conservative and advisory unless policy overrides it."


def _capability_summary(
    mode: RecommendationMode,
    advisory: bool,
    mode_options: list[str],
) -> str:
    if not advisory or mode != "direct_fix_candidate" or "direct_fix" in mode_options:
        return ""
    return "Direct fix is not currently exposed in mode_options, so this stays an advisory candidate rather than an execution gate."


def _policy_summary(action: Any, enforced_by_policy: str | None) -> str:
    if enforced_by_policy == "unsupported_pr_only_action":
        return "Policy override applied: unmapped pr_only controls require exception review instead of an execution recommendation."
    if enforced_by_policy == "manual_high_risk_root_credentials_required":
        return (
            "Policy override applied: this action is marked manual/high-risk and requires explicit exception-style review "
            "before execution."
        )
    return ""


def _score(action: Any) -> int:
    raw = getattr(action, "score", None)
    if raw is None:
        raw = getattr(action, "priority", 0)
    return int(raw or 0)


def _components(action: Any) -> dict[str, Any]:
    value = getattr(action, "score_components", None)
    if isinstance(value, dict):
        return value
    return {}


def _context_incomplete(components: dict[str, Any]) -> bool:
    marker = components.get("context_incomplete")
    if isinstance(marker, bool):
        return marker
    toxic = components.get("toxic_combinations")
    if isinstance(toxic, dict):
        return bool(toxic.get("context_incomplete"))
    return True


def _normalized_component(components: dict[str, Any], key: str) -> float:
    payload = components.get(key)
    if not isinstance(payload, dict):
        return 0.0
    return round(float(payload.get("normalized") or 0.0), 4)


def _action_text(action: Any) -> str:
    values = (
        getattr(action, "title", ""),
        getattr(action, "description", ""),
        getattr(action, "resource_id", ""),
        getattr(action, "resource_type", ""),
        getattr(action, "control_id", ""),
    )
    return " ".join(str(value or "") for value in values).lower()


def _action_type(action: Any) -> str:
    return str(getattr(action, "action_type", "") or "").strip()


def _has_high_keyword(signals: list[str]) -> bool:
    return any(signal.removeprefix("keyword:") in _HIGH_CRITICALITY_KEYWORDS for signal in signals)
