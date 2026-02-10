"""
Control-plane event intake helpers (phase 1).

This module focuses on:
- event filtering (management events + explicit allowlist)
- synchronous read-after-write enrichment
- posture evaluation for high-value controls
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

SUPPORTED_DETAIL_TYPE = "AWS API Call via CloudTrail"
WORLD_IPV4 = "0.0.0.0/0"
WORLD_IPV6 = "::/0"
ADMIN_PORTS = (22, 3389)

SG_EVENT_NAMES = {
    "AuthorizeSecurityGroupIngress",
    "RevokeSecurityGroupIngress",
    "ModifySecurityGroupRules",
    "UpdateSecurityGroupRuleDescriptionsIngress",
}
S3_EVENT_NAMES = {
    "PutBucketPolicy",
    "DeleteBucketPolicy",
    "PutBucketAcl",
    "PutPublicAccessBlock",
    "DeletePublicAccessBlock",
}
SUPPORTED_EVENT_NAMES = SG_EVENT_NAMES | S3_EVENT_NAMES

SHADOW_STATUS_OPEN = "OPEN"
SHADOW_STATUS_RESOLVED = "RESOLVED"
SHADOW_STATUS_SOFT_RESOLVED = "SOFT_RESOLVED"


@dataclass
class ControlEvaluation:
    control_id: str
    resource_id: str
    resource_type: str
    severity_label: str
    title: str
    description: str
    status: str
    status_reason: str
    state_confidence: int
    evidence_ref: dict[str, Any]


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_fingerprint(
    account_id: str,
    region: str,
    resource_id: str,
    control_id: str,
) -> str:
    # Deliberately deterministic and human-readable for debugging/audit.
    return f"{account_id}|{region}|{resource_id}|{control_id}"


def is_supported_management_event(event: dict[str, Any]) -> tuple[bool, str | None]:
    detail_type = str(event.get("detail-type") or "").strip()
    if detail_type != SUPPORTED_DETAIL_TYPE:
        return False, f"unsupported_detail_type:{detail_type or 'missing'}"

    detail = event.get("detail") or {}
    event_name = str(detail.get("eventName") or "").strip()
    if not event_name:
        return False, "missing_event_name"
    if event_name not in SUPPORTED_EVENT_NAMES:
        return False, f"unsupported_event_name:{event_name}"

    event_category = str(detail.get("eventCategory") or "").strip().upper()
    # Some EventBridge deliveries omit eventCategory for management APIs; allow missing.
    if event_category and event_category != "MANAGEMENT":
        return False, f"unsupported_event_category:{event_category}"

    return True, None


def _collect_str_values(node: Any, key: str) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        v = node.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
        for child in node.values():
            out.extend(_collect_str_values(child, key))
    elif isinstance(node, list):
        for child in node:
            out.extend(_collect_str_values(child, key))
    return out


def extract_security_group_ids(event: dict[str, Any]) -> list[str]:
    detail = event.get("detail") or {}
    request = detail.get("requestParameters") or {}
    response = detail.get("responseElements") or {}

    values = []
    values.extend(_collect_str_values(request, "groupId"))
    values.extend(_collect_str_values(response, "groupId"))

    resources = event.get("resources") or []
    if isinstance(resources, list):
        for r in resources:
            arn = str((r or {}).get("ARN") or "").strip()
            if ":security-group/" in arn:
                values.append(arn.rsplit("/", 1)[-1])

    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if not v.startswith("sg-"):
            continue
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def extract_s3_bucket_names(event: dict[str, Any]) -> list[str]:
    detail = event.get("detail") or {}
    request = detail.get("requestParameters") or {}
    values: list[str] = []

    bucket = request.get("bucketName")
    if isinstance(bucket, str) and bucket.strip():
        values.append(bucket.strip())

    resources = event.get("resources") or []
    if isinstance(resources, list):
        for r in resources:
            arn = str((r or {}).get("ARN") or "").strip()
            if arn.startswith("arn:aws:s3:::"):
                values.append(arn.replace("arn:aws:s3:::", "", 1))

    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _port_matches_admin(from_port: int | None, to_port: int | None, protocol: str | None) -> bool:
    proto = (protocol or "").lower()
    if proto in {"-1", "all"}:
        return True
    if proto != "tcp":
        return False
    if from_port is None or to_port is None:
        return False
    for p in ADMIN_PORTS:
        if from_port <= p <= to_port:
            return True
    return False


def evaluate_security_group_public_admin_ports(group: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    violations: list[dict[str, Any]] = []
    for perm in group.get("IpPermissions") or []:
        if not isinstance(perm, dict):
            continue
        from_port = perm.get("FromPort")
        to_port = perm.get("ToPort")
        protocol = perm.get("IpProtocol")
        if not _port_matches_admin(from_port, to_port, protocol):
            continue

        for r in perm.get("IpRanges") or []:
            cidr = str((r or {}).get("CidrIp") or "")
            if cidr == WORLD_IPV4:
                violations.append(
                    {
                        "ip_protocol": protocol,
                        "from_port": from_port,
                        "to_port": to_port,
                        "cidr": cidr,
                    }
                )
        for r in perm.get("Ipv6Ranges") or []:
            cidr = str((r or {}).get("CidrIpv6") or "")
            if cidr == WORLD_IPV6:
                violations.append(
                    {
                        "ip_protocol": protocol,
                        "from_port": from_port,
                        "to_port": to_port,
                        "cidr": cidr,
                    }
                )
    return (len(violations) > 0, violations)


def evaluate_s3_bucket_public_posture(
    public_access_block: dict[str, Any] | None,
    policy_is_public: bool,
) -> tuple[bool, dict[str, Any]]:
    pab = public_access_block or {}
    required = (
        "BlockPublicAcls",
        "IgnorePublicAcls",
        "BlockPublicPolicy",
        "RestrictPublicBuckets",
    )
    pab_all_on = all(bool(pab.get(k)) for k in required)
    non_compliant = bool(policy_is_public or not pab_all_on)
    return (
        non_compliant,
        {
            "policy_is_public": bool(policy_is_public),
            "public_access_block": {k: bool(pab.get(k)) for k in required},
        },
    )


def _extract_error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "ClientError")
    return type(exc).__name__


def _is_not_found_error(exc: Exception) -> bool:
    code = _extract_error_code(exc)
    return code in {
        "InvalidGroup.NotFound",
        "NoSuchBucket",
        "NoSuchBucketPolicy",
        "NoSuchPublicAccessBlockConfiguration",
    }


def evaluate_security_group_control(
    session_boto: Any,
    region: str,
    group_id: str,
    event_name: str,
) -> ControlEvaluation:
    ec2 = session_boto.client("ec2", region_name=region)
    try:
        response = ec2.describe_security_groups(GroupIds=[group_id])
    except Exception as exc:
        if _is_not_found_error(exc):
            return ControlEvaluation(
                control_id="EC2.53",
                resource_id=group_id,
                resource_type="AwsEc2SecurityGroup",
                severity_label="HIGH",
                title="Security group allows public admin access",
                description="Security group is absent; treat control as resolved for this fingerprint.",
                status=SHADOW_STATUS_RESOLVED,
                status_reason="resource_not_found_after_change",
                state_confidence=90,
                evidence_ref={"event_name": event_name, "resource_state": "not_found"},
            )
        raise

    groups = response.get("SecurityGroups") or []
    if not groups:
        return ControlEvaluation(
            control_id="EC2.53",
            resource_id=group_id,
            resource_type="AwsEc2SecurityGroup",
            severity_label="HIGH",
            title="Security group allows public admin access",
            description="Security group state could not be loaded; mark as soft-resolved until reconciliation.",
            status=SHADOW_STATUS_SOFT_RESOLVED,
            status_reason="empty_enrichment_result",
            state_confidence=50,
            evidence_ref={"event_name": event_name, "resource_state": "empty"},
        )

    non_compliant, violations = evaluate_security_group_public_admin_ports(groups[0])
    if non_compliant:
        return ControlEvaluation(
            control_id="EC2.53",
            resource_id=group_id,
            resource_type="AwsEc2SecurityGroup",
            severity_label="HIGH",
            title="Security group allows public SSH/RDP access",
            description="Inbound rule exposes SSH/RDP to the internet (0.0.0.0/0 or ::/0).",
            status=SHADOW_STATUS_OPEN,
            status_reason="enrichment_confirmed_non_compliant",
            state_confidence=95,
            evidence_ref={"event_name": event_name, "violations": violations},
        )

    return ControlEvaluation(
        control_id="EC2.53",
        resource_id=group_id,
        resource_type="AwsEc2SecurityGroup",
        severity_label="HIGH",
        title="Security group allows public SSH/RDP access",
        description="Security group no longer exposes SSH/RDP publicly.",
        status=SHADOW_STATUS_RESOLVED,
        status_reason="enrichment_confirmed_compliant",
        state_confidence=95,
        evidence_ref={"event_name": event_name, "violations": []},
    )


def _get_bucket_policy_is_public(s3_client: Any, bucket_name: str) -> bool:
    try:
        resp = s3_client.get_bucket_policy_status(Bucket=bucket_name)
        return bool((resp.get("PolicyStatus") or {}).get("IsPublic"))
    except ClientError as exc:
        code = _extract_error_code(exc)
        if code in {"NoSuchBucketPolicy", "NoSuchBucket"}:
            return False
        raise


def _get_bucket_public_access_block(s3_client: Any, bucket_name: str) -> dict[str, Any]:
    try:
        resp = s3_client.get_public_access_block(Bucket=bucket_name)
        return resp.get("PublicAccessBlockConfiguration") or {}
    except ClientError as exc:
        code = _extract_error_code(exc)
        if code in {"NoSuchPublicAccessBlockConfiguration", "NoSuchBucket"}:
            return {}
        raise


def evaluate_s3_control(
    session_boto: Any,
    region: str,
    bucket_name: str,
    event_name: str,
) -> ControlEvaluation:
    s3 = session_boto.client("s3", region_name=region)
    policy_public = _get_bucket_policy_is_public(s3, bucket_name)
    pab = _get_bucket_public_access_block(s3, bucket_name)
    non_compliant, evidence = evaluate_s3_bucket_public_posture(pab, policy_public)
    resource_id = f"arn:aws:s3:::{bucket_name}"

    if non_compliant:
        return ControlEvaluation(
            control_id="S3.2",
            resource_id=resource_id,
            resource_type="AwsS3Bucket",
            severity_label="HIGH",
            title="S3 bucket public access block is incomplete or bucket policy is public",
            description="Bucket is potentially publicly accessible based on effective posture checks.",
            status=SHADOW_STATUS_OPEN,
            status_reason="enrichment_confirmed_non_compliant",
            state_confidence=95,
            evidence_ref={"event_name": event_name, **evidence},
        )

    return ControlEvaluation(
        control_id="S3.2",
        resource_id=resource_id,
        resource_type="AwsS3Bucket",
        severity_label="HIGH",
        title="S3 bucket public access block is incomplete or bucket policy is public",
        description="Bucket public exposure checks are compliant.",
        status=SHADOW_STATUS_RESOLVED,
        status_reason="enrichment_confirmed_compliant",
        state_confidence=95,
        evidence_ref={"event_name": event_name, **evidence},
    )


def derive_control_evaluations(
    session_boto: Any,
    account_id: str,
    region: str,
    event: dict[str, Any],
) -> list[ControlEvaluation]:
    detail = event.get("detail") or {}
    event_name = str(detail.get("eventName") or "").strip()
    if not event_name:
        return []

    out: list[ControlEvaluation] = []
    if event_name in SG_EVENT_NAMES:
        sg_ids = extract_security_group_ids(event)
        for sg_id in sg_ids:
            out.append(evaluate_security_group_control(session_boto, region, sg_id, event_name))

    if event_name in S3_EVENT_NAMES:
        bucket_names = extract_s3_bucket_names(event)
        for bucket_name in bucket_names:
            out.append(evaluate_s3_control(session_boto, region, bucket_name, event_name))

    # For now we intentionally support a narrow allowlist.
    _ = account_id
    return out


__all__ = [
    "ADMIN_PORTS",
    "ControlEvaluation",
    "SG_EVENT_NAMES",
    "S3_EVENT_NAMES",
    "SHADOW_STATUS_OPEN",
    "SHADOW_STATUS_RESOLVED",
    "SHADOW_STATUS_SOFT_RESOLVED",
    "SUPPORTED_DETAIL_TYPE",
    "SUPPORTED_EVENT_NAMES",
    "build_fingerprint",
    "derive_control_evaluations",
    "evaluate_s3_bucket_public_posture",
    "evaluate_security_group_public_admin_ports",
    "extract_s3_bucket_names",
    "extract_security_group_ids",
    "is_supported_management_event",
    "parse_iso_datetime",
]
