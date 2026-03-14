from __future__ import annotations

import json

import pytest

from backend.services.remediation_profile_resolver import (
    RESOLVER_DECISION_VERSION_V1,
    build_compat_resolution_decision,
    normalize_resolution_decision,
)


def test_build_compat_resolution_decision_defaults_profile_id_to_strategy_id() -> None:
    decision = build_compat_resolution_decision(
        strategy_id="cloudtrail_enable_guided",
        support_tier="deterministic_bundle",
    )

    assert decision["strategy_id"] == "cloudtrail_enable_guided"
    assert decision["profile_id"] == "cloudtrail_enable_guided"


def test_build_compat_resolution_decision_defaults_decision_version() -> None:
    decision = build_compat_resolution_decision(
        strategy_id="config_enable_account_local_delivery",
        support_tier="review_required_bundle",
    )

    assert decision["decision_version"] == RESOLVER_DECISION_VERSION_V1


def test_build_compat_resolution_decision_rejects_unsupported_support_tier() -> None:
    with pytest.raises(ValueError, match="Unsupported support_tier"):
        build_compat_resolution_decision(
            strategy_id="config_enable_account_local_delivery",
            support_tier="unsupported_bundle",
        )


def test_build_compat_resolution_decision_preserves_explicit_profile_id() -> None:
    decision = build_compat_resolution_decision(
        strategy_id="config_enable_centralized_delivery",
        profile_id="config-guided-profile",
        support_tier="manual_guidance_only",
    )

    assert decision["strategy_id"] == "config_enable_centralized_delivery"
    assert decision["profile_id"] == "config-guided-profile"


def test_normalize_resolution_decision_preserves_explicit_fields_without_mutation() -> None:
    raw_decision = {
        "strategy_id": "s3_enable_access_logging_guided",
        "support_tier": "review-required-bundle",
        "resolved_inputs": {"log_bucket_name": "security-autopilot-logs"},
        "missing_inputs": ["target_bucket_name"],
        "missing_defaults": ["delivery_prefix"],
        "blocked_reasons": ["log_bucket_policy_missing"],
        "rejected_profiles": [{"profile_id": "manual-fallback", "reason": "not_selected"}],
        "finding_coverage": {"summary": "single finding covered"},
        "preservation_summary": {"summary": "single-profile compatibility preserved"},
        "decision_rationale": "Matches current guided logging flow.",
    }

    decision = normalize_resolution_decision(raw_decision)
    raw_decision["missing_inputs"].append("mutated")
    raw_decision["blocked_reasons"].append("mutated")
    raw_decision["rejected_profiles"][0]["reason"] = "mutated"
    raw_decision["finding_coverage"]["summary"] = "mutated"
    raw_decision["preservation_summary"]["summary"] = "mutated"

    assert decision["support_tier"] == "review_required_bundle"
    assert decision["missing_inputs"] == ["target_bucket_name"]
    assert decision["missing_defaults"] == ["delivery_prefix"]
    assert decision["blocked_reasons"] == ["log_bucket_policy_missing"]
    assert decision["rejected_profiles"] == [{"profile_id": "manual-fallback", "reason": "not_selected"}]
    assert decision["finding_coverage"] == {"summary": "single finding covered"}
    assert decision["preservation_summary"] == {"summary": "single-profile compatibility preserved"}


def test_normalize_resolution_decision_is_plain_dict_based_and_json_serializable() -> None:
    raw_decision = {
        "strategy_id": "ebs_enable_default_encryption_aws_managed_kms",
        "support_tier": "DETERMINISTIC_BUNDLE",
        "resolved_inputs": {"kms_key_mode": "aws_managed"},
        "decision_rationale": "Matches current default direct-fix path.",
    }

    decision = normalize_resolution_decision(raw_decision)
    encoded = json.dumps(decision)
    decoded = json.loads(encoded)

    assert isinstance(decision, dict)
    assert decoded["profile_id"] == "ebs_enable_default_encryption_aws_managed_kms"
    assert decoded["decision_version"] == RESOLVER_DECISION_VERSION_V1
    assert decoded["resolved_inputs"] == {"kms_key_mode": "aws_managed"}
