"""Resolver-side S3 family downgrade and preservation helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping, TypedDict

from backend.services.remediation_profile_resolver import ResolverRejectedProfile, SupportTier

S3_2_FAMILY_RESOLVER_KIND = "s3_2_public_access_family"
S3_5_FAMILY_RESOLVER_KIND = "s3_5_policy_preservation_family"
S3_11_FAMILY_RESOLVER_KIND = "s3_11_lifecycle_preservation_family"

S3_2_STANDARD_STRATEGY_ID = "s3_bucket_block_public_access_standard"
S3_2_STANDARD_MANUAL_PROFILE_ID = "s3_bucket_block_public_access_manual_preservation"
S3_2_OAC_STRATEGY_ID = "s3_migrate_cloudfront_oac_private"
S3_2_OAC_MANUAL_PROFILE_ID = "s3_migrate_cloudfront_oac_private_manual_preservation"

S3_5_STRICT_STRATEGY_ID = "s3_enforce_ssl_strict_deny"
S3_5_EXEMPTION_STRATEGY_ID = "s3_enforce_ssl_with_principal_exemptions"
S3_11_STRATEGY_ID = "s3_enable_abort_incomplete_uploads"


class FamilySelectionOutcome(TypedDict):
    """Canonical family-specific selection result."""

    profile_id: str
    support_tier: SupportTier
    blocked_reasons: list[str]
    rejected_profiles: list[ResolverRejectedProfile]
    preservation_summary: dict[str, Any]
    decision_rationale: str


def resolve_s3_2_selection(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    runtime_signals: Mapping[str, Any] | None,
) -> FamilySelectionOutcome:
    explicit_profile = _clean_text(requested_profile_id)
    blocked_reasons = _s3_2_blocked_reasons(strategy_id=strategy_id, runtime_signals=runtime_signals)
    fallback_profile_id = _s3_2_fallback_profile_id(strategy_id)
    profile_id = explicit_profile or _automatic_s3_2_profile_id(strategy_id, blocked_reasons)
    rejected_profiles = _automatic_rejected_profile(
        explicit_profile=explicit_profile,
        fallback_profile_id=fallback_profile_id,
        strategy_id=strategy_id,
        blocked_reasons=blocked_reasons,
    )
    return {
        "profile_id": profile_id,
        "support_tier": _s3_2_support_tier(
            strategy_id=strategy_id,
            profile_id=profile_id,
            blocked_reasons=blocked_reasons,
        ),
        "blocked_reasons": blocked_reasons,
        "rejected_profiles": rejected_profiles,
        "preservation_summary": _s3_2_preservation_summary(
            strategy_id=strategy_id,
            profile_id=profile_id,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_2_rationale(
            strategy_id=strategy_id,
            profile_id=profile_id,
            explicit_profile=explicit_profile,
            blocked_reasons=blocked_reasons,
        ),
    }


def resolve_s3_5_selection(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
) -> FamilySelectionOutcome:
    profile_id = _clean_text(requested_profile_id) or strategy_id
    preserve_existing_policy = _coerce_bool(
        _mapping_value(explicit_inputs, "preserve_existing_policy"),
        default=True,
    )
    blocked_reasons = _s3_5_blocked_reasons(
        preserve_existing_policy=preserve_existing_policy,
        runtime_signals=runtime_signals,
    )
    return {
        "profile_id": profile_id,
        "support_tier": _s3_5_support_tier(
            preserve_existing_policy=preserve_existing_policy,
            blocked_reasons=blocked_reasons,
        ),
        "blocked_reasons": blocked_reasons,
        "rejected_profiles": [],
        "preservation_summary": _s3_5_preservation_summary(
            strategy_id=strategy_id,
            preserve_existing_policy=preserve_existing_policy,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_5_rationale(
            strategy_id=strategy_id,
            preserve_existing_policy=preserve_existing_policy,
            blocked_reasons=blocked_reasons,
        ),
    }


def resolve_s3_11_selection(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
) -> FamilySelectionOutcome:
    profile_id = _clean_text(requested_profile_id) or strategy_id
    abort_days = _abort_days(explicit_inputs)
    blocked_reasons = _s3_11_blocked_reasons(
        abort_days=abort_days,
        runtime_signals=runtime_signals,
    )
    return {
        "profile_id": profile_id,
        "support_tier": _s3_11_support_tier(blocked_reasons=blocked_reasons, runtime_signals=runtime_signals),
        "blocked_reasons": blocked_reasons,
        "rejected_profiles": [],
        "preservation_summary": _s3_11_preservation_summary(
            strategy_id=strategy_id,
            abort_days=abort_days,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_11_rationale(
            strategy_id=strategy_id,
            abort_days=abort_days,
            blocked_reasons=blocked_reasons,
        ),
    }


def _automatic_rejected_profile(
    *,
    explicit_profile: str | None,
    fallback_profile_id: str,
    strategy_id: str,
    blocked_reasons: list[str],
) -> list[ResolverRejectedProfile]:
    if explicit_profile is not None or not blocked_reasons:
        return []
    detail = blocked_reasons[0]
    if fallback_profile_id == strategy_id:
        return []
    return [{"profile_id": strategy_id, "reason": "branch_unavailable", "detail": detail}]


def _automatic_s3_2_profile_id(strategy_id: str, blocked_reasons: list[str]) -> str:
    if not blocked_reasons:
        return strategy_id
    return _s3_2_fallback_profile_id(strategy_id)


def _s3_2_fallback_profile_id(strategy_id: str) -> str:
    if strategy_id == S3_2_STANDARD_STRATEGY_ID:
        return S3_2_STANDARD_MANUAL_PROFILE_ID
    return S3_2_OAC_MANUAL_PROFILE_ID


def _s3_2_support_tier(
    *,
    strategy_id: str,
    profile_id: str,
    blocked_reasons: list[str],
) -> SupportTier:
    if profile_id in {
        S3_2_STANDARD_MANUAL_PROFILE_ID,
        S3_2_OAC_MANUAL_PROFILE_ID,
    }:
        return "manual_guidance_only"
    if strategy_id != profile_id or blocked_reasons:
        return "manual_guidance_only"
    return "deterministic_bundle"


def _s3_2_blocked_reasons(
    *,
    strategy_id: str,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    if strategy_id == S3_2_STANDARD_STRATEGY_ID:
        return _s3_2_standard_blocked_reasons(runtime_signals)
    return _s3_2_oac_blocked_reasons(runtime_signals)


def _s3_2_standard_blocked_reasons(
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    policy_public = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_policy_public"))
    website_configured = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_website_configured"))
    reasons: list[str] = []
    if website_configured is True:
        reasons.append(
            "Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."
        )
    if policy_public is True:
        reasons.append(
            "Bucket policy is currently public; direct public-access preservation must be reviewed manually."
        )
    if not reasons and (policy_public is not False or website_configured is not False):
        reasons.append("Runtime evidence could not prove the bucket is private and website hosting is disabled.")
    return _append_access_path_reason(reasons, runtime_signals)


def _s3_2_oac_blocked_reasons(
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    evidence = _evidence(runtime_signals)
    statement_count = _coerce_int(evidence.get("existing_bucket_policy_statement_count"))
    policy_json_captured = _clean_text(evidence.get("existing_bucket_policy_json")) is not None
    reasons: list[str] = []
    capture_error = _clean_text(evidence.get("existing_bucket_policy_capture_error"))
    parse_error = _clean_text(evidence.get("existing_bucket_policy_parse_error"))
    if capture_error is not None:
        reasons.append(
            f"Existing bucket policy capture failed ({capture_error}); CloudFront + OAC preservation must be reviewed manually."
        )
    if parse_error is not None:
        reasons.append(
            "Existing bucket policy could not be parsed for preservation; CloudFront + OAC migration is manual-only."
        )
    if statement_count is None and not policy_json_captured:
        reasons.append(
            "Existing bucket policy preservation evidence is missing for CloudFront + OAC migration."
        )
    if statement_count not in (None, 0) and not policy_json_captured:
        reasons.append(
            "Existing bucket policy statements were detected, but their JSON was not captured for safe preservation."
        )
    return _append_access_path_reason(reasons, runtime_signals)


def _append_access_path_reason(
    reasons: list[str],
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    if _mapping_value(runtime_signals, "access_path_evidence_available") is False:
        reasons.append(
            str(
                _mapping_value(runtime_signals, "access_path_evidence_reason")
                or "Required access-path evidence is unavailable."
            ).strip()
        )
    return _dedupe_strings(reasons)


def _s3_2_preservation_summary(
    *,
    strategy_id: str,
    profile_id: str,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    evidence = _evidence(runtime_signals)
    return {
        "family": "s3_bucket_block_public_access",
        "selected_branch": profile_id,
        "bucket_policy_public": _optional_bool(_mapping_value(runtime_signals, "s3_bucket_policy_public")),
        "website_configured": _optional_bool(_mapping_value(runtime_signals, "s3_bucket_website_configured")),
        "existing_bucket_policy_statement_count": _coerce_int(
            evidence.get("existing_bucket_policy_statement_count")
        ),
        "existing_bucket_policy_json_captured": _clean_text(
            evidence.get("existing_bucket_policy_json")
        )
        is not None,
        "access_path_evidence_available": _optional_bool(
            _mapping_value(runtime_signals, "access_path_evidence_available")
        ),
        "executable_preservation_allowed": not blocked_reasons,
        "manual_preservation_required": bool(blocked_reasons),
        "family_strategy": strategy_id,
    }


def _s3_2_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    explicit_profile: str | None,
    blocked_reasons: list[str],
) -> str:
    if not blocked_reasons and explicit_profile is not None:
        return f"Family resolver preserved explicit S3.2 profile '{profile_id}' for strategy '{strategy_id}'."
    if not blocked_reasons:
        return f"Family resolver kept executable S3.2 profile '{profile_id}' for strategy '{strategy_id}'."
    detail = " ".join(blocked_reasons)
    if explicit_profile is not None:
        return (
            f"Family resolver preserved explicit S3.2 profile '{profile_id}' but downgraded it to non-executable "
            f"guidance. {detail}"
        )
    return (
        f"Family resolver downgraded strategy '{strategy_id}' to manual S3.2 preservation profile '{profile_id}'. "
        f"{detail}"
    )


def _s3_5_blocked_reasons(
    *,
    preserve_existing_policy: bool,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    if not preserve_existing_policy:
        return [
            "Unsafe bucket policy overwrite is not executable in Wave 6; preserve_existing_policy must remain true."
        ]
    evidence = _evidence(runtime_signals)
    statement_count = _coerce_int(evidence.get("existing_bucket_policy_statement_count"))
    policy_json_captured = _clean_text(evidence.get("existing_bucket_policy_json")) is not None
    reasons: list[str] = []
    if _mapping_value(runtime_signals, "s3_policy_analysis_possible") is False:
        reasons.append(
            str(
                _mapping_value(runtime_signals, "s3_policy_analysis_error")
                or "Unable to inspect the current bucket policy for merge-safe SSL enforcement."
            ).strip()
        )
    if statement_count is None and not policy_json_captured:
        reasons.append("Bucket policy preservation evidence is missing for merge-safe SSL enforcement.")
    if statement_count not in (None, 0) and not policy_json_captured:
        reasons.append(
            "Existing bucket policy statements were detected, but their JSON was not captured for safe merge."
        )
    capture_error = _clean_text(evidence.get("existing_bucket_policy_capture_error"))
    parse_error = _clean_text(evidence.get("existing_bucket_policy_parse_error"))
    if capture_error is not None:
        reasons.append(f"Existing bucket policy capture failed ({capture_error}).")
    if parse_error is not None:
        reasons.append("Existing bucket policy could not be parsed for merge-safe preservation.")
    return _dedupe_strings(reasons)


def _s3_5_support_tier(
    *,
    preserve_existing_policy: bool,
    blocked_reasons: list[str],
) -> SupportTier:
    if not blocked_reasons:
        return "deterministic_bundle"
    if not preserve_existing_policy:
        return "manual_guidance_only"
    return "review_required_bundle"


def _s3_5_preservation_summary(
    *,
    strategy_id: str,
    preserve_existing_policy: bool,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    evidence = _evidence(runtime_signals)
    return {
        "family": "s3_bucket_require_ssl",
        "family_strategy": strategy_id,
        "preserve_existing_policy": preserve_existing_policy,
        "bucket_policy_analysis_possible": _optional_bool(
            _mapping_value(runtime_signals, "s3_policy_analysis_possible")
        ),
        "existing_bucket_policy_statement_count": _coerce_int(
            evidence.get("existing_bucket_policy_statement_count")
        ),
        "existing_bucket_policy_json_captured": _clean_text(
            evidence.get("existing_bucket_policy_json")
        )
        is not None,
        "merge_safe_policy_available": not blocked_reasons,
        "unsafe_overwrite_requested": not preserve_existing_policy,
        "executable_policy_merge_allowed": not blocked_reasons,
    }


def _s3_5_rationale(
    *,
    strategy_id: str,
    preserve_existing_policy: bool,
    blocked_reasons: list[str],
) -> str:
    if not blocked_reasons:
        return (
            f"Family resolver kept S3.5 strategy '{strategy_id}' executable because merge-safe policy "
            "preservation evidence is available."
        )
    if not preserve_existing_policy:
        return (
            f"Family resolver downgraded S3.5 strategy '{strategy_id}' because unsafe bucket policy overwrite "
            "must remain non-executable."
        )
    return (
        f"Family resolver downgraded S3.5 strategy '{strategy_id}' because merge-safe bucket policy "
        f"preservation evidence is incomplete. {' '.join(blocked_reasons)}"
    )


def _s3_11_blocked_reasons(
    *,
    abort_days: int,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    evidence = _evidence(runtime_signals)
    analysis_possible = _optional_bool(_mapping_value(runtime_signals, "s3_lifecycle_analysis_possible"))
    rule_count = _coerce_int(evidence.get("existing_lifecycle_rule_count"))
    lifecycle_json = _clean_text(evidence.get("existing_lifecycle_configuration_json"))
    if rule_count == 0:
        return []
    if _s3_11_equivalent_safe_state(lifecycle_json, abort_days=abort_days):
        return []
    reasons: list[str] = []
    if analysis_possible is False:
        reasons.append(
            str(
                _mapping_value(runtime_signals, "s3_lifecycle_analysis_error")
                or "Unable to inspect the current lifecycle configuration."
            ).strip()
        )
    if lifecycle_json is None and rule_count is None:
        reasons.append("Lifecycle preservation evidence is missing for additive merge review.")
    elif lifecycle_json is None and rule_count not in (None, 0):
        reasons.append(
            "Existing lifecycle rules were detected, but the lifecycle document was not captured for additive review."
        )
    elif rule_count not in (None, 0):
        reasons.append(
            "Existing lifecycle rules are present, and additive merge generation is not implemented for this branch."
        )
    return _dedupe_strings(reasons)


def _s3_11_support_tier(
    *,
    blocked_reasons: list[str],
    runtime_signals: Mapping[str, Any] | None,
) -> SupportTier:
    if not blocked_reasons:
        return "deterministic_bundle"
    evidence = _evidence(runtime_signals)
    if _clean_text(evidence.get("existing_lifecycle_configuration_json")) is not None:
        return "review_required_bundle"
    if _coerce_int(evidence.get("existing_lifecycle_rule_count")) not in (None, 0):
        return "review_required_bundle"
    return "manual_guidance_only"


def _s3_11_preservation_summary(
    *,
    strategy_id: str,
    abort_days: int,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    evidence = _evidence(runtime_signals)
    lifecycle_json = _clean_text(evidence.get("existing_lifecycle_configuration_json"))
    return {
        "family": "s3_bucket_lifecycle_configuration",
        "family_strategy": strategy_id,
        "abort_days": abort_days,
        "existing_lifecycle_rule_count": _coerce_int(evidence.get("existing_lifecycle_rule_count")),
        "existing_lifecycle_configuration_captured": lifecycle_json is not None,
        "existing_lifecycle_configuration_equivalent": _s3_11_equivalent_safe_state(
            lifecycle_json,
            abort_days=abort_days,
        ),
        "additive_merge_safe": not blocked_reasons,
        "executable_lifecycle_merge_allowed": not blocked_reasons,
    }


def _s3_11_rationale(
    *,
    strategy_id: str,
    abort_days: int,
    blocked_reasons: list[str],
) -> str:
    if not blocked_reasons:
        return (
            f"Family resolver kept S3.11 strategy '{strategy_id}' executable with abort_days={abort_days} "
            "because lifecycle preservation is already safe."
        )
    return (
        f"Family resolver downgraded S3.11 strategy '{strategy_id}' because additive lifecycle preservation "
        f"is under-proven. {' '.join(blocked_reasons)}"
    )


def _s3_11_equivalent_safe_state(lifecycle_json: str | None, *, abort_days: int) -> bool:
    parsed = _parse_json_object(lifecycle_json)
    if parsed is None:
        return False
    rules = parsed.get("Rules")
    if not isinstance(rules, list) or len(rules) != 1:
        return False
    return _equivalent_abort_rule(rules[0], abort_days=abort_days)


def _equivalent_abort_rule(rule: Any, *, abort_days: int) -> bool:
    if not isinstance(rule, Mapping):
        return False
    if str(rule.get("Status") or "").strip().lower() != "enabled":
        return False
    abort_block = rule.get("AbortIncompleteMultipartUpload")
    if not isinstance(abort_block, Mapping):
        return False
    days_value = _coerce_int(abort_block.get("DaysAfterInitiation"))
    if days_value != abort_days:
        return False
    if rule.get("Expiration") or rule.get("Transitions"):
        return False
    return True


def _abort_days(explicit_inputs: Mapping[str, Any] | None) -> int:
    candidate = _coerce_int(_mapping_value(explicit_inputs, "abort_days"))
    if candidate is None:
        return 7
    return max(1, min(candidate, 365))


def _parse_json_object(raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    try:
        parsed = json.loads(raw_value)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _evidence(runtime_signals: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence = _mapping_value(runtime_signals, "evidence")
    if not isinstance(evidence, Mapping):
        return {}
    return dict(evidence)


def _mapping_value(mapping: Mapping[str, Any] | None, key: str) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    return mapping.get(key)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return default


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if cleaned is not None and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped

