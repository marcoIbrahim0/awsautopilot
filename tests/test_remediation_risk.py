"""Unit tests for remediation risk deltas and conditional promotions."""
from __future__ import annotations

from types import SimpleNamespace

from backend.services.remediation_risk import evaluate_strategy_impact


def _fake_strategy(
    strategy_id: str,
    action_type: str = "s3_bucket_require_ssl",
    mode: str = "pr_only",
    risk_level: str = "high",
) -> dict:
    return {
        "strategy_id": strategy_id,
        "action_type": action_type,
        "label": "x",
        "mode": mode,
        "risk_level": risk_level,
        "recommended": True,
        "requires_inputs": False,
        "input_schema": {"fields": []},
        "supports_exception_flow": False,
        "warnings": [],
        "legacy_pr_bundle_variant": None,
    }


def _code_status(snapshot: dict) -> dict[str, str]:
    return {check["code"]: check["status"] for check in snapshot["checks"]}


def test_unspecialized_medium_high_strategy_is_fail() -> None:
    action = SimpleNamespace(action_type="custom_control")
    strategy = _fake_strategy("custom_unspecialized_strategy", risk_level="high")
    snapshot = evaluate_strategy_impact(action, strategy)

    status_map = _code_status(snapshot)
    assert status_map["risk_evaluation_not_specialized"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_config_central_bucket_unreachable_blocks() -> None:
    action = SimpleNamespace(action_type="aws_config_enabled")
    strategy = _fake_strategy(
        "config_enable_centralized_delivery",
        action_type="aws_config_enabled",
        risk_level="high",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        strategy_inputs={"delivery_bucket": "central-config-bucket"},
        runtime_signals={
            "config_delivery_bucket_reachable": False,
            "config_delivery_bucket_error": "HeadBucket AccessDenied",
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["config_delivery_bucket_unreachable"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_ebs_customer_kms_invalid_blocks() -> None:
    action = SimpleNamespace(action_type="ebs_default_encryption")
    strategy = _fake_strategy(
        "ebs_enable_default_encryption_customer_kms",
        action_type="ebs_default_encryption",
        mode="direct_fix",
        risk_level="medium",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        strategy_inputs={"kms_key_arn": "arn:aws:kms:us-east-1:123:key/abc"},
        account=SimpleNamespace(role_write_arn="arn:aws:iam::123:role/WriteRole"),
        runtime_signals={
            "ebs_customer_kms_key_valid": False,
            "ebs_customer_kms_key_error": "KMS key is disabled.",
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["ebs_customer_kms_key_invalid"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_strict_access_path_strategy_without_evidence_blocks() -> None:
    action = SimpleNamespace(action_type="s3_bucket_require_ssl")
    strategy = _fake_strategy("s3_enforce_ssl_strict_deny", action_type="s3_bucket_require_ssl")
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={
            "access_path_evidence_available": False,
            "access_path_evidence_reason": "ReadRole probe unavailable.",
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["access_path_evidence_unavailable"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_ssl_exemption_strategy_merge_risk_warn_when_analyzable() -> None:
    action = SimpleNamespace(action_type="s3_bucket_require_ssl")
    strategy = _fake_strategy(
        "s3_enforce_ssl_with_principal_exemptions",
        action_type="s3_bucket_require_ssl",
        risk_level="high",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={"s3_policy_analysis_possible": True},
    )

    status_map = _code_status(snapshot)
    assert status_map["s3_policy_merge_risk"] == "warn"
    assert snapshot["recommendation"] == "review_and_acknowledge"


def test_snapshot_public_shares_inventory_adds_warn() -> None:
    action = SimpleNamespace(action_type="ebs_snapshot_block_public_access")
    strategy = _fake_strategy(
        "snapshot_block_all_sharing",
        action_type="ebs_snapshot_block_public_access",
        risk_level="medium",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={"snapshot_public_shares_count": 3},
    )

    status_map = _code_status(snapshot)
    assert status_map["snapshot_public_shares_present"] == "warn"


def test_s3_public_access_dependency_passes_when_bucket_not_public_and_website_disabled() -> None:
    action = SimpleNamespace(action_type="s3_bucket_block_public_access")
    strategy = _fake_strategy(
        "s3_bucket_block_public_access_standard",
        action_type="s3_bucket_block_public_access",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={
            "s3_bucket_policy_public": False,
            "s3_bucket_website_configured": False,
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["s3_public_access_dependency"] == "pass"
    assert snapshot["recommendation"] == "safe_to_proceed"


def test_s3_public_access_dependency_warns_when_probe_data_is_incomplete() -> None:
    action = SimpleNamespace(action_type="s3_bucket_block_public_access")
    strategy = _fake_strategy(
        "s3_bucket_block_public_access_standard",
        action_type="s3_bucket_block_public_access",
    )
    snapshot = evaluate_strategy_impact(action, strategy, runtime_signals={})

    status_map = _code_status(snapshot)
    assert status_map["s3_public_access_dependency"] == "warn"


def test_iam_root_delete_strategy_blocks_when_root_mfa_not_enrolled() -> None:
    action = SimpleNamespace(action_type="iam_root_access_key_absent")
    strategy = _fake_strategy(
        "iam_root_key_delete",
        action_type="iam_root_access_key_absent",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={"iam_root_account_mfa_enrolled": False},
    )

    status_map = _code_status(snapshot)
    assert status_map["iam_root_mfa_enrollment_gate"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_iam_root_delete_strategy_allows_when_root_mfa_enrolled() -> None:
    action = SimpleNamespace(action_type="iam_root_access_key_absent")
    strategy = _fake_strategy(
        "iam_root_key_delete",
        action_type="iam_root_access_key_absent",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={"iam_root_account_mfa_enrolled": True},
    )

    status_map = _code_status(snapshot)
    assert status_map["iam_root_mfa_enrollment_gate"] == "pass"
    assert snapshot["recommendation"] == "review_and_acknowledge"
