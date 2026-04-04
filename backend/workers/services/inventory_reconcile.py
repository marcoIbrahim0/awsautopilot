"""
Inventory collectors and control evaluators for reconciliation sweeps.

Phase-2 goals:
- coverage for non-eventable controls
- reconciliation for missed/late/noisy event streams
"""
from __future__ import annotations

import json
import logging
from typing import Any

from botocore.exceptions import ClientError

from backend.services.control_scope import unsupported_control_decision
from backend.services.remediation_support_bucket import (
    is_product_managed_support_log_sink,
    support_bucket_role_from_tags,
)
from backend.workers.services.control_plane_events import (
    SHADOW_STATUS_OPEN,
    SHADOW_STATUS_RESOLVED,
    SHADOW_STATUS_SOFT_RESOLVED,
    WORLD_IPV4,
    ControlEvaluation,
    evaluate_s3_bucket_public_posture,
    evaluate_security_group_public_admin_ports,
)
from backend.workers.services.inventory_assets import InventorySnapshot

logger = logging.getLogger(__name__)

INVENTORY_SERVICES_DEFAULT: tuple[str, ...] = (
    "ec2",
    "s3",
    "cloudtrail",
    "config",
    "iam",
    "ebs",
    "rds",
    "eks",
    "ssm",
    "guardduty",
    "securityhub",
)
_RDS_PUBLIC_ACCESS_CONTROL_ID = "RDS.PUBLIC_ACCESS"
_RDS_ENCRYPTION_CONTROL_ID = "RDS.ENCRYPTION"
_EKS_PUBLIC_ENDPOINT_CONTROL_ID = "EKS.PUBLIC_ENDPOINT"
_RDS_PUBLIC_ACCESS_UNSUPPORTED_DECISION = unsupported_control_decision(_RDS_PUBLIC_ACCESS_CONTROL_ID)
_RDS_ENCRYPTION_UNSUPPORTED_DECISION = unsupported_control_decision(_RDS_ENCRYPTION_CONTROL_ID)
_EKS_PUBLIC_ENDPOINT_UNSUPPORTED_DECISION = unsupported_control_decision(_EKS_PUBLIC_ENDPOINT_CONTROL_ID)


def _extract_error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "ClientError")
    return type(exc).__name__


_ACCESS_DENIED_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "UnauthorizedAccess",
}


def _is_access_denied_error_code(code: str) -> bool:
    return code in _ACCESS_DENIED_ERROR_CODES


def _bucket_name_from_any(value: str) -> str:
    v = (value or "").strip()
    if v.startswith("arn:aws:s3:::"):
        return v.replace("arn:aws:s3:::", "", 1)
    return v


def _security_group_id_from_any(value: str) -> str | None:
    raw = (value or "").strip()
    if raw.startswith("sg-"):
        return raw
    marker = ":security-group/"
    if marker not in raw:
        return None
    tail = raw.split(marker, 1)[1].strip()
    if tail.startswith("sg-"):
        return tail
    return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


_S3_APPROVED_DEFAULT_ENCRYPTION_ALGORITHMS = {"aes256", "aws:kms"}


def _control_eval(
    control_id: str,
    resource_id: str,
    resource_type: str,
    status: str,
    title: str,
    description: str,
    status_reason: str,
    evidence_ref: dict[str, Any],
    severity_label: str = "HIGH",
    state_confidence: int = 95,
) -> ControlEvaluation:
    return ControlEvaluation(
        control_id=control_id,
        resource_id=resource_id,
        resource_type=resource_type,
        severity_label=severity_label,
        title=title,
        description=description,
        status=status,
        status_reason=status_reason,
        state_confidence=state_confidence,
        evidence_ref=evidence_ref,
    )


def _unsupported_control_evidence(decision: dict[str, Any] | None) -> dict[str, str]:
    if decision is None:
        return {
            "support_status": "unsupported",
            "remediation_classification": "UNSUPPORTED",
            "action_type": "pr_only",
            "support_reason": (
                "Inventory-only visibility exists, but no mapped remediation action type, "
                "strategy, direct-fix executor, or PR-bundle generator is implemented."
            ),
        }
    return {
        "support_status": str(decision["support_status"]),
        "remediation_classification": str(decision["remediation_classification"]),
        "action_type": str(decision["action_type"]),
        "support_reason": str(decision["reason"]),
    }


def _s3_bucket_region(s3_client: Any, bucket: str) -> str | None:
    try:
        resp = s3_client.get_bucket_location(Bucket=bucket)
    except ClientError as exc:
        if _extract_error_code(exc) == "NoSuchBucket":
            return None
        raise
    loc = resp.get("LocationConstraint")
    # AWS returns None for us-east-1.
    if not loc:
        return "us-east-1"
    return str(loc)


def _s3_bucket_public_access_block(s3_client: Any, bucket: str) -> dict[str, Any]:
    try:
        resp = s3_client.get_public_access_block(Bucket=bucket)
        return resp.get("PublicAccessBlockConfiguration") or {}
    except ClientError as exc:
        if _extract_error_code(exc) in {"NoSuchPublicAccessBlockConfiguration", "NoSuchBucket"}:
            return {}
        raise


def _s3_account_public_access_block(s3control_client: Any, account_id: str) -> tuple[dict[str, Any], bool]:
    try:
        resp = s3control_client.get_public_access_block(AccountId=account_id)
        return (resp.get("PublicAccessBlockConfiguration") or {}, True)
    except ClientError as exc:
        code = _extract_error_code(exc)
        if code == "NoSuchPublicAccessBlockConfiguration":
            return ({}, True)
        if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "UnauthorizedAccess"}:
            return ({}, False)
        raise


def _s3_bucket_policy_is_public(s3_client: Any, bucket: str) -> bool:
    try:
        resp = s3_client.get_bucket_policy_status(Bucket=bucket)
        return bool((resp.get("PolicyStatus") or {}).get("IsPublic"))
    except ClientError as exc:
        if _extract_error_code(exc) in {"NoSuchBucketPolicy", "NoSuchBucket"}:
            return False
        raise


def _s3_bucket_default_encryption_summary(s3_client: Any, bucket: str) -> tuple[str | None, bool, bool]:
    try:
        resp = s3_client.get_bucket_encryption(Bucket=bucket)
    except ClientError as exc:
        if _extract_error_code(exc) in {"ServerSideEncryptionConfigurationNotFoundError", "NoSuchBucket"}:
            return (None, False, False)
        raise
    rules = _as_list((resp.get("ServerSideEncryptionConfiguration") or {}).get("Rules"))
    first_algo: str | None = None
    if rules:
        first = rules[0] if isinstance(rules[0], dict) else {}
        by_default = first.get("ApplyServerSideEncryptionByDefault") if isinstance(first, dict) else {}
        if isinstance(by_default, dict):
            algo = by_default.get("SSEAlgorithm")
            if algo:
                first_algo = str(algo).strip().lower()

    has_approved_default = False
    has_kms_default = False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        by_default = rule.get("ApplyServerSideEncryptionByDefault")
        if not isinstance(by_default, dict):
            continue
        algo = by_default.get("SSEAlgorithm")
        normalized = str(algo).strip().lower() if algo else ""
        if normalized in _S3_APPROVED_DEFAULT_ENCRYPTION_ALGORITHMS:
            has_approved_default = True
        if normalized == "aws:kms":
            has_kms_default = True
        if has_approved_default and has_kms_default:
            break
    return first_algo, has_approved_default, has_kms_default


def _s3_bucket_default_encryption_algorithm(s3_client: Any, bucket: str) -> str | None:
    first_algo, _, _ = _s3_bucket_default_encryption_summary(s3_client, bucket)
    return first_algo


def _s3_bucket_logging_enabled(s3_client: Any, bucket: str) -> bool:
    try:
        resp = s3_client.get_bucket_logging(Bucket=bucket)
    except ClientError as exc:
        if _extract_error_code(exc) == "NoSuchBucket":
            return False
        raise
    logging_enabled = resp.get("LoggingEnabled")
    if not isinstance(logging_enabled, dict) or not logging_enabled:
        return False

    target_bucket = logging_enabled.get("TargetBucket")
    if not isinstance(target_bucket, str) or not target_bucket.strip():
        return False

    if "TargetPrefix" not in logging_enabled:
        return False

    return True


def _rule_has_meaningful_lifecycle_action(rule: dict[str, Any]) -> bool:
    action_keys = (
        "Expiration",
        "Transitions",
        "NoncurrentVersionExpiration",
        "NoncurrentVersionTransitions",
        "AbortIncompleteMultipartUpload",
    )
    for key in action_keys:
        value = rule.get(key)
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, list) and any(isinstance(item, dict) and item for item in value):
            return True
    return False


def _s3_bucket_has_valid_lifecycle_rule(s3_client: Any, bucket: str) -> bool:
    try:
        resp = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket)
    except ClientError as exc:
        if _extract_error_code(exc) in {"NoSuchLifecycleConfiguration", "NoSuchBucket"}:
            return False
        raise
    rules = _as_list(resp.get("Rules"))
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("Status") or "").strip().lower() != "enabled":
            continue
        if _rule_has_meaningful_lifecycle_action(rule):
            return True
    return False


