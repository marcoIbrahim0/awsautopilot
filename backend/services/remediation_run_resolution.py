"""Single-run remediation resolution helpers for Wave 2 create wiring."""
from __future__ import annotations

import copy
import re
from typing import Any, Mapping

from backend.models.action import Action
from backend.services.remediation_profile_catalog import (
    default_profile_id_for_strategy,
    get_profile_definition,
)
from backend.services.remediation_profile_resolver import (
    ResolverDecision,
    SupportTier,
    build_compat_resolution_decision,
)
from backend.services.remediation_risk import requires_risk_ack
from backend.services.remediation_strategy import RemediationStrategy, StrategyInputField

LEGACY_RESOLUTION_MIRROR_FIELDS = (
    "selected_strategy",
    "strategy_inputs",
    "pr_bundle_variant",
)
_MISSING = object()
_SAFE_DEFAULT_TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class RemediationRunResolutionError(ValueError):
    """Raised when single-run profile resolution cannot be normalized."""


def resolve_create_profile_id(
    action_type: str | None,
    strategy_id: str,
    profile_id: str | None,
) -> str:
    requested_profile_id = _clean_text(profile_id)
    resolved_profile_id = requested_profile_id or default_profile_id_for_strategy(action_type, strategy_id)
    if resolved_profile_id is None:
        raise RemediationRunResolutionError(
            f"No remediation profile is registered for strategy_id '{strategy_id}'."
        )
    if get_profile_definition(action_type, strategy_id, resolved_profile_id) is None:
        raise RemediationRunResolutionError(
            f"profile_id '{resolved_profile_id}' is not valid for strategy_id '{strategy_id}'."
        )
    return resolved_profile_id


def build_single_run_resolution(
    *,
    action: Action,
    strategy: RemediationStrategy,
    profile_id: str,
    strategy_inputs: dict[str, Any] | None,
    risk_snapshot: Mapping[str, Any] | None,
    risk_acknowledged: bool,
    requested_profile_id: str | None,
) -> ResolverDecision:
    support_tier = _support_tier(risk_snapshot, risk_acknowledged=risk_acknowledged)
    return build_compat_resolution_decision(
        strategy_id=strategy["strategy_id"],
        profile_id=profile_id,
        support_tier=support_tier,
        resolved_inputs=_resolved_inputs(strategy, strategy_inputs, action=action),
        missing_inputs=[],
        missing_defaults=[],
        blocked_reasons=[],
        rejected_profiles=[],
        finding_coverage={},
        preservation_summary={},
        decision_rationale=_decision_rationale(
            strategy_id=strategy["strategy_id"],
            profile_id=profile_id,
            support_tier=support_tier,
            requested_profile_id=requested_profile_id,
        ),
    )


def apply_resolution_artifacts(
    artifacts: Mapping[str, Any] | None,
    *,
    resolution: ResolverDecision | None,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    pr_bundle_variant: str | None,
) -> dict[str, Any]:
    merged = dict(artifacts or {})
    if resolution is not None:
        merged["resolution"] = copy.deepcopy(resolution)
    if strategy_id:
        merged["selected_strategy"] = strategy_id
    if strategy_inputs is not None:
        merged["strategy_inputs"] = copy.deepcopy(strategy_inputs)
    if pr_bundle_variant is not None:
        merged["pr_bundle_variant"] = pr_bundle_variant
    return merged


def _support_tier(
    risk_snapshot: Mapping[str, Any] | None,
    *,
    risk_acknowledged: bool,
) -> SupportTier:
    if not risk_acknowledged:
        return "deterministic_bundle"
    checks = risk_snapshot.get("checks") if isinstance(risk_snapshot, Mapping) else None
    if isinstance(checks, list) and requires_risk_ack(checks):
        return "review_required_bundle"
    return "deterministic_bundle"


def _resolved_inputs(
    strategy: RemediationStrategy,
    strategy_inputs: dict[str, Any] | None,
    *,
    action: Action,
) -> dict[str, Any]:
    resolved = copy.deepcopy(strategy_inputs or {})
    for field in strategy["input_schema"].get("fields", []):
        _apply_field_default(resolved, field, action=action)
    return resolved


def _apply_field_default(
    resolved: dict[str, Any],
    field: StrategyInputField,
    *,
    action: Action,
) -> None:
    key = field["key"]
    if key in resolved:
        return
    default_value = _default_value(field, action=action)
    if default_value is _MISSING:
        return
    resolved[key] = default_value


def _default_value(field: StrategyInputField, *, action: Action) -> Any:
    if "default_value" in field:
        return copy.deepcopy(field["default_value"])
    if "safe_default_value" not in field:
        return _MISSING
    safe_default = field["safe_default_value"]
    return _render_safe_default(safe_default, action=action)


def _render_safe_default(value: Any, *, action: Action) -> Any:
    if not isinstance(value, str):
        return copy.deepcopy(value)
    if "{{" not in value:
        return value
    try:
        return _SAFE_DEFAULT_TOKEN_PATTERN.sub(
            lambda match: _safe_default_token(action, match.group(1)),
            value,
        )
    except KeyError:
        return _MISSING


def _safe_default_token(action: Action, token: str) -> str:
    context = {
        "account_id": getattr(action, "account_id", None),
        "region": getattr(action, "region", None),
        "target_id": getattr(action, "target_id", None),
        "resource_id": getattr(action, "resource_id", None),
    }
    value = context.get(token)
    if value in (None, ""):
        raise KeyError(token)
    return str(value)


def _decision_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    support_tier: SupportTier,
    requested_profile_id: str | None,
) -> str:
    profile_note = (
        f"Caller selected remediation profile '{profile_id}' within strategy '{strategy_id}'."
        if _clean_text(requested_profile_id)
        else f"Wave 1 single-profile compatibility defaulted profile_id to '{profile_id}'."
    )
    review_note = (
        "Run creation was accepted after risk_acknowledged=true satisfied review-required checks."
        if support_tier == "review_required_bundle"
        else "Run creation did not require review-only acceptance."
    )
    return f"{profile_note} {review_note}"


def _clean_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


__all__ = [
    "LEGACY_RESOLUTION_MIRROR_FIELDS",
    "RemediationRunResolutionError",
    "apply_resolution_artifacts",
    "build_single_run_resolution",
    "resolve_create_profile_id",
]
