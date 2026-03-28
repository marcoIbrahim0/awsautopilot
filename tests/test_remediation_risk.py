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


def test_s3_5_apply_time_merge_keeps_access_path_unavailable_at_warn() -> None:
    action = SimpleNamespace(action_type="s3_bucket_require_ssl")
    strategy = _fake_strategy("s3_enforce_ssl_strict_deny", action_type="s3_bucket_require_ssl")
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={
            "s3_policy_analysis_possible": False,
            "access_path_evidence_available": False,
            "access_path_evidence_reason": "Unable to inspect current bucket policy (AccessDenied).",
            "evidence": {
                "target_bucket": "ssl-bucket",
                "existing_bucket_policy_capture_error": "AccessDenied",
            },
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["s3_policy_merge_risk"] == "warn"
    assert status_map["access_path_evidence_unavailable"] == "warn"
    assert snapshot["recommendation"] == "review_and_acknowledge"


def test_s3_2_oac_apply_time_merge_keeps_access_path_unavailable_at_warn() -> None:
    action = SimpleNamespace(action_type="s3_bucket_block_public_access")
    strategy = _fake_strategy("s3_migrate_cloudfront_oac_private", action_type="s3_bucket_block_public_access")
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={
            "access_path_evidence_available": False,
            "access_path_evidence_reason": "Unable to capture existing bucket policy (AccessDenied).",
            "evidence": {
                "target_bucket": "oac-bucket",
                "existing_bucket_policy_capture_error": "AccessDenied",
            },
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["s3_public_access_dependency"] == "warn"
    assert status_map["access_path_evidence_unavailable"] == "warn"
    assert snapshot["recommendation"] == "review_and_acknowledge"


def test_s3_2_oac_zero_policy_proof_skips_access_path_failure() -> None:
    action = SimpleNamespace(action_type="s3_bucket_block_public_access")
    strategy = _fake_strategy("s3_migrate_cloudfront_oac_private", action_type="s3_bucket_block_public_access")
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={
            "s3_bucket_policy_public": False,
            "s3_bucket_website_configured": False,
            "access_path_evidence_available": False,
            "access_path_evidence_reason": "Unable to capture existing bucket policy (AccessDenied).",
            "evidence": {
                "target_bucket": "oac-bucket",
                "existing_bucket_policy_statement_count": 0,
            },
        },
    )

    status_map = _code_status(snapshot)
    assert "access_path_evidence_unavailable" not in status_map
    assert status_map["s3_public_access_dependency"] == "pass"
    assert snapshot["recommendation"] == "safe_to_proceed"


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
        runtime_signals={
            "s3_policy_analysis_possible": True,
            "evidence": {"existing_bucket_policy_statement_count": 0},
        },
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


def test_snapshot_strategy_does_not_require_access_path_evidence() -> None:
    action = SimpleNamespace(action_type="ebs_snapshot_block_public_access")
    strategy = _fake_strategy(
        "snapshot_block_all_sharing",
        action_type="ebs_snapshot_block_public_access",
        risk_level="medium",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={
            "access_path_evidence_available": False,
            "access_path_evidence_reason": "ReadRole probe unavailable.",
        },
    )

    status_map = _code_status(snapshot)
    assert "access_path_evidence_unavailable" not in status_map
    assert status_map["snapshot_sharing_dependency"] == "warn"
    assert snapshot["recommendation"] == "review_and_acknowledge"


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


def test_cloudtrail_guided_strategy_requires_review_instead_of_unspecialized_fail() -> None:
    action = SimpleNamespace(action_type="cloudtrail_enabled")
    strategy = _fake_strategy(
        "cloudtrail_enable_guided",
        action_type="cloudtrail_enabled",
        risk_level="medium",
    )
    snapshot = evaluate_strategy_impact(action, strategy, runtime_signals={})

    status_map = _code_status(snapshot)
    assert "risk_evaluation_not_specialized" not in status_map
    assert status_map["cloudtrail_cost_impact"] == "warn"
    assert status_map["cloudtrail_log_bucket_prereq"] == "warn"
    assert status_map["adjacency_safety_unproven"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_cloudtrail_guided_strategy_warns_when_existing_trail_is_present() -> None:
    action = SimpleNamespace(action_type="cloudtrail_enabled")
    strategy = _fake_strategy(
        "cloudtrail_enable_guided",
        action_type="cloudtrail_enabled",
        risk_level="medium",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        runtime_signals={
            "cloudtrail_existing_trail_present": True,
            "cloudtrail_existing_trail_name": "existing-org-trail",
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["cloudtrail_existing_trail_present"] == "warn"
    existing_check = next(
        check for check in snapshot["checks"] if check["code"] == "cloudtrail_existing_trail_present"
    )
    assert "existing-org-trail" in existing_check["message"]


def test_cloudtrail_guided_create_if_missing_treats_bucket_creation_as_safe_by_construction() -> None:
    action = SimpleNamespace(action_type="cloudtrail_enabled")
    strategy = _fake_strategy(
        "cloudtrail_enable_guided",
        action_type="cloudtrail_enabled",
        risk_level="medium",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        strategy_inputs={
            "trail_bucket_name": "new-cloudtrail-logs",
            "create_bucket_if_missing": True,
        },
        runtime_signals={"cloudtrail_bucket_available_for_creation": True},
    )

    status_map = _code_status(snapshot)
    assert "adjacency_safety_unproven" not in status_map
    assert status_map["cloudtrail_cost_impact"] == "warn"
    assert status_map["cloudtrail_log_bucket_prereq"] == "warn"
    assert snapshot["recommendation"] == "review_and_acknowledge"


def test_s3_access_logging_bucket_scope_is_specialized_and_executable() -> None:
    action = SimpleNamespace(
        action_type="s3_bucket_access_logging",
        target_id="123456789012|eu-north-1|arn:aws:s3:::config-bucket-123456789012|S3.9",
        resource_id="arn:aws:s3:::config-bucket-123456789012",
    )
    strategy = _fake_strategy(
        "s3_enable_access_logging_guided",
        action_type="s3_bucket_access_logging",
        risk_level="low",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        strategy_inputs={"log_bucket_name": "security-autopilot-access-logs-123456789012"},
        runtime_signals={
            "s3_access_logging_destination_safe": True,
            "support_bucket_probe": {"safe": True},
        },
    )

    status_map = _code_status(snapshot)
    assert "risk_evaluation_not_specialized" not in status_map
    assert status_map["s3_access_logging_bucket_scope_confirmed"] == "pass"
    assert status_map["s3_access_logging_destination_safety_proven"] == "pass"
    assert snapshot["recommendation"] == "safe_to_proceed"


def test_s3_access_logging_account_scope_downgrades_to_review() -> None:
    action = SimpleNamespace(
        action_type="s3_bucket_access_logging",
        target_id="123456789012|eu-north-1|AWS::::Account:123456789012|S3.9",
        resource_id="AWS::::Account:123456789012",
    )
    strategy = _fake_strategy(
        "s3_enable_access_logging_guided",
        action_type="s3_bucket_access_logging",
        risk_level="low",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        strategy_inputs={"log_bucket_name": "security-autopilot-access-logs-123456789012"},
    )

    status_map = _code_status(snapshot)
    assert "risk_evaluation_not_specialized" not in status_map
    assert status_map["s3_access_logging_scope_requires_review"] == "warn"
    assert status_map["adjacency_safety_unproven"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_s3_access_logging_bucket_scope_blocks_when_destination_safety_is_missing() -> None:
    action = SimpleNamespace(
        action_type="s3_bucket_access_logging",
        target_id="123456789012|eu-north-1|arn:aws:s3:::config-bucket-123456789012|S3.9",
        resource_id="arn:aws:s3:::config-bucket-123456789012",
    )
    strategy = _fake_strategy(
        "s3_enable_access_logging_guided",
        action_type="s3_bucket_access_logging",
        risk_level="low",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        strategy_inputs={"log_bucket_name": "security-autopilot-access-logs-123456789012"},
        runtime_signals={
            "s3_access_logging_destination_safe": False,
            "s3_access_logging_destination_safety_reason": "Destination safety could not be proven.",
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["s3_access_logging_destination_safety_unproven"] == "fail"
    assert snapshot["recommendation"] == "blocked"


def test_s3_15_aws_managed_branch_is_specialized_and_executable() -> None:
    action = SimpleNamespace(
        action_type="s3_bucket_encryption_kms",
        target_id="123456789012|us-east-1|arn:aws:s3:::kms-bucket|S3.15",
        resource_id="arn:aws:s3:::kms-bucket",
    )
    strategy = _fake_strategy(
        "s3_enable_sse_kms_guided",
        action_type="s3_bucket_encryption_kms",
        risk_level="low",
    )
    snapshot = evaluate_strategy_impact(action, strategy, strategy_inputs={"kms_key_mode": "aws_managed"})

    status_map = _code_status(snapshot)
    assert "risk_evaluation_not_specialized" not in status_map
    assert status_map["s3_sse_kms_bucket_scope_confirmed"] == "pass"
    assert status_map["s3_sse_kms_aws_managed_branch_ready"] == "pass"
    assert snapshot["recommendation"] == "safe_to_proceed"


def test_s3_15_customer_managed_branch_blocks_without_dependency_proof() -> None:
    action = SimpleNamespace(
        action_type="s3_bucket_encryption_kms",
        target_id="123456789012|us-east-1|arn:aws:s3:::kms-bucket|S3.15",
        resource_id="arn:aws:s3:::kms-bucket",
    )
    strategy = _fake_strategy(
        "s3_enable_sse_kms_guided",
        action_type="s3_bucket_encryption_kms",
        risk_level="low",
    )
    snapshot = evaluate_strategy_impact(
        action,
        strategy,
        strategy_inputs={
            "kms_key_mode": "custom",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
        },
        runtime_signals={
            "s3_customer_kms_key_valid": True,
            "s3_customer_kms_dependency_proven": False,
            "s3_customer_kms_dependency_error": "Customer-managed KMS key policy/grant evidence is under-specified.",
        },
    )

    status_map = _code_status(snapshot)
    assert status_map["s3_customer_kms_dependency_unproven"] == "fail"
    assert snapshot["recommendation"] == "blocked"


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