def _s3_bucket_policy_json(s3_client: Any, bucket: str) -> tuple[dict[str, Any] | None, bool]:
    try:
        resp = s3_client.get_bucket_policy(Bucket=bucket)
    except ClientError as exc:
        if _extract_error_code(exc) in {"NoSuchBucketPolicy", "NoSuchBucket"}:
            return (None, False)
        raise
    policy_str = resp.get("Policy")
    if not isinstance(policy_str, str) or not policy_str.strip():
        return (None, False)
    try:
        parsed = json.loads(policy_str)
        return ((parsed if isinstance(parsed, dict) else None), not isinstance(parsed, dict))
    except Exception:
        return (None, True)


def _s3_bucket_tag_map(s3_client: Any, bucket: str) -> dict[str, str]:
    if not hasattr(s3_client, "get_bucket_tagging"):
        return {}
    try:
        resp = s3_client.get_bucket_tagging(Bucket=bucket)
    except ClientError as exc:
        if _extract_error_code(exc) in {"NoSuchTagSet", "NoSuchBucket"}:
            return {}
        raise
    tag_set = _as_list(resp.get("TagSet"))
    tag_map: dict[str, str] = {}
    for tag in tag_set:
        if not isinstance(tag, dict):
            continue
        key = str(tag.get("Key") or "").strip()
        value = str(tag.get("Value") or "").strip()
        if key:
            tag_map[key] = value
    return tag_map


def _policy_condition_has_secure_transport_false(condition: Any) -> bool:
    if not isinstance(condition, dict):
        return False
    for operator_key, operator_value in condition.items():
        if str(operator_key).strip().lower() != "bool":
            continue
        if not isinstance(operator_value, dict):
            continue
        for cond_key, cond_value in operator_value.items():
            if str(cond_key).strip().lower() != "aws:securetransport":
                continue
            if str(cond_value).strip().lower() == "false":
                return True
    return False


def _policy_action_covers_ssl_deny(action: Any) -> bool:
    items = action if isinstance(action, list) else [action]
    normalized = {str(item).strip().lower() for item in items if str(item).strip()}
    if "s3:*" in normalized:
        return True
    return {"s3:getobject", "s3:putobject"}.issubset(normalized)


def _policy_resource_covers_bucket_and_object(resource: Any, bucket_arn: str, object_arn: str) -> bool:
    items = resource if isinstance(resource, list) else [resource]
    normalized = {str(item).strip().lower() for item in items if str(item).strip()}
    return bucket_arn.lower() in normalized and object_arn.lower() in normalized


def _policy_has_ssl_deny(policy: dict[str, Any] | None, bucket_name: str) -> bool:
    if not isinstance(policy, dict):
        return False
    bucket = str(bucket_name or "").strip()
    if not bucket:
        return False
    bucket_arn = f"arn:aws:s3:::{bucket}"
    object_arn = f"{bucket_arn}/*"
    statements = policy.get("Statement")
    items = statements if isinstance(statements, list) else [statements]
    for statement in items:
        if not isinstance(statement, dict):
            continue
        if str(statement.get("Effect") or "").upper() != "DENY":
            continue
        if not _policy_condition_has_secure_transport_false(statement.get("Condition")):
            continue
        if not _policy_action_covers_ssl_deny(statement.get("Action")):
            continue
        if not _policy_resource_covers_bucket_and_object(statement.get("Resource"), bucket_arn, object_arn):
            continue
        return True
    return False


def _collect_ec2_security_groups(
    session_boto: Any,
    region: str,
    resource_ids: list[str] | None,
    max_resources: int,
) -> list[InventorySnapshot]:
    ec2 = session_boto.client("ec2", region_name=region)
    groups: list[dict[str, Any]] = []

    if resource_ids:
        ids: list[str] = []
        for rid in resource_ids:
            raw_value = str(rid)
            normalized = _security_group_id_from_any(raw_value)
            if normalized:
                ids.append(normalized)
                continue
            logger.warning(
                "Skipping unsupported EC2.53 resource identifier during targeted reconcile: %s",
                raw_value,
            )
        if not ids:
            return []
        for group_id in ids[:max_resources]:
            try:
                response = ec2.describe_security_groups(GroupIds=[group_id])
                groups.extend(_as_list(response.get("SecurityGroups")))
            except ClientError as exc:
                if _extract_error_code(exc) == "InvalidGroup.NotFound":
                    groups.append({"GroupId": group_id, "_deleted_marker": True})
                    continue
                raise
    else:
        paginator = ec2.get_paginator("describe_security_groups")
        for page in paginator.paginate(PaginationConfig={"PageSize": 200}):
            for g in _as_list(page.get("SecurityGroups")):
                if not isinstance(g, dict):
                    continue
                groups.append(g)
                if len(groups) >= max_resources:
                    break
            if len(groups) >= max_resources:
                break

    snapshots: list[InventorySnapshot] = []
    for group in groups:
        group_id = str(group.get("GroupId") or "").strip()
        if not group_id:
            continue
            
        if group.get("_deleted_marker"):
            evals = [
                _control_eval(
                    control_id="EC2.53",
                    resource_id=group_id,
                    resource_type="AwsEc2SecurityGroup",
                    status=SHADOW_STATUS_RESOLVED,
                    title="Security group allows public SSH/RDP access",
                    description="Inventory reconciliation check for public admin ports.",
                    status_reason="inventory_resource_deleted",
                    evidence_ref={"source": "inventory", "resource_deleted": True},
                )
            ]
            snapshots.append(
                InventorySnapshot(
                    service="ec2",
                    resource_id=group_id,
                    resource_type="AwsEc2SecurityGroup",
                    key_fields={"group_id": group_id, "deleted": True},
                    state_for_hash={"group_id": group_id, "deleted": True},
                    metadata_json={"group_name": "DELETED"},
                    evaluations=evals,
                )
            )
            continue

        non_compliant, violations = evaluate_security_group_public_admin_ports(group)
        status = SHADOW_STATUS_OPEN if non_compliant else SHADOW_STATUS_RESOLVED
        reason = "inventory_confirmed_non_compliant" if non_compliant else "inventory_confirmed_compliant"
        evals = [
            _control_eval(
                control_id="EC2.53",
                resource_id=group_id,
                resource_type="AwsEc2SecurityGroup",
                status=status,
                title="Security group allows public SSH/RDP access",
                description="Inventory reconciliation check for public admin ports.",
                status_reason=reason,
                evidence_ref={"source": "inventory", "violations": violations},
            )
        ]
        state_for_hash = {
            "group_id": group_id,
            "vpc_id": group.get("VpcId"),
            "ip_permissions": group.get("IpPermissions") or [],
        }
        key_fields = {
            "group_id": group_id,
            "vpc_id": group.get("VpcId"),
            "ingress_rule_count": len(_as_list(group.get("IpPermissions"))),
        }
        snapshots.append(
            InventorySnapshot(
                service="ec2",
                resource_id=group_id,
                resource_type="AwsEc2SecurityGroup",
                key_fields=key_fields,
                state_for_hash=state_for_hash,
                metadata_json={"group_name": group.get("GroupName")},
                evaluations=evals,
            )
        )
    return snapshots


