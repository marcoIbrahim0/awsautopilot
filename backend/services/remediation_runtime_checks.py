"""
Runtime risk probes for remediation strategy gating.

These checks are intentionally incremental and non-mutating. They collect
high-signal evidence before run creation to reduce avoidable runtime failures.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.services.aws import assume_role
from backend.services.remediation_strategy import RemediationStrategy

logger = logging.getLogger(__name__)

_ACCESS_DENIED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "UnauthorizedException",
}
_S3_POLICY_MAX_BYTES = 20 * 1024
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
_KMS_ARN_PATTERN = re.compile(
    r"^arn:(aws|aws-us-gov|aws-cn):kms:[a-z0-9-]+:\d{12}:(key|alias)/[A-Za-z0-9/_+=,.@-]+$"
)
_S3_BUCKET_ARN_PATTERN = re.compile(r"arn:aws:s3:::(?P<bucket>[A-Za-z0-9.\-_]{3,63})")


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", "")).strip()


def _error_message(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Message", "")).strip()


def _is_access_denied(exc: ClientError) -> bool:
    code = _error_code(exc)
    if code in _ACCESS_DENIED_CODES:
        return True
    message = _error_message(exc).lower()
    return "access denied" in message or "not authorized" in message


def _bucket_name_from_target_id(target_id: str | None) -> str | None:
    if target_id is None:
        return None
    if not isinstance(target_id, str):
        return None
    tid = target_id.strip()
    if not tid:
        return None

    match = _S3_BUCKET_ARN_PATTERN.search(tid)
    if match:
        return match.group("bucket")

    if "|" in tid:
        for part in tid.split("|"):
            part = part.strip()
            match = _S3_BUCKET_ARN_PATTERN.search(part)
            if match:
                return match.group("bucket")
        return None

    if tid.startswith("arn:aws:s3:::"):
        candidate = tid.split("arn:aws:s3:::")[-1].split("/")[0].strip()
        return candidate or None

    return tid


def _estimate_ssl_policy_size_bytes(bucket: str, exempt_principals: list[str]) -> int:
    statements: list[dict[str, Any]] = [
        {
            "Sid": "DenyInsecureTransport",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                f"arn:aws:s3:::{bucket}",
                f"arn:aws:s3:::{bucket}/*",
            ],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
        }
    ]
    if exempt_principals:
        statements.append(
            {
                "Sid": "AllowExemptPrincipals",
                "Effect": "Allow",
                "Principal": {"AWS": exempt_principals},
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*",
                ],
            }
        )
    doc = {"Version": "2012-10-17", "Statement": statements}
    return len(json.dumps(doc, separators=(",", ":")))


def _normalize_bucket_policy_document(policy_json: str | None) -> str | None:
    """Return canonical bucket-policy JSON string or None when invalid."""
    if not isinstance(policy_json, str):
        return None
    raw = policy_json.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None

    statements = parsed.get("Statement")
    if statements is None:
        parsed["Statement"] = []
    elif isinstance(statements, dict):
        parsed["Statement"] = [statements]
    elif not isinstance(statements, list):
        return None

    return json.dumps(parsed, separators=(",", ":"), sort_keys=True)


def _policy_statement_count(policy_json: str | None) -> int:
    """Count policy statements from normalized/raw policy JSON."""
    normalized = _normalize_bucket_policy_document(policy_json)
    if not normalized:
        return 0
    parsed = json.loads(normalized)
    statements = parsed.get("Statement")
    if isinstance(statements, list):
        return len(statements)
    if isinstance(statements, dict):
        return 1
    return 0


def probe_direct_fix_permissions(action: Action, account: AwsAccount) -> tuple[bool | None, str | None]:
    """
    Non-mutating direct-fix permission probe.

    Returns:
      - (False, msg): deterministic permission failure (should block run creation)
      - (True, None): probe succeeded / known non-permission state
      - (None, msg): probe unavailable (do not block solely on this signal)
    """
    role_arn = (account.role_write_arn or "").strip()
    external_id = (account.external_id or "").strip()
    if not role_arn or not external_id:
        return None, "WriteRole probe skipped: missing role or external_id."

    try:
        session = assume_role(role_arn=role_arn, external_id=external_id)
    except ClientError as exc:
        if _is_access_denied(exc):
            code = _error_code(exc) or "AccessDenied"
            return False, f"WriteRole assume-role denied ({code})."
        return None, f"WriteRole probe unavailable: {_error_code(exc) or 'ClientError'}."
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"WriteRole probe unavailable: {exc}"

    action_type = (action.action_type or "").strip().lower()
    account_id = (action.account_id or "").strip()
    region = (action.region or "").strip()
    try:
        if action_type == "s3_block_public_access":
            # S3 account-level Public Access Block is global-to-account but S3Control is a regional endpoint.
            # Default to the session/config region (eu-north-1 in this repo) unless an explicit action region is provided.
            s3c_region = region or session.region_name or "eu-north-1"
            s3c = session.client("s3control", region_name=s3c_region)
            try:
                s3c.get_public_access_block(AccountId=account_id)
            except ClientError as exc:
                if _error_code(exc) == "NoSuchPublicAccessBlockConfiguration":
                    return True, None
                raise
            return True, None

        if action_type == "enable_security_hub":
            if not region:
                return False, "Region is required for Security Hub remediation."
            sh = session.client("securityhub", region_name=region)
            try:
                sh.get_enabled_standards(MaxResults=1)
            except ClientError as exc:
                code = _error_code(exc)
                # Not enabled yet is expected for remediation targets.
                if code in {"InvalidAccessException", "ResourceNotFoundException"}:
                    return True, None
                raise
            return True, None

        if action_type == "enable_guardduty":
            if not region:
                return False, "Region is required for GuardDuty remediation."
            gd = session.client("guardduty", region_name=region)
            gd.list_detectors()
            return True, None

        if action_type == "ebs_default_encryption":
            if not region:
                return False, "Region is required for EBS default encryption remediation."
            ec2 = session.client("ec2", region_name=region)
            ec2.get_ebs_encryption_by_default()
            return True, None

        return None, f"Direct-fix probe not implemented for action_type '{action_type}'."
    except ClientError as exc:
        code = _error_code(exc) or "ClientError"
        if _is_access_denied(exc):
            return False, f"WriteRole probe denied by AWS API ({code})."
        return None, f"WriteRole probe unavailable: {code}."
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"WriteRole probe unavailable: {exc}"


def collect_runtime_risk_signals(
    action: Action,
    strategy: RemediationStrategy,
    strategy_inputs: dict[str, Any] | None,
    account: AwsAccount | None,
) -> dict[str, Any]:
    """
    Collect optional runtime signals for strategy risk evaluation.

    Signals are best-effort and non-mutating. Missing signals should not be
    interpreted as success.
    """
    strategy_inputs = strategy_inputs or {}
    strategy_id = strategy["strategy_id"]
    signals: dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": strategy_id,
        "evidence": {},
    }

    read_session = None
    read_probe_error: str | None = None

    def _get_read_session():
        nonlocal read_session, read_probe_error
        if read_session is not None:
            return read_session
        if read_probe_error is not None:
            return None
        if account is None:
            read_probe_error = "AWS account metadata missing for runtime probes."
            return None
        role_arn = (account.role_read_arn or "").strip()
        external_id = (account.external_id or "").strip()
        if not role_arn or not external_id:
            read_probe_error = "ReadRole is not configured for runtime probes."
            return None
        try:
            read_session = assume_role(role_arn=role_arn, external_id=external_id)
            return read_session
        except Exception as exc:  # pragma: no cover - network-dependent
            read_probe_error = str(exc)
            return None

    def _mark_access_path_unavailable(reason: str) -> None:
        signals["access_path_evidence_available"] = False
        if "access_path_evidence_reason" not in signals:
            signals["access_path_evidence_reason"] = reason

    is_access_path_strategy = strategy_id in _STRICT_ACCESS_PATH_STRATEGIES
    if is_access_path_strategy:
        if account is not None:
            session = _get_read_session()
            if session is None:
                _mark_access_path_unavailable(read_probe_error or "ReadRole runtime probe unavailable.")
            else:
                signals["access_path_evidence_available"] = True

    if strategy_id == "config_enable_centralized_delivery":
        bucket = str(strategy_inputs.get("delivery_bucket", "")).strip()
        if bucket:
            signals["evidence"]["delivery_bucket"] = bucket
            session = _get_read_session()
            if session is None:
                _mark_access_path_unavailable(read_probe_error or "Unable to validate Config delivery bucket.")
            else:
                s3 = session.client("s3")
                try:
                    s3.head_bucket(Bucket=bucket)
                    signals["config_delivery_bucket_reachable"] = True
                    signals["config_central_bucket_policy_valid"] = True
                except ClientError as exc:
                    code = _error_code(exc) or "HeadBucketFailed"
                    signals["config_delivery_bucket_reachable"] = False
                    signals["config_delivery_bucket_error"] = code
                    if _is_access_denied(exc):
                        signals["config_central_bucket_policy_valid"] = False
                        signals["config_central_bucket_policy_error"] = (
                            "Centralized delivery bucket access is denied for this account context."
                        )
        kms_key_arn = str(strategy_inputs.get("kms_key_arn", "")).strip()
        if kms_key_arn:
            session = _get_read_session()
            if not _KMS_ARN_PATTERN.match(kms_key_arn):
                signals["config_kms_policy_valid"] = False
                signals["config_kms_policy_error"] = "kms_key_arn is not a valid KMS ARN."
            elif session is not None:
                arn_parts = kms_key_arn.split(":", 5)
                kms_region = arn_parts[3] if len(arn_parts) > 4 else ""
                kms = session.client("kms", region_name=action.region or kms_region or None)
                try:
                    key_metadata = kms.describe_key(KeyId=kms_key_arn).get("KeyMetadata", {})
                    if key_metadata.get("KeyState") != "Enabled":
                        signals["config_kms_policy_valid"] = False
                        signals["config_kms_policy_error"] = "Configured KMS key is not enabled."
                    else:
                        signals["config_kms_policy_valid"] = True
                except ClientError as exc:
                    signals["config_kms_policy_valid"] = False
                    signals["config_kms_policy_error"] = _error_code(exc) or "DescribeKeyFailed"

    if strategy_id in (
        "ebs_enable_default_encryption_customer_kms",
        "ebs_enable_default_encryption_customer_kms_pr_bundle",
    ):
        kms_key_arn = str(strategy_inputs.get("kms_key_arn", "")).strip()
        if kms_key_arn:
            signals["evidence"]["kms_key_arn"] = kms_key_arn
            if not _KMS_ARN_PATTERN.match(kms_key_arn):
                signals["ebs_customer_kms_key_valid"] = False
                signals["ebs_customer_kms_key_error"] = "kms_key_arn is not a valid KMS ARN."
            else:
                arn_parts = kms_key_arn.split(":", 5)
                kms_region = arn_parts[3] if len(arn_parts) > 4 else ""
                kms_account_id = arn_parts[4] if len(arn_parts) > 5 else ""
                if action.region and kms_region and kms_region != action.region:
                    signals["ebs_customer_kms_key_valid"] = False
                    signals["ebs_customer_kms_key_error"] = (
                        f"KMS key region {kms_region} does not match action region {action.region}."
                    )
                elif account is not None and kms_account_id and kms_account_id != account.account_id:
                    signals["ebs_customer_kms_key_valid"] = False
                    signals["ebs_customer_kms_key_error"] = (
                        f"KMS key account {kms_account_id} does not match action account {account.account_id}."
                    )
                else:
                    session = _get_read_session()
                    if session is not None:
                        kms = session.client("kms", region_name=action.region or kms_region or None)
                        try:
                            key_metadata = kms.describe_key(KeyId=kms_key_arn).get("KeyMetadata", {})
                            if key_metadata.get("KeyState") != "Enabled":
                                signals["ebs_customer_kms_key_valid"] = False
                                signals["ebs_customer_kms_key_error"] = "KMS key is not enabled."
                            else:
                                signals["ebs_customer_kms_key_valid"] = True
                        except ClientError as exc:
                            signals["ebs_customer_kms_key_valid"] = False
                            signals["ebs_customer_kms_key_error"] = _error_code(exc) or "DescribeKeyFailed"

    if strategy_id in ("s3_enforce_ssl_strict_deny", "s3_enforce_ssl_with_principal_exemptions"):
        bucket = _bucket_name_from_target_id(action.target_id)
        exempt_principals = strategy_inputs.get("exempt_principals")
        if not isinstance(exempt_principals, list):
            exempt_principals = []
        exempt_principals = [str(v).strip() for v in exempt_principals if str(v).strip()]
        if not bucket:
            signals["s3_ssl_policy_generation_ok"] = False
            signals["s3_ssl_policy_generation_error"] = "Could not derive bucket name from action target."
            if is_access_path_strategy and account is not None:
                _mark_access_path_unavailable("Missing bucket identifier for SSL policy analysis.")
        else:
            signals["evidence"]["target_bucket"] = bucket
            signals["s3_ssl_policy_generation_ok"] = True
            signals["s3_ssl_policy_estimated_bytes"] = _estimate_ssl_policy_size_bytes(
                bucket=bucket,
                exempt_principals=exempt_principals,
            )
            session = _get_read_session()
            if session is None:
                if is_access_path_strategy and account is not None:
                    _mark_access_path_unavailable(read_probe_error or "Unable to read current bucket policy.")
            else:
                s3 = session.client("s3")
                try:
                    s3.get_bucket_policy(Bucket=bucket)
                    signals["s3_policy_analysis_possible"] = True
                except ClientError as exc:
                    code = _error_code(exc)
                    if code == "NoSuchBucketPolicy":
                        signals["s3_policy_analysis_possible"] = True
                    else:
                        signals["s3_policy_analysis_possible"] = False
                        signals["s3_policy_analysis_error"] = code or "GetBucketPolicyFailed"
                        if is_access_path_strategy and account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to inspect current bucket policy ({code or 'GetBucketPolicyFailed'})."
                            )

    if strategy_id in ("s3_bucket_block_public_access_standard", "s3_migrate_cloudfront_oac_private"):
        bucket = _bucket_name_from_target_id(action.target_id)
        if bucket:
            signals["evidence"]["target_bucket"] = bucket
            session = _get_read_session()
            if session is None:
                if account is not None:
                    _mark_access_path_unavailable(read_probe_error or "Unable to inspect bucket access posture.")
            else:
                s3 = session.client("s3")
                try:
                    policy_status = s3.get_bucket_policy_status(Bucket=bucket).get("PolicyStatus", {})
                    signals["s3_bucket_policy_public"] = bool(policy_status.get("IsPublic"))
                except ClientError as exc:
                    code = _error_code(exc)
                    if code == "NoSuchBucketPolicy":
                        signals["s3_bucket_policy_public"] = False
                    elif code not in {"NoSuchBucket"}:
                        if account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to inspect bucket policy status ({code or 'GetBucketPolicyStatusFailed'})."
                            )
                if strategy_id == "s3_migrate_cloudfront_oac_private":
                    try:
                        raw_policy = s3.get_bucket_policy(Bucket=bucket).get("Policy")
                        normalized_policy = _normalize_bucket_policy_document(raw_policy)
                        if normalized_policy is not None:
                            statement_count = _policy_statement_count(normalized_policy)
                            evidence_payload = signals.setdefault("evidence", {})
                            if isinstance(evidence_payload, dict):
                                evidence_payload["existing_bucket_policy_statement_count"] = statement_count
                                if statement_count > 0:
                                    evidence_payload["existing_bucket_policy_json"] = normalized_policy
                        else:
                            evidence_payload = signals.setdefault("evidence", {})
                            if isinstance(evidence_payload, dict):
                                evidence_payload["existing_bucket_policy_parse_error"] = (
                                    "GetBucketPolicy returned invalid JSON."
                                )
                    except ClientError as exc:
                        code = _error_code(exc)
                        evidence_payload = signals.setdefault("evidence", {})
                        if isinstance(evidence_payload, dict):
                            if code == "NoSuchBucketPolicy":
                                evidence_payload["existing_bucket_policy_statement_count"] = 0
                            else:
                                evidence_payload["existing_bucket_policy_capture_error"] = code or "GetBucketPolicyFailed"
                        if code not in {"NoSuchBucketPolicy", "NoSuchBucket"} and account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to capture existing bucket policy ({code or 'GetBucketPolicyFailed'})."
                            )
                try:
                    s3.get_bucket_website(Bucket=bucket)
                    signals["s3_bucket_website_configured"] = True
                except ClientError as exc:
                    code = _error_code(exc)
                    if code == "NoSuchWebsiteConfiguration":
                        signals["s3_bucket_website_configured"] = False
                    elif code not in {"NoSuchBucket"}:
                        if account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to inspect bucket website configuration ({code or 'GetBucketWebsiteFailed'})."
                            )
        else:
            if account is not None:
                _mark_access_path_unavailable("Missing bucket identifier for access-path validation.")

    if strategy_id in ("snapshot_block_all_sharing", "snapshot_block_new_sharing_only"):
        session = _get_read_session()
        if session is not None:
            ec2 = session.client("ec2", region_name=action.region or None)
            try:
                resp = ec2.describe_snapshots(
                    OwnerIds=["self"],
                    Filters=[{"Name": "create-volume-permission.group", "Values": ["all"]}],
                    MaxResults=200,
                )
                snapshots = resp.get("Snapshots", [])
                signals["snapshot_public_shares_count"] = len(snapshots) if isinstance(snapshots, list) else 0
            except ClientError as exc:
                signals["snapshot_public_shares_error"] = _error_code(exc) or "DescribeSnapshotsFailed"

    evidence = signals.get("evidence")
    if isinstance(evidence, dict) and not evidence:
        signals.pop("evidence", None)

    # If no meaningful signal beyond metadata was produced, return empty.
    meaningful_keys = set(signals.keys()) - {"collected_at", "strategy_id", "evidence"}
    if not meaningful_keys and "evidence" not in signals:
        return {}

    # Include policy size threshold for evaluator diagnostics.
    signals["s3_policy_size_limit_bytes"] = _S3_POLICY_MAX_BYTES
    return signals


__all__ = [
    "collect_runtime_risk_signals",
    "probe_direct_fix_permissions",
]
