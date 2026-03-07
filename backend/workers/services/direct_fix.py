"""
Direct fix executor service (Step 8.2): pre-check, apply, post-check for safe remediations.

Runs a three-phase flow for each fix:
  1. Pre-check: Verify current state. If already compliant, return success with
     "Already compliant; no change needed" (idempotent). If pre-check fails
     (e.g. org policy blocking), return failure with clear message.
  2. Apply: Execute the remediation (S3 Control, Security Hub, or GuardDuty API).
  3. Post-check: Verify the fix took effect. If post-check fails, run is failed;
     do not mark finding as resolved.

Supports action types for low-risk direct fixes:
  - s3_block_public_access: Account-level S3 Block Public Access (all four settings)
  - enable_security_hub: Enable Security Hub in region
  - enable_guardduty: Enable GuardDuty in region
  - ebs_default_encryption: Enable default EBS encryption (AWS-managed or customer KMS)

All fixes are idempotent and safe to re-run. Receives an already-assumed boto3
session (WriteRole) from the worker; logs each phase for remediation_runs.logs
(audit trail).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

__all__ = [
    "DirectFixResult",
    "RemediationPreviewResult",
    "run_direct_fix",
    "run_remediation_preview",
    "SUPPORTED_ACTION_TYPES",
]

# Action types supported by this executor (Step 8.2; only these get direct fix)
SUPPORTED_ACTION_TYPES = frozenset(
    {"s3_block_public_access", "enable_security_hub", "enable_guardduty", "ebs_default_encryption"}
)

# Log phase prefixes for audit trail (remediation_runs.logs)
_LOG_PRE_CHECK = "Pre-check:"
_LOG_APPLY = "Apply:"
_LOG_POST_CHECK = "Post-check:"


@dataclass(frozen=True)
class DirectFixResult:
    """Result of a direct fix execution."""

    success: bool
    outcome: str
    logs: list[str]

    def log_text(self) -> str:
        """Join logs with newlines for storage in remediation_runs.logs."""
        return "\n".join(self.logs)


@dataclass(frozen=True)
class RemediationPreviewResult:
    """Result of a pre-check-only (dry-run) for remediation preview."""

    compliant: bool
    message: str
    will_apply: bool
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    diff_lines: list[dict[str, str]] = field(default_factory=list)


def run_direct_fix(
    session: boto3.Session,
    action_type: str,
    account_id: str,
    region: str | None,
    strategy_id: str | None = None,
    strategy_inputs: dict | None = None,
    *,
    run_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
) -> DirectFixResult:
    """
    Run direct fix: pre-check, apply, post-check (Step 8.2 executor).

    Caller must have already assumed WriteRole; this function uses the provided
    session for the customer account. Appends each phase to logs for
    remediation_runs.logs (audit trail). Idempotent: if already compliant,
    returns success with outcome "Already compliant; no change needed".

    Args:
        session: boto3 session with assumed WriteRole (customer account).
        action_type: One of s3_block_public_access, enable_security_hub, enable_guardduty.
        account_id: AWS account ID.
        region: AWS region (required for Security Hub and GuardDuty; None for S3 account-level).
        run_id: Optional remediation run ID for audit logs.
        action_id: Optional action ID for audit logs.

    Returns:
        DirectFixResult(success, outcome, logs) for remediation_runs.
    """
    if action_type not in SUPPORTED_ACTION_TYPES:
        return DirectFixResult(
            success=False,
            outcome=f"Unsupported action_type: {action_type}. Supported: {', '.join(sorted(SUPPORTED_ACTION_TYPES))}.",
            logs=[f"Unsupported action_type: {action_type}."],
        )

    if action_type == "s3_block_public_access":
        return _fix_s3_block_public_access(session, account_id, run_id=run_id, action_id=action_id)
    if action_type == "enable_security_hub":
        return _fix_enable_security_hub(session, account_id, region, run_id=run_id, action_id=action_id)
    if action_type == "enable_guardduty":
        return _fix_enable_guardduty(session, account_id, region, run_id=run_id, action_id=action_id)
    if action_type == "ebs_default_encryption":
        return _fix_ebs_default_encryption(
            session,
            account_id,
            region,
            strategy_id=strategy_id,
            strategy_inputs=strategy_inputs,
            run_id=run_id,
            action_id=action_id,
        )

    # Unreachable
    return DirectFixResult(success=False, outcome=f"Unknown action_type: {action_type}", logs=[])


def run_remediation_preview(
    session: boto3.Session,
    action_type: str,
    account_id: str,
    region: str | None,
    strategy_id: str | None = None,
    strategy_inputs: dict | None = None,
) -> RemediationPreviewResult:
    """
    Run pre-check only (dry-run) for remediation preview (Step 8.4).

    Does not apply any fix. Returns compliant, message, and will_apply (True when
    not compliant and fix would be applied). Used by GET /api/actions/{id}/remediation-preview.
    """
    if action_type not in SUPPORTED_ACTION_TYPES:
        return RemediationPreviewResult(
            compliant=False,
            message=f"Unsupported action_type: {action_type}",
            will_apply=False,
        )

    if action_type == "s3_block_public_access":
        compliant, message = _precheck_s3_block_public_access(session, account_id)
    elif action_type == "enable_security_hub":
        compliant, message = _precheck_enable_security_hub(session, account_id, region)
    elif action_type == "enable_guardduty":
        compliant, message = _precheck_enable_guardduty(session, account_id, region)
    elif action_type == "ebs_default_encryption":
        compliant, message = _precheck_ebs_default_encryption(
            session,
            account_id,
            region,
            strategy_id=strategy_id,
            strategy_inputs=strategy_inputs,
        )
    else:
        compliant, message = False, f"Unknown action_type: {action_type}"

    # will_apply: not compliant and no pre-check error (fix would run)
    will_apply = not compliant and "failed" not in message.lower() and "error" not in message.lower()
    return RemediationPreviewResult(compliant=compliant, message=message, will_apply=will_apply)


def _precheck_s3_block_public_access(session: boto3.Session, account_id: str) -> tuple[bool, str]:
    """Pre-check S3 Block Public Access. Returns (compliant, message)."""
    try:
        s3c = session.client("s3control", region_name="us-east-1")
        resp = s3c.get_public_access_block(AccountId=account_id)
        config = resp.get("PublicAccessBlockConfiguration", {})
        all_true = (
            config.get("BlockPublicAcls") is True
            and config.get("IgnorePublicAcls") is True
            and config.get("BlockPublicPolicy") is True
            and config.get("RestrictPublicBuckets") is True
        )
        if all_true:
            return True, "S3 Block Public Access already enabled (all four settings True)."
        return False, "S3 Block Public Access not fully configured; will enable all four settings."
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "NoSuchPublicAccessBlockConfiguration":
            return False, "S3 Block Public Access not configured; will enable."
        return False, f"Pre-check failed: {code}"
    except Exception as e:
        return False, f"Pre-check error: {e}"


def _precheck_enable_security_hub(
    session: boto3.Session, account_id: str, region: str | None
) -> tuple[bool, str]:
    """Pre-check Security Hub. Returns (compliant, message)."""
    if not region:
        return False, "Region required for Security Hub enablement."
    try:
        sh = session.client("securityhub", region_name=region)
        resp = sh.get_enabled_standards()
        standards = resp.get("StandardsSubscriptions", [])
        if standards:
            return True, f"Security Hub already enabled ({len(standards)} standards)."
        return False, "Security Hub not enabled; will enable with default standards."
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("InvalidAccessException", "ResourceNotFoundException"):
            return False, "Security Hub not enabled; will enable."
        return False, f"Pre-check failed: {code}"
    except Exception as e:
        return False, f"Pre-check error: {e}"


def _precheck_enable_guardduty(
    session: boto3.Session, account_id: str, region: str | None
) -> tuple[bool, str]:
    """Pre-check GuardDuty. Returns (compliant, message)."""
    if not region:
        return False, "Region required for GuardDuty enablement."
    try:
        gd = session.client("guardduty", region_name=region)
        resp = gd.list_detectors()
        detector_ids = resp.get("DetectorIds", [])
        for did in detector_ids:
            get_resp = gd.get_detector(DetectorId=did)
            if get_resp.get("Status") == "ENABLED":
                return True, "GuardDuty already enabled."
        if detector_ids:
            return False, "GuardDuty detector exists but disabled; will enable."
        return False, "GuardDuty not enabled; will create detector."
    except Exception as e:
        return False, f"Pre-check error: {e}"


def _precheck_ebs_default_encryption(
    session: boto3.Session,
    account_id: str,
    region: str | None,
    strategy_id: str | None = None,
    strategy_inputs: dict | None = None,
) -> tuple[bool, str]:
    """Pre-check EBS default encryption and optional default KMS key."""
    if not region:
        return False, "Region required for EBS default encryption."

    strategy = (strategy_id or "ebs_enable_default_encryption_aws_managed_kms").strip().lower()
    requires_customer_kms = "customer_kms" in strategy
    desired_kms = ""
    if requires_customer_kms:
        desired_kms = str((strategy_inputs or {}).get("kms_key_arn", "")).strip()
        if not desired_kms:
            return False, "strategy_inputs.kms_key_arn is required for customer KMS strategy."

    ec2 = session.client("ec2", region_name=region)
    try:
        enc = ec2.get_ebs_encryption_by_default()
        enabled = bool(enc.get("EbsEncryptionByDefault"))
        if not enabled:
            return False, "EBS default encryption is disabled; fix will enable it."
        if requires_customer_kms:
            current_kms = ec2.get_ebs_default_kms_key_id().get("KmsKeyId", "")
            if current_kms == desired_kms:
                return True, "EBS default encryption is enabled with the selected customer KMS key."
            return False, "EBS default encryption enabled, but default KMS key differs from selected key."
        return True, "EBS default encryption is already enabled."
    except Exception as e:
        return False, f"Pre-check error: {e}"


def _fix_s3_block_public_access(
    session: boto3.Session,
    account_id: str,
    *,
    run_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
) -> DirectFixResult:
    """
    Fix 1 — S3 Block Public Access (action_type: s3_block_public_access).

    Scope: account-level; region is NULL. Pre-check: get_public_access_block;
    if all four settings True, return "Already compliant". Apply: put_public_access_block
    with BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets = True.
    Post-check: get_public_access_block again; verify all four True.
    """
    logs: list[str] = []
    s3c = session.client("s3control", region_name="us-east-1")  # S3 Control uses us-east-1 for account-level

    # Pre-check (Step 8.2: verify current state; if compliant, return idempotent success)
    logs.append(f"{_LOG_PRE_CHECK} get_public_access_block")
    try:
        resp = s3c.get_public_access_block(AccountId=account_id)
        config = resp.get("PublicAccessBlockConfiguration", {})
        all_true = (
            config.get("BlockPublicAcls") is True
            and config.get("IgnorePublicAcls") is True
            and config.get("BlockPublicPolicy") is True
            and config.get("RestrictPublicBuckets") is True
        )
        if all_true:
            logs.append(f"{_LOG_PRE_CHECK} Already compliant (all four settings True).")
            return DirectFixResult(
                success=True,
                outcome="Already compliant; no change needed",
                logs=logs,
            )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "NoSuchPublicAccessBlockConfiguration":
            logs.append(f"{_LOG_PRE_CHECK} No block public access config; will apply.")
        else:
            logs.append(f"{_LOG_PRE_CHECK} failed: {code} - {e}")
            return DirectFixResult(success=False, outcome=f"Pre-check failed: {code}", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_PRE_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Pre-check error: {e}", logs=logs)

    # Apply (Step 8.2: execute remediation)
    logs.append(f"{_LOG_APPLY} put_public_access_block (all four True)")
    try:
        s3c.put_public_access_block(
            AccountId=account_id,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        logs.append(f"{_LOG_APPLY} Success.")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        logs.append(f"{_LOG_APPLY} failed: {code} - {msg}")
        return DirectFixResult(success=False, outcome=f"Apply failed: {code}", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_APPLY} error: {e}")
        return DirectFixResult(success=False, outcome=f"Apply error: {e}", logs=logs)

    # Post-check (Step 8.2: verify fix took effect; if not, run is failed)
    logs.append(f"{_LOG_POST_CHECK} get_public_access_block")
    try:
        resp = s3c.get_public_access_block(AccountId=account_id)
        config = resp.get("PublicAccessBlockConfiguration", {})
        all_true = (
            config.get("BlockPublicAcls") is True
            and config.get("IgnorePublicAcls") is True
            and config.get("BlockPublicPolicy") is True
            and config.get("RestrictPublicBuckets") is True
        )
        if all_true:
            logs.append(f"{_LOG_POST_CHECK} Verified all four settings True.")
            return DirectFixResult(
                success=True,
                outcome="S3 Block Public Access enabled at account level",
                logs=logs,
            )
        logs.append(f"{_LOG_POST_CHECK} Settings not all True: {config}")
        return DirectFixResult(
            success=False,
            outcome="Post-check failed: settings not fully applied",
            logs=logs,
        )
    except Exception as e:
        logs.append(f"{_LOG_POST_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Post-check failed: {e}", logs=logs)


def _fix_enable_security_hub(
    session: boto3.Session,
    account_id: str,
    region: str,
    *,
    run_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
) -> DirectFixResult:
    """
    Fix 2 — Security Hub enablement (action_type: enable_security_hub).

    Scope: per-region; region is required. Pre-check: get_enabled_standards;
    if any standards enabled, return "Already compliant". Apply: enable_security_hub(EnableDefaultStandards=True).
    Post-check: get_enabled_standards; verify Security Hub enabled.
    """
    if not region:
        return DirectFixResult(
            success=False,
            outcome="Region required for Security Hub enablement",
            logs=["Region is required for enable_security_hub."],
        )

    logs: list[str] = []
    sh = session.client("securityhub", region_name=region)

    # Pre-check
    logs.append(f"{_LOG_PRE_CHECK} get_enabled_standards")
    try:
        resp = sh.get_enabled_standards()
        standards = resp.get("StandardsSubscriptions", [])
        if standards:
            logs.append(f"{_LOG_PRE_CHECK} Security Hub already enabled ({len(standards)} standards).")
            return DirectFixResult(
                success=True,
                outcome="Already compliant; no change needed",
                logs=logs,
            )
        logs.append(f"{_LOG_PRE_CHECK} No standards enabled; will enable.")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("InvalidAccessException", "ResourceNotFoundException"):
            logs.append(f"{_LOG_PRE_CHECK} Security Hub not enabled; will enable.")
        else:
            logs.append(f"{_LOG_PRE_CHECK} failed: {code} - {e}")
            return DirectFixResult(success=False, outcome=f"Pre-check failed: {code}", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_PRE_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Pre-check error: {e}", logs=logs)

    # Apply
    logs.append(f"{_LOG_APPLY} enable_security_hub")
    try:
        sh.enable_security_hub(EnableDefaultStandards=True)
        logs.append(f"{_LOG_APPLY} Success.")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        logs.append(f"{_LOG_APPLY} failed: {code} - {msg}")
        return DirectFixResult(success=False, outcome=f"Apply failed: {code}", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_APPLY} error: {e}")
        return DirectFixResult(success=False, outcome=f"Apply error: {e}", logs=logs)

    # Post-check
    logs.append(f"{_LOG_POST_CHECK} get_enabled_standards")
    try:
        resp = sh.get_enabled_standards()
        standards = resp.get("StandardsSubscriptions", [])
        if standards:
            logs.append(f"{_LOG_POST_CHECK} Verified Security Hub enabled ({len(standards)} standards).")
            return DirectFixResult(
                success=True,
                outcome="Security Hub enabled",
                logs=logs,
            )
        logs.append(f"{_LOG_POST_CHECK} No standards found after enable.")
        return DirectFixResult(
            success=False,
            outcome="Post-check failed: Security Hub may not have enabled correctly",
            logs=logs,
        )
    except Exception as e:
        logs.append(f"{_LOG_POST_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Post-check failed: {e}", logs=logs)


def _fix_enable_guardduty(
    session: boto3.Session,
    account_id: str,
    region: str,
    *,
    run_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
) -> DirectFixResult:
    """
    Fix 3 — GuardDuty enablement (action_type: enable_guardduty).

    Scope: per-region; region is required. Pre-check: list_detectors; if detector
    exists and status ENABLED, return "Already compliant". Apply: create_detector(Enable=True)
    or update_detector(Enable=True) if detector exists but disabled. Post-check: get_detector; verify ENABLED.
    """
    if not region:
        return DirectFixResult(
            success=False,
            outcome="Region required for GuardDuty enablement",
            logs=["Region is required for enable_guardduty."],
        )

    logs: list[str] = []
    gd = session.client("guardduty", region_name=region)

    # Pre-check
    logs.append(f"{_LOG_PRE_CHECK} list_detectors")
    try:
        resp = gd.list_detectors()
        detector_ids = resp.get("DetectorIds", [])
        if detector_ids:
            for did in detector_ids:
                get_resp = gd.get_detector(DetectorId=did)
                if get_resp.get("Status") == "ENABLED":
                    logs.append(f"{_LOG_PRE_CHECK} GuardDuty already enabled.")
                    return DirectFixResult(
                        success=True,
                        outcome="Already compliant; no change needed",
                        logs=logs,
                    )
            logs.append(f"{_LOG_PRE_CHECK} Detector exists but disabled; will enable.")
        else:
            logs.append(f"{_LOG_PRE_CHECK} No detector; will create.")
    except ClientError as e:
        logs.append(f"{_LOG_PRE_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Pre-check failed: {e}", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_PRE_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Pre-check error: {e}", logs=logs)

    # Apply
    logs.append(f"{_LOG_APPLY} create_detector(Enable=True)")
    try:
        resp = gd.create_detector(Enable=True)
        detector_id = resp.get("DetectorId", "")
        logs.append(f"{_LOG_APPLY} Created detector {detector_id}.")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        if code == "BadRequestException" and "already has a guardduty detector" in str(msg).lower():
            # Idempotency: detector already exists, fetch and enable if needed
            list_resp = gd.list_detectors()
            ids = list_resp.get("DetectorIds", [])
            if ids:
                logs.append(f"{_LOG_APPLY} Detector already exists ({ids[0]}); verifying enabled.")
                detector_id = ids[0]
                get_resp = gd.get_detector(DetectorId=detector_id)
                if get_resp.get("Status") == "ENABLED":
                    logs.append(f"{_LOG_POST_CHECK} GuardDuty enabled.")
                    return DirectFixResult(success=True, outcome="GuardDuty enabled", logs=logs)
                gd.update_detector(DetectorId=detector_id, Enable=True)
                logs.append(f"{_LOG_APPLY} Enabled existing detector.")
                logs.append(f"{_LOG_POST_CHECK} GuardDuty enabled.")
                return DirectFixResult(success=True, outcome="GuardDuty enabled", logs=logs)
            logs.append(f"{_LOG_APPLY} failed: {code} - {msg}")
            return DirectFixResult(success=False, outcome=f"Apply failed: {code}", logs=logs)
        logs.append(f"{_LOG_APPLY} failed: {code} - {msg}")
        return DirectFixResult(success=False, outcome=f"Apply failed: {code}", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_APPLY} error: {e}")
        return DirectFixResult(success=False, outcome=f"Apply error: {e}", logs=logs)

    # Post-check (when we created a new detector)
    detector_id = resp.get("DetectorId", "")
    if detector_id:
        logs.append(f"{_LOG_POST_CHECK} get_detector")
        try:
            get_resp = gd.get_detector(DetectorId=detector_id)
            if get_resp.get("Status") == "ENABLED":
                logs.append(f"{_LOG_POST_CHECK} Verified GuardDuty enabled.")
                return DirectFixResult(success=True, outcome="GuardDuty enabled", logs=logs)
            logs.append(f"{_LOG_POST_CHECK} Detector status={get_resp.get('Status')}")
            return DirectFixResult(
                success=False,
                outcome="Post-check failed: detector not enabled",
                logs=logs,
            )
        except Exception as e:
            logs.append(f"{_LOG_POST_CHECK} error: {e}")
            return DirectFixResult(success=False, outcome=f"Post-check failed: {e}", logs=logs)

    return DirectFixResult(success=True, outcome="GuardDuty enabled", logs=logs)


def _fix_ebs_default_encryption(
    session: boto3.Session,
    account_id: str,
    region: str | None,
    strategy_id: str | None = None,
    strategy_inputs: dict | None = None,
    *,
    run_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
) -> DirectFixResult:
    """
    Fix 4 — EBS default encryption (action_type: ebs_default_encryption).

    Strategies:
      - ebs_enable_default_encryption_aws_managed_kms
      - ebs_enable_default_encryption_customer_kms (requires kms_key_arn)
    """
    if not region:
        return DirectFixResult(
            success=False,
            outcome="Region required for EBS default encryption",
            logs=["Region is required for ebs_default_encryption."],
        )

    logs: list[str] = []
    strategy = (strategy_id or "ebs_enable_default_encryption_aws_managed_kms").strip().lower()
    requires_customer_kms = "customer_kms" in strategy
    desired_kms = ""
    if requires_customer_kms:
        desired_kms = str((strategy_inputs or {}).get("kms_key_arn", "")).strip()
        if not desired_kms:
            return DirectFixResult(
                success=False,
                outcome="strategy_inputs.kms_key_arn is required for customer KMS strategy",
                logs=["Missing strategy_inputs.kms_key_arn."],
            )

    ec2 = session.client("ec2", region_name=region)

    # Pre-check
    logs.append(f"{_LOG_PRE_CHECK} get_ebs_encryption_by_default")
    try:
        pre_resp = ec2.get_ebs_encryption_by_default()
        enabled = bool(pre_resp.get("EbsEncryptionByDefault"))
        if enabled and not requires_customer_kms:
            logs.append(f"{_LOG_PRE_CHECK} Already compliant (default encryption enabled).")
            return DirectFixResult(success=True, outcome="Already compliant; no change needed", logs=logs)
        if enabled and requires_customer_kms:
            current_kms = ec2.get_ebs_default_kms_key_id().get("KmsKeyId", "")
            if current_kms == desired_kms:
                logs.append(f"{_LOG_PRE_CHECK} Already compliant (default encryption + selected KMS key).")
                return DirectFixResult(success=True, outcome="Already compliant; no change needed", logs=logs)
            logs.append(f"{_LOG_PRE_CHECK} Encryption enabled; updating default KMS key.")
        elif not enabled:
            logs.append(f"{_LOG_PRE_CHECK} Default encryption disabled; will enable.")
    except Exception as e:
        logs.append(f"{_LOG_PRE_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Pre-check error: {e}", logs=logs)

    # Apply
    logs.append(f"{_LOG_APPLY} enable_ebs_encryption_by_default")
    try:
        ec2.enable_ebs_encryption_by_default()
        if requires_customer_kms:
            logs.append(f"{_LOG_APPLY} modify_ebs_default_kms_key_id")
            ec2.modify_ebs_default_kms_key_id(KmsKeyId=desired_kms)
        logs.append(f"{_LOG_APPLY} Success.")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        logs.append(f"{_LOG_APPLY} failed: {code} - {msg}")
        return DirectFixResult(success=False, outcome=f"Apply failed: {code}", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_APPLY} error: {e}")
        return DirectFixResult(success=False, outcome=f"Apply error: {e}", logs=logs)

    # Post-check
    logs.append(f"{_LOG_POST_CHECK} verify EBS default encryption")
    try:
        post_resp = ec2.get_ebs_encryption_by_default()
        enabled = bool(post_resp.get("EbsEncryptionByDefault"))
        if not enabled:
            logs.append(f"{_LOG_POST_CHECK} Encryption still disabled.")
            return DirectFixResult(success=False, outcome="Post-check failed: encryption still disabled", logs=logs)
        if requires_customer_kms:
            current_kms = ec2.get_ebs_default_kms_key_id().get("KmsKeyId", "")
            if current_kms != desired_kms:
                logs.append(f"{_LOG_POST_CHECK} Default KMS key mismatch: {current_kms}")
                return DirectFixResult(
                    success=False,
                    outcome="Post-check failed: default KMS key mismatch",
                    logs=logs,
                )
        logs.append(f"{_LOG_POST_CHECK} Verified default encryption configuration.")
        return DirectFixResult(success=True, outcome="EBS default encryption enabled", logs=logs)
    except Exception as e:
        logs.append(f"{_LOG_POST_CHECK} error: {e}")
        return DirectFixResult(success=False, outcome=f"Post-check failed: {e}", logs=logs)