def _collect_s3_buckets(
    session_boto: Any,
    account_id: str,
    region: str,
    resource_ids: list[str] | None,
    max_resources: int,
) -> list[InventorySnapshot]:
    # S3 control-plane APIs are global; region filtering is done per bucket location.
    s3 = session_boto.client("s3", region_name=region)
    s3control = session_boto.client("s3control", region_name=region)

    account_pab, account_probe_ok = _s3_account_public_access_block(s3control, account_id)
    required_account_flags = (
        "BlockPublicAcls",
        "IgnorePublicAcls",
        "BlockPublicPolicy",
        "RestrictPublicBuckets",
    )
    account_pab_all_on = all(bool(account_pab.get(flag)) for flag in required_account_flags)
    s31_status = (
        SHADOW_STATUS_SOFT_RESOLVED
        if not account_probe_ok
        else (SHADOW_STATUS_RESOLVED if account_pab_all_on else SHADOW_STATUS_OPEN)
    )
    s31_reason = (
        "inventory_access_denied_s3control_get_public_access_block"
        if not account_probe_ok
        else ("inventory_confirmed_compliant" if account_pab_all_on else "inventory_confirmed_non_compliant")
    )
    s31_confidence = 40 if not account_probe_ok else 95

    snapshots: list[InventorySnapshot] = [
        InventorySnapshot(
            service="s3",
            resource_id=account_id,
            resource_type="AwsAccount",
            key_fields={
                "account_id": account_id,
                "public_access_block": {flag: bool(account_pab.get(flag)) for flag in required_account_flags},
                "probe_ok": account_probe_ok,
            },
            state_for_hash={
                "public_access_block": {flag: bool(account_pab.get(flag)) for flag in required_account_flags},
                "probe_ok": account_probe_ok,
            },
            metadata_json=None,
            evaluations=[
                _control_eval(
                    control_id="S3.1",
                    resource_id=account_id,
                    resource_type="AwsAccount",
                    status=s31_status,
                    title="S3 account-level block public access is enabled",
                    description="Inventory reconciliation for S3.1 account-level public access block.",
                    status_reason=s31_reason,
                    evidence_ref={
                        "source": "inventory",
                        "public_access_block": {flag: bool(account_pab.get(flag)) for flag in required_account_flags},
                        "probe_ok": account_probe_ok,
                    },
                    state_confidence=s31_confidence,
                )
            ],
        )
    ]

    if resource_ids:
        bucket_names = []
        for value in resource_ids:
            raw_value = str(value).strip()
            if not raw_value or raw_value.startswith("AWS::::Account:"):
                continue
            bucket_names.append(_bucket_name_from_any(raw_value))
    else:
        resp = s3.list_buckets()
        bucket_names = [str((b or {}).get("Name") or "") for b in _as_list(resp.get("Buckets"))]
    emit_account_shaped_s32 = bool(resource_ids) and len(bucket_names) == 1

    for bucket in bucket_names:
        bucket = bucket.strip()
        if not bucket:
            continue
        bucket_region = _s3_bucket_region(s3, bucket)
        resource_id = f"arn:aws:s3:::{bucket}"
        if bucket_region is None:
            snapshots.append(
                InventorySnapshot(
                    service="s3",
                    resource_id=resource_id,
                    resource_type="AwsS3Bucket",
                    key_fields={"bucket_name": bucket, "deleted": True},
                    state_for_hash={"bucket_name": bucket, "deleted": True},
                    metadata_json={"bucket_name": "DELETED"},
                    evaluations=[
                        _control_eval(
                            control_id="S3.2",
                            resource_id=resource_id,
                            resource_type="AwsS3Bucket",
                            status=SHADOW_STATUS_RESOLVED,
                            title="S3 bucket public access posture",
                            description="Inventory reconciliation for public access posture.",
                            status_reason="inventory_resource_deleted",
                            evidence_ref={"source": "inventory", "resource_deleted": True},
                        ),
                        _control_eval(
                            control_id="S3.4",
                            resource_id=resource_id,
                            resource_type="AwsS3Bucket",
                            status=SHADOW_STATUS_RESOLVED,
                            title="S3 bucket default encryption enabled",
                            description="Inventory reconciliation for default encryption.",
                            status_reason="inventory_resource_deleted",
                            evidence_ref={"source": "inventory", "resource_deleted": True},
                        ),
                        _control_eval(
                            control_id="S3.15",
                            resource_id=resource_id,
                            resource_type="AwsS3Bucket",
                            status=SHADOW_STATUS_RESOLVED,
                            title="S3 bucket default encryption uses AWS KMS",
                            description="Inventory reconciliation for KMS default encryption.",
                            status_reason="inventory_resource_deleted",
                            evidence_ref={"source": "inventory", "resource_deleted": True},
                        ),
                        _control_eval(
                            control_id="S3.9",
                            resource_id=resource_id,
                            resource_type="AwsS3Bucket",
                            status=SHADOW_STATUS_RESOLVED,
                            title="S3 bucket server access logging enabled",
                            description="Inventory reconciliation for logging coverage.",
                            status_reason="inventory_resource_deleted",
                            evidence_ref={"source": "inventory", "resource_deleted": True},
                        ),
                        _control_eval(
                            control_id="S3.11",
                            resource_id=resource_id,
                            resource_type="AwsS3Bucket",
                            status=SHADOW_STATUS_RESOLVED,
                            title="S3 bucket lifecycle rules configured",
                            description="Inventory reconciliation for lifecycle policy coverage.",
                            status_reason="inventory_resource_deleted",
                            evidence_ref={"source": "inventory", "resource_deleted": True},
                        ),
                        _control_eval(
                            control_id="S3.5",
                            resource_id=resource_id,
                            resource_type="AwsS3Bucket",
                            status=SHADOW_STATUS_RESOLVED,
                            title="S3 bucket enforces SSL-only access",
                            description="Inventory reconciliation for SSL-only bucket policy.",
                            status_reason="inventory_resource_deleted",
                            evidence_ref={"source": "inventory", "resource_deleted": True},
                        ),
                    ],
                )
            )
            continue
        if bucket_region != region:
            continue

        pab: dict[str, Any] = {}
        policy_public = False
        s32_access_denied_error_codes: list[str] = []
        s32_api_error_codes: list[str] = []
        try:
            pab = _s3_bucket_public_access_block(s3, bucket)
        except ClientError as exc:
            code = _extract_error_code(exc)
            if _is_access_denied_error_code(code):
                s32_access_denied_error_codes.append(code)
            else:
                s32_api_error_codes.append(code)
        try:
            policy_public = _s3_bucket_policy_is_public(s3, bucket)
        except ClientError as exc:
            code = _extract_error_code(exc)
            if _is_access_denied_error_code(code):
                s32_access_denied_error_codes.append(code)
            else:
                s32_api_error_codes.append(code)
        non_compliant_public, public_evidence = evaluate_s3_bucket_public_posture(pab, policy_public)
        if s32_access_denied_error_codes:
            s32_status = SHADOW_STATUS_SOFT_RESOLVED
            s32_reason = "inventory_access_denied_s3_get_bucket_public_posture"
            s32_confidence = 40
            s32_branch = "access_denied"
        elif s32_api_error_codes:
            s32_status = SHADOW_STATUS_SOFT_RESOLVED
            s32_reason = "inventory_api_error_s3_get_bucket_public_posture"
            s32_confidence = 40
            s32_branch = "api_error"
        else:
            s32_status = SHADOW_STATUS_OPEN if non_compliant_public else SHADOW_STATUS_RESOLVED
            s32_reason = "inventory_confirmed_non_compliant" if non_compliant_public else "inventory_confirmed_compliant"
            s32_confidence = 95
            s32_branch = "normal"

        algo: str | None = None
        encryption_enabled = False
        kms_enabled = False
        s34_s315_error_code: str | None = None
        s34_s315_access_denied = False
        try:
            algo, encryption_enabled, kms_enabled = _s3_bucket_default_encryption_summary(s3, bucket)
        except ClientError as exc:
            code = _extract_error_code(exc)
            s34_s315_error_code = code
            s34_s315_access_denied = _is_access_denied_error_code(code)

        if s34_s315_access_denied:
            s34_status = SHADOW_STATUS_SOFT_RESOLVED
            s34_reason = "inventory_access_denied_s3_get_bucket_encryption"
            s34_confidence = 40
            s34_s315_branch = "access_denied"
            s315_status = SHADOW_STATUS_SOFT_RESOLVED
            s315_reason = "inventory_access_denied_s3_get_bucket_encryption"
            s315_confidence = 40
        elif s34_s315_error_code is not None:
            s34_status = SHADOW_STATUS_SOFT_RESOLVED
            s34_reason = "inventory_api_error_s3_get_bucket_encryption"
            s34_confidence = 40
            s34_s315_branch = "api_error"
            s315_status = SHADOW_STATUS_SOFT_RESOLVED
            s315_reason = "inventory_api_error_s3_get_bucket_encryption"
            s315_confidence = 40
        else:
            s34_status = SHADOW_STATUS_RESOLVED if encryption_enabled else SHADOW_STATUS_OPEN
            s34_reason = "inventory_confirmed_compliant" if encryption_enabled else "inventory_confirmed_non_compliant"
            s34_confidence = 95
            s34_s315_branch = "normal"
            s315_status = SHADOW_STATUS_RESOLVED if kms_enabled else SHADOW_STATUS_OPEN
            s315_reason = "inventory_confirmed_compliant" if kms_enabled else "inventory_confirmed_non_compliant"
            s315_confidence = 95

        logging_enabled = False
        s39_error_code: str | None = None
        s39_access_denied = False
        bucket_tags: dict[str, str] = {}
        bucket_tag_error_code: str | None = None
        managed_support_log_sink = False
        support_bucket_role: str | None = None
        try:
            bucket_tags = _s3_bucket_tag_map(s3, bucket)
            managed_support_log_sink = is_product_managed_support_log_sink(bucket_tags)
            support_bucket_role = support_bucket_role_from_tags(bucket_tags)
        except ClientError as exc:
            bucket_tag_error_code = _extract_error_code(exc)
        try:
            logging_enabled = _s3_bucket_logging_enabled(s3, bucket)
        except ClientError as exc:
            code = _extract_error_code(exc)
            s39_error_code = code
            s39_access_denied = _is_access_denied_error_code(code)

        if s39_access_denied:
            s39_status = SHADOW_STATUS_SOFT_RESOLVED
            s39_reason = "inventory_access_denied_s3_get_bucket_logging"
            s39_confidence = 40
            s39_branch = "access_denied"
        elif s39_error_code is not None:
            s39_status = SHADOW_STATUS_SOFT_RESOLVED
            s39_reason = "inventory_api_error_s3_get_bucket_logging"
            s39_confidence = 40
            s39_branch = "api_error"
        elif managed_support_log_sink:
            s39_status = SHADOW_STATUS_RESOLVED
            s39_reason = "inventory_product_managed_support_log_sink"
            s39_confidence = 95
            s39_branch = "product_managed_support_log_sink"
        else:
            s39_status = SHADOW_STATUS_RESOLVED if logging_enabled else SHADOW_STATUS_OPEN
            s39_reason = "inventory_confirmed_compliant" if logging_enabled else "inventory_confirmed_non_compliant"
            s39_confidence = 95
            s39_branch = "normal"

        lifecycle_has_valid_rule = False
        s311_error_code: str | None = None
        s311_access_denied = False
        try:
            lifecycle_has_valid_rule = _s3_bucket_has_valid_lifecycle_rule(s3, bucket)
        except ClientError as exc:
            code = _extract_error_code(exc)
            s311_error_code = code
            s311_access_denied = _is_access_denied_error_code(code)

        if s311_access_denied:
            s311_status = SHADOW_STATUS_SOFT_RESOLVED
            s311_reason = "inventory_access_denied_s3_get_bucket_lifecycle_configuration"
            s311_confidence = 40
            s311_branch = "access_denied"
        elif s311_error_code is not None:
            s311_status = SHADOW_STATUS_SOFT_RESOLVED
            s311_reason = "inventory_api_error_s3_get_bucket_lifecycle_configuration"
            s311_confidence = 40
            s311_branch = "api_error"
        else:
            s311_status = SHADOW_STATUS_RESOLVED if lifecycle_has_valid_rule else SHADOW_STATUS_OPEN
            s311_reason = "inventory_confirmed_compliant" if lifecycle_has_valid_rule else "inventory_confirmed_non_compliant"
            s311_confidence = 95
            s311_branch = "normal"

        policy_json: dict[str, Any] | None = None
        policy_parse_error = False
        s35_error_code: str | None = None
        s35_access_denied = False
        ssl_deny = False
        try:
            policy_json, policy_parse_error = _s3_bucket_policy_json(s3, bucket)
        except ClientError as exc:
            code = _extract_error_code(exc)
            s35_error_code = code
            s35_access_denied = _is_access_denied_error_code(code)

        if s35_access_denied:
            s35_status = SHADOW_STATUS_SOFT_RESOLVED
            s35_reason = "inventory_access_denied_s3_get_bucket_policy"
            s35_confidence = 40
            s35_branch = "access_denied"
        elif s35_error_code is not None:
            s35_status = SHADOW_STATUS_SOFT_RESOLVED
            s35_reason = "inventory_api_error_s3_get_bucket_policy"
            s35_confidence = 40
            s35_branch = "api_error"
        elif policy_parse_error:
            s35_status = SHADOW_STATUS_SOFT_RESOLVED
            s35_reason = "inventory_partial_data_s3_bucket_policy_parse_failed"
            s35_confidence = 50
            s35_branch = "partial_data"
        else:
            ssl_deny = _policy_has_ssl_deny(policy_json, bucket)
            s35_status = SHADOW_STATUS_RESOLVED if ssl_deny else SHADOW_STATUS_OPEN
            s35_reason = "inventory_confirmed_compliant" if ssl_deny else "inventory_confirmed_non_compliant"
            s35_confidence = 95
            s35_branch = "normal"

        evals = [
            _control_eval(
                control_id="S3.2",
                resource_id=resource_id,
                resource_type="AwsS3Bucket",
                status=s32_status,
                title="S3 bucket public access posture",
                description="Inventory reconciliation for public access posture.",
                status_reason=s32_reason,
                state_confidence=s32_confidence,
                evidence_ref={
                    "source": "inventory",
                    "probe_branch": s32_branch,
                    "access_denied_error_codes": s32_access_denied_error_codes,
                    "api_error_codes": s32_api_error_codes,
                    **public_evidence,
                },
            ),
            _control_eval(
                control_id="S3.4",
                resource_id=resource_id,
                resource_type="AwsS3Bucket",
                status=s34_status,
                title="S3 bucket default encryption enabled",
                description="Inventory reconciliation for bucket default encryption.",
                status_reason=s34_reason,
                evidence_ref={
                    "source": "inventory",
                    "probe_branch": s34_s315_branch,
                    "error_code": s34_s315_error_code,
                    "default_encryption_algorithm": algo,
                },
                state_confidence=s34_confidence,
            ),
            _control_eval(
                control_id="S3.15",
                resource_id=resource_id,
                resource_type="AwsS3Bucket",
                status=s315_status,
                title="S3 bucket uses SSE-KMS by default",
                description="Inventory reconciliation for KMS default encryption.",
                status_reason=s315_reason,
                evidence_ref={
                    "source": "inventory",
                    "probe_branch": s34_s315_branch,
                    "error_code": s34_s315_error_code,
                    "default_encryption_algorithm": algo,
                    "kms_default_enabled": kms_enabled,
                },
                state_confidence=s315_confidence,
            ),
            _control_eval(
                control_id="S3.9",
                resource_id=resource_id,
                resource_type="AwsS3Bucket",
                status=s39_status,
                title="S3 bucket access logging enabled",
                description="Inventory reconciliation for server access logging.",
                status_reason=s39_reason,
                evidence_ref={
                    "source": "inventory",
                    "probe_branch": s39_branch,
                    "error_code": s39_error_code,
                    "logging_enabled": logging_enabled,
                    "bucket_tags": bucket_tags,
                    "bucket_tag_error_code": bucket_tag_error_code,
                    "product_managed_support_log_sink": managed_support_log_sink,
                    "support_bucket_role": support_bucket_role,
                },
                state_confidence=s39_confidence,
            ),
            _control_eval(
                control_id="S3.11",
                resource_id=resource_id,
                resource_type="AwsS3Bucket",
                status=s311_status,
                title="S3 bucket lifecycle rules configured",
                description="Inventory reconciliation for lifecycle policy coverage.",
                status_reason=s311_reason,
                evidence_ref={
                    "source": "inventory",
                    "probe_branch": s311_branch,
                    "error_code": s311_error_code,
                    "lifecycle_has_valid_rule": lifecycle_has_valid_rule,
                },
                severity_label="MEDIUM",
                state_confidence=s311_confidence,
            ),
            _control_eval(
                control_id="S3.5",
                resource_id=resource_id,
                resource_type="AwsS3Bucket",
                status=s35_status,
                title="S3 bucket enforces SSL requests",
                description="Inventory reconciliation for deny-insecure-transport policy.",
                status_reason=s35_reason,
                evidence_ref={
                    "source": "inventory",
                    "probe_branch": s35_branch,
                    "error_code": s35_error_code,
                    "policy_parse_error": policy_parse_error,
                    "ssl_deny_policy": ssl_deny,
                },
                severity_label="MEDIUM",
                state_confidence=s35_confidence,
            ),
        ]
        if emit_account_shaped_s32:
            evals.insert(
                1,
                _control_eval(
                    control_id="S3.2",
                    resource_id=account_id,
                    resource_type="AwsAccount",
                    status=s32_status,
                    title="S3 bucket public access posture",
                    description="Inventory reconciliation for public access posture.",
                    status_reason=s32_reason,
                    state_confidence=s32_confidence,
                    evidence_ref={
                        "source": "inventory",
                        "probe_branch": s32_branch,
                        "access_denied_error_codes": s32_access_denied_error_codes,
                        "api_error_codes": s32_api_error_codes,
                        **public_evidence,
                    },
                ),
            )
        state_for_hash = {
            "public_access_block": public_evidence.get("public_access_block"),
            "policy_is_public": public_evidence.get("policy_is_public"),
            "default_encryption_algorithm": algo,
            "kms_default_enabled": kms_enabled,
            "logging_enabled": logging_enabled,
            "product_managed_support_log_sink": managed_support_log_sink,
            "support_bucket_role": support_bucket_role,
            "lifecycle_has_valid_rule": lifecycle_has_valid_rule,
            "ssl_deny_policy": ssl_deny,
            "s32_branch": s32_branch,
            "s34_s315_branch": s34_s315_branch,
            "s39_branch": s39_branch,
            "s311_branch": s311_branch,
            "s35_branch": s35_branch,
        }
        key_fields = {
            "bucket": bucket,
            "region": bucket_region,
            "policy_is_public": bool(public_evidence.get("policy_is_public")),
            "default_encryption_algorithm": algo,
            "kms_default_enabled": kms_enabled,
            "logging_enabled": logging_enabled,
            "product_managed_support_log_sink": managed_support_log_sink,
            "support_bucket_role": support_bucket_role,
            "lifecycle_has_valid_rule": lifecycle_has_valid_rule,
            "ssl_deny_policy": ssl_deny,
        }
        snapshots.append(
            InventorySnapshot(
                service="s3",
                resource_id=resource_id,
                resource_type="AwsS3Bucket",
                key_fields=key_fields,
                state_for_hash=state_for_hash,
                metadata_json={"bucket_tags": bucket_tags} if bucket_tags else None,
                evaluations=evals,
            )
        )
        if len(snapshots) >= (max_resources + 1):
            break

    return snapshots


