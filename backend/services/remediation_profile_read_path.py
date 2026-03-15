"""Pure Wave 2 helpers for remediation profile options and preview metadata."""
from __future__ import annotations

from typing import Any, Mapping, TypedDict

from backend.models.action import Action
from backend.services.remediation_profile_catalog import list_profiles_for_strategy
from backend.services.remediation_profile_selection import (
    ProfileSelectionResolution,
    resolve_profile_selection,
)
from backend.services.remediation_profile_resolver import (
    ResolverDecision,
    build_compat_resolution_decision,
)
from backend.services.root_key_resolution_adapter import (
    build_root_key_guidance_metadata,
    is_root_key_action_type,
)
from backend.services.remediation_strategy import RemediationStrategy


class InvalidProfileSelection(ValueError):
    """Raised when a selected profile does not belong to the chosen strategy family."""


class RemediationProfileOptionPayload(TypedDict):
    """One additive compatibility-profile row nested beneath a strategy."""

    profile_id: str
    support_tier: str
    recommended: bool
    requires_inputs: bool
    supports_exception_flow: bool
    exception_only: bool


class RemediationStrategyProfileMetadata(TypedDict):
    """Additive remediation-options metadata derived from the Wave 1 catalog."""

    profiles: list[RemediationProfileOptionPayload]
    recommended_profile_id: str | None
    missing_defaults: list[str]
    blocked_reasons: list[str]
    preservation_summary: dict[str, Any]
    decision_rationale: str

def build_strategy_profile_metadata(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    dependency_checks: list[Mapping[str, Any]] | None,
    action: Action | None = None,
) -> RemediationStrategyProfileMetadata:
    """Build additive Wave 2 profile metadata for one remediation-options row."""
    strategy_id = strategy["strategy_id"]
    selection = _resolve_selection_or_error(
        action_type=action_type,
        strategy=strategy,
        profile_id=None,
        strategy_inputs=None,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    profiles = _profile_payloads(
        action_type,
        strategy,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        recommended_profile_id=selection.profile.profile_id,
        action=action,
    )
    blocked_reasons = _merge_reasons(selection.blocked_reasons, _blocked_reasons(dependency_checks))
    preservation_summary = _preservation_summary(
        strategy=strategy,
        selection=selection,
    )
    decision_rationale = _selection_rationale(selection, blocked_reasons=blocked_reasons)
    if is_root_key_action_type(action_type):
        guidance = build_root_key_guidance_metadata(
            strategy_id=selection.profile.profile_id,
            blocked_reasons=blocked_reasons,
        )
        blocked_reasons = guidance["blocked_reasons"]
        preservation_summary.update(guidance["preservation_summary"])
        decision_rationale = guidance["decision_rationale"]
    return {
        "profiles": profiles,
        "recommended_profile_id": selection.profile.profile_id,
        "missing_defaults": list(selection.missing_defaults),
        "blocked_reasons": blocked_reasons,
        "preservation_summary": preservation_summary,
        "decision_rationale": decision_rationale,
    }


def build_preview_resolution(
    *,
    action_type: str | None,
    strategy: RemediationStrategy | None,
    profile_id: str | None,
    strategy_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    dependency_checks: list[Mapping[str, Any]] | None,
    action: Action | None = None,
) -> ResolverDecision | None:
    """Return additive preview resolution metadata when a strategy family is known."""
    if strategy is None:
        return None
    selection = _resolve_selection_or_error(
        action_type=action_type,
        strategy=strategy,
        profile_id=profile_id,
        strategy_inputs=strategy_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    blocked_reasons = _merge_reasons(selection.blocked_reasons, _blocked_reasons(dependency_checks))
    support_tier = selection.support_tier
    preservation_summary = _preservation_summary(strategy=strategy, selection=selection)
    decision_rationale = _selection_rationale(selection, blocked_reasons=blocked_reasons)
    if is_root_key_action_type(action_type):
        guidance = build_root_key_guidance_metadata(
            strategy_id=selection.profile.profile_id,
            blocked_reasons=blocked_reasons,
        )
        support_tier = guidance["support_tier"]
        blocked_reasons = guidance["blocked_reasons"]
        preservation_summary.update(guidance["preservation_summary"])
        decision_rationale = guidance["decision_rationale"]
    return build_compat_resolution_decision(
        strategy_id=strategy["strategy_id"],
        profile_id=selection.profile.profile_id,
        support_tier=support_tier,
        resolved_inputs=selection.resolved_inputs,
        missing_inputs=selection.missing_inputs,
        missing_defaults=selection.missing_defaults,
        blocked_reasons=blocked_reasons,
        rejected_profiles=selection.rejected_profiles,
        preservation_summary=preservation_summary,
        decision_rationale=decision_rationale,
    )


def _profile_payloads(
    action_type: str | None,
    strategy: RemediationStrategy,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    recommended_profile_id: str | None,
    action: Action | None,
) -> list[RemediationProfileOptionPayload]:
    strategy_id = strategy["strategy_id"]
    payloads: list[RemediationProfileOptionPayload] = []
    for profile in list_profiles_for_strategy(action_type, strategy_id):
        selection = _resolve_selection_or_error(
            action_type=action_type,
            strategy=strategy,
            profile_id=profile.profile_id,
            strategy_inputs=None,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
        support_tier = selection.support_tier
        if is_root_key_action_type(action_type):
            support_tier = build_root_key_guidance_metadata(
                strategy_id=profile.profile_id,
            )["support_tier"]
        payloads.append(
            {
                "profile_id": profile.profile_id,
                "support_tier": support_tier,
                "recommended": profile.profile_id == recommended_profile_id,
                "requires_inputs": profile.requires_inputs,
                "supports_exception_flow": profile.supports_exception_flow,
                "exception_only": profile.exception_only,
            }
        )
    return payloads


def _resolve_selection_or_error(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    profile_id: str | None,
    strategy_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    try:
        return resolve_profile_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=profile_id,
            explicit_inputs=strategy_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    except ValueError as exc:
        raise InvalidProfileSelection(str(exc)) from exc


def _preservation_summary(
    *,
    strategy: RemediationStrategy,
    selection: ProfileSelectionResolution,
) -> dict[str, Any]:
    return {
        "single_profile_compatible": selection.profile.profile_id == strategy["strategy_id"],
        "strategy_only_supported": True,
        **dict(selection.preservation_summary),
    }


def _blocked_reasons(dependency_checks: list[Mapping[str, Any]] | None) -> list[str]:
    reasons: list[str] = []
    for check in dependency_checks or []:
        if check.get("status") != "fail":
            continue
        message = str(check.get("message") or check.get("code") or "").strip()
        if message and message not in reasons:
            reasons.append(message)
    return reasons


def _merge_reasons(*reason_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if reason and reason not in merged:
                merged.append(reason)
    return merged


def _selection_rationale(
    selection: ProfileSelectionResolution,
    *,
    blocked_reasons: list[str],
) -> str:
    if not blocked_reasons:
        return selection.decision_rationale
    extra = [reason for reason in blocked_reasons if reason not in selection.blocked_reasons]
    if not extra:
        return selection.decision_rationale
    if not selection.decision_rationale:
        return f"Blocking checks: {', '.join(extra)}."
    return f"{selection.decision_rationale} Blocking checks: {', '.join(extra)}."


__all__ = [
    "InvalidProfileSelection",
    "RemediationProfileOptionPayload",
    "RemediationStrategyProfileMetadata",
    "build_preview_resolution",
    "build_strategy_profile_metadata",
]
