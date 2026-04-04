"""Resolver-side S3 family downgrade and preservation helpers."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, TypedDict

from backend.services.remediation_profile_resolver import ResolverRejectedProfile, SupportTier
from backend.services.s3_lifecycle_preservation import (
    analyze_lifecycle_preservation,
    rule_is_equivalent_abort_incomplete,
)

S3_2_FAMILY_RESOLVER_KIND = "s3_2_public_access_family"
S3_9_FAMILY_RESOLVER_KIND = "s3_9_access_logging_family"
S3_5_FAMILY_RESOLVER_KIND = "s3_5_policy_preservation_family"
S3_11_FAMILY_RESOLVER_KIND = "s3_11_lifecycle_preservation_family"
S3_15_FAMILY_RESOLVER_KIND = "s3_15_kms_family"

S3_2_STANDARD_STRATEGY_ID = "s3_bucket_block_public_access_standard"
S3_2_STANDARD_MANUAL_PROFILE_ID = "s3_bucket_block_public_access_manual_preservation"
S3_2_STANDARD_POLICY_SCRUB_PROFILE_ID = "s3_bucket_block_public_access_review_public_policy_scrub"
S3_2_OAC_STRATEGY_ID = "s3_migrate_cloudfront_oac_private"
S3_2_OAC_MANUAL_PROFILE_ID = "s3_migrate_cloudfront_oac_private_manual_preservation"
S3_2_OAC_CREATE_PROFILE_ID = "s3_migrate_cloudfront_oac_private_create_missing_bucket"
S3_2_WEBSITE_STRATEGY_ID = "s3_migrate_website_cloudfront_private"
S3_2_WEBSITE_REVIEW_PROFILE_ID = "s3_migrate_website_cloudfront_private_review_required"

S3_9_STRATEGY_ID = "s3_enable_access_logging_guided"
S3_9_REVIEW_PROFILE_ID = "s3_enable_access_logging_review_destination_safety"
S3_9_CREATE_PROFILE_ID = "s3_enable_access_logging_create_missing_bucket"

S3_5_STRICT_STRATEGY_ID = "s3_enforce_ssl_strict_deny"
S3_5_EXEMPTION_STRATEGY_ID = "s3_enforce_ssl_with_principal_exemptions"
S3_5_STRICT_CREATE_PROFILE_ID = "s3_enforce_ssl_strict_deny_create_missing_bucket"
S3_5_EXEMPTION_CREATE_PROFILE_ID = "s3_enforce_ssl_with_principal_exemptions_create_missing_bucket"
S3_11_STRATEGY_ID = "s3_enable_abort_incomplete_uploads"
S3_11_CREATE_PROFILE_ID = "s3_enable_abort_incomplete_uploads_create_missing_bucket"
S3_15_STRATEGY_ID = "s3_enable_sse_kms_guided"
S3_15_CUSTOMER_MANAGED_PROFILE_ID = "s3_enable_sse_kms_customer_managed"
S3_15_CREATE_PROFILE_ID = "s3_enable_sse_kms_guided_create_missing_bucket"

_S3_BUCKET_ARN_PATTERN = re.compile(r"arn:aws:s3:::(?P<bucket>[A-Za-z0-9.\-_]{3,63})")
_S3_BUCKET_NAME_PATTERN = re.compile(
    r"^(?!\d{1,3}(?:\.\d{1,3}){3}$)(?!xn--)(?!sthree-)(?!amzn-s3-demo-)[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
)
_S3_ACCESS_LOG_BUCKET_SUFFIX = "-access-logs"


class FamilySelectionOutcome(TypedDict):
    """Canonical family-specific selection result."""

    profile_id: str
    support_tier: SupportTier
    blocked_reasons: list[str]
    rejected_profiles: list[ResolverRejectedProfile]
    preservation_summary: dict[str, Any]
    decision_rationale: str


def resolve_s3_access_logging_source_bucket(action: Any | None) -> str | None:
    return _bucket_name_from_runtime_like_action_fields(action, "target_id", "resource_id")


def derive_s3_access_logging_log_bucket_name(source_bucket: str | None) -> str | None:
    source = _clean_text(source_bucket)
    if source is None:
        return None
    max_source_len = 63 - len(_S3_ACCESS_LOG_BUCKET_SUFFIX)
    candidate_source = source[:max_source_len].rstrip(".-")
    if not candidate_source:
        return None
    candidate = f"{candidate_source}{_S3_ACCESS_LOG_BUCKET_SUFFIX}"
    if _S3_BUCKET_NAME_PATTERN.fullmatch(candidate):
        return candidate
    return None


def default_s3_access_logging_log_bucket_name(action: Any | None) -> str | None:
    return derive_s3_access_logging_log_bucket_name(resolve_s3_access_logging_source_bucket(action))


def resolve_s3_kms_key_mode(values: Mapping[str, Any] | None) -> str:
    raw_mode = _clean_text(_mapping_value(values, "kms_key_mode"))
    if raw_mode == "custom":
        return "custom"
    if _clean_text(_mapping_value(values, "kms_key_arn")) is not None:
        return "custom"
    return "aws_managed"


def resolve_s3_2_selection(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
) -> FamilySelectionOutcome:
    explicit_profile = _clean_text(requested_profile_id)
    initial_blocked_reasons = _s3_2_blocked_reasons(
        strategy_id=strategy_id,
        explicit_inputs=explicit_inputs,
        runtime_signals=runtime_signals,
        requested_profile_id=explicit_profile,
    )
    fallback_profile_id = _s3_2_fallback_profile_id(strategy_id)
    profile_id = explicit_profile or _automatic_s3_2_profile_id(
        strategy_id,
        initial_blocked_reasons,
        runtime_signals,
    )
    blocked_reasons = (
        initial_blocked_reasons
        if explicit_profile is not None or profile_id == strategy_id
        else _s3_2_blocked_reasons(
            strategy_id=strategy_id,
            explicit_inputs=explicit_inputs,
            runtime_signals=runtime_signals,
            requested_profile_id=profile_id,
        )
    )
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
            explicit_inputs=explicit_inputs,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_2_rationale(
            strategy_id=strategy_id,
            profile_id=profile_id,
            explicit_profile=explicit_profile,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
    }


def resolve_s3_9_selection(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    resolved_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Any | None,
) -> FamilySelectionOutcome:
    explicit_profile = _clean_text(requested_profile_id)
    initial_blocked_reasons = _s3_9_blocked_reasons(
        strategy_id=strategy_id,
        requested_profile_id=explicit_profile,
        resolved_inputs=resolved_inputs,
        runtime_signals=runtime_signals,
        action=action,
    )
    profile_id = explicit_profile or _automatic_s3_9_profile_id(initial_blocked_reasons, runtime_signals)
    blocked_reasons = (
        initial_blocked_reasons
        if explicit_profile is not None or profile_id == strategy_id
        else _s3_9_blocked_reasons(
            strategy_id=strategy_id,
            requested_profile_id=profile_id,
            resolved_inputs=resolved_inputs,
            runtime_signals=runtime_signals,
            action=action,
        )
    )
    return {
        "profile_id": profile_id,
        "support_tier": _s3_9_support_tier(profile_id=profile_id, blocked_reasons=blocked_reasons),
        "blocked_reasons": blocked_reasons,
        "rejected_profiles": _automatic_rejected_profile(
            explicit_profile=explicit_profile,
            fallback_profile_id=S3_9_REVIEW_PROFILE_ID,
            strategy_id=strategy_id,
            blocked_reasons=blocked_reasons,
        ),
        "preservation_summary": _s3_9_preservation_summary(
            strategy_id=strategy_id,
            profile_id=profile_id,
            resolved_inputs=resolved_inputs,
            runtime_signals=runtime_signals,
            action=action,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_9_rationale(profile_id=profile_id, blocked_reasons=blocked_reasons),
    }


def resolve_s3_5_selection(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    explicit_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
) -> FamilySelectionOutcome:
    explicit_profile = _clean_text(requested_profile_id)
    profile_id = explicit_profile or _automatic_s3_5_profile_id(strategy_id=strategy_id, runtime_signals=runtime_signals)
    preserve_existing_policy = _coerce_bool(
        _mapping_value(explicit_inputs, "preserve_existing_policy"),
        default=True,
    )
    blocked_reasons = _s3_5_blocked_reasons(
        strategy_id=strategy_id,
        profile_id=profile_id,
        explicit_inputs=explicit_inputs,
        preserve_existing_policy=preserve_existing_policy,
        runtime_signals=runtime_signals,
    )
    return {
        "profile_id": profile_id,
        "support_tier": _s3_5_support_tier(
            strategy_id=strategy_id,
            profile_id=profile_id,
            preserve_existing_policy=preserve_existing_policy,
            blocked_reasons=blocked_reasons,
        ),
        "blocked_reasons": blocked_reasons,
        "rejected_profiles": [],
        "preservation_summary": _s3_5_preservation_summary(
            strategy_id=strategy_id,
            profile_id=profile_id,
            explicit_inputs=explicit_inputs,
            preserve_existing_policy=preserve_existing_policy,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_5_rationale(
            strategy_id=strategy_id,
            profile_id=profile_id,
            preserve_existing_policy=preserve_existing_policy,
            runtime_signals=runtime_signals,
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
    explicit_profile = _clean_text(requested_profile_id)
    profile_id = explicit_profile or _automatic_s3_11_profile_id(strategy_id=strategy_id, runtime_signals=runtime_signals)
    abort_days = _abort_days(explicit_inputs)
    blocked_reasons = _s3_11_blocked_reasons(
        strategy_id=strategy_id,
        profile_id=profile_id,
        explicit_inputs=explicit_inputs,
        abort_days=abort_days,
        runtime_signals=runtime_signals,
    )
    return {
        "profile_id": profile_id,
        "support_tier": _s3_11_support_tier(
            strategy_id=strategy_id,
            profile_id=profile_id,
            blocked_reasons=blocked_reasons,
            runtime_signals=runtime_signals,
        ),
        "blocked_reasons": blocked_reasons,
        "rejected_profiles": [],
        "preservation_summary": _s3_11_preservation_summary(
            strategy_id=strategy_id,
            profile_id=profile_id,
            explicit_inputs=explicit_inputs,
            abort_days=abort_days,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_11_rationale(
            strategy_id=strategy_id,
            profile_id=profile_id,
            abort_days=abort_days,
            runtime_signals=runtime_signals,
            blocked_reasons=blocked_reasons,
        ),
    }


def resolve_s3_15_selection(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    resolved_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Any | None,
) -> FamilySelectionOutcome:
    explicit_profile = _clean_text(requested_profile_id)
    key_mode = resolve_s3_kms_key_mode(resolved_inputs)
    profile_id = explicit_profile or _automatic_s3_15_profile_id(
        strategy_id=strategy_id,
        key_mode=key_mode,
        runtime_signals=runtime_signals,
    )
    blocked_reasons = _s3_15_blocked_reasons(
        strategy_id=strategy_id,
        requested_profile_id=profile_id,
        key_mode=key_mode,
        resolved_inputs=resolved_inputs,
        runtime_signals=runtime_signals,
        action=action,
    )
    return {
        "profile_id": profile_id,
        "support_tier": _s3_15_support_tier(
            strategy_id=strategy_id,
            profile_id=profile_id,
            key_mode=key_mode,
            resolved_inputs=resolved_inputs,
            blocked_reasons=blocked_reasons,
        ),
        "blocked_reasons": blocked_reasons,
        "rejected_profiles": [],
        "preservation_summary": _s3_15_preservation_summary(
            strategy_id=strategy_id,
            profile_id=profile_id,
            key_mode=key_mode,
            resolved_inputs=resolved_inputs,
            runtime_signals=runtime_signals,
            action=action,
            blocked_reasons=blocked_reasons,
        ),
        "decision_rationale": _s3_15_rationale(profile_id=profile_id, key_mode=key_mode, blocked_reasons=blocked_reasons),
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


def _missing_bucket_create_profile_id(strategy_id: str) -> str | None:
    if strategy_id == S3_2_OAC_STRATEGY_ID:
        return S3_2_OAC_CREATE_PROFILE_ID
    if strategy_id == S3_9_STRATEGY_ID:
        return S3_9_CREATE_PROFILE_ID
    if strategy_id == S3_5_STRICT_STRATEGY_ID:
        return S3_5_STRICT_CREATE_PROFILE_ID
    if strategy_id == S3_5_EXEMPTION_STRATEGY_ID:
        return S3_5_EXEMPTION_CREATE_PROFILE_ID
    if strategy_id == S3_11_STRATEGY_ID:
        return S3_11_CREATE_PROFILE_ID
    if strategy_id == S3_15_STRATEGY_ID:
        return S3_15_CREATE_PROFILE_ID
    return None


def _create_missing_bucket_requested(
    strategy_id: str,
    profile_id: str,
    resolved_inputs: Mapping[str, Any] | None,
) -> bool:
    if _coerce_bool(_mapping_value(resolved_inputs, "create_bucket_if_missing"), default=False):
        return True
    return profile_id == _missing_bucket_create_profile_id(strategy_id)


def _missing_target_bucket_reason(runtime_signals: Mapping[str, Any] | None) -> str | None:
    if _mapping_value(runtime_signals, "s3_target_bucket_missing") is not True:
        return None
    reason = _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_reason"))
    if reason is not None:
        return reason
    bucket = _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_name"))
    if bucket is None:
        bucket = _clean_text(_evidence(runtime_signals).get("target_bucket"))
    if bucket is None:
        return "Target bucket no longer exists."
    return f"Target bucket '{bucket}' no longer exists."


def _unverified_target_bucket_reason(runtime_signals: Mapping[str, Any] | None) -> str | None:
    if _missing_target_bucket_reason(runtime_signals) is not None:
        return None
    if _mapping_value(runtime_signals, "s3_target_bucket_verification_available") is not False:
        return None
    reason = _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_verification_reason"))
    if reason is not None:
        return reason
    reason = _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_reason"))
    if reason is not None:
        return reason
    bucket = _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_name"))
    if bucket is None:
        bucket = _clean_text(_evidence(runtime_signals).get("target_bucket"))
    if bucket is None:
        return "Target bucket existence could not be verified from this account context."
    return (
        f"Target bucket '{bucket}' existence could not be verified from this account context. "
        "Do not keep the existing-bucket remediation path executable until bucket existence is proven."
    )


def _automatic_s3_2_profile_id(
    strategy_id: str,
    blocked_reasons: list[str],
    runtime_signals: Mapping[str, Any] | None,
) -> str:
    if _missing_target_bucket_reason(runtime_signals) is not None:
        create_profile_id = _missing_bucket_create_profile_id(strategy_id)
        if create_profile_id is not None:
            return create_profile_id
    if not blocked_reasons:
        return strategy_id
    if strategy_id == S3_2_STANDARD_STRATEGY_ID and blocked_reasons == [
        "Bucket policy is currently public; generated Terraform will scrub unconditional public Allow statements before enabling Block Public Access."
    ]:
        return S3_2_STANDARD_POLICY_SCRUB_PROFILE_ID
    return _s3_2_fallback_profile_id(strategy_id)


def _automatic_s3_9_profile_id(
    blocked_reasons: list[str],
    runtime_signals: Mapping[str, Any] | None,
) -> str:
    if _missing_target_bucket_reason(runtime_signals) is not None:
        return S3_9_CREATE_PROFILE_ID
    if not blocked_reasons:
        return S3_9_STRATEGY_ID
    return S3_9_REVIEW_PROFILE_ID


def _automatic_s3_5_profile_id(
    *,
    strategy_id: str,
    runtime_signals: Mapping[str, Any] | None,
) -> str:
    if _missing_target_bucket_reason(runtime_signals) is not None:
        create_profile_id = _missing_bucket_create_profile_id(strategy_id)
        if create_profile_id is not None:
            return create_profile_id
    return strategy_id


def _automatic_s3_11_profile_id(
    *,
    strategy_id: str,
    runtime_signals: Mapping[str, Any] | None,
) -> str:
    if _missing_target_bucket_reason(runtime_signals) is not None:
        create_profile_id = _missing_bucket_create_profile_id(strategy_id)
        if create_profile_id is not None:
            return create_profile_id
    return strategy_id


def _s3_2_fallback_profile_id(strategy_id: str) -> str:
    if strategy_id == S3_2_STANDARD_STRATEGY_ID:
        return S3_2_STANDARD_MANUAL_PROFILE_ID
    if strategy_id == S3_2_WEBSITE_STRATEGY_ID:
        return S3_2_WEBSITE_REVIEW_PROFILE_ID
    return S3_2_OAC_MANUAL_PROFILE_ID


def _s3_2_support_tier(
    *,
    strategy_id: str,
    profile_id: str,
    blocked_reasons: list[str],
) -> SupportTier:
    if profile_id == S3_2_OAC_CREATE_PROFILE_ID:
        return "deterministic_bundle" if not blocked_reasons else "review_required_bundle"
    if profile_id in {
        S3_2_STANDARD_MANUAL_PROFILE_ID,
        S3_2_OAC_MANUAL_PROFILE_ID,
    }:
        return "manual_guidance_only"
    if profile_id == S3_2_STANDARD_POLICY_SCRUB_PROFILE_ID:
        return "review_required_bundle"
    if profile_id == S3_2_WEBSITE_REVIEW_PROFILE_ID:
        return "review_required_bundle"
    if strategy_id != profile_id or blocked_reasons:
        if strategy_id == S3_2_WEBSITE_STRATEGY_ID:
            return "review_required_bundle"
        return "manual_guidance_only"
    return "deterministic_bundle"


def _s3_9_support_tier(*, profile_id: str, blocked_reasons: list[str]) -> SupportTier:
    if profile_id == S3_9_CREATE_PROFILE_ID:
        return "deterministic_bundle" if not blocked_reasons else "review_required_bundle"
    if profile_id == S3_9_REVIEW_PROFILE_ID:
        return "review_required_bundle"
    if blocked_reasons:
        return "review_required_bundle"
    return "deterministic_bundle"


def _s3_2_blocked_reasons(
    *,
    strategy_id: str,
    explicit_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    requested_profile_id: str | None,
) -> list[str]:
    if _missing_target_bucket_reason(runtime_signals) is not None:
        if _missing_bucket_create_profile_id(strategy_id) is not None and _create_missing_bucket_requested(
            strategy_id,
            requested_profile_id or "",
            explicit_inputs,
        ):
            return []
        return [_missing_target_bucket_reason(runtime_signals) or "Target bucket no longer exists."]
    unverified_reason = _unverified_target_bucket_reason(runtime_signals)
    if unverified_reason is not None:
        return [unverified_reason]
    if strategy_id == S3_2_STANDARD_STRATEGY_ID:
        return _s3_2_standard_blocked_reasons(runtime_signals)
    if strategy_id == S3_2_WEBSITE_STRATEGY_ID:
        return _s3_2_website_blocked_reasons(runtime_signals, explicit_inputs=explicit_inputs)
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
        if website_configured is not True:
            reasons.append(
                "Bucket policy is currently public; generated Terraform will scrub unconditional public Allow statements before enabling Block Public Access."
            )
        else:
            reasons.append(
                "Bucket policy is currently public; direct public-access preservation must be reviewed manually."
            )
    if not reasons and (policy_public is not False or website_configured is not False):
        reasons.append("Runtime evidence could not prove the bucket is private and website hosting is disabled.")
    return _append_access_path_reason(reasons, runtime_signals)


def _s3_2_oac_blocked_reasons(
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    reasons = _s3_2_oac_preservation_blocked_reasons(runtime_signals)
    website_policy_reason = _s3_2_oac_website_public_policy_reason(runtime_signals)
    if website_policy_reason is not None:
        reasons.append(website_policy_reason)
        return _append_access_path_reason(reasons, runtime_signals)
    if _s3_2_oac_preservation_evidence_available(runtime_signals):
        return _dedupe_strings(reasons)
    return _append_access_path_reason(reasons, runtime_signals)


def _s3_2_website_blocked_reasons(
    runtime_signals: Mapping[str, Any] | None,
    *,
    explicit_inputs: Mapping[str, Any] | None,
) -> list[str]:
    evidence = _evidence(runtime_signals)
    website_configured = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_website_configured"))
    website_translation_supported = _optional_bool(
        _mapping_value(runtime_signals, "s3_bucket_website_translation_supported")
    )
    reasons = _s3_2_oac_preservation_blocked_reasons(runtime_signals)
    if website_configured is not True:
        reasons.append(
            "S3 static website hosting is not confirmed for this bucket; use the non-website S3.2 strategy instead."
        )
    if (
        website_configured is True
        and _clean_text(evidence.get("existing_bucket_website_configuration_json")) is None
    ):
        reasons.append("S3 website configuration was not captured for translation into the CloudFront bundle.")
    if website_configured is True and website_translation_supported is not True:
        reasons.append(
            _clean_text(_mapping_value(runtime_signals, "s3_bucket_website_translation_reason"))
            or "The captured S3 website configuration requires manual review before CloudFront cutover."
        )
    reasons.extend(_s3_2_website_dns_reasons(explicit_inputs))
    if not reasons:
        return []
    return _append_access_path_reason(reasons, runtime_signals)


def _s3_2_oac_preservation_blocked_reasons(
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    evidence = _evidence(runtime_signals)
    statement_count = _coerce_int(evidence.get("existing_bucket_policy_statement_count"))
    policy_json_captured = _clean_text(evidence.get("existing_bucket_policy_json")) is not None
    apply_time_merge_reason = _s3_2_oac_apply_time_merge_reason(runtime_signals)
    reasons: list[str] = []
    capture_error = _clean_text(evidence.get("existing_bucket_policy_capture_error"))
    parse_error = _clean_text(evidence.get("existing_bucket_policy_parse_error"))
    if capture_error is not None and apply_time_merge_reason is None:
        reasons.append(
            f"Existing bucket policy capture failed ({capture_error}); CloudFront + OAC preservation must be reviewed manually."
        )
    if parse_error is not None:
        reasons.append(
            "Existing bucket policy could not be parsed for preservation; CloudFront + OAC migration is manual-only."
        )
    if statement_count is None and not policy_json_captured and apply_time_merge_reason is None:
        reasons.append(
            "Existing bucket policy preservation evidence is missing for CloudFront + OAC migration."
        )
    if statement_count not in (None, 0) and not policy_json_captured:
        reasons.append(
            "Existing bucket policy statements were detected, but their JSON was not captured for safe preservation."
        )
    return _dedupe_strings(reasons)


def _s3_2_oac_website_public_policy_reason(
    runtime_signals: Mapping[str, Any] | None,
) -> str | None:
    website_configured = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_website_configured"))
    policy_public = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_policy_public"))
    if website_configured is not True or policy_public is not True:
        return None
    effective = _optional_bool(_mapping_value(runtime_signals, "s3_effective_block_public_policy_enabled"))
    if effective is True:
        return (
            "Bucket is still configured for S3 website hosting with a public website-read policy, and "
            "BlockPublicPolicy would reject preserving that public statement. Use the website-specific "
            "CloudFront cutover path or manual review instead of the generic CloudFront + OAC migration."
        )
    bucket_bpa = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_block_public_policy_enabled"))
    account_bpa = _optional_bool(_mapping_value(runtime_signals, "s3_account_block_public_policy_enabled"))
    if bucket_bpa is False and account_bpa is False:
        return (
            "Bucket is still configured for S3 website hosting with a public website-read policy. The "
            "generic CloudFront + OAC migration cannot preserve that public statement and still make the "
            "bucket private; use the website-specific CloudFront cutover path or manual review instead."
        )
    return (
        "Bucket is still configured for S3 website hosting with a public website-read policy, but "
        "BlockPublicPolicy visibility is incomplete. Do not keep the generic CloudFront + OAC migration "
        "executable until the website path is translated or reviewed manually."
    )


def _s3_9_blocked_reasons(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    resolved_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Any | None,
) -> list[str]:
    source_bucket = resolve_s3_access_logging_source_bucket(action)
    if source_bucket is None:
        return [
            "Source bucket scope could not be proven for S3 access logging; review the affected bucket relationship manually."
        ]
    reasons: list[str] = []
    missing_reason = _missing_target_bucket_reason(runtime_signals)
    if missing_reason is not None and not _create_missing_bucket_requested(
        strategy_id,
        requested_profile_id or "",
        resolved_inputs,
    ):
        reasons.append(missing_reason)
    unverified_reason = _unverified_target_bucket_reason(runtime_signals)
    if unverified_reason is not None:
        reasons.append(unverified_reason)
    reasons.extend(
        _s3_9_destination_blocked_reasons(
        source_bucket=source_bucket,
        resolved_inputs=resolved_inputs,
        runtime_signals=runtime_signals,
        )
    )
    return _dedupe_strings(reasons)


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


def _s3_2_oac_preservation_evidence_available(
    runtime_signals: Mapping[str, Any] | None,
) -> bool:
    evidence = _evidence(runtime_signals)
    statement_count = _coerce_int(evidence.get("existing_bucket_policy_statement_count"))
    if statement_count == 0:
        return True
    if _clean_text(evidence.get("existing_bucket_policy_json")) is not None:
        return True
    return _s3_2_oac_apply_time_merge_reason(runtime_signals) is not None


def _s3_2_oac_apply_time_merge_reason(
    runtime_signals: Mapping[str, Any] | None,
) -> str | None:
    evidence = _evidence(runtime_signals)
    if _clean_text(evidence.get("existing_bucket_policy_json")) is not None:
        return None
    if _clean_text(evidence.get("existing_bucket_policy_parse_error")) is not None:
        return None
    if _clean_text(evidence.get("target_bucket")) is None:
        return None
    if _coerce_int(evidence.get("existing_bucket_policy_statement_count")) is not None:
        return None
    capture_error = _clean_text(evidence.get("existing_bucket_policy_capture_error"))
    if capture_error is None:
        return None
    return (
        f"Runtime capture failed ({capture_error}), so the customer-run Terraform bundle must fetch "
        "the live bucket policy."
    )


def _s3_9_destination_blocked_reasons(
    *,
    source_bucket: str,
    resolved_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    destination_bucket = _clean_text(_mapping_value(resolved_inputs, "log_bucket_name"))
    if destination_bucket is None:
        return ["Destination log bucket could not be resolved for S3 access logging."]
    if destination_bucket == source_bucket:
        return ["Log destination must be a dedicated bucket and cannot match the source bucket."]
    if _mapping_value(runtime_signals, "s3_access_logging_destination_safe") is True:
        return []
    detail = _clean_text(_mapping_value(runtime_signals, "s3_access_logging_destination_safety_reason"))
    return [detail or "Destination safety could not be proven for the selected S3 access-log bucket."]


def _s3_2_preservation_summary(
    *,
    strategy_id: str,
    profile_id: str,
    explicit_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    evidence = _evidence(runtime_signals)
    apply_time_merge_reason = _s3_2_oac_apply_time_merge_reason(runtime_signals)
    public_policy_scrub_reason = _s3_2_public_policy_scrub_reason(runtime_signals)
    website_public_policy_reason = _s3_2_oac_website_public_policy_reason(runtime_signals)
    return {
        "family": "s3_bucket_block_public_access",
        "selected_branch": profile_id,
        "create_bucket_if_missing": _create_missing_bucket_requested(strategy_id, profile_id, explicit_inputs),
        "target_bucket_exists": _mapping_value(runtime_signals, "s3_target_bucket_exists") is True,
        "target_bucket_missing": _mapping_value(runtime_signals, "s3_target_bucket_missing") is True,
        "target_bucket_verification_available": _optional_bool(
            _mapping_value(runtime_signals, "s3_target_bucket_verification_available")
        ),
        "target_bucket_creation_possible": _mapping_value(runtime_signals, "s3_target_bucket_creation_possible") is True,
        "target_bucket_reason": _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_reason")),
        "bucket_policy_public": _optional_bool(_mapping_value(runtime_signals, "s3_bucket_policy_public")),
        "website_configured": _optional_bool(_mapping_value(runtime_signals, "s3_bucket_website_configured")),
        "website_configuration_captured": _clean_text(
            evidence.get("existing_bucket_website_configuration_json")
        )
        is not None,
        "website_translation_supported": _optional_bool(
            _mapping_value(runtime_signals, "s3_bucket_website_translation_supported")
        ),
        "website_translation_reason": _clean_text(
            _mapping_value(runtime_signals, "s3_bucket_website_translation_reason")
        ),
        "bucket_block_public_policy_enabled": _optional_bool(
            _mapping_value(runtime_signals, "s3_bucket_block_public_policy_enabled")
        ),
        "account_block_public_policy_enabled": _optional_bool(
            _mapping_value(runtime_signals, "s3_account_block_public_policy_enabled")
        ),
        "effective_block_public_policy_enabled": _optional_bool(
            _mapping_value(runtime_signals, "s3_effective_block_public_policy_enabled")
        ),
        "website_public_policy_conflict": website_public_policy_reason is not None,
        "website_public_policy_reason": website_public_policy_reason,
        "dns_inputs_complete": _s3_2_website_dns_inputs_complete(explicit_inputs),
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
        "apply_time_merge": apply_time_merge_reason is not None and not blocked_reasons,
        "apply_time_merge_reason": apply_time_merge_reason,
        "public_policy_scrub_available": profile_id == S3_2_STANDARD_POLICY_SCRUB_PROFILE_ID,
        "public_policy_scrub_reason": public_policy_scrub_reason,
        "executable_preservation_allowed": not blocked_reasons,
        "manual_preservation_required": profile_id in {
            S3_2_STANDARD_MANUAL_PROFILE_ID,
            S3_2_OAC_MANUAL_PROFILE_ID,
        },
        "family_strategy": strategy_id,
    }


def _s3_2_public_policy_scrub_reason(
    runtime_signals: Mapping[str, Any] | None,
) -> str | None:
    policy_public = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_policy_public"))
    website_configured = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_website_configured"))
    if policy_public is True and website_configured is not True:
        return (
            "Runtime probes found a public bucket policy without website hosting, so the review bundle will "
            "remove unconditional public Allow statements and then enable Block Public Access."
        )
    return None


def _s3_9_preservation_summary(
    *,
    strategy_id: str,
    profile_id: str,
    resolved_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Any | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    source_bucket = resolve_s3_access_logging_source_bucket(action)
    return {
        "family": "s3_bucket_access_logging",
        "family_strategy": strategy_id,
        "selected_branch": profile_id,
        "create_bucket_if_missing": _create_missing_bucket_requested(strategy_id, profile_id, resolved_inputs),
        "source_bucket_name": source_bucket,
        "source_bucket_scope_proven": source_bucket is not None,
        "target_bucket_exists": _mapping_value(runtime_signals, "s3_target_bucket_exists") is True,
        "target_bucket_missing": _mapping_value(runtime_signals, "s3_target_bucket_missing") is True,
        "target_bucket_verification_available": _optional_bool(
            _mapping_value(runtime_signals, "s3_target_bucket_verification_available")
        ),
        "target_bucket_creation_possible": _mapping_value(runtime_signals, "s3_target_bucket_creation_possible") is True,
        "target_bucket_reason": _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_reason")),
        "destination_bucket_name": _clean_text(_mapping_value(resolved_inputs, "log_bucket_name")),
        "destination_bucket_reachable": _optional_bool(
            _mapping_value(runtime_signals, "s3_access_logging_destination_bucket_reachable")
        ),
        "destination_safety_proven": _mapping_value(runtime_signals, "s3_access_logging_destination_safe") is True,
        "ambiguous_source_destination_relationship": bool(blocked_reasons),
        "executable_destination_allowed": not blocked_reasons,
    }


def _s3_2_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    explicit_profile: str | None,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> str:
    if profile_id == S3_2_OAC_CREATE_PROFILE_ID and not blocked_reasons:
        return (
            "Family resolver selected the create-missing-bucket CloudFront/OAC branch because the target bucket "
            "no longer exists and the new bucket can start from a zero-policy private baseline."
        )
    apply_time_merge_reason = _s3_2_oac_apply_time_merge_reason(runtime_signals)
    if not blocked_reasons and explicit_profile is not None:
        return f"Family resolver preserved explicit S3.2 profile '{profile_id}' for strategy '{strategy_id}'."
    if not blocked_reasons:
        if strategy_id == S3_2_WEBSITE_STRATEGY_ID:
            return (
                f"Family resolver kept executable S3.2 profile '{profile_id}' for strategy '{strategy_id}' "
                "because website translation evidence, DNS cutover inputs, and private-origin preservation checks are satisfied."
            )
        if apply_time_merge_reason is not None:
            return (
                f"Family resolver kept executable S3.2 profile '{profile_id}' because Terraform can merge "
                f"the current bucket policy at apply time. {apply_time_merge_reason}"
            )
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


def _s3_9_rationale(*, profile_id: str, blocked_reasons: list[str]) -> str:
    if profile_id == S3_9_CREATE_PROFILE_ID and not blocked_reasons:
        return "Family resolver selected the create-missing-bucket S3.9 branch because the source bucket no longer exists."
    if not blocked_reasons:
        return "Family resolver kept S3.9 executable because bucket scope and destination safety are proven."
    if profile_id == S3_9_REVIEW_PROFILE_ID:
        return f"Family resolver downgraded S3.9 to destination-safety review. {' '.join(blocked_reasons)}"
    return f"Family resolver preserved the explicit S3.9 profile but downgraded executability. {' '.join(blocked_reasons)}"


def _s3_2_website_dns_reasons(explicit_inputs: Mapping[str, Any] | None) -> list[str]:
    aliases = _string_list(_mapping_value(explicit_inputs, "aliases"))
    route53_hosted_zone_id = _clean_text(_mapping_value(explicit_inputs, "route53_hosted_zone_id"))
    acm_certificate_arn = _clean_text(_mapping_value(explicit_inputs, "acm_certificate_arn"))
    reasons: list[str] = []
    if not aliases:
        reasons.append("Website migration requires strategy_inputs.aliases for the Route53 cutover hostnames.")
    if route53_hosted_zone_id is None:
        reasons.append("Website migration requires strategy_inputs.route53_hosted_zone_id for Route53 alias updates.")
    if acm_certificate_arn is None:
        reasons.append("Website migration requires strategy_inputs.acm_certificate_arn for the CloudFront viewer certificate.")
    elif ":acm:us-east-1:" not in acm_certificate_arn:
        reasons.append("CloudFront website migration requires an ACM certificate ARN from us-east-1.")
    return reasons


def _s3_2_website_dns_inputs_complete(explicit_inputs: Mapping[str, Any] | None) -> bool:
    return not _s3_2_website_dns_reasons(explicit_inputs)


def _s3_5_blocked_reasons(
    *,
    strategy_id: str,
    profile_id: str,
    explicit_inputs: Mapping[str, Any] | None,
    preserve_existing_policy: bool,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    missing_reason = _missing_target_bucket_reason(runtime_signals)
    if missing_reason is not None and not _create_missing_bucket_requested(
        strategy_id,
        profile_id,
        explicit_inputs,
    ):
        return [missing_reason]
    if missing_reason is not None:
        return []
    unverified_reason = _unverified_target_bucket_reason(runtime_signals)
    if unverified_reason is not None:
        return [unverified_reason]
    if not preserve_existing_policy:
        return [
            "Unsafe bucket policy overwrite is not executable in Wave 6; preserve_existing_policy must remain true."
        ]
    evidence = _evidence(runtime_signals)
    statement_count = _coerce_int(evidence.get("existing_bucket_policy_statement_count"))
    policy_json_captured = _clean_text(evidence.get("existing_bucket_policy_json")) is not None
    apply_time_merge_reason = _s3_5_apply_time_merge_reason(
        preserve_existing_policy=preserve_existing_policy,
        runtime_signals=runtime_signals,
    )
    reasons: list[str] = []
    block_public_policy_reason = _s3_5_block_public_policy_reason(runtime_signals)
    if block_public_policy_reason is not None:
        reasons.append(block_public_policy_reason)
    if _mapping_value(runtime_signals, "s3_policy_analysis_possible") is False and apply_time_merge_reason is None:
        reasons.append(
            str(
                _mapping_value(runtime_signals, "s3_policy_analysis_error")
                or "Unable to inspect the current bucket policy for merge-safe SSL enforcement."
            ).strip()
        )
    if statement_count is None and not policy_json_captured and apply_time_merge_reason is None:
        reasons.append("Bucket policy preservation evidence is missing for merge-safe SSL enforcement.")
    if statement_count not in (None, 0) and not policy_json_captured:
        reasons.append(
            "Existing bucket policy statements were detected, but their JSON was not captured for safe merge."
        )
    capture_error = _clean_text(evidence.get("existing_bucket_policy_capture_error"))
    parse_error = _clean_text(evidence.get("existing_bucket_policy_parse_error"))
    if capture_error is not None and apply_time_merge_reason is None:
        reasons.append(f"Existing bucket policy capture failed ({capture_error}).")
    if parse_error is not None:
        reasons.append("Existing bucket policy could not be parsed for merge-safe preservation.")
    return _dedupe_strings(reasons)


def _s3_5_support_tier(
    *,
    strategy_id: str,
    profile_id: str,
    preserve_existing_policy: bool,
    blocked_reasons: list[str],
) -> SupportTier:
    if profile_id == _missing_bucket_create_profile_id(strategy_id):
        return "deterministic_bundle" if not blocked_reasons else "review_required_bundle"
    if not blocked_reasons:
        return "deterministic_bundle"
    if not preserve_existing_policy:
        return "manual_guidance_only"
    return "review_required_bundle"


def _s3_5_preservation_summary(
    *,
    strategy_id: str,
    profile_id: str,
    explicit_inputs: Mapping[str, Any] | None,
    preserve_existing_policy: bool,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    evidence = _evidence(runtime_signals)
    apply_time_merge_reason = _s3_5_apply_time_merge_reason(
        preserve_existing_policy=preserve_existing_policy,
        runtime_signals=runtime_signals,
    )
    merge_safe_policy_available = (
        _clean_text(evidence.get("existing_bucket_policy_json")) is not None and not blocked_reasons
    )
    block_public_policy_reason = _s3_5_block_public_policy_reason(runtime_signals)
    return {
        "family": "s3_bucket_require_ssl",
        "family_strategy": strategy_id,
        "selected_branch": profile_id,
        "create_bucket_if_missing": _create_missing_bucket_requested(strategy_id, profile_id, explicit_inputs),
        "preserve_existing_policy": preserve_existing_policy,
        "target_bucket_exists": _mapping_value(runtime_signals, "s3_target_bucket_exists") is True,
        "target_bucket_missing": _mapping_value(runtime_signals, "s3_target_bucket_missing") is True,
        "target_bucket_verification_available": _optional_bool(
            _mapping_value(runtime_signals, "s3_target_bucket_verification_available")
        ),
        "target_bucket_creation_possible": _mapping_value(runtime_signals, "s3_target_bucket_creation_possible") is True,
        "target_bucket_reason": _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_reason")),
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
        "bucket_policy_public": _optional_bool(_mapping_value(runtime_signals, "s3_bucket_policy_public")),
        "bucket_block_public_policy_enabled": _optional_bool(
            _mapping_value(runtime_signals, "s3_bucket_block_public_policy_enabled")
        ),
        "account_block_public_policy_enabled": _optional_bool(
            _mapping_value(runtime_signals, "s3_account_block_public_policy_enabled")
        ),
        "effective_block_public_policy_enabled": _optional_bool(
            _mapping_value(runtime_signals, "s3_effective_block_public_policy_enabled")
        ),
        "block_public_policy_conflict": block_public_policy_reason is not None,
        "block_public_policy_reason": block_public_policy_reason,
        "merge_safe_policy_available": merge_safe_policy_available,
        "unsafe_overwrite_requested": not preserve_existing_policy,
        "apply_time_merge": apply_time_merge_reason is not None and not blocked_reasons,
        "apply_time_merge_reason": apply_time_merge_reason,
        "executable_policy_merge_allowed": not blocked_reasons,
    }


def _s3_5_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    preserve_existing_policy: bool,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> str:
    if profile_id == _missing_bucket_create_profile_id(strategy_id) and not blocked_reasons:
        return (
            f"Family resolver selected the create-missing-bucket S3.5 profile for strategy '{strategy_id}' "
            "because the target bucket no longer exists."
        )
    apply_time_merge_reason = _s3_5_apply_time_merge_reason(
        preserve_existing_policy=preserve_existing_policy,
        runtime_signals=runtime_signals,
    )
    if not blocked_reasons:
        if apply_time_merge_reason is not None:
            return (
                f"Family resolver kept S3.5 strategy '{strategy_id}' executable because Terraform can merge "
                f"the current bucket policy at apply time. {apply_time_merge_reason}"
            )
        return (
            f"Family resolver kept S3.5 strategy '{strategy_id}' executable because merge-safe policy "
            "preservation evidence is available."
        )
    block_public_policy_reason = _s3_5_block_public_policy_reason(runtime_signals)
    if block_public_policy_reason is not None:
        return (
            f"Family resolver downgraded S3.5 strategy '{strategy_id}' because preserving the current "
            f"public bucket policy would conflict with S3 Block Public Access. {block_public_policy_reason}"
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


def _s3_5_block_public_policy_reason(runtime_signals: Mapping[str, Any] | None) -> str | None:
    if _optional_bool(_mapping_value(runtime_signals, "s3_bucket_policy_public")) is not True:
        return None
    effective = _optional_bool(_mapping_value(runtime_signals, "s3_effective_block_public_policy_enabled"))
    if effective is True:
        return (
            "Current bucket policy is public and S3 Block Public Access prevents public policies, so "
            "merge-preserving SSL enforcement would be rejected by PutBucketPolicy."
        )
    bucket_bpa = _optional_bool(_mapping_value(runtime_signals, "s3_bucket_block_public_policy_enabled"))
    account_bpa = _optional_bool(_mapping_value(runtime_signals, "s3_account_block_public_policy_enabled"))
    if bucket_bpa is False and account_bpa is False:
        return None
    return (
        "Current bucket policy is public, but BlockPublicPolicy visibility is incomplete. Do not keep "
        "merge-preserving SSL enforcement executable until bucket/account S3 Block Public Access proves "
        "the policy write is safe."
    )


def _s3_5_apply_time_merge_reason(
    *,
    preserve_existing_policy: bool,
    runtime_signals: Mapping[str, Any] | None,
) -> str | None:
    if not preserve_existing_policy:
        return None
    evidence = _evidence(runtime_signals)
    if _mapping_value(runtime_signals, "s3_policy_analysis_possible") is not False:
        return None
    if _clean_text(evidence.get("existing_bucket_policy_json")) is not None:
        return None
    if _clean_text(evidence.get("existing_bucket_policy_parse_error")) is not None:
        return None
    if _clean_text(evidence.get("target_bucket")) is None:
        return None
    capture_error = _clean_text(evidence.get("existing_bucket_policy_capture_error"))
    if capture_error is None:
        return None
    return f"Runtime capture failed ({capture_error}), so the customer-run Terraform bundle must fetch the live policy."


def _s3_11_blocked_reasons(
    *,
    strategy_id: str,
    profile_id: str,
    explicit_inputs: Mapping[str, Any] | None,
    abort_days: int,
    runtime_signals: Mapping[str, Any] | None,
) -> list[str]:
    missing_reason = _missing_target_bucket_reason(runtime_signals)
    if missing_reason is not None and not _create_missing_bucket_requested(
        strategy_id,
        profile_id,
        explicit_inputs,
    ):
        return [missing_reason]
    if missing_reason is not None:
        return []
    unverified_reason = _unverified_target_bucket_reason(runtime_signals)
    if unverified_reason is not None:
        return [unverified_reason]
    evidence = _evidence(runtime_signals)
    analysis_possible = _optional_bool(_mapping_value(runtime_signals, "s3_lifecycle_analysis_possible"))
    rule_count = _coerce_int(evidence.get("existing_lifecycle_rule_count"))
    lifecycle_json = _clean_text(evidence.get("existing_lifecycle_configuration_json"))
    lifecycle_analysis = analyze_lifecycle_preservation(lifecycle_json, abort_days=abort_days)
    apply_time_merge_reason = _s3_11_apply_time_merge_reason(runtime_signals)
    if rule_count == 0:
        return []
    if lifecycle_analysis["equivalent_safe_state"]:
        return []
    if lifecycle_analysis["merge_renderable"]:
        return []
    if apply_time_merge_reason is not None:
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
            lifecycle_analysis["render_failure_reason"]
            or "Existing lifecycle rules are present, but the captured lifecycle document cannot be rendered safely for additive merge."
        )
    return _dedupe_strings(reasons)


def _s3_11_support_tier(
    *,
    strategy_id: str,
    profile_id: str,
    blocked_reasons: list[str],
    runtime_signals: Mapping[str, Any] | None,
) -> SupportTier:
    if profile_id == _missing_bucket_create_profile_id(strategy_id):
        return "deterministic_bundle" if not blocked_reasons else "review_required_bundle"
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
    profile_id: str,
    explicit_inputs: Mapping[str, Any] | None,
    abort_days: int,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    evidence = _evidence(runtime_signals)
    lifecycle_json = _clean_text(evidence.get("existing_lifecycle_configuration_json"))
    lifecycle_analysis = analyze_lifecycle_preservation(lifecycle_json, abort_days=abort_days)
    apply_time_merge_reason = _s3_11_apply_time_merge_reason(runtime_signals)
    return {
        "family": "s3_bucket_lifecycle_configuration",
        "family_strategy": strategy_id,
        "selected_branch": profile_id,
        "create_bucket_if_missing": _create_missing_bucket_requested(strategy_id, profile_id, explicit_inputs),
        "abort_days": abort_days,
        "target_bucket_exists": _mapping_value(runtime_signals, "s3_target_bucket_exists") is True,
        "target_bucket_missing": _mapping_value(runtime_signals, "s3_target_bucket_missing") is True,
        "target_bucket_verification_available": _optional_bool(
            _mapping_value(runtime_signals, "s3_target_bucket_verification_available")
        ),
        "target_bucket_creation_possible": _mapping_value(runtime_signals, "s3_target_bucket_creation_possible") is True,
        "target_bucket_reason": _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_reason")),
        "existing_lifecycle_rule_count": _coerce_int(evidence.get("existing_lifecycle_rule_count")),
        "existing_lifecycle_configuration_captured": lifecycle_json is not None,
        "existing_lifecycle_configuration_equivalent": lifecycle_analysis["equivalent_safe_state"],
        "existing_lifecycle_merge_renderable": lifecycle_analysis["merge_renderable"],
        "existing_lifecycle_render_failure_reason": lifecycle_analysis["render_failure_reason"],
        "existing_equivalent_abort_rule_present": lifecycle_analysis["has_equivalent_abort_rule"],
        "apply_time_merge": apply_time_merge_reason is not None and not blocked_reasons,
        "apply_time_merge_reason": apply_time_merge_reason,
        "additive_merge_safe": not blocked_reasons,
        "executable_lifecycle_merge_allowed": not blocked_reasons,
    }


def _s3_11_rationale(
    *,
    strategy_id: str,
    profile_id: str,
    abort_days: int,
    runtime_signals: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> str:
    if profile_id == _missing_bucket_create_profile_id(strategy_id) and not blocked_reasons:
        return (
            f"Family resolver selected the create-missing-bucket S3.11 profile for strategy '{strategy_id}' "
            "because the target bucket no longer exists."
        )
    if not blocked_reasons:
        apply_time_merge_reason = _s3_11_apply_time_merge_reason(runtime_signals)
        if apply_time_merge_reason is not None:
            return (
                f"Family resolver kept S3.11 strategy '{strategy_id}' executable with abort_days={abort_days} "
                f"because Terraform can fetch and merge the current lifecycle configuration at apply time. {apply_time_merge_reason}"
            )
        return (
            f"Family resolver kept S3.11 strategy '{strategy_id}' executable with abort_days={abort_days} "
            "because lifecycle preservation is already safe."
        )
    return (
        f"Family resolver downgraded S3.11 strategy '{strategy_id}' because additive lifecycle preservation "
        f"is under-proven. {' '.join(blocked_reasons)}"
    )


def _s3_11_apply_time_merge_reason(runtime_signals: Mapping[str, Any] | None) -> str | None:
    evidence = _evidence(runtime_signals)
    if _mapping_value(runtime_signals, "s3_lifecycle_analysis_possible") is not False:
        return None
    if _clean_text(evidence.get("existing_lifecycle_configuration_json")) is not None:
        return None
    if _coerce_int(evidence.get("existing_lifecycle_rule_count")) is not None:
        return None
    if _clean_text(evidence.get("target_bucket")) is None:
        return None
    capture_error = _clean_text(evidence.get("existing_lifecycle_capture_error"))
    if capture_error is None:
        return None
    return (
        f"Runtime capture failed ({capture_error}), so the customer-run Terraform bundle must fetch and merge "
        "the live lifecycle configuration."
    )


def _automatic_s3_15_profile_id(
    *,
    strategy_id: str,
    key_mode: str,
    runtime_signals: Mapping[str, Any] | None,
) -> str:
    if _missing_target_bucket_reason(runtime_signals) is not None and key_mode != "custom":
        create_profile_id = _missing_bucket_create_profile_id(strategy_id)
        if create_profile_id is not None:
            return create_profile_id
    if key_mode == "custom":
        return S3_15_CUSTOMER_MANAGED_PROFILE_ID
    return strategy_id


def _s3_15_blocked_reasons(
    *,
    strategy_id: str,
    requested_profile_id: str | None,
    key_mode: str,
    resolved_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Any | None,
) -> list[str]:
    reasons: list[str] = []
    missing_reason = _missing_target_bucket_reason(runtime_signals)
    if missing_reason is not None and not _create_missing_bucket_requested(
        strategy_id,
        requested_profile_id or "",
        resolved_inputs,
    ):
        reasons.append(missing_reason)
    unverified_reason = _unverified_target_bucket_reason(runtime_signals)
    if unverified_reason is not None:
        reasons.append(unverified_reason)
    if _bucket_name_from_action_fields(action, "target_id", "resource_id") is None:
        reasons.append("Target bucket scope could not be proven for S3 SSE-KMS enforcement.")
    if key_mode != "custom":
        return reasons
    if _clean_text(_mapping_value(resolved_inputs, "kms_key_arn")) is None:
        reasons.append("Customer-managed KMS branch requires an approved kms_key_arn.")
        return reasons
    if _mapping_value(runtime_signals, "s3_customer_kms_key_valid") is False:
        detail = _clean_text(_mapping_value(runtime_signals, "s3_customer_kms_key_error"))
        reasons.append(detail or "Customer-managed KMS key is invalid for this bucket/account scope.")
    if _mapping_value(runtime_signals, "s3_customer_kms_dependency_proven") is not True:
        detail = _clean_text(_mapping_value(runtime_signals, "s3_customer_kms_dependency_error"))
        reasons.append(detail or "Customer-managed KMS key policy/grant evidence is under-specified.")
    return _dedupe_strings(reasons)


def _s3_15_support_tier(
    *,
    strategy_id: str,
    profile_id: str,
    key_mode: str,
    resolved_inputs: Mapping[str, Any] | None,
    blocked_reasons: list[str],
) -> SupportTier:
    if profile_id == _missing_bucket_create_profile_id(strategy_id):
        return "deterministic_bundle" if not blocked_reasons else "review_required_bundle"
    if not blocked_reasons:
        return "deterministic_bundle"
    if profile_id != S3_15_CUSTOMER_MANAGED_PROFILE_ID and key_mode != "custom":
        return "review_required_bundle"
    if _clean_text(_mapping_value(resolved_inputs, "kms_key_arn")) is None:
        return "manual_guidance_only"
    return "review_required_bundle"


def _s3_15_preservation_summary(
    *,
    strategy_id: str,
    profile_id: str,
    key_mode: str,
    resolved_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    action: Any | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    evidence = _evidence(runtime_signals)
    return {
        "family": "s3_bucket_encryption_kms",
        "family_strategy": strategy_id,
        "selected_branch": profile_id,
        "create_bucket_if_missing": _create_missing_bucket_requested(strategy_id, profile_id, resolved_inputs),
        "kms_key_mode": key_mode,
        "kms_key_arn_present": _clean_text(_mapping_value(resolved_inputs, "kms_key_arn")) is not None,
        "target_bucket_name": _bucket_name_from_action_fields(action, "target_id", "resource_id"),
        "target_bucket_scope_proven": _bucket_name_from_action_fields(action, "target_id", "resource_id") is not None,
        "target_bucket_exists": _mapping_value(runtime_signals, "s3_target_bucket_exists") is True,
        "target_bucket_missing": _mapping_value(runtime_signals, "s3_target_bucket_missing") is True,
        "target_bucket_verification_available": _optional_bool(
            _mapping_value(runtime_signals, "s3_target_bucket_verification_available")
        ),
        "target_bucket_creation_possible": _mapping_value(runtime_signals, "s3_target_bucket_creation_possible") is True,
        "target_bucket_reason": _clean_text(_mapping_value(runtime_signals, "s3_target_bucket_reason")),
        "customer_managed_key_valid": _optional_bool(_mapping_value(runtime_signals, "s3_customer_kms_key_valid")),
        "customer_managed_dependency_proven": _mapping_value(runtime_signals, "s3_customer_kms_dependency_proven") is True,
        "customer_managed_policy_json_captured": _clean_text(evidence.get("customer_kms_policy_json")) is not None,
        "customer_managed_grants_captured": _coerce_int(evidence.get("customer_kms_grant_count")) is not None,
        "executable_kms_change_allowed": not blocked_reasons,
    }


def _s3_15_rationale(*, profile_id: str, key_mode: str, blocked_reasons: list[str]) -> str:
    if profile_id == S3_15_CREATE_PROFILE_ID and not blocked_reasons:
        return "Family resolver selected the create-missing-bucket S3.15 branch because the target bucket no longer exists."
    if not blocked_reasons:
        return f"Family resolver kept S3.15 branch '{profile_id}' executable with key_mode={key_mode}."
    return f"Family resolver downgraded S3.15 branch '{profile_id}' because KMS safety is under-proven. {' '.join(blocked_reasons)}"


def _s3_11_equivalent_safe_state(lifecycle_json: str | None, *, abort_days: int) -> bool:
    parsed = _parse_json_object(lifecycle_json)
    if parsed is None:
        return False
    rules = parsed.get("Rules")
    if not isinstance(rules, list) or len(rules) != 1:
        return False
    return rule_is_equivalent_abort_incomplete(rules[0], abort_days=abort_days)


def _equivalent_abort_rule(rule: Any, *, abort_days: int) -> bool:
    return rule_is_equivalent_abort_incomplete(rule, abort_days=abort_days)


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


def _bucket_name_from_action_fields(action: Any | None, *field_names: str) -> str | None:
    for field_name in field_names:
        candidate = _bucket_name_candidate(getattr(action, field_name, None))
        if candidate:
            return candidate
    return None


def _bucket_name_from_runtime_like_action_fields(action: Any | None, *field_names: str) -> str | None:
    for field_name in field_names:
        candidate = _runtime_like_bucket_name_candidate(getattr(action, field_name, None))
        if candidate:
            return candidate
    return None


def _bucket_name_candidate(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().strip("'\"")
    if not value:
        return None
    match = _S3_BUCKET_ARN_PATTERN.search(value)
    if match:
        return match.group("bucket")
    if "|" in value:
        for part in value.split("|"):
            candidate = _bucket_name_candidate(part)
            if candidate:
                return candidate
        return None
    if value.startswith("AWS::::Account:") or value.lower().startswith("account:"):
        return None
    if value.lower().startswith("aws-account-") or re.fullmatch(r"\d{12}", value):
        return None
    return value


def _runtime_like_bucket_name_candidate(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().strip("'\"")
    if not value:
        return None
    match = _S3_BUCKET_ARN_PATTERN.search(value)
    if match:
        return match.group("bucket")
    if "|" in value:
        for part in value.split("|"):
            match = _S3_BUCKET_ARN_PATTERN.search(part.strip())
            if match:
                return match.group("bucket")
        return None
    if value.startswith("AWS::::Account:") or value.lower().startswith("account:"):
        return None
    if value.lower().startswith("aws-account-") or re.fullmatch(r"\d{12}", value):
        return None
    return value


def _mapping_value(mapping: Mapping[str, Any] | None, key: str) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    return mapping.get(key)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text is not None and text not in cleaned:
            cleaned.append(text)
    return cleaned


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