def _collect_cloudtrail_account(
    session_boto: Any,
    account_id: str,
    region: str,
) -> list[InventorySnapshot]:
    cloudtrail = session_boto.client("cloudtrail", region_name=region)
    trails: list[Any] = []
    describe_access_denied = False
    describe_error_code: str | None = None
    try:
        trails_resp = cloudtrail.describe_trails(includeShadowTrails=True)
        trails = _as_list(trails_resp.get("trailList"))
    except ClientError as exc:
        code = _extract_error_code(exc)
        describe_error_code = code
        if _is_access_denied_error_code(code):
            describe_access_denied = True
        else:
            trails = []

    logging_multi_region = 0
    multi_region_trail_count = 0
    trail_status_access_denied = False
    trail_status_access_denied_count = 0
    trail_status_not_found_count = 0
    trail_status_unknown_error_count = 0
    trail_status_read_success_count = 0
    for trail in trails:
        if not isinstance(trail, dict):
            continue
        if not bool(trail.get("IsMultiRegionTrail")):
            continue
        multi_region_trail_count += 1
        name = trail.get("TrailARN") or trail.get("Name")
        try:
            status = cloudtrail.get_trail_status(Name=name)
            trail_status_read_success_count += 1
            if bool(status.get("IsLogging")):
                logging_multi_region += 1
        except ClientError as exc:
            code = _extract_error_code(exc)
            if _is_access_denied_error_code(code):
                trail_status_access_denied = True
                trail_status_access_denied_count += 1
                continue
            if code == "TrailNotFoundException":
                trail_status_not_found_count += 1
                continue
            trail_status_unknown_error_count += 1
            continue

    if describe_access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_cloudtrail_describe_trails"
        confidence = 40
        status_branch = "access_denied_describe_trails"
    elif describe_error_code is not None:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_error_cloudtrail_describe_trails"
        confidence = 40
        status_branch = "api_error_describe_trails"
    elif trail_status_access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_cloudtrail_get_trail_status"
        confidence = 40
        status_branch = "access_denied_get_trail_status"
    elif trail_status_unknown_error_count > 0:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_error_cloudtrail_get_trail_status"
        confidence = 40
        status_branch = "api_error_get_trail_status"
    elif multi_region_trail_count > 0 and trail_status_read_success_count == 0:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_partial_data_cloudtrail_trail_status_indeterminate"
        confidence = 50
        status_branch = "partial_data_indeterminate_trail_status"
    else:
        compliant = logging_multi_region > 0
        status = SHADOW_STATUS_RESOLVED if compliant else SHADOW_STATUS_OPEN
        reason = "inventory_confirmed_compliant" if compliant else "inventory_confirmed_non_compliant"
        confidence = 95
        status_branch = "normal"
    evals = [
        _control_eval(
            control_id="CloudTrail.1",
            resource_id=account_id,
            resource_type="AwsAccount",
            status=status,
            title="CloudTrail multi-region trail enabled",
            description="Inventory reconciliation for CloudTrail.1.",
            status_reason=reason,
            evidence_ref={
                "source": "inventory",
                "trail_count": len(trails),
                "multi_region_trail_count": multi_region_trail_count,
                "logging_multi_region_trails": logging_multi_region,
                "describe_access_denied": describe_access_denied,
                "describe_error_code": describe_error_code,
                "trail_status_access_denied": trail_status_access_denied,
                "trail_status_access_denied_count": trail_status_access_denied_count,
                "trail_status_not_found_count": trail_status_not_found_count,
                "trail_status_unknown_error_count": trail_status_unknown_error_count,
                "trail_status_read_success_count": trail_status_read_success_count,
                "status_branch": status_branch,
            },
            state_confidence=confidence,
        )
    ]
    state_for_hash = {
        "trail_count": len(trails),
        "multi_region_trail_count": multi_region_trail_count,
        "logging_multi_region_trails": logging_multi_region,
        "describe_access_denied": describe_access_denied,
        "describe_error_code": describe_error_code,
        "trail_status_access_denied": trail_status_access_denied,
        "trail_status_access_denied_count": trail_status_access_denied_count,
        "trail_status_not_found_count": trail_status_not_found_count,
        "trail_status_unknown_error_count": trail_status_unknown_error_count,
        "trail_status_read_success_count": trail_status_read_success_count,
        "status_branch": status_branch,
    }
    key_fields = state_for_hash.copy()
    return [
        InventorySnapshot(
            service="cloudtrail",
            resource_id=account_id,
            resource_type="AwsAccount",
            key_fields=key_fields,
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=evals,
        )
    ]


