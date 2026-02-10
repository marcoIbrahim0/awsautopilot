"""
Risk evaluation for remediation strategies.

The evaluator produces explicit dependency checks so API/UI can require risk
acknowledgement before potentially disruptive changes.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.services.remediation_strategy import RemediationStrategy

CheckStatus = Literal["pass", "warn", "unknown", "fail"]


class DependencyCheck(TypedDict):
    """One dependency/risk check emitted for a strategy selection."""

    code: str
    status: CheckStatus
    message: str


class RiskSnapshot(TypedDict):
    """Serializable risk snapshot persisted to remediation_runs.artifacts."""

    checks: list[DependencyCheck]
    warnings: list[str]
    recommendation: str
    evidence: NotRequired[dict[str, Any]]


def _build_check(code: str, status: CheckStatus, message: str) -> DependencyCheck:
    return {"code": code, "status": status, "message": message}


def has_failing_checks(checks: list[DependencyCheck]) -> bool:
    """True when any check is blocking."""
    return any(check["status"] == "fail" for check in checks)


def requires_risk_ack(checks: list[DependencyCheck]) -> bool:
    """True when explicit acknowledgement is required (warn/unknown)."""
    return any(check["status"] in ("warn", "unknown") for check in checks)


_STRICT_ACCESS_PATH_STRATEGIES = frozenset(
    {
        "s3_bucket_block_public_access_standard",
        "s3_migrate_cloudfront_oac_private",
        "s3_enforce_ssl_strict_deny",
        "ssm_disable_public_document_sharing",
        "snapshot_block_all_sharing",
        "snapshot_block_new_sharing_only",
    }
)
_MEDIUM_HIGH_RISK_LEVELS = {"medium", "high"}


def _specialization_fallback_status(strategy: RemediationStrategy) -> CheckStatus:
    """Promote unspecialized checks to fail for medium/high-risk controls."""
    return "fail" if strategy.get("risk_level") in _MEDIUM_HIGH_RISK_LEVELS else "unknown"


def evaluate_strategy_impact(
    action: Action,
    strategy: RemediationStrategy,
    strategy_inputs: dict[str, Any] | None = None,
    account: AwsAccount | None = None,
    runtime_signals: dict[str, Any] | None = None,
) -> RiskSnapshot:
    """
    Evaluate likely impact/dependencies for the selected strategy.

    Checks are intentionally conservative; unknowns are surfaced and require
    explicit acknowledgement in run creation.
    """
    strategy_inputs = strategy_inputs or {}
    runtime_signals = runtime_signals or {}
    strategy_id = strategy["strategy_id"]
    checks: list[DependencyCheck] = []
    warnings = list(strategy.get("warnings", []))

    if strategy["mode"] == "direct_fix":
        if account is None:
            checks.append(
                _build_check(
                    "direct_fix_account_missing",
                    "fail",
                    "AWS account metadata was not found for this action.",
                )
            )
        elif not account.role_write_arn:
            checks.append(
                _build_check(
                    "direct_fix_writerole_missing",
                    "fail",
                    "WriteRole is required for direct-fix execution.",
                )
            )
        else:
            checks.append(
                _build_check(
                    "direct_fix_writerole_present",
                    "pass",
                    "WriteRole is configured for direct-fix execution.",
                )
            )
        if runtime_signals.get("direct_fix_permission_probe_ok") is False:
            checks.append(
                _build_check(
                    "direct_fix_permission_probe_failed",
                    "fail",
                    str(
                        runtime_signals.get("direct_fix_permission_probe_error")
                        or "Direct-fix permission probe failed for required AWS APIs."
                    ),
                )
            )

    # Strategy-specific dependency checks
    if strategy_id == "config_enable_account_local_delivery":
        checks.append(
            _build_check(
                "config_cost_impact",
                "warn",
                "Enabling AWS Config may increase logging and storage costs.",
            )
        )
    elif strategy_id == "config_enable_centralized_delivery":
        central_bucket_status: CheckStatus = "unknown"
        central_bucket_message = "Verify centralized delivery bucket policy allows AWS Config in this account/region."
        if runtime_signals.get("config_central_bucket_policy_valid") is False:
            central_bucket_status = "fail"
            central_bucket_message = str(
                runtime_signals.get("config_central_bucket_policy_error")
                or "Centralized delivery bucket policy blocks AWS Config in this account/region."
            )
        elif runtime_signals.get("config_central_bucket_policy_valid") is True:
            central_bucket_status = "pass"
            central_bucket_message = "Centralized delivery bucket policy validation passed."
        checks.append(
            _build_check(
                "config_central_bucket_policy",
                central_bucket_status,
                central_bucket_message,
            )
        )
        if runtime_signals.get("config_delivery_bucket_reachable") is False:
            checks.append(
                _build_check(
                    "config_delivery_bucket_unreachable",
                    "fail",
                    str(
                        runtime_signals.get("config_delivery_bucket_error")
                        or "Configured delivery bucket is unreachable from account context."
                    ),
                )
            )
        if strategy_inputs.get("kms_key_arn"):
            kms_status: CheckStatus = "unknown"
            kms_message = "Validate KMS key policy permits AWS Config delivery encryption operations."
            if runtime_signals.get("config_kms_policy_valid") is False:
                kms_status = "fail"
                kms_message = str(
                    runtime_signals.get("config_kms_policy_error")
                    or "KMS key policy blocks AWS Config delivery encryption operations."
                )
            elif runtime_signals.get("config_kms_policy_valid") is True:
                kms_status = "pass"
                kms_message = "KMS policy validation passed for AWS Config delivery."
            checks.append(
                _build_check(
                    "config_kms_policy",
                    kms_status,
                    kms_message,
                )
            )
    elif strategy_id in ("config_keep_exception",):
        checks.append(
            _build_check(
                "config_visibility_gap",
                "warn",
                "Keeping AWS Config disabled reduces asset/configuration change visibility.",
            )
        )
    elif strategy_id == "ssm_disable_public_document_sharing":
        checks.append(
            _build_check(
                "ssm_document_sharing_breakage",
                "warn",
                "Publicly shared SSM document consumers may lose access after enforcement.",
            )
        )
    elif strategy_id == "ssm_keep_public_sharing_exception":
        checks.append(
            _build_check(
                "ssm_public_sharing_exposure",
                "warn",
                "Public document sharing remains enabled and may expose sensitive runbooks.",
            )
        )
    elif strategy_id in ("snapshot_block_all_sharing", "snapshot_block_new_sharing_only"):
        checks.append(
            _build_check(
                "snapshot_sharing_dependency",
                "warn",
                "Confirm no workflows depend on public snapshot sharing before enforcement.",
            )
        )
        public_shares_count = runtime_signals.get("snapshot_public_shares_count")
        if isinstance(public_shares_count, int) and public_shares_count > 0:
            checks.append(
                _build_check(
                    "snapshot_public_shares_present",
                    "warn",
                    f"{public_shares_count} publicly shared snapshot(s) currently exist in this region/account scope.",
                )
            )
        if strategy_id == "snapshot_block_new_sharing_only":
            checks.append(
                _build_check(
                    "snapshot_existing_public_shares",
                    "unknown",
                    "Existing public snapshot shares may remain and need separate cleanup.",
                )
            )
    elif strategy_id == "snapshot_keep_sharing_exception":
        checks.append(
            _build_check(
                "snapshot_public_exposure",
                "warn",
                "Public snapshot sharing can expose sensitive data and AMI lineage.",
            )
        )
    elif strategy_id in (
        "ebs_enable_default_encryption_aws_managed_kms",
        "ebs_enable_default_encryption_aws_managed_kms_pr_bundle",
    ):
        checks.append(
            _build_check(
                "ebs_new_volume_scope",
                "pass",
                "Default encryption applies to newly created volumes; existing volumes are unchanged.",
            )
        )
    elif strategy_id in (
        "ebs_enable_default_encryption_customer_kms",
        "ebs_enable_default_encryption_customer_kms_pr_bundle",
    ):
        checks.append(
            _build_check(
                "ebs_customer_kms_policy",
                "warn",
                "Validate KMS key policy/grants for all required service and compute principals.",
            )
        )
        if runtime_signals.get("ebs_customer_kms_key_valid") is False:
            checks.append(
                _build_check(
                    "ebs_customer_kms_key_invalid",
                    "fail",
                    str(
                        runtime_signals.get("ebs_customer_kms_key_error")
                        or "Selected customer-managed KMS key is invalid for this account/region."
                    ),
                )
            )
    elif strategy_id == "s3_enforce_ssl_strict_deny":
        checks.append(
            _build_check(
                "s3_non_tls_client_breakage",
                "warn",
                "Non-TLS clients and legacy integrations will fail after strict SSL policy enforcement.",
            )
        )
        merge_status: CheckStatus = "warn"
        merge_message = "Strict SSL enforcement can conflict with existing bucket policy statements."
        if runtime_signals.get("s3_policy_analysis_possible") is False:
            merge_status = "fail"
            merge_message = str(
                runtime_signals.get("s3_policy_analysis_error")
                or "Unable to analyze current bucket policy for strict SSL enforcement."
            )
        checks.append(_build_check("s3_policy_merge_risk", merge_status, merge_message))
        if runtime_signals.get("s3_ssl_policy_generation_ok") is False:
            checks.append(
                _build_check(
                    "s3_ssl_policy_generation_failed",
                    "fail",
                    str(
                        runtime_signals.get("s3_ssl_policy_generation_error")
                        or "Unable to generate SSL enforcement policy statements."
                    ),
                )
            )
        estimated_size = runtime_signals.get("s3_ssl_policy_estimated_bytes")
        size_limit = runtime_signals.get("s3_policy_size_limit_bytes", 20 * 1024)
        if isinstance(estimated_size, int) and estimated_size > int(size_limit):
            checks.append(
                _build_check(
                    "s3_ssl_policy_size_exceeded",
                    "fail",
                    f"Estimated SSL bucket policy size {estimated_size} exceeds AWS limit {size_limit}.",
                )
            )
    elif strategy_id == "s3_enforce_ssl_with_principal_exemptions":
        merge_status: CheckStatus = "unknown"
        merge_message = "Review principal exemptions carefully to avoid over-broad bypass paths."
        if runtime_signals.get("s3_policy_analysis_possible") is True:
            merge_status = "warn"
        elif runtime_signals.get("s3_policy_analysis_possible") is False:
            merge_message = str(
                runtime_signals.get("s3_policy_analysis_error")
                or "Unable to analyze current bucket policy while applying exemptions."
            )
        checks.append(
            _build_check(
                "s3_policy_merge_risk",
                merge_status,
                merge_message,
            )
        )
        if runtime_signals.get("s3_ssl_policy_generation_ok") is False:
            checks.append(
                _build_check(
                    "s3_ssl_policy_generation_failed",
                    "fail",
                    str(
                        runtime_signals.get("s3_ssl_policy_generation_error")
                        or "Unable to generate SSL policy with selected principal exemptions."
                    ),
                )
            )
        estimated_size = runtime_signals.get("s3_ssl_policy_estimated_bytes")
        size_limit = runtime_signals.get("s3_policy_size_limit_bytes", 20 * 1024)
        if isinstance(estimated_size, int) and estimated_size > int(size_limit):
            checks.append(
                _build_check(
                    "s3_ssl_policy_size_exceeded",
                    "fail",
                    f"Estimated SSL bucket policy size {estimated_size} exceeds AWS limit {size_limit}.",
                )
            )
    elif strategy_id == "s3_keep_non_ssl_exception":
        checks.append(
            _build_check(
                "s3_non_tls_allowed",
                "warn",
                "Keeping non-SSL traffic allows plaintext request channels.",
            )
        )
    elif strategy_id in ("iam_root_key_disable", "iam_root_key_delete"):
        checks.append(
            _build_check(
                "iam_root_break_glass_review",
                "warn",
                "Confirm break-glass and emergency automation does not depend on root access keys.",
            )
        )
        if strategy_id == "iam_root_key_delete":
            checks.append(
                _build_check(
                    "iam_root_delete_irreversible",
                    "warn",
                    "Root key deletion is irreversible; ensure fallback access is validated.",
                )
            )
    elif strategy_id == "iam_root_key_keep_exception":
        checks.append(
            _build_check(
                "iam_root_key_exposure",
                "warn",
                "Root access keys remain a high-severity compromise path.",
            )
        )
    elif strategy_id in (
        "s3_bucket_block_public_access_standard",
        "s3_migrate_cloudfront_oac_private",
    ):
        checks.append(
            _build_check(
                "s3_public_access_dependency",
                "warn",
                (
                    "Validate direct bucket access dependencies before applying this strategy. "
                    "Analyze the affected S3 bucket policy/ACL/public-access-block settings, "
                    "the bucket KMS key policy/grants (if SSE-KMS), CloudFront OAC/OAI configuration, "
                    "and any VPC endpoint or cross-account IAM principals that access the bucket. "
                    "If IAM Access Analyzer is enabled in this account/region, this validation can be automated."
                ),
            )
        )
    elif strategy_id == "s3_keep_public_exception":
        checks.append(
            _build_check(
                "s3_public_exception",
                "warn",
                "Public access remains enabled; exception must include business approval and review date.",
            )
        )
    else:
        checks.append(
            _build_check(
                "risk_evaluation_not_specialized",
                _specialization_fallback_status(strategy),
                "No specialized dependency checks are available for this strategy yet.",
            )
        )

    if (
        strategy_id in _STRICT_ACCESS_PATH_STRATEGIES
        and runtime_signals.get("access_path_evidence_available") is False
    ):
        checks.append(
            _build_check(
                "access_path_evidence_unavailable",
                "fail",
                str(
                    runtime_signals.get("access_path_evidence_reason")
                    or "Required access-path discovery evidence is unavailable for strict strategy."
                ),
            )
        )

    # Generic sanity signal when no checks were emitted by strategy-specific logic.
    if not checks:
        checks.append(
            _build_check(
                "risk_evaluation_empty",
                _specialization_fallback_status(strategy),
                "Dependency impact could not be fully determined automatically.",
            )
        )

    recommendation = "review_and_acknowledge" if requires_risk_ack(checks) else "safe_to_proceed"
    if has_failing_checks(checks):
        recommendation = "blocked"

    snapshot: RiskSnapshot = {
        "checks": checks,
        "warnings": warnings,
        "recommendation": recommendation,
    }
    evidence_payload = runtime_signals.get("evidence")
    if isinstance(evidence_payload, dict):
        evidence: dict[str, Any] = dict(evidence_payload)
    else:
        evidence = {}
    for key in (
        "collected_at",
        "strategy_id",
        "access_path_evidence_available",
        "access_path_evidence_reason",
    ):
        if key in runtime_signals:
            evidence[key] = runtime_signals.get(key)
    if evidence:
        snapshot["evidence"] = evidence
    return snapshot
