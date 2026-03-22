"""
Shared reconciliation prechecks extracted from internal router orchestration.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence

from botocore.exceptions import ClientError

from backend.models.aws_account import AwsAccount
from backend.services.aws import (
    API_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)
from backend.services.aws_config_probe import (
    CONFIG_COMPLIANCE_SUMMARY_PERMISSION,
    describe_non_compliant_config_rule_summary,
)


def extract_error_code(exc: Exception) -> str:
    """Return a stable error code for logging and API responses."""
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "ClientError")
    return type(exc).__name__


def is_access_denied_code(code: str) -> bool:
    return code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "UnauthorizedAccess"}


def deduplicate_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


async def assume_role_precheck(account: AwsAccount, tenant_external_id: str) -> tuple[bool, str | None]:
    """Best-effort assume-role sanity check used by global reconcile scheduling."""

    def _run() -> tuple[bool, str | None]:
        try:
            session = assume_role(
                role_arn=account.role_read_arn,
                external_id=tenant_external_id,
                source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
                tags=build_assume_role_tags(service_component="api", tenant_id=account.tenant_id),
            )
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            caller = str(identity.get("Account") or "")
            if caller and caller != str(account.account_id):
                return False, f"AccountMismatch:{caller}"
            return True, None
        except Exception as exc:  # pragma: no cover - defensive guard
            return False, extract_error_code(exc)

    return await asyncio.to_thread(_run)


async def authoritative_permissions_precheck(
    account: AwsAccount,
    tenant_external_id: str,
    region: str,
) -> tuple[bool, list[str]]:
    """Probe read permissions required for authoritative control-plane mode."""

    def _run() -> tuple[bool, list[str]]:
        missing: list[str] = []
        try:
            session = assume_role(
                role_arn=account.role_read_arn,
                external_id=tenant_external_id,
                source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
                tags=build_assume_role_tags(service_component="api", tenant_id=account.tenant_id),
            )
        except Exception as exc:
            return False, [f"assume_role:{extract_error_code(exc)}"]

        try:
            session.client("securityhub", region_name=region).get_findings(MaxResults=1)
        except ClientError as exc:
            if is_access_denied_code(extract_error_code(exc)):
                missing.append("securityhub:GetFindings")

        try:
            session.client("ec2", region_name=region).describe_security_groups(MaxResults=5)
        except ClientError as exc:
            if is_access_denied_code(extract_error_code(exc)):
                missing.append("ec2:DescribeSecurityGroups")

        config_client = session.client("config", region_name=region)
        config_rule_names: list[str] = []
        try:
            config_client.describe_configuration_recorders()
        except ClientError as exc:
            if is_access_denied_code(extract_error_code(exc)):
                missing.append("config:DescribeConfigurationRecorders")

        try:
            config_client.describe_delivery_channels()
        except ClientError as exc:
            if is_access_denied_code(extract_error_code(exc)):
                missing.append("config:DescribeDeliveryChannels")

        try:
            response = config_client.describe_config_rules()
            config_rule_names = [str(rule.get("ConfigRuleName") or "").strip() for rule in (response.get("ConfigRules") or []) if rule]
            config_rule_names = [name for name in config_rule_names if name]
        except ClientError as exc:
            if is_access_denied_code(extract_error_code(exc)):
                missing.append("config:DescribeConfigRules")

        try:
            compliance_probe = describe_non_compliant_config_rule_summary(config_client, limit=1)
            if compliance_probe.unavailable_reason:
                missing.append(CONFIG_COMPLIANCE_SUMMARY_PERMISSION)
        except ClientError as exc:
            if is_access_denied_code(extract_error_code(exc)):
                missing.append(CONFIG_COMPLIANCE_SUMMARY_PERMISSION)

        if config_rule_names:
            try:
                config_client.get_compliance_details_by_config_rule(
                    ConfigRuleName=config_rule_names[0],
                    ComplianceTypes=["NON_COMPLIANT"],
                    Limit=1,
                )
            except ClientError as exc:
                if is_access_denied_code(extract_error_code(exc)):
                    missing.append("config:GetComplianceDetailsByConfigRule")

        buckets: list[dict] = []
        try:
            buckets = session.client("s3", region_name=region).list_buckets().get("Buckets") or []
        except ClientError as exc:
            if is_access_denied_code(extract_error_code(exc)):
                missing.append("s3:ListAllMyBuckets")

        if buckets:
            s3 = session.client("s3", region_name=region)
            bucket_name = str((buckets[0] or {}).get("Name") or "").strip()
            if bucket_name:
                probes = (
                    (
                        "get_public_access_block",
                        "s3:GetBucketPublicAccessBlock",
                        {"NoSuchPublicAccessBlockConfiguration", "NoSuchBucket"},
                    ),
                    ("get_bucket_policy_status", "s3:GetBucketPolicyStatus", {"NoSuchBucketPolicy", "NoSuchBucket"}),
                    ("get_bucket_policy", "s3:GetBucketPolicy", {"NoSuchBucketPolicy", "NoSuchBucket"}),
                    ("get_bucket_location", "s3:GetBucketLocation", {"NoSuchBucket"}),
                    (
                        "get_bucket_encryption",
                        "s3:GetEncryptionConfiguration",
                        {"ServerSideEncryptionConfigurationNotFoundError", "NoSuchBucket"},
                    ),
                    ("get_bucket_logging", "s3:GetBucketLogging", {"NoSuchBucket"}),
                    (
                        "get_bucket_lifecycle_configuration",
                        "s3:GetLifecycleConfiguration",
                        {"NoSuchLifecycleConfiguration", "NoSuchBucket"},
                    ),
                )
                for call_name, required_action, ignored_codes in probes:
                    try:
                        getattr(s3, call_name)(Bucket=bucket_name)
                    except ClientError as exc:
                        code = extract_error_code(exc)
                        if is_access_denied_code(code):
                            missing.append(required_action)
                        elif code in ignored_codes:
                            continue

        deduped_missing = deduplicate_strings(missing)
        return (len(deduped_missing) == 0, deduped_missing)

    return await asyncio.to_thread(_run)