def _collect_config_account(
    session_boto: Any,
    account_id: str,
    region: str,
) -> list[InventorySnapshot]:
    config_client = session_boto.client("config", region_name=region)
    recorders_raw: list[Any] = []
    recorders_access_denied = False
    recorders_error_code: str | None = None
    try:
        recorders_raw = _as_list(config_client.describe_configuration_recorders().get("ConfigurationRecorders"))
    except ClientError as exc:
        code = _extract_error_code(exc)
        recorders_error_code = code
        if _is_access_denied_error_code(code):
            recorders_access_denied = True
        else:
            recorders_raw = []
    recorders = [recorder for recorder in recorders_raw if isinstance(recorder, dict)]
    status_access_denied = False
    status_error_code: str | None = None
    try:
        statuses_raw = _as_list(config_client.describe_configuration_recorder_status().get("ConfigurationRecordersStatus"))
    except ClientError as exc:
        code = _extract_error_code(exc)
        status_error_code = code
        if _is_access_denied_error_code(code):
            status_access_denied = True
            statuses_raw = []
        else:
            statuses_raw = []
    statuses = [status for status in statuses_raw if isinstance(status, dict)]
    delivery_channels_raw: list[Any] = []
    delivery_access_denied = False
    delivery_error_code: str | None = None
    try:
        delivery_channels_raw = _as_list(config_client.describe_delivery_channels().get("DeliveryChannels"))
    except ClientError as exc:
        code = _extract_error_code(exc)
        delivery_error_code = code
        if _is_access_denied_error_code(code):
            delivery_access_denied = True
        else:
            delivery_channels_raw = []
    delivery_channels = [channel for channel in delivery_channels_raw if isinstance(channel, dict)]

    status_by_name: dict[str, bool] = {}
    recording_any = False
    for status in statuses:
        status_name = str(status.get("name") or "").strip()
        status_recording = bool(status.get("recording"))
        recording_any = recording_any or status_recording
        if status_name:
            status_by_name[status_name] = status_recording

    recorder_quality_passed = False
    recorders_evaluated: list[dict[str, Any]] = []
    recorder_has_role_arn = False
    recorder_all_supported = False
    recorder_has_explicit_resource_types = False
    recorder_has_resource_coverage = False
    recorder_captures_required_scope = False
    for recorder in recorders:
        name = str(recorder.get("name") or "").strip()
        role_arn_present = bool(str(recorder.get("roleARN") or "").strip())
        recording_group = recorder.get("recordingGroup")
        all_supported = bool((recording_group or {}).get("allSupported")) if isinstance(recording_group, dict) else False
        resource_types = [str(value).strip() for value in _as_list((recording_group or {}).get("resourceTypes")) if str(value).strip()]
        explicit_resource_type_count = len(resource_types)
        explicit_resource_types_present = explicit_resource_type_count > 0
        has_resource_coverage = all_supported or explicit_resource_types_present
        captures_required_scope = all_supported
        if name and name in status_by_name:
            recording_for_recorder = bool(status_by_name.get(name))
        elif len(recorders) == 1:
            recording_for_recorder = recording_any
        else:
            recording_for_recorder = False

        recorder_has_role_arn = recorder_has_role_arn or role_arn_present
        recorder_all_supported = recorder_all_supported or all_supported
        recorder_has_explicit_resource_types = recorder_has_explicit_resource_types or explicit_resource_types_present
        recorder_has_resource_coverage = recorder_has_resource_coverage or has_resource_coverage
        recorder_captures_required_scope = recorder_captures_required_scope or captures_required_scope

        quality_ok = recording_for_recorder and role_arn_present and captures_required_scope
        recorder_quality_passed = recorder_quality_passed or quality_ok
        recorders_evaluated.append(
            {
                "name": name,
                "recording": recording_for_recorder,
                "role_arn_present": role_arn_present,
                "all_supported": all_supported,
                "explicit_resource_type_count": explicit_resource_type_count,
                "has_resource_coverage": has_resource_coverage,
                "captures_required_scope": captures_required_scope,
            }
        )

    delivery_channel_count = len(delivery_channels)
    delivery_channel_present = delivery_channel_count > 0
    delivery_channel_configured = any(
        bool(str(channel.get("name") or "").strip()) and bool(str(channel.get("s3BucketName") or "").strip())
        for channel in delivery_channels
    )
    recording = recording_any
    recorder_status_name_mismatch_count = sum(
        1
        for recorder in recorders
        if str(recorder.get("name") or "").strip()
        and str(recorder.get("name") or "").strip() not in status_by_name
    )
    read_access_denied = status_access_denied or recorders_access_denied or delivery_access_denied
    read_error_codes = [code for code in [recorders_error_code, status_error_code, delivery_error_code] if code]
    has_non_access_read_error = any(
        code and not _is_access_denied_error_code(code)
        for code in [recorders_error_code, status_error_code, delivery_error_code]
    )

    if status_access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_config_describe_configuration_recorder_status"
        confidence = 40
        status_branch = "access_denied_describe_configuration_recorder_status"
    elif recorders_access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_config_describe_configuration_recorders"
        confidence = 40
        status_branch = "access_denied_describe_configuration_recorders"
    elif delivery_access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_config_describe_delivery_channels"
        confidence = 40
        status_branch = "access_denied_describe_delivery_channels"
    elif has_non_access_read_error:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_error_config_read_state"
        confidence = 40
        status_branch = "api_error_read_state"
    elif len(recorders) > 1 and recorder_status_name_mismatch_count > 0:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_partial_data_config_recorder_status_mismatch"
        confidence = 50
        status_branch = "partial_data_recorder_status_mismatch"
    else:
        compliant = recorder_quality_passed and delivery_channel_present and delivery_channel_configured
        status = SHADOW_STATUS_RESOLVED if compliant else SHADOW_STATUS_OPEN
        reason = "inventory_confirmed_compliant" if compliant else "inventory_confirmed_non_compliant"
        confidence = 95
        status_branch = "normal"
    resource_id = account_id
    resource_type = "AwsAccount"
    evals = [
        _control_eval(
            control_id="Config.1",
            resource_id=resource_id,
            resource_type=resource_type,
            status=status,
            title="AWS Config recorder enabled",
            description="Inventory reconciliation for Config.1.",
            status_reason=reason,
            evidence_ref={
                "source": "inventory",
                "recorder_count": len(recorders),
                "recorder_status_count": len(statuses),
                "recording": recording,
                "recorder_quality_passed": recorder_quality_passed,
                "recorder_has_role_arn": recorder_has_role_arn,
                "recorder_all_supported": recorder_all_supported,
                "recorder_has_explicit_resource_types": recorder_has_explicit_resource_types,
                "recorder_has_resource_coverage": recorder_has_resource_coverage,
                "recorder_captures_required_scope": recorder_captures_required_scope,
                "delivery_channel_count": delivery_channel_count,
                "delivery_channel_present": delivery_channel_present,
                "delivery_channel_configured": delivery_channel_configured,
                "recorders_access_denied": recorders_access_denied,
                "status_access_denied": status_access_denied,
                "delivery_access_denied": delivery_access_denied,
                "recorders_error_code": recorders_error_code,
                "status_error_code": status_error_code,
                "delivery_error_code": delivery_error_code,
                "read_access_denied": read_access_denied,
                "read_error_codes": read_error_codes,
                "recorder_status_name_mismatch_count": recorder_status_name_mismatch_count,
                "status_branch": status_branch,
                "recorders_evaluated": recorders_evaluated,
            },
            state_confidence=confidence,
        )
    ]
    state_for_hash = {
        "recorder_count": len(recorders),
        "recording": recording,
        "recorder_quality_passed": recorder_quality_passed,
        "recorder_captures_required_scope": recorder_captures_required_scope,
        "delivery_channel_present": delivery_channel_present,
        "delivery_channel_configured": delivery_channel_configured,
        "recorders_access_denied": recorders_access_denied,
        "status_access_denied": status_access_denied,
        "delivery_access_denied": delivery_access_denied,
        "recorders_error_code": recorders_error_code,
        "status_error_code": status_error_code,
        "delivery_error_code": delivery_error_code,
        "recorder_status_name_mismatch_count": recorder_status_name_mismatch_count,
        "status_branch": status_branch,
    }
    return [
        InventorySnapshot(
            service="config",
            resource_id=resource_id,
            resource_type=resource_type,
            key_fields=state_for_hash.copy(),
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=evals,
        )
    ]


