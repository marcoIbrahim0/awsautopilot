"""Single-run remediation resolution helpers for Wave 2 create wiring."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from backend.services.remediation_profile_selection import (
    ProfileSelectionResolution,
    resolve_profile_selection,
)
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
from backend.services.remediation_strategy import RemediationStrategy

LEGACY_RESOLUTION_MIRROR_FIELDS = (
    "selected_strategy",
    "strategy_inputs",
    "pr_bundle_variant",
)


class RemediationRunResolutionError(ValueError):
    """Raised when single-run profile resolution cannot be normalized."""


_SUPPORT_TIER_ORDER: dict[SupportTier, int] = {
    "deterministic_bundle": 0,
    "review_required_bundle": 1,
    "manual_guidance_only": 2,
}


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


def resolve_create_profile_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Any | None = None,
) -> ProfileSelectionResolution:
    try:
        return resolve_profile_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    except ValueError as exc:
        raise RemediationRunResolutionError(str(exc)) from exc


def build_single_run_resolution(
    *,
    strategy: RemediationStrategy,
    profile_selection: ProfileSelectionResolution,
    risk_snapshot: Mapping[str, Any] | None,
    risk_acknowledged: bool,
    requested_profile_id: str | None,
) -> ResolverDecision:
    support_tier = _support_tier(
        profile_selection.support_tier,
        risk_snapshot,
        risk_acknowledged=risk_acknowledged,
    )
    return build_compat_resolution_decision(
        strategy_id=strategy["strategy_id"],
        profile_id=profile_selection.profile.profile_id,
        support_tier=support_tier,
        resolved_inputs=profile_selection.resolved_inputs,
        missing_inputs=profile_selection.missing_inputs,
        missing_defaults=profile_selection.missing_defaults,
        blocked_reasons=profile_selection.blocked_reasons,
        rejected_profiles=profile_selection.rejected_profiles,
        finding_coverage={},
        preservation_summary={
            "single_profile_compatible": profile_selection.profile.profile_id == strategy["strategy_id"],
            "strategy_only_supported": True,
            **dict(profile_selection.preservation_summary),
        },
        decision_rationale=_decision_rationale(
            strategy_id=strategy["strategy_id"],
            profile_id=profile_selection.profile.profile_id,
            support_tier=support_tier,
            requested_profile_id=requested_profile_id,
            selection_rationale=profile_selection.decision_rationale,
            selection_support_tier=profile_selection.support_tier,
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
    selected_support_tier: SupportTier,
    risk_snapshot: Mapping[str, Any] | None,
    *,
    risk_acknowledged: bool,
) -> SupportTier:
    support_tier = selected_support_tier
    if not risk_acknowledged:
        return support_tier
    checks = risk_snapshot.get("checks") if isinstance(risk_snapshot, Mapping) else None
    if isinstance(checks, list) and requires_risk_ack(checks):
        support_tier = _max_support_tier(support_tier, "review_required_bundle")
    return support_tier


def _max_support_tier(left: SupportTier, right: SupportTier) -> SupportTier:
    if _SUPPORT_TIER_ORDER[left] >= _SUPPORT_TIER_ORDER[right]:
        return left
    return right


def _decision_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    support_tier: SupportTier,
    requested_profile_id: str | None,
    selection_rationale: str,
    selection_support_tier: SupportTier,
) -> str:
    parts: list[str] = []
    if selection_rationale:
        parts.append(selection_rationale)
    elif _clean_text(requested_profile_id):
        parts.append(f"Caller selected remediation profile '{profile_id}' within strategy '{strategy_id}'.")
    else:
        parts.append(f"Compatibility resolver selected profile '{profile_id}' within strategy '{strategy_id}'.")
    if support_tier != selection_support_tier and support_tier == "review_required_bundle":
        parts.append("Run creation was accepted after risk_acknowledged=true satisfied review-required checks.")
    else:
        parts.append("Run creation did not require additional risk-only acceptance.")
    return " ".join(parts)


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
    "resolve_create_profile_selection",
    "resolve_create_profile_id",
]
