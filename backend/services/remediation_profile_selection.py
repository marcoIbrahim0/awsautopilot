"""Shared profile-family selection and input resolution helpers."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Mapping

from backend.models.action import Action
from backend.services.remediation_profile_catalog import (
    CLOUDTRAIL_FAMILY_RESOLVER_KIND,
    CONFIG_FAMILY_RESOLVER_KIND,
    RemediationProfileDefinition,
    default_profile_id_for_strategy,
    get_profile_definition,
    list_profiles_for_strategy,
)
from backend.services.remediation_profile_resolver import ResolverRejectedProfile, SupportTier
from backend.services.remediation_settings import normalize_remediation_settings
from backend.services.s3_family_resolution_adapter import (
    S3_11_FAMILY_RESOLVER_KIND,
    S3_15_CUSTOMER_MANAGED_PROFILE_ID,
    S3_15_FAMILY_RESOLVER_KIND,
    S3_2_FAMILY_RESOLVER_KIND,
    S3_5_FAMILY_RESOLVER_KIND,
    S3_9_FAMILY_RESOLVER_KIND,
    resolve_s3_11_selection,
    resolve_s3_15_selection,
    resolve_s3_2_selection,
    resolve_s3_5_selection,
    resolve_s3_9_selection,
    resolve_s3_kms_key_mode,
)
from backend.services.remediation_strategy import RemediationStrategy, StrategyInputField

_SAFE_DEFAULT_TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_EC2_53_STRATEGY_ID = "sg_restrict_public_ports_guided"
_EC2_53_ACCESS_MODES = {
    "close_public",
    "close_and_revoke",
    "restrict_to_ip",
    "restrict_to_cidr",
}
_TENANT_DEFAULT_INPUT_PATHS: dict[str, tuple[tuple[str, str], ...]] = {
    "cloudtrail_enable_guided": (
        ("trail_bucket_name", "cloudtrail.default_bucket_name"),
        ("kms_key_arn", "cloudtrail.default_kms_key_arn"),
    ),
    "config_enable_account_local_delivery": (
        ("delivery_bucket", "config.default_bucket_name"),
        ("kms_key_arn", "config.default_kms_key_arn"),
    ),
    "config_enable_centralized_delivery": (
        ("delivery_bucket", "config.default_bucket_name"),
        ("existing_bucket_name", "config.default_bucket_name"),
        ("kms_key_arn", "config.default_kms_key_arn"),
    ),
    "s3_enable_access_logging_guided": (
        ("log_bucket_name", "s3_access_logs.default_target_bucket_name"),
    ),
    "s3_enable_sse_kms_guided": (
        ("kms_key_mode", "s3_encryption.mode"),
        ("kms_key_arn", "s3_encryption.kms_key_arn"),
    ),
}


@dataclass(frozen=True, slots=True)
class ProfileSelectionResolution:
    """Canonical selection result shared by read/create/grouped flows."""

    profile: RemediationProfileDefinition
    support_tier: SupportTier
    resolved_inputs: dict[str, Any]
    persisted_strategy_inputs: dict[str, Any]
    missing_inputs: list[str]
    missing_defaults: list[str]
    blocked_reasons: list[str]
    rejected_profiles: list[ResolverRejectedProfile]
    preservation_summary: dict[str, Any]
    decision_rationale: str


def resolve_profile_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None = None,
) -> ProfileSelectionResolution:
    profiles = list_profiles_for_strategy(action_type, strategy["strategy_id"])
    if not profiles:
        raise ValueError(f"No remediation profiles are registered for strategy_id '{strategy['strategy_id']}'.")
    family_kind = profiles[0].family_resolver_kind
    if family_kind == "ec2_53_access_path":
        return _resolve_ec2_53_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    if family_kind == S3_2_FAMILY_RESOLVER_KIND:
        return _resolve_s3_2_family_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    if family_kind == S3_9_FAMILY_RESOLVER_KIND:
        return _resolve_s3_9_family_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    if family_kind == S3_5_FAMILY_RESOLVER_KIND:
        return _resolve_s3_5_family_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    if family_kind == S3_11_FAMILY_RESOLVER_KIND:
        return _resolve_s3_11_family_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    if family_kind == S3_15_FAMILY_RESOLVER_KIND:
        return _resolve_s3_15_family_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    if family_kind == CLOUDTRAIL_FAMILY_RESOLVER_KIND:
        return _resolve_cloudtrail_family_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    if family_kind == CONFIG_FAMILY_RESOLVER_KIND:
        return _resolve_config_family_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    return _resolve_compatibility_selection(
        action_type=action_type,
        strategy=strategy,
        requested_profile_id=requested_profile_id,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )


def resolve_runtime_probe_inputs(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    action: Action | None = None,
) -> dict[str, Any]:
    """Resolve non-runtime defaults so callers can collect branch-aware runtime probes."""
    profile = _profile_or_error(action_type, strategy["strategy_id"], requested_profile_id)
    if profile.family_resolver_kind == CLOUDTRAIL_FAMILY_RESOLVER_KIND:
        return _cloudtrail_resolved_inputs(
            strategy=strategy,
            profile=profile,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=None,
            action=action,
        )
    if profile.family_resolver_kind == CONFIG_FAMILY_RESOLVER_KIND:
        return _config_resolved_inputs(
            strategy=strategy,
            profile=profile,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=None,
            action=action,
        )
    return _resolved_inputs(
        strategy=strategy,
        profile=profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=None,
        action=action,
    )


def _resolve_compatibility_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    selected_profile = _profile_or_error(action_type, strategy["strategy_id"], requested_profile_id)
    resolved_inputs = _resolved_inputs(
        strategy=strategy,
        profile=selected_profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    missing_defaults = _compat_missing_defaults(
        strategy=strategy,
        resolved_inputs=resolved_inputs,
    )
    rationale = _compatibility_rationale(
        strategy_id=strategy["strategy_id"],
        profile_id=selected_profile.profile_id,
        explicit_profile=requested_profile_id is not None,
        missing_defaults=missing_defaults,
    )
    return ProfileSelectionResolution(
        profile=selected_profile,
        support_tier=selected_profile.default_support_tier,
        resolved_inputs=resolved_inputs,
        persisted_strategy_inputs=copy.deepcopy(dict(explicit_inputs or {})),
        missing_inputs=_required_missing_inputs(strategy, resolved_inputs),
        missing_defaults=missing_defaults,
        blocked_reasons=[],
        rejected_profiles=[],
        preservation_summary={},
        decision_rationale=rationale,
    )


def _resolve_ec2_53_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    selection = _ec2_53_selection_target(
        action_type=action_type,
        strategy_id=strategy["strategy_id"],
        requested_profile_id=requested_profile_id,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
    )
    resolution = _ec2_53_profile_resolution(
        action_type=action_type,
        strategy=strategy,
        selection=selection,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    return _ec2_53_with_safe_fallback(
        action_type=action_type,
        strategy=strategy,
        selection=selection,
        resolution=resolution,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )


def _ec2_53_selection_target(
    *,
    action_type: str | None,
    strategy_id: str,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
) -> tuple[str, str]:
    explicit_profile = _clean_text(requested_profile_id)
    if explicit_profile is not None:
        _profile_or_error(action_type, strategy_id, explicit_profile)
        return ("explicit_profile", explicit_profile)
    access_mode = _clean_text(_mapping_value(explicit_inputs, "access_mode"))
    if access_mode in _EC2_53_ACCESS_MODES:
        return ("explicit_inputs", access_mode)
    preference = _clean_text(_settings_value(tenant_settings, "sg_access_path_preference"))
    preferred = _preferred_profile_for_sg_access_path(preference)
    if preferred is not None:
        return ("tenant_preference", preferred)
    fallback = default_profile_id_for_strategy(action_type, strategy_id) or "close_public"
    return ("safe_default", fallback)


def _ec2_53_profile_resolution(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    selection: tuple[str, str],
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    source, profile_id = selection
    profile = _profile_or_error(action_type, strategy["strategy_id"], profile_id)
    resolved_inputs = _resolved_inputs(
        strategy=strategy,
        profile=profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    missing_inputs = _ec2_53_missing_inputs(profile_id, resolved_inputs)
    missing_defaults = _ec2_53_missing_defaults(profile_id, explicit_inputs, tenant_settings)
    blocked_reasons = _ec2_53_blocked_reasons(profile_id, missing_inputs, tenant_settings)
    support_tier = _ec2_53_support_tier(profile_id, blocked_reasons, tenant_settings)
    return ProfileSelectionResolution(
        profile=profile,
        support_tier=support_tier,
        resolved_inputs=resolved_inputs,
        persisted_strategy_inputs=_ec2_53_persisted_inputs(profile_id, resolved_inputs, explicit_inputs),
        missing_inputs=missing_inputs,
        missing_defaults=missing_defaults,
        blocked_reasons=blocked_reasons,
        rejected_profiles=[],
        preservation_summary={},
        decision_rationale=_ec2_53_rationale(
            strategy_id=strategy["strategy_id"],
            profile_id=profile_id,
            selection_source=source,
            blocked_reasons=blocked_reasons,
        ),
    )


def _ec2_53_with_safe_fallback(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    selection: tuple[str, str],
    resolution: ProfileSelectionResolution,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    source, _ = selection
    if source != "tenant_preference" or resolution.profile.profile_id not in {"restrict_to_ip", "restrict_to_cidr"}:
        return resolution
    if resolution.support_tier == "deterministic_bundle":
        return resolution
    fallback = _ec2_53_profile_resolution(
        action_type=action_type,
        strategy=strategy,
        selection=("safe_default", "close_public"),
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    detail = resolution.blocked_reasons[0] if resolution.blocked_reasons else "Preferred branch requires more data."
    rejected = [{"profile_id": resolution.profile.profile_id, "reason": "branch_unavailable", "detail": detail}]
    return ProfileSelectionResolution(
        profile=fallback.profile,
        support_tier=fallback.support_tier,
        resolved_inputs=fallback.resolved_inputs,
        persisted_strategy_inputs=fallback.persisted_strategy_inputs,
        missing_inputs=fallback.missing_inputs,
        missing_defaults=fallback.missing_defaults,
        blocked_reasons=fallback.blocked_reasons,
        rejected_profiles=rejected,
        preservation_summary=fallback.preservation_summary,
        decision_rationale=(
            f"Tenant preference selected '{resolution.profile.profile_id}' but it could not be resolved safely. "
            f"Fell back to compatibility profile '{fallback.profile.profile_id}'. {detail}"
        ),
    )


def _resolve_s3_2_family_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    outcome = resolve_s3_2_selection(
        strategy_id=strategy["strategy_id"],
        requested_profile_id=requested_profile_id,
        runtime_signals=runtime_signals,
    )
    return _family_selection_resolution(
        action_type=action_type,
        strategy=strategy,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
        outcome=outcome,
    )


def _resolve_s3_9_family_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    requested_profile = _clean_text(requested_profile_id)
    probe_inputs = resolve_runtime_probe_inputs(
        action_type=action_type,
        strategy=strategy,
        requested_profile_id=requested_profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        action=action,
    )
    outcome = resolve_s3_9_selection(
        strategy_id=strategy["strategy_id"],
        requested_profile_id=requested_profile_id,
        resolved_inputs=probe_inputs,
        runtime_signals=runtime_signals,
        action=action,
    )
    selected_profile = _profile_or_error(action_type, strategy["strategy_id"], str(outcome["profile_id"]))
    resolved_inputs = probe_inputs
    initial_profile_id = requested_profile or default_profile_id_for_strategy(action_type, strategy["strategy_id"])
    if selected_profile.profile_id != initial_profile_id:
        resolved_inputs = _resolved_inputs(
            strategy=strategy,
            profile=selected_profile,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    return _family_selection_resolution(
        action_type=action_type,
        strategy=strategy,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
        outcome=outcome,
        resolved_inputs=resolved_inputs,
        persisted_strategy_inputs=_s3_9_persisted_inputs(
            resolved_inputs=resolved_inputs,
            explicit_inputs=explicit_inputs,
        ),
    )


def _resolve_s3_5_family_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    outcome = resolve_s3_5_selection(
        strategy_id=strategy["strategy_id"],
        requested_profile_id=requested_profile_id,
        explicit_inputs=explicit_inputs,
        runtime_signals=runtime_signals,
    )
    return _family_selection_resolution(
        action_type=action_type,
        strategy=strategy,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
        outcome=outcome,
    )


def _resolve_s3_11_family_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    outcome = resolve_s3_11_selection(
        strategy_id=strategy["strategy_id"],
        requested_profile_id=requested_profile_id,
        explicit_inputs=explicit_inputs,
        runtime_signals=runtime_signals,
    )
    return _family_selection_resolution(
        action_type=action_type,
        strategy=strategy,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
        outcome=outcome,
    )


def _resolve_s3_15_family_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    probe_inputs = resolve_runtime_probe_inputs(
        action_type=action_type,
        strategy=strategy,
        requested_profile_id=requested_profile_id,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        action=action,
    )
    outcome = resolve_s3_15_selection(
        strategy_id=strategy["strategy_id"],
        requested_profile_id=requested_profile_id,
        resolved_inputs=probe_inputs,
        runtime_signals=runtime_signals,
        action=action,
    )
    selected_profile = _profile_or_error(action_type, strategy["strategy_id"], str(outcome["profile_id"]))
    resolved_inputs = _resolved_inputs(
        strategy=strategy,
        profile=selected_profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    missing_inputs = _dedupe_strings(
        [
            *_required_missing_inputs(strategy, resolved_inputs),
            *_s3_15_missing_inputs(
                profile_id=selected_profile.profile_id,
                resolved_inputs=resolved_inputs,
            ),
        ]
    )
    missing_defaults = _dedupe_strings(
        [
            *_compat_missing_defaults(strategy=strategy, resolved_inputs=resolved_inputs),
            *_s3_15_missing_defaults(
                profile_id=selected_profile.profile_id,
                resolved_inputs=resolved_inputs,
                explicit_inputs=explicit_inputs,
            ),
        ]
    )
    return _family_selection_resolution(
        action_type=action_type,
        strategy=strategy,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
        outcome=outcome,
        resolved_inputs=resolved_inputs,
        missing_inputs=missing_inputs,
        missing_defaults=missing_defaults,
        persisted_strategy_inputs=_s3_15_persisted_inputs(
            resolved_inputs=resolved_inputs,
            explicit_inputs=explicit_inputs,
        ),
    )


def _resolve_cloudtrail_family_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    profile = _profile_or_error(action_type, strategy["strategy_id"], requested_profile_id)
    resolved_inputs = _cloudtrail_resolved_inputs(
        strategy=strategy,
        profile=profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    blocked_reasons = _cloudtrail_blocked_reasons(resolved_inputs, runtime_signals=runtime_signals)
    return _family_selection_resolution(
        action_type=action_type,
        strategy=strategy,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
        outcome={
            "profile_id": profile.profile_id,
            "support_tier": "review_required_bundle" if blocked_reasons else "deterministic_bundle",
            "blocked_reasons": blocked_reasons,
            "preservation_summary": _cloudtrail_preservation_summary(
                resolved_inputs=resolved_inputs,
                runtime_signals=runtime_signals,
            ),
            "decision_rationale": _family_rationale(
                strategy_id=strategy["strategy_id"],
                profile_id=profile.profile_id,
                blocked_reasons=blocked_reasons,
            ),
        },
        resolved_inputs=resolved_inputs,
        missing_defaults=_cloudtrail_missing_defaults(resolved_inputs),
        persisted_strategy_inputs=_cloudtrail_persisted_inputs(
            resolved_inputs=resolved_inputs,
            explicit_inputs=explicit_inputs,
        ),
    )


def _resolve_config_family_selection(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> ProfileSelectionResolution:
    if strategy.get("exception_only"):
        return _resolve_compatibility_selection(
            action_type=action_type,
            strategy=strategy,
            requested_profile_id=requested_profile_id,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    profile = _profile_or_error(action_type, strategy["strategy_id"], requested_profile_id)
    resolved_inputs = _config_resolved_inputs(
        strategy=strategy,
        profile=profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )
    blocked_reasons = _config_blocked_reasons(
        strategy_id=strategy["strategy_id"],
        resolved_inputs=resolved_inputs,
        runtime_signals=runtime_signals,
    )
    return _family_selection_resolution(
        action_type=action_type,
        strategy=strategy,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
        outcome={
            "profile_id": profile.profile_id,
            "support_tier": "review_required_bundle" if blocked_reasons else "deterministic_bundle",
            "blocked_reasons": blocked_reasons,
            "preservation_summary": _config_preservation_summary(
                strategy_id=strategy["strategy_id"],
                resolved_inputs=resolved_inputs,
                runtime_signals=runtime_signals,
            ),
            "decision_rationale": _config_rationale(
                strategy_id=strategy["strategy_id"],
                profile_id=profile.profile_id,
                tenant_settings=tenant_settings,
                blocked_reasons=blocked_reasons,
            ),
        },
        resolved_inputs=resolved_inputs,
        missing_defaults=_config_missing_defaults(
            strategy_id=strategy["strategy_id"],
            resolved_inputs=resolved_inputs,
        ),
        persisted_strategy_inputs=_config_persisted_inputs(
            resolved_inputs=resolved_inputs,
            explicit_inputs=explicit_inputs,
        ),
    )


def _family_selection_resolution(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
    outcome: Mapping[str, Any],
    resolved_inputs: Mapping[str, Any] | None = None,
    missing_inputs: list[str] | None = None,
    missing_defaults: list[str] | None = None,
    persisted_strategy_inputs: Mapping[str, Any] | None = None,
) -> ProfileSelectionResolution:
    profile = _profile_or_error(action_type, strategy["strategy_id"], str(outcome["profile_id"]))
    resolved_values = dict(resolved_inputs or {})
    if not resolved_values:
        resolved_values = _resolved_inputs(
            strategy=strategy,
            profile=profile,
            explicit_inputs=explicit_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    return ProfileSelectionResolution(
        profile=profile,
        support_tier=outcome["support_tier"],
        resolved_inputs=resolved_values,
        persisted_strategy_inputs=copy.deepcopy(
            dict(persisted_strategy_inputs if persisted_strategy_inputs is not None else (explicit_inputs or {}))
        ),
        missing_inputs=list(
            missing_inputs if missing_inputs is not None else _required_missing_inputs(strategy, resolved_values)
        ),
        missing_defaults=list(
            missing_defaults if missing_defaults is not None else _compat_missing_defaults(
                strategy=strategy,
                resolved_inputs=resolved_values,
            )
        ),
        blocked_reasons=list(outcome.get("blocked_reasons") or []),
        rejected_profiles=list(outcome.get("rejected_profiles") or []),
        preservation_summary=copy.deepcopy(dict(outcome.get("preservation_summary") or {})),
        decision_rationale=str(outcome.get("decision_rationale") or ""),
    )


def _profile_or_error(
    action_type: str | None,
    strategy_id: str,
    requested_profile_id: str | None,
) -> RemediationProfileDefinition:
    profile_id = _clean_text(requested_profile_id) or default_profile_id_for_strategy(action_type, strategy_id)
    profile = get_profile_definition(action_type, strategy_id, profile_id)
    if profile is None:
        raise ValueError(f"profile_id '{profile_id}' is not valid for strategy_id '{strategy_id}'.")
    return profile


def _resolved_inputs(
    *,
    strategy: RemediationStrategy,
    profile: RemediationProfileDefinition,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> dict[str, Any]:
    values = _schema_defaults(strategy, action=action)
    values.update(_runtime_default_inputs(strategy["strategy_id"], profile.profile_id, runtime_signals))
    values.update(_tenant_default_inputs(strategy["strategy_id"], profile.profile_id, tenant_settings))
    values.update(dict(explicit_inputs or {}))
    values.update(dict(profile.default_inputs))
    return {key: value for key, value in values.items() if _present(value)}


def _cloudtrail_resolved_inputs(
    *,
    strategy: RemediationStrategy,
    profile: RemediationProfileDefinition,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> dict[str, Any]:
    return _resolved_inputs(
        strategy=strategy,
        profile=profile,
        explicit_inputs=explicit_inputs,
        tenant_settings=tenant_settings,
        runtime_signals=runtime_signals,
        action=action,
    )


def _config_resolved_inputs(
    *,
    strategy: RemediationStrategy,
    profile: RemediationProfileDefinition,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Action | None,
) -> dict[str, Any]:
    values = _schema_defaults_without_keys(strategy, action=action, ignored_keys={"delivery_bucket"})
    values.update(_runtime_default_inputs(strategy["strategy_id"], profile.profile_id, runtime_signals))
    values.update(_tenant_default_inputs(strategy["strategy_id"], profile.profile_id, tenant_settings))
    values.update(dict(explicit_inputs or {}))
    values.update(dict(profile.default_inputs))
    if strategy["strategy_id"] == "config_enable_account_local_delivery":
        values.setdefault("delivery_bucket_mode", "create_new")
    elif strategy["strategy_id"] == "config_enable_centralized_delivery":
        values.setdefault("delivery_bucket_mode", "use_existing")
    if "encrypt_with_kms" not in dict(explicit_inputs or {}) and _present(values.get("kms_key_arn")):
        values["encrypt_with_kms"] = True
    return {key: value for key, value in values.items() if _present(value)}


def _schema_defaults(strategy: RemediationStrategy, *, action: Action | None) -> dict[str, Any]:
    return _schema_defaults_without_keys(strategy, action=action, ignored_keys=set())


def _schema_defaults_without_keys(
    strategy: RemediationStrategy,
    *,
    action: Action | None,
    ignored_keys: set[str],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in strategy["input_schema"].get("fields", []):
        if field["key"] in ignored_keys:
            continue
        default_value = _render_field_default(field, action=action)
        if default_value is not _MISSING:
            values[field["key"]] = default_value
    return values


def _render_field_default(field: StrategyInputField, *, action: Action | None) -> Any:
    if "default_value" in field:
        return copy.deepcopy(field["default_value"])
    if "safe_default_value" not in field:
        return _MISSING
    return _render_safe_default(field["safe_default_value"], action=action)


def _runtime_default_inputs(
    strategy_id: str,
    profile_id: str,
    runtime_signals: Mapping[str, Any] | None,
) -> dict[str, Any]:
    runtime_context = _runtime_context(runtime_signals)
    default_inputs = _mapping_value(runtime_context, "default_inputs")
    values = dict(default_inputs) if isinstance(default_inputs, Mapping) else {}
    if strategy_id != _EC2_53_STRATEGY_ID or profile_id != "restrict_to_ip":
        return values
    detected_cidr = _clean_text(values.get("detected_public_ipv4_cidr"))
    if detected_cidr:
        values.setdefault("allowed_cidr", detected_cidr)
    return values


def _runtime_context(runtime_signals: Mapping[str, Any] | None) -> dict[str, Any]:
    context = _mapping_value(runtime_signals, "context")
    if not isinstance(context, Mapping):
        return {}
    return dict(context)


def _tenant_default_inputs(
    strategy_id: str,
    profile_id: str,
    tenant_settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_settings = normalize_remediation_settings(tenant_settings)
    if strategy_id == _EC2_53_STRATEGY_ID:
        return _ec2_53_tenant_inputs(profile_id, normalized_settings)
    if strategy_id.startswith("config_"):
        return _config_tenant_inputs(strategy_id, normalized_settings)
    values: dict[str, Any] = {}
    for input_key, settings_path in _TENANT_DEFAULT_INPUT_PATHS.get(strategy_id, ()):
        raw_value = _settings_value(normalized_settings, settings_path)
        translated = _translate_setting_value(strategy_id, input_key, raw_value)
        if _present(translated):
            values[input_key] = translated
    return values


def _ec2_53_tenant_inputs(profile_id: str, tenant_settings: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    approved_cidrs = list(tenant_settings.get("approved_admin_cidrs") or [])
    bastion_ids = list(tenant_settings.get("approved_bastion_security_group_ids") or [])
    if profile_id == "restrict_to_cidr" and len(approved_cidrs) == 1:
        values["allowed_cidr"] = approved_cidrs[0]
    if profile_id == "bastion_sg_reference" and bastion_ids:
        values["approved_bastion_security_group_ids"] = bastion_ids
    return values


def _config_tenant_inputs(strategy_id: str, tenant_settings: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    delivery_mode = _clean_text(_settings_value(tenant_settings, "config.delivery_mode"))
    if strategy_id == "config_enable_account_local_delivery" and delivery_mode == "account_local_delivery":
        values["delivery_bucket_mode"] = "create_new"
    if strategy_id == "config_enable_centralized_delivery" and delivery_mode == "centralized_delivery":
        values["delivery_bucket_mode"] = "use_existing"
    for input_key, settings_path in _TENANT_DEFAULT_INPUT_PATHS.get(strategy_id, ()):
        raw_value = _settings_value(tenant_settings, settings_path)
        translated = _translate_setting_value(strategy_id, input_key, raw_value)
        if _present(translated):
            values[input_key] = translated
    if strategy_id == "config_enable_centralized_delivery" and _present(values.get("delivery_bucket")):
        values.setdefault("existing_bucket_name", values["delivery_bucket"])
    return values


def _compat_missing_defaults(
    *,
    strategy: RemediationStrategy,
    resolved_inputs: Mapping[str, Any],
) -> list[str]:
    missing: list[str] = []
    for input_key, settings_path in _TENANT_DEFAULT_INPUT_PATHS.get(strategy["strategy_id"], ()):
        if _present(resolved_inputs.get(input_key)) or not _field_required(strategy, input_key):
            continue
        missing.append(settings_path)
    return missing


def _required_missing_inputs(strategy: RemediationStrategy, resolved_inputs: Mapping[str, Any]) -> list[str]:
    return [
        field["key"]
        for field in strategy["input_schema"].get("fields", [])
        if field["required"] and not _present(resolved_inputs.get(field["key"]))
    ]


def _ec2_53_missing_inputs(profile_id: str, resolved_inputs: Mapping[str, Any]) -> list[str]:
    if profile_id in {"restrict_to_ip", "restrict_to_cidr"} and not _present(resolved_inputs.get("allowed_cidr")):
        return ["allowed_cidr"]
    return []


def _ec2_53_missing_defaults(
    profile_id: str,
    explicit_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
) -> list[str]:
    if profile_id == "restrict_to_cidr" and _present(_mapping_value(explicit_inputs, "allowed_cidr")):
        return []
    normalized_settings = normalize_remediation_settings(tenant_settings)
    approved_cidrs = list(normalized_settings.get("approved_admin_cidrs") or [])
    if profile_id == "restrict_to_cidr" and len(approved_cidrs) != 1:
        return ["approved_admin_cidrs"]
    if profile_id == "bastion_sg_reference" and not normalized_settings.get("approved_bastion_security_group_ids"):
        return ["approved_bastion_security_group_ids"]
    return []


def _ec2_53_blocked_reasons(
    profile_id: str,
    missing_inputs: list[str],
    tenant_settings: Mapping[str, Any] | None,
) -> list[str]:
    normalized_settings = normalize_remediation_settings(tenant_settings)
    if profile_id == "restrict_to_ip" and missing_inputs:
        return ["Detected public IP evidence is unavailable; explicit allowed_cidr is required."]
    if profile_id == "restrict_to_cidr" and missing_inputs:
        approved_cidrs = list(normalized_settings.get("approved_admin_cidrs") or [])
        if len(approved_cidrs) > 1:
            return ["Multiple approved admin CIDRs are configured; explicit allowed_cidr is required."]
        return ["No approved admin CIDRs are configured; explicit allowed_cidr is required."]
    if profile_id == "ssm_only":
        return ["Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented."]
    if profile_id == "bastion_sg_reference":
        reasons = [
            "Wave 6 downgrades 'bastion_sg_reference' because SG-reference execution is not implemented."
        ]
        if not normalized_settings.get("approved_bastion_security_group_ids"):
            reasons.append("No approved bastion security group IDs are configured.")
        return reasons
    return []


def _ec2_53_support_tier(
    profile_id: str,
    blocked_reasons: list[str],
    tenant_settings: Mapping[str, Any] | None,
) -> SupportTier:
    if profile_id in {"close_public", "close_and_revoke"}:
        return "deterministic_bundle"
    if profile_id in {"restrict_to_ip", "restrict_to_cidr"}:
        return "review_required_bundle" if blocked_reasons else "deterministic_bundle"
    if profile_id == "bastion_sg_reference":
        settings = normalize_remediation_settings(tenant_settings)
        return "review_required_bundle" if settings.get("approved_bastion_security_group_ids") else "manual_guidance_only"
    return "manual_guidance_only"


def _ec2_53_persisted_inputs(
    profile_id: str,
    resolved_inputs: Mapping[str, Any],
    explicit_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if profile_id not in _EC2_53_ACCESS_MODES:
        return {}
    values = copy.deepcopy(dict(explicit_inputs or {}))
    values["access_mode"] = str(resolved_inputs.get("access_mode") or profile_id)
    if _present(resolved_inputs.get("allowed_cidr")):
        values["allowed_cidr"] = resolved_inputs["allowed_cidr"]
    if _present(resolved_inputs.get("allowed_cidr_ipv6")):
        values["allowed_cidr_ipv6"] = resolved_inputs["allowed_cidr_ipv6"]
    return values


def _cloudtrail_missing_defaults(resolved_inputs: Mapping[str, Any]) -> list[str]:
    if _present(resolved_inputs.get("trail_bucket_name")):
        return []
    return ["cloudtrail.default_bucket_name"]


def _cloudtrail_blocked_reasons(
    resolved_inputs: Mapping[str, Any],
    *,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    if not _present(resolved_inputs.get("trail_bucket_name")):
        reasons.append(
            "CloudTrail log bucket name is unresolved. Configure cloudtrail.default_bucket_name or provide strategy_inputs.trail_bucket_name."
        )
    if runtime_signals and resolved_inputs.get("trail_bucket_name"):
        if runtime_signals.get("cloudtrail_log_bucket_reachable") is False:
            reasons.append(
                str(runtime_signals.get("cloudtrail_log_bucket_error") or "CloudTrail log bucket could not be verified from this account context.")
            )
        elif runtime_signals.get("cloudtrail_log_bucket_reachable") is not True:
            reasons.append("CloudTrail log bucket reachability has not been proven from this account context.")
    if resolved_inputs.get("create_bucket_policy") is False:
        reasons.append(
            "CloudTrail bundle is review-only when create_bucket_policy=false because required delivery policy is managed outside the bundle."
        )
    if resolved_inputs.get("multi_region") is False:
        reasons.append("CloudTrail.1 multi-region coverage is under-proven when multi_region=false.")
    if _present(resolved_inputs.get("kms_key_arn")):
        reasons.append("CloudTrail KMS-encrypted delivery is review-only until KMS dependency proof is implemented.")
    return _dedupe_strings(reasons)


def _cloudtrail_preservation_summary(
    *,
    resolved_inputs: Mapping[str, Any],
    runtime_signals: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "trail_bucket_name_resolved": _present(resolved_inputs.get("trail_bucket_name")),
        "log_bucket_reachable": bool(runtime_signals and runtime_signals.get("cloudtrail_log_bucket_reachable") is True),
        "kms_delivery_requested": _present(resolved_inputs.get("kms_key_arn")),
        "external_bucket_policy_management": resolved_inputs.get("create_bucket_policy") is False,
        "multi_region_requested": resolved_inputs.get("multi_region") is not False,
    }


def _cloudtrail_persisted_inputs(
    *,
    resolved_inputs: Mapping[str, Any],
    explicit_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    values = copy.deepcopy(dict(explicit_inputs or {}))
    for key in ("trail_name", "trail_bucket_name", "kms_key_arn", "create_bucket_policy", "multi_region"):
        if _present(resolved_inputs.get(key)):
            values[key] = resolved_inputs[key]
    return values


def _config_missing_defaults(
    *,
    strategy_id: str,
    resolved_inputs: Mapping[str, Any],
) -> list[str]:
    if strategy_id != "config_enable_centralized_delivery":
        return []
    if _present(resolved_inputs.get("delivery_bucket")) or _present(resolved_inputs.get("existing_bucket_name")):
        return []
    return ["config.default_bucket_name"]


def _config_blocked_reasons(
    *,
    strategy_id: str,
    resolved_inputs: Mapping[str, Any],
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    if strategy_id == "config_enable_account_local_delivery":
        return _config_local_blocked_reasons(resolved_inputs, runtime_signals=runtime_signals)
    return _config_centralized_blocked_reasons(resolved_inputs, runtime_signals=runtime_signals)


def _config_local_blocked_reasons(
    resolved_inputs: Mapping[str, Any],
    *,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    if resolved_inputs.get("delivery_bucket_mode") == "use_existing":
        reasons.extend(_config_existing_bucket_reasons(runtime_signals))
    reasons.extend(_config_kms_reasons(resolved_inputs, runtime_signals=runtime_signals))
    return _dedupe_strings(reasons)


def _config_centralized_blocked_reasons(
    resolved_inputs: Mapping[str, Any],
    *,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    if not (_present(resolved_inputs.get("delivery_bucket")) or _present(resolved_inputs.get("existing_bucket_name"))):
        reasons.append(
            "Centralized AWS Config delivery bucket is unresolved. Configure config.default_bucket_name or provide strategy_inputs.delivery_bucket."
        )
    reasons.extend(_config_existing_bucket_reasons(runtime_signals))
    reasons.extend(_config_kms_reasons(resolved_inputs, runtime_signals=runtime_signals))
    return _dedupe_strings(reasons)


def _config_existing_bucket_reasons(runtime_signals: Mapping[str, Any] | None) -> list[str]:
    if not runtime_signals:
        return ["AWS Config delivery bucket dependencies have not been proven from this account context."]
    reasons: list[str] = []
    if runtime_signals.get("config_delivery_bucket_reachable") is False:
        reasons.append(
            str(runtime_signals.get("config_delivery_bucket_error") or "Configured delivery bucket is unreachable from this account context.")
        )
    elif runtime_signals.get("config_delivery_bucket_reachable") is not True:
        reasons.append("AWS Config delivery bucket reachability has not been proven from this account context.")
    if runtime_signals.get("config_central_bucket_policy_valid") is False:
        reasons.append(
            str(runtime_signals.get("config_central_bucket_policy_error") or "Centralized delivery bucket policy is not proven for this account context.")
        )
    elif runtime_signals.get("config_central_bucket_policy_valid") is not True:
        reasons.append("AWS Config delivery bucket policy compatibility has not been proven from this account context.")
    return reasons


def _config_kms_reasons(
    resolved_inputs: Mapping[str, Any],
    *,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    if not _present(resolved_inputs.get("kms_key_arn")):
        return []
    if not runtime_signals:
        return ["AWS Config delivery KMS dependency proof is under-specified."]
    if runtime_signals.get("config_kms_policy_valid") is True:
        return []
    return [
        str(runtime_signals.get("config_kms_policy_error") or "AWS Config delivery KMS dependency proof is under-specified.")
    ]


def _config_preservation_summary(
    *,
    strategy_id: str,
    resolved_inputs: Mapping[str, Any],
    runtime_signals: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "delivery_mode": "centralized_delivery"
        if strategy_id == "config_enable_centralized_delivery"
        else "account_local_delivery",
        "existing_bucket_path": resolved_inputs.get("delivery_bucket_mode") == "use_existing",
        "delivery_bucket_resolved": _present(resolved_inputs.get("delivery_bucket"))
        or _present(resolved_inputs.get("existing_bucket_name")),
        "delivery_bucket_reachable": bool(runtime_signals and runtime_signals.get("config_delivery_bucket_reachable") is True),
        "delivery_policy_proven": bool(runtime_signals and runtime_signals.get("config_central_bucket_policy_valid") is True),
        "kms_delivery_requested": _present(resolved_inputs.get("kms_key_arn")),
    }


def _config_persisted_inputs(
    *,
    resolved_inputs: Mapping[str, Any],
    explicit_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    values = copy.deepcopy(dict(explicit_inputs or {}))
    for key in (
        "recording_scope",
        "delivery_bucket_mode",
        "existing_bucket_name",
        "delivery_bucket",
        "encrypt_with_kms",
        "kms_key_arn",
    ):
        if _present(resolved_inputs.get(key)):
            values[key] = resolved_inputs[key]
    return values


def _s3_9_persisted_inputs(
    *,
    resolved_inputs: Mapping[str, Any],
    explicit_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    values = copy.deepcopy(dict(explicit_inputs or {}))
    if _present(resolved_inputs.get("log_bucket_name")):
        values["log_bucket_name"] = resolved_inputs["log_bucket_name"]
    return values


def _s3_15_missing_inputs(
    *,
    profile_id: str,
    resolved_inputs: Mapping[str, Any],
) -> list[str]:
    key_mode = resolve_s3_kms_key_mode(resolved_inputs)
    if profile_id != S3_15_CUSTOMER_MANAGED_PROFILE_ID and key_mode != "custom":
        return []
    if _present(resolved_inputs.get("kms_key_arn")):
        return []
    return ["kms_key_arn"]


def _s3_15_missing_defaults(
    *,
    profile_id: str,
    resolved_inputs: Mapping[str, Any],
    explicit_inputs: Mapping[str, Any] | None,
) -> list[str]:
    key_mode = resolve_s3_kms_key_mode(resolved_inputs)
    if profile_id != S3_15_CUSTOMER_MANAGED_PROFILE_ID and key_mode != "custom":
        return []
    if _present(_mapping_value(explicit_inputs, "kms_key_arn")) or _present(resolved_inputs.get("kms_key_arn")):
        return []
    return ["s3_encryption.kms_key_arn"]


def _s3_15_persisted_inputs(
    *,
    resolved_inputs: Mapping[str, Any],
    explicit_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    values = copy.deepcopy(dict(explicit_inputs or {}))
    key_mode = resolve_s3_kms_key_mode(resolved_inputs)
    if key_mode == "custom" or _present(values.get("kms_key_mode")):
        values["kms_key_mode"] = key_mode
    if key_mode == "custom" and _present(resolved_inputs.get("kms_key_arn")):
        values["kms_key_arn"] = resolved_inputs["kms_key_arn"]
    return values


def _family_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    blocked_reasons: list[str],
) -> str:
    if not blocked_reasons:
        return f"Family resolver kept compatibility profile '{profile_id}' executable for strategy '{strategy_id}'."
    return (
        f"Family resolver kept compatibility profile '{profile_id}' for strategy '{strategy_id}' "
        f"but downgraded executability. {' '.join(blocked_reasons)}"
    )


def _config_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    tenant_settings: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> str:
    preferred_mode = _clean_text(_settings_value(tenant_settings, "config.delivery_mode"))
    prefix = _family_rationale(
        strategy_id=strategy_id,
        profile_id=profile_id,
        blocked_reasons=blocked_reasons,
    )
    if not preferred_mode:
        return prefix
    return f"{prefix} Tenant config.delivery_mode preference is '{preferred_mode}'."


def _compatibility_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    explicit_profile: bool,
    missing_defaults: list[str],
) -> str:
    selection = "preserved the explicit profile" if explicit_profile else "defaulted to the compatible profile"
    if not missing_defaults:
        return f"Compatibility resolver {selection} '{profile_id}' for strategy '{strategy_id}'."
    defaults = ", ".join(missing_defaults)
    return (
        f"Compatibility resolver {selection} '{profile_id}' for strategy '{strategy_id}'. "
        f"Missing tenant defaults: {defaults}."
    )


def _ec2_53_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    selection_source: str,
    blocked_reasons: list[str],
) -> str:
    source_text = {
        "explicit_profile": "preserved the explicit profile",
        "explicit_inputs": "matched the explicit legacy access_mode",
        "tenant_preference": "matched the tenant access-path preference",
        "safe_default": "used the compatibility-safe default",
    }.get(selection_source, "selected")
    if not blocked_reasons:
        return f"Family resolver {source_text} '{profile_id}' for strategy '{strategy_id}'."
    return (
        f"Family resolver {source_text} '{profile_id}' for strategy '{strategy_id}'. "
        f"Downgrade reasons: {' '.join(blocked_reasons)}"
    )


def _preferred_profile_for_sg_access_path(preference: str | None) -> str | None:
    mapping = {
        "close_public": "close_public",
        "restrict_to_detected_public_ip": "restrict_to_ip",
        "restrict_to_approved_admin_cidr": "restrict_to_cidr",
        "bastion_sg_reference": "bastion_sg_reference",
        "ssm_only": "ssm_only",
    }
    return mapping.get(preference or "")


def _field_required(strategy: RemediationStrategy, input_key: str) -> bool:
    for field in strategy["input_schema"].get("fields", []):
        if field["key"] == input_key:
            return bool(field["required"])
    return False


def _translate_setting_value(strategy_id: str, input_key: str, value: Any) -> Any:
    if strategy_id != "s3_enable_sse_kms_guided" or input_key != "kms_key_mode":
        return value
    if value == "customer_managed":
        return "custom"
    return value


def _render_safe_default(value: Any, *, action: Action | None) -> Any:
    if not isinstance(value, str):
        return copy.deepcopy(value)
    if "{{" not in value:
        return value
    if action is None:
        return _MISSING
    try:
        return _SAFE_DEFAULT_TOKEN_PATTERN.sub(lambda match: _safe_default_token(action, match.group(1)), value)
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


def _settings_value(tenant_settings: Mapping[str, Any] | None, settings_path: str) -> Any:
    current: Any = normalize_remediation_settings(tenant_settings)
    for segment in settings_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(segment)
    return current


def _mapping_value(mapping: Mapping[str, Any] | None, key: str) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    return mapping.get(key)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


_MISSING = object()


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


__all__ = ["ProfileSelectionResolution", "resolve_profile_selection", "resolve_runtime_probe_inputs"]