def _collect_iam_account(
    session_boto: Any,
    account_id: str,
    region: str,
) -> list[InventorySnapshot]:
    iam = session_boto.client("iam", region_name=region)
    summary = (iam.get_account_summary() or {}).get("SummaryMap") or {}
    root_keys_present = int(summary.get("AccountAccessKeysPresent") or 0)
    compliant = root_keys_present == 0
    evals = [
        _control_eval(
            control_id="IAM.4",
            resource_id=account_id,
            resource_type="AwsAccount",
            status=SHADOW_STATUS_RESOLVED if compliant else SHADOW_STATUS_OPEN,
            title="IAM root access key absent",
            description="Inventory reconciliation for IAM.4.",
            status_reason=("inventory_confirmed_compliant" if compliant else "inventory_confirmed_non_compliant"),
            evidence_ref={"source": "inventory", "root_access_keys_present": root_keys_present},
        )
    ]
    state_for_hash = {"root_access_keys_present": root_keys_present}
    return [
        InventorySnapshot(
            service="iam",
            resource_id=account_id,
            resource_type="AwsAccount",
            key_fields=state_for_hash.copy(),
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=evals,
        )
    ]


def _collect_ebs_account(
    session_boto: Any,
    account_id: str,
    region: str,
) -> list[InventorySnapshot]:
    ec2 = session_boto.client("ec2", region_name=region)
    default_encryption = bool((ec2.get_ebs_encryption_by_default() or {}).get("EbsEncryptionByDefault"))
    snapshot_state: str | None = None
    snapshot_supported = True
    snapshot_access_denied = False
    snapshot_unsupported_operation = False
    snapshot_error_code: str | None = None
    try:
        snapshot_state = str((ec2.get_snapshot_block_public_access_state() or {}).get("State") or "")
    except ClientError as exc:
        code = _extract_error_code(exc)
        snapshot_error_code = code
        if code in {"UnsupportedOperation", "UnsupportedOperationException", "InvalidRequest", "OperationNotSupportedException"}:
            snapshot_supported = False
            snapshot_unsupported_operation = True
        elif code in {"AccessDenied", "AccessDeniedException"}:
            snapshot_supported = False
            snapshot_access_denied = True
        elif code == "ThrottlingException":
            raise
        else:
            raise

    ebs7_compliant = default_encryption
    ec2182_compliant = snapshot_supported and snapshot_state == "block-all-sharing"
    if snapshot_access_denied:
        ec2182_status = SHADOW_STATUS_SOFT_RESOLVED
        ec2182_reason = "inventory_access_denied_ec2_snapshot_block_public_access"
        ec2182_confidence = 40
    elif snapshot_unsupported_operation:
        ec2182_status = SHADOW_STATUS_SOFT_RESOLVED
        ec2182_reason = "inventory_unsupported_operation_ec2_snapshot_block_public_access"
        ec2182_confidence = 40
    elif ec2182_compliant:
        ec2182_status = SHADOW_STATUS_RESOLVED
        ec2182_reason = "inventory_confirmed_compliant"
        ec2182_confidence = 95
    else:
        ec2182_status = SHADOW_STATUS_OPEN
        ec2182_reason = "inventory_confirmed_non_compliant"
        ec2182_confidence = 95

    resource_id = f"AWS::::Account:{account_id}"
    resource_type = "AwsAccount"
    snapshot_block_public_access_resource_id = (
        f"arn:aws:ec2:{region}:{account_id}:snapshotblockpublicaccess/{account_id}"
    )
    snapshot_block_public_access_resource_type = "AwsEc2SnapshotBlockPublicAccess"
    evals = [
        _control_eval(
            control_id="EC2.7",
            resource_id=resource_id,
            resource_type=resource_type,
            status=SHADOW_STATUS_RESOLVED if ebs7_compliant else SHADOW_STATUS_OPEN,
            title="EBS default encryption enabled",
            description="Inventory reconciliation for EC2.7.",
            status_reason=("inventory_confirmed_compliant" if ebs7_compliant else "inventory_confirmed_non_compliant"),
            evidence_ref={"source": "inventory", "ebs_encryption_by_default": default_encryption},
        ),
        _control_eval(
            control_id="EC2.182",
            resource_id=resource_id,
            resource_type=resource_type,
            status=ec2182_status,
            title="EBS snapshot public sharing block enabled",
            description="Inventory reconciliation for EC2.182.",
            status_reason=ec2182_reason,
            evidence_ref={
                "source": "inventory",
                "snapshot_block_public_access_state": snapshot_state,
                "api_supported": snapshot_supported,
                "access_denied": snapshot_access_denied,
                "unsupported_operation": snapshot_unsupported_operation,
                "error_code": snapshot_error_code,
            },
            state_confidence=ec2182_confidence,
        ),
    ]
    ec2182_arn_eval = _control_eval(
        control_id="EC2.182",
        resource_id=snapshot_block_public_access_resource_id,
        resource_type=snapshot_block_public_access_resource_type,
        status=ec2182_status,
        title="EBS snapshot public sharing block enabled",
        description="Inventory reconciliation for EC2.182.",
        status_reason=ec2182_reason,
        evidence_ref={
            "source": "inventory",
            "snapshot_block_public_access_state": snapshot_state,
            "api_supported": snapshot_supported,
            "access_denied": snapshot_access_denied,
            "unsupported_operation": snapshot_unsupported_operation,
            "error_code": snapshot_error_code,
        },
        state_confidence=ec2182_confidence,
    )
    state_for_hash = {
        "ebs_encryption_by_default": default_encryption,
        "snapshot_block_public_access_state": snapshot_state,
        "snapshot_api_supported": snapshot_supported,
        "snapshot_access_denied": snapshot_access_denied,
        "snapshot_unsupported_operation": snapshot_unsupported_operation,
        "snapshot_error_code": snapshot_error_code,
    }
    return [
        InventorySnapshot(
            service="ebs",
            resource_id=resource_id,
            resource_type=resource_type,
            key_fields=state_for_hash.copy(),
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=evals,
        ),
        InventorySnapshot(
            service="ebs",
            resource_id=snapshot_block_public_access_resource_id,
            resource_type=snapshot_block_public_access_resource_type,
            key_fields=state_for_hash.copy(),
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=[ec2182_arn_eval],
        ),
    ]


def _collect_rds_instances(
    session_boto: Any,
    region: str,
    resource_ids: list[str] | None,
    max_resources: int,
) -> list[InventorySnapshot]:
    rds = session_boto.client("rds", region_name=region)
    public_access_unsupported_evidence = _unsupported_control_evidence(
        _RDS_PUBLIC_ACCESS_UNSUPPORTED_DECISION
    )
    encryption_unsupported_evidence = _unsupported_control_evidence(
        _RDS_ENCRYPTION_UNSUPPORTED_DECISION
    )
    instances: list[dict[str, Any]] = []
    if resource_ids:
        for rid in resource_ids:
            try:
                resp = rds.describe_db_instances(DBInstanceIdentifier=str(rid))
                instances.extend(_as_list(resp.get("DBInstances")))
            except ClientError as exc:
                if _extract_error_code(exc) == "DBInstanceNotFound":
                    instances.append({"DBInstanceArn": f"arn:aws:rds:{region}:account:db:{rid}", "_deleted_marker": True})
                    continue
                raise
    else:
        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate(PaginationConfig={"PageSize": 100}):
            for inst in _as_list(page.get("DBInstances")):
                if not isinstance(inst, dict):
                    continue
                instances.append(inst)
                if len(instances) >= max_resources:
                    break
            if len(instances) >= max_resources:
                break

    snapshots: list[InventorySnapshot] = []
    for inst in instances:
        identifier = str(inst.get("DBInstanceIdentifier") or "").strip()
        if not identifier:
            continue
        public = bool(inst.get("PubliclyAccessible"))
        encrypted = bool(inst.get("StorageEncrypted"))
        evals = [
            _control_eval(
                control_id=_RDS_PUBLIC_ACCESS_CONTROL_ID,
                resource_id=identifier,
                resource_type="AwsRdsDbInstance",
                status=SHADOW_STATUS_OPEN if public else SHADOW_STATUS_RESOLVED,
                title="RDS instance is publicly accessible",
                description="Inventory-only signal for RDS network exposure.",
                status_reason=("inventory_confirmed_non_compliant" if public else "inventory_confirmed_compliant"),
                evidence_ref={
                    "source": "inventory",
                    "publicly_accessible": public,
                    **public_access_unsupported_evidence,
                },
            ),
            _control_eval(
                control_id=_RDS_ENCRYPTION_CONTROL_ID,
                resource_id=identifier,
                resource_type="AwsRdsDbInstance",
                status=SHADOW_STATUS_RESOLVED if encrypted else SHADOW_STATUS_OPEN,
                title="RDS storage encryption enabled",
                description="Inventory-only signal for RDS at-rest encryption.",
                status_reason=("inventory_confirmed_compliant" if encrypted else "inventory_confirmed_non_compliant"),
                evidence_ref={
                    "source": "inventory",
                    "storage_encrypted": encrypted,
                    **encryption_unsupported_evidence,
                },
                severity_label="MEDIUM",
            ),
        ]
        state_for_hash = {
            "publicly_accessible": public,
            "storage_encrypted": encrypted,
            "engine": inst.get("Engine"),
            "db_instance_status": inst.get("DBInstanceStatus"),
        }
        key_fields = {
            "db_instance_identifier": identifier,
            "publicly_accessible": public,
            "storage_encrypted": encrypted,
            "engine": inst.get("Engine"),
        }
        snapshots.append(
            InventorySnapshot(
                service="rds",
                resource_id=identifier,
                resource_type="AwsRdsDbInstance",
                key_fields=key_fields,
                state_for_hash=state_for_hash,
                metadata_json=None,
                evaluations=evals,
            )
        )
    return snapshots


def _collect_eks_clusters(
    session_boto: Any,
    region: str,
    resource_ids: list[str] | None,
    max_resources: int,
) -> list[InventorySnapshot]:
    eks = session_boto.client("eks", region_name=region)
    unsupported_evidence = _unsupported_control_evidence(_EKS_PUBLIC_ENDPOINT_UNSUPPORTED_DECISION)
    if resource_ids:
        cluster_names = [str(v).strip() for v in resource_ids if str(v).strip()]
    else:
        cluster_names = []
        paginator = eks.get_paginator("list_clusters")
        for page in paginator.paginate():
            for name in _as_list(page.get("clusters")):
                cluster_names.append(str(name))
                if len(cluster_names) >= max_resources:
                    break
            if len(cluster_names) >= max_resources:
                break

    snapshots: list[InventorySnapshot] = []
    for cluster_name in cluster_names:
        try:
            cluster = (eks.describe_cluster(name=cluster_name) or {}).get("cluster") or {}
        except ClientError as exc:
            if _extract_error_code(exc) == "ResourceNotFoundException":
                cluster = {"_deleted_marker": True}
            else:
                raise
        if cluster.get("_deleted_marker"):
            evals = [
                _control_eval(
                    control_id=_EKS_PUBLIC_ENDPOINT_CONTROL_ID,
                    resource_id=cluster_name,
                    resource_type="AwsEksCluster",
                    status=SHADOW_STATUS_RESOLVED,
                    title="EKS API endpoint publicly reachable",
                    description="Inventory-only signal for EKS control-plane exposure.",
                    status_reason="inventory_resource_deleted",
                    evidence_ref={"source": "inventory", "resource_deleted": True, **unsupported_evidence},
                )
            ]
            snapshots.append(
                InventorySnapshot(
                    service="eks",
                    resource_id=cluster_name,
                    resource_type="AwsEksCluster",
                    key_fields={"cluster_name": cluster_name, "deleted": True},
                    state_for_hash={"cluster_name": cluster_name, "deleted": True},
                    metadata_json={"cluster_name": "DELETED"},
                    evaluations=evals,
                )
            )
            continue
            
        vpc_cfg = cluster.get("resourcesVpcConfig") if isinstance(cluster, dict) else {}
        if not isinstance(vpc_cfg, dict):
            vpc_cfg = {}
        endpoint_public = bool(vpc_cfg.get("endpointPublicAccess"))
        public_cidrs = [str(v) for v in _as_list(vpc_cfg.get("publicAccessCidrs"))]
        world_exposed = endpoint_public and (not public_cidrs or WORLD_IPV4 in public_cidrs)
        evals = [
            _control_eval(
                control_id=_EKS_PUBLIC_ENDPOINT_CONTROL_ID,
                resource_id=cluster_name,
                resource_type="AwsEksCluster",
                status=SHADOW_STATUS_OPEN if world_exposed else SHADOW_STATUS_RESOLVED,
                title="EKS API endpoint publicly reachable",
                description="Inventory-only signal for EKS control-plane exposure.",
                status_reason=(
                    "inventory_confirmed_non_compliant" if world_exposed else "inventory_confirmed_compliant"
                ),
                evidence_ref={
                    "source": "inventory",
                    "endpoint_public_access": endpoint_public,
                    "public_access_cidrs": public_cidrs,
                    **unsupported_evidence,
                },
            )
        ]
        state_for_hash = {
            "endpoint_public_access": endpoint_public,
            "public_access_cidrs": public_cidrs,
            "endpoint_private_access": bool(vpc_cfg.get("endpointPrivateAccess")),
        }
        key_fields = {
            "cluster_name": cluster_name,
            "endpoint_public_access": endpoint_public,
            "public_access_cidrs": public_cidrs,
        }
        snapshots.append(
            InventorySnapshot(
                service="eks",
                resource_id=cluster_name,
                resource_type="AwsEksCluster",
                key_fields=key_fields,
                state_for_hash=state_for_hash,
                metadata_json=None,
                evaluations=evals,
            )
        )
    return snapshots


def _collect_ssm_account(
    session_boto: Any,
    account_id: str,
    region: str,
) -> list[InventorySnapshot]:
    ssm = session_boto.client("ssm", region_name=region)
    setting_id = "/ssm/documents/console/public-sharing-permission"
    setting_value: str | None = None
    setting_value_present = False
    supported = True
    access_denied = False
    unsupported_operation = False
    partial_data = False
    api_error = False
    error_code: str | None = None
    try:
        resp = ssm.get_service_setting(SettingId=setting_id)
        service_setting = resp.get("ServiceSetting") if isinstance(resp, dict) else {}
        if isinstance(service_setting, dict):
            raw = service_setting.get("SettingValue")
            setting_value_present = raw is not None
            setting_value = str(raw).strip().lower() if raw is not None else None
        else:
            partial_data = True
    except ClientError as exc:
        code = _extract_error_code(exc)
        error_code = code
        if _is_access_denied_error_code(code):
            supported = False
            access_denied = True
        elif code == "ThrottlingException":
            raise
        elif code in {
            "UnsupportedOperationException",
            "UnsupportedOperation",
            "OperationNotSupportedException",
            "NotSupportedException",
        }:
            supported = False
            unsupported_operation = True
        else:
            supported = False
            api_error = True

    enabled_tokens = {"enabled", "true", "1", "on"}
    if supported and not setting_value_present:
        partial_data = True
    public_sharing_enabled = bool(setting_value in enabled_tokens)
    if access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_ssm_get_service_setting"
        confidence = 40
        status_branch = "access_denied"
    elif unsupported_operation:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_unsupported_operation_ssm_default_host_management"
        confidence = 40
        status_branch = "unsupported_operation"
    elif api_error:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_error_ssm_get_service_setting"
        confidence = 40
        status_branch = "api_error"
    elif partial_data:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_partial_data_ssm_get_service_setting"
        confidence = 50
        status_branch = "partial_data"
    elif supported:
        status = SHADOW_STATUS_OPEN if public_sharing_enabled else SHADOW_STATUS_RESOLVED
        reason = "inventory_confirmed_non_compliant" if public_sharing_enabled else "inventory_confirmed_compliant"
        confidence = 90
        status_branch = "normal"
    else:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_unavailable"
        confidence = 40
        status_branch = "api_unavailable"
    resource_id = account_id
    resource_type = "AwsAccount"
    evals = [
        _control_eval(
            control_id="SSM.7",
            resource_id=resource_id,
            resource_type=resource_type,
            status=status,
            title="SSM document public sharing blocked",
            description="Inventory reconciliation for SSM.7.",
            status_reason=reason,
            evidence_ref={
                "source": "inventory",
                "setting_id": setting_id,
                "setting_value": setting_value,
                "setting_value_present": setting_value_present,
                "api_supported": supported,
                "access_denied": access_denied,
                "unsupported_operation": unsupported_operation,
                "partial_data": partial_data,
                "api_error": api_error,
                "error_code": error_code,
                "status_branch": status_branch,
            },
            state_confidence=confidence,
        )
    ]
    state_for_hash = {
        "setting_id": setting_id,
        "setting_value": setting_value,
        "setting_value_present": setting_value_present,
        "api_supported": supported,
        "access_denied": access_denied,
        "unsupported_operation": unsupported_operation,
        "partial_data": partial_data,
        "api_error": api_error,
        "error_code": error_code,
        "status_branch": status_branch,
    }
    return [
        InventorySnapshot(
            service="ssm",
            resource_id=resource_id,
            resource_type=resource_type,
            key_fields=state_for_hash.copy(),
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=evals,
        )
    ]


def _collect_guardduty_account(
    session_boto: Any,
    account_id: str,
    region: str,
) -> list[InventorySnapshot]:
    guardduty = session_boto.client("guardduty", region_name=region)
    detector_ids: list[str] = []
    access_ok = True
    list_access_denied = False
    list_error_code: str | None = None
    try:
        next_token: str | None = None
        while True:
            request: dict[str, Any] = {}
            if next_token:
                request["NextToken"] = next_token
            page = guardduty.list_detectors(**request)
            page_ids = [str(v) for v in _as_list((page or {}).get("DetectorIds")) if str(v).strip()]
            detector_ids.extend(page_ids)
            raw_next_token = (page or {}).get("NextToken")
            next_token = str(raw_next_token).strip() if raw_next_token else None
            if not next_token:
                break
    except ClientError as exc:
        code = _extract_error_code(exc)
        list_error_code = code
        if _is_access_denied_error_code(code):
            access_ok = False
            list_access_denied = True
        else:
            access_ok = False

    detector_statuses: list[str] = []
    has_enabled_detector = False
    detector_access_denied = False
    detector_access_denied_count = 0
    detector_invalid_input_count = 0
    detector_api_error_count = 0
    detector_api_error_codes: list[str] = []
    detector_status_read_success_count = 0
    if access_ok:
        for detector_id in detector_ids:
            try:
                status = str((guardduty.get_detector(DetectorId=detector_id) or {}).get("Status") or "").upper()
            except ClientError as exc:
                code = _extract_error_code(exc)
                if _is_access_denied_error_code(code):
                    detector_access_denied = True
                    detector_access_denied_count += 1
                    continue
                if code in {"InvalidInputException", "BadRequestException"}:
                    detector_invalid_input_count += 1
                    continue
                detector_api_error_count += 1
                detector_api_error_codes.append(code)
                continue
            detector_status_read_success_count += 1
            if status:
                detector_statuses.append(status)
            if status == "ENABLED":
                has_enabled_detector = True

    if list_access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_guardduty_list_detectors"
        confidence = 40
        status_branch = "access_denied_list_detectors"
    elif list_error_code is not None:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_error_guardduty_list_detectors"
        confidence = 40
        status_branch = "api_error_list_detectors"
    elif detector_access_denied:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_guardduty_get_detector"
        confidence = 40
        status_branch = "access_denied_get_detector"
    elif detector_api_error_count > 0:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_error_guardduty_get_detector"
        confidence = 40
        status_branch = "api_error_get_detector"
    elif detector_ids and detector_invalid_input_count == len(detector_ids):
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_partial_data_guardduty_invalid_detector_ids"
        confidence = 50
        status_branch = "partial_data_invalid_detector_ids"
    elif has_enabled_detector:
        status = SHADOW_STATUS_RESOLVED
        reason = "inventory_confirmed_compliant"
        confidence = 95
        status_branch = "normal_compliant"
    else:
        status = SHADOW_STATUS_OPEN
        reason = "inventory_confirmed_non_compliant"
        confidence = 95
        status_branch = "normal_non_compliant"

    state_for_hash = {
        "detector_count": len(detector_ids),
        "detector_statuses": detector_statuses,
        "access_ok": access_ok,
        "list_access_denied": list_access_denied,
        "list_error_code": list_error_code,
        "detector_access_denied": detector_access_denied,
        "detector_access_denied_count": detector_access_denied_count,
        "detector_invalid_input_count": detector_invalid_input_count,
        "detector_api_error_count": detector_api_error_count,
        "detector_api_error_codes": detector_api_error_codes,
        "detector_status_read_success_count": detector_status_read_success_count,
        "status_branch": status_branch,
    }
    # GuardDuty.1 findings are account-scoped (AwsAccount). Keep the same
    # identity here so shadow evaluation can attach to the target finding.
    resource_id = account_id
    resource_type = "AwsAccount"
    return [
        InventorySnapshot(
            service="guardduty",
            resource_id=resource_id,
            resource_type=resource_type,
            key_fields=state_for_hash.copy(),
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=[
                _control_eval(
                    control_id="GuardDuty.1",
                    resource_id=resource_id,
                    resource_type=resource_type,
                    status=status,
                    title="GuardDuty detector enabled",
                    description="Inventory reconciliation for GuardDuty.1.",
                    status_reason=reason,
                    evidence_ref={
                        "source": "inventory",
                        "detector_ids": detector_ids,
                        "detector_statuses": detector_statuses,
                        "access_ok": access_ok,
                        "list_access_denied": list_access_denied,
                        "list_error_code": list_error_code,
                        "detector_access_denied": detector_access_denied,
                        "detector_access_denied_count": detector_access_denied_count,
                        "detector_invalid_input_count": detector_invalid_input_count,
                        "detector_api_error_count": detector_api_error_count,
                        "detector_api_error_codes": detector_api_error_codes,
                        "detector_status_read_success_count": detector_status_read_success_count,
                        "status_branch": status_branch,
                    },
                    state_confidence=confidence,
                )
            ],
        )
    ]


def _collect_securityhub_account(
    session_boto: Any,
    account_id: str,
    region: str,
) -> list[InventorySnapshot]:
    securityhub = session_boto.client("securityhub", region_name=region)
    enabled = False
    access_ok = True
    hub_arn: str | None = None
    partial_data = False
    api_error = False
    not_enabled_error = False
    error_code: str | None = None
    try:
        describe_resp = securityhub.describe_hub() or {}
        hub_arn = str(describe_resp.get("HubArn") or "").strip() or None
        enabled = bool(hub_arn)
        if not enabled:
            partial_data = True
    except ClientError as exc:
        error_code = _extract_error_code(exc)
        if error_code in {"InvalidAccessException", "ResourceNotFoundException"}:
            not_enabled_error = True
            enabled = False
        elif _is_access_denied_error_code(error_code):
            access_ok = False
        else:
            api_error = True

    if not access_ok:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_access_denied_securityhub_describe_hub"
        confidence = 40
        status_branch = "access_denied"
    elif api_error:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_api_error_securityhub_describe_hub"
        confidence = 40
        status_branch = "api_error"
    elif partial_data:
        status = SHADOW_STATUS_SOFT_RESOLVED
        reason = "inventory_partial_data_securityhub_describe_hub"
        confidence = 50
        status_branch = "partial_data"
    elif enabled:
        status = SHADOW_STATUS_RESOLVED
        reason = "inventory_confirmed_compliant"
        confidence = 95
        status_branch = "normal_compliant"
    else:
        status = SHADOW_STATUS_OPEN
        reason = "inventory_confirmed_non_compliant"
        confidence = 95
        status_branch = "normal_non_compliant"

    # SecurityHub.1 findings are account-scoped (AwsAccount). Keep the same
    # identity here so shadow evaluation can attach to the target finding.
    resource_id = account_id
    resource_type = "AwsAccount"
    state_for_hash = {
        "enabled": enabled,
        "hub_arn": hub_arn,
        "access_ok": access_ok,
        "partial_data": partial_data,
        "api_error": api_error,
        "not_enabled_error": not_enabled_error,
        "error_code": error_code,
        "status_branch": status_branch,
    }
    return [
        InventorySnapshot(
            service="securityhub",
            resource_id=resource_id,
            resource_type=resource_type,
            key_fields=state_for_hash.copy(),
            state_for_hash=state_for_hash,
            metadata_json=None,
            evaluations=[
                _control_eval(
                    control_id="SecurityHub.1",
                    resource_id=resource_id,
                    resource_type=resource_type,
                    status=status,
                    title="Security Hub enabled",
                    description="Inventory reconciliation for SecurityHub.1.",
                    status_reason=reason,
                    evidence_ref={
                        "source": "inventory",
                        "enabled": enabled,
                        "hub_arn": hub_arn,
                        "access_ok": access_ok,
                        "partial_data": partial_data,
                        "api_error": api_error,
                        "not_enabled_error": not_enabled_error,
                        "error_code": error_code,
                        "status_branch": status_branch,
                    },
                    state_confidence=confidence,
                )
            ],
        )
    ]


def collect_inventory_snapshots(
    session_boto: Any,
    account_id: str,
    region: str,
    service: str,
    resource_ids: list[str] | None = None,
    max_resources: int = 500,
) -> list[InventorySnapshot]:
    svc = (service or "").strip().lower()
    if svc == "ec2":
        return _collect_ec2_security_groups(session_boto, region, resource_ids, max_resources)
    if svc == "s3":
        return _collect_s3_buckets(session_boto, account_id, region, resource_ids, max_resources)
    if svc == "cloudtrail":
        return _collect_cloudtrail_account(session_boto, account_id, region)
    if svc == "config":
        return _collect_config_account(session_boto, account_id, region)
    if svc == "iam":
        return _collect_iam_account(session_boto, account_id, region)
    if svc == "ebs":
        return _collect_ebs_account(session_boto, account_id, region)
    if svc == "rds":
        return _collect_rds_instances(session_boto, region, resource_ids, max_resources)
    if svc == "eks":
        return _collect_eks_clusters(session_boto, region, resource_ids, max_resources)
    if svc == "ssm":
        return _collect_ssm_account(session_boto, account_id, region)
    if svc == "guardduty":
        return _collect_guardduty_account(session_boto, account_id, region)
    if svc == "securityhub":
        return _collect_securityhub_account(session_boto, account_id, region)
    return []
