"""
Shared orchestration helpers for AWS account router endpoints.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.finding import Finding


AssumeRoleFn = Callable[..., Any]


class IngestRegionResolutionError(ValueError):
    """Raised when ingest region overrides are invalid."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ValidationProbeResult:
    permissions_ok: bool
    missing_permissions: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class RegionServiceReadinessResult:
    region: str
    security_hub_enabled: bool
    aws_config_enabled: bool
    access_analyzer_enabled: bool
    inspector_enabled: bool
    security_hub_error: str | None
    aws_config_error: str | None
    access_analyzer_error: str | None
    inspector_error: str | None


@dataclass(frozen=True)
class ServiceReadinessSummary:
    all_security_hub_enabled: bool
    all_aws_config_enabled: bool
    all_access_analyzer_enabled: bool
    all_inspector_enabled: bool
    missing_security_hub_regions: list[str]
    missing_aws_config_regions: list[str]
    missing_access_analyzer_regions: list[str]
    missing_inspector_regions: list[str]
    regions: list[RegionServiceReadinessResult]


def _dedup_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _client_error_code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code") or "ClientError")


def _is_access_denied(code: str) -> bool:
    return code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "UnauthorizedAccess"}


def validate_registration_role_accounts(
    *,
    account_id: str,
    role_read_arn: str,
    role_write_arn: str | None,
) -> None:
    """Ensure role ARN account IDs match the requested AWS account_id."""
    arns_to_validate = [("role_read_arn", role_read_arn)]
    if role_write_arn:
        arns_to_validate.append(("role_write_arn", role_write_arn))
    for arn_name, arn_value in arns_to_validate:
        arn_parts = arn_value.split(":")
        if len(arn_parts) < 5:
            raise ValueError(f"Invalid {arn_name} format: {arn_value}")
        if arn_parts[4] != account_id:
            raise ValueError(
                f"account_id {account_id} does not match the account ID in {arn_name} ({arn_parts[4]})"
            )


def assume_and_verify_role_account(
    *,
    role_arn: str,
    external_id: str,
    account_id: str,
    role_label: str,
    assume_role_fn: AssumeRoleFn,
) -> Any:
    """Assume a role and verify caller identity account match."""
    session = assume_role_fn(role_arn=role_arn, external_id=external_id)
    caller_account_id = session.client("sts").get_caller_identity().get("Account")
    if caller_account_id != account_id:
        raise ValueError(
            f"Account ID mismatch ({role_label}): expected {account_id}, got {caller_account_id}"
        )
    return session


def run_validation_probes(
    *,
    account_id: str,
    role_read_arn: str,
    tenant_external_id: str,
    configured_regions: Sequence[str] | None,
    default_region: str,
    assume_role_fn: AssumeRoleFn,
) -> ValidationProbeResult:
    """
    Run baseline ReadRole probes used by POST /validate.

    Raises ValueError for caller-identity mismatch and ClientError for AWS failures.
    """
    session = assume_and_verify_role_account(
        role_arn=role_read_arn,
        external_id=tenant_external_id,
        account_id=account_id,
        role_label="ReadRole",
        assume_role_fn=assume_role_fn,
    )
    region = (list(configured_regions or []) or [default_region])[0]
    missing_permissions: list[str] = []
    warnings: list[str] = []

    try:
        session.client("securityhub", region_name=region).get_findings(MaxResults=1)
    except ClientError as error:
        code = _client_error_code(error)
        if _is_access_denied(code):
            missing_permissions.append("securityhub:GetFindings")
        else:
            warnings.append(f"Security Hub probe failed: {code}")

    try:
        session.client("ec2", region_name=region).describe_security_groups(MaxResults=5)
    except ClientError as error:
        code = _client_error_code(error)
        if _is_access_denied(code):
            missing_permissions.append("ec2:DescribeSecurityGroups")
        else:
            warnings.append(f"EC2 probe failed: {code}")

    buckets: list[dict] = []
    try:
        buckets = (session.client("s3", region_name=region).list_buckets().get("Buckets") or [])
    except ClientError as error:
        code = _client_error_code(error)
        if _is_access_denied(code):
            missing_permissions.append("s3:ListAllMyBuckets")
        else:
            warnings.append(f"S3 list_buckets probe failed: {code}")

    if buckets:
        s3 = session.client("s3", region_name=region)
        bucket_name = str(buckets[0].get("Name") or "").strip()
        if bucket_name:
            probes = (
                ("get_public_access_block", "s3:GetBucketPublicAccessBlock", {"NoSuchPublicAccessBlockConfiguration", "NoSuchBucket"}),
                ("get_bucket_policy_status", "s3:GetBucketPolicyStatus", {"NoSuchBucketPolicy", "NoSuchBucket"}),
                ("get_bucket_policy", "s3:GetBucketPolicy", {"NoSuchBucketPolicy", "NoSuchBucket"}),
                ("get_bucket_location", "s3:GetBucketLocation", {"NoSuchBucket"}),
                ("get_bucket_encryption", "s3:GetEncryptionConfiguration", {"ServerSideEncryptionConfigurationNotFoundError", "NoSuchBucket"}),
                ("get_bucket_logging", "s3:GetBucketLogging", {"NoSuchBucket"}),
                ("get_bucket_lifecycle_configuration", "s3:GetLifecycleConfiguration", {"NoSuchLifecycleConfiguration", "NoSuchBucket"}),
            )
            for call_name, required_action, ignored_codes in probes:
                try:
                    getattr(s3, call_name)(Bucket=bucket_name)
                except ClientError as error:
                    code = _client_error_code(error)
                    if _is_access_denied(code):
                        missing_permissions.append(required_action)
                    elif code not in ignored_codes:
                        warnings.append(f"S3 {call_name} probe failed: {code}")
    else:
        warnings.append("No S3 buckets found to probe bucket-level read permissions.")

    deduped_missing = _dedup_preserve_order(missing_permissions)
    deduped_warnings = _dedup_preserve_order(warnings)
    return ValidationProbeResult(
        permissions_ok=len(deduped_missing) == 0,
        missing_permissions=deduped_missing,
        warnings=deduped_warnings,
    )


def resolve_ingest_regions(
    *,
    account_regions: Sequence[str] | None,
    override_regions: Sequence[str] | None,
) -> list[str]:
    """Resolve ingest target regions with subset validation."""
    resolved_account_regions = list(account_regions or [])
    if override_regions is not None:
        requested = list(override_regions)
        if not requested:
            raise IngestRegionResolutionError("override_empty")
        allowed = set(resolved_account_regions)
        if any(region not in allowed for region in requested):
            raise IngestRegionResolutionError("override_not_subset")
        resolved_regions = requested
    else:
        resolved_regions = resolved_account_regions

    if not resolved_regions:
        raise IngestRegionResolutionError("no_regions")
    return resolved_regions


async def _has_findings_for_source(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: str,
    region: str,
    source: str,
) -> bool:
    stmt = (
        select(Finding.id)
        .where(
            Finding.tenant_id == tenant_id,
            Finding.account_id == account_id,
            Finding.region == region,
            Finding.source == source,
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def _has_security_hub_control_findings(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: str,
    region: str,
) -> bool:
    stmt = (
        select(Finding.id)
        .where(
            Finding.tenant_id == tenant_id,
            Finding.account_id == account_id,
            Finding.region == region,
            Finding.source == "security_hub",
            Finding.control_id.isnot(None),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def collect_service_readiness(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    account_id: str,
    role_read_arn: str,
    tenant_external_id: str,
    regions: Sequence[str] | None,
    default_region: str,
    assume_role_fn: AssumeRoleFn,
) -> ServiceReadinessSummary:
    """Evaluate Security Hub/Config/AA/Inspector enablement across regions."""
    session = assume_and_verify_role_account(
        role_arn=role_read_arn,
        external_id=tenant_external_id,
        account_id=account_id,
        role_label="ReadRole",
        assume_role_fn=assume_role_fn,
    )

    resolved_regions = list(regions or []) or [default_region]
    region_results: list[RegionServiceReadinessResult] = []
    missing_security_hub_regions: list[str] = []
    missing_aws_config_regions: list[str] = []
    missing_access_analyzer_regions: list[str] = []
    missing_inspector_regions: list[str] = []

    for region in resolved_regions:
        security_hub_enabled = False
        aws_config_enabled = False
        access_analyzer_enabled = False
        inspector_enabled = False
        security_hub_error: str | None = None
        aws_config_error: str | None = None
        access_analyzer_error: str | None = None
        inspector_error: str | None = None

        try:
            session.client("securityhub", region_name=region).describe_hub()
            security_hub_enabled = True
        except ClientError as error:
            security_hub_error = error.response.get("Error", {}).get("Message", str(error))
            if await _has_findings_for_source(
                db,
                tenant_id=tenant_id,
                account_id=account_id,
                region=region,
                source="security_hub",
            ):
                security_hub_enabled = True
                security_hub_error = "Inferred enabled from ingested Security Hub findings."

        try:
            config = session.client("config", region_name=region)
            recorders_resp = config.describe_configuration_recorders()
            recorder_status_resp = config.describe_configuration_recorder_status()
            has_recorders = bool(recorders_resp.get("ConfigurationRecorders"))
            statuses = recorder_status_resp.get("ConfigurationRecordersStatus", [])
            has_active_recorder = any(bool(status.get("recording")) for status in statuses)
            aws_config_enabled = has_recorders and has_active_recorder
            if has_recorders and not has_active_recorder:
                aws_config_error = "AWS Config recorder exists but is not recording."
            elif not has_recorders:
                aws_config_error = "No AWS Config recorder found."
        except ClientError as error:
            aws_config_error = error.response.get("Error", {}).get("Message", str(error))
            if await _has_security_hub_control_findings(
                db,
                tenant_id=tenant_id,
                account_id=account_id,
                region=region,
            ):
                aws_config_enabled = True
                aws_config_error = "Inferred enabled from ingested Security Hub control findings."

        try:
            access_analyzer = session.client("accessanalyzer", region_name=region)
            active_analyzers: list[dict] = []
            for analyzer_scope in ("ACCOUNT", "ORGANIZATION"):
                next_token = None
                while True:
                    kwargs = {"type": analyzer_scope}
                    if next_token:
                        kwargs["nextToken"] = next_token
                    analyzers_resp = access_analyzer.list_analyzers(**kwargs)
                    analyzers = analyzers_resp.get("analyzers", [])
                    active_analyzers.extend(
                        analyzer for analyzer in analyzers if analyzer.get("status") == "ACTIVE"
                    )
                    next_token = analyzers_resp.get("nextToken")
                    if not next_token:
                        break
            access_analyzer_enabled = len(active_analyzers) > 0
            if not access_analyzer_enabled:
                access_analyzer_error = "No active Access Analyzer analyzer found."
        except ClientError as error:
            access_analyzer_error = error.response.get("Error", {}).get("Message", str(error))
            if await _has_findings_for_source(
                db,
                tenant_id=tenant_id,
                account_id=account_id,
                region=region,
                source="access_analyzer",
            ):
                access_analyzer_enabled = True
                access_analyzer_error = "Inferred enabled from ingested Access Analyzer findings."

        try:
            inspector = session.client("inspector2", region_name=region)
            status_resp = inspector.batch_get_account_status(accountIds=[account_id])
            accounts = status_resp.get("accounts", [])
            account_status = accounts[0].get("state", {}).get("status") if accounts else None
            inspector_enabled = account_status == "ENABLED"
            if not inspector_enabled:
                inspector_error = f"Inspector account status is {account_status or 'UNKNOWN'}."
        except ClientError as error:
            inspector_error = error.response.get("Error", {}).get("Message", str(error))
            if await _has_findings_for_source(
                db,
                tenant_id=tenant_id,
                account_id=account_id,
                region=region,
                source="inspector",
            ):
                inspector_enabled = True
                inspector_error = "Inferred enabled from ingested Inspector findings."

        if not security_hub_enabled:
            missing_security_hub_regions.append(region)
        if not aws_config_enabled:
            missing_aws_config_regions.append(region)
        if not access_analyzer_enabled:
            missing_access_analyzer_regions.append(region)
        if not inspector_enabled:
            missing_inspector_regions.append(region)

        region_results.append(
            RegionServiceReadinessResult(
                region=region,
                security_hub_enabled=security_hub_enabled,
                aws_config_enabled=aws_config_enabled,
                access_analyzer_enabled=access_analyzer_enabled,
                inspector_enabled=inspector_enabled,
                security_hub_error=security_hub_error,
                aws_config_error=aws_config_error,
                access_analyzer_error=access_analyzer_error,
                inspector_error=inspector_error,
            )
        )

    return ServiceReadinessSummary(
        all_security_hub_enabled=len(missing_security_hub_regions) == 0,
        all_aws_config_enabled=len(missing_aws_config_regions) == 0,
        all_access_analyzer_enabled=len(missing_access_analyzer_regions) == 0,
        all_inspector_enabled=len(missing_inspector_regions) == 0,
        missing_security_hub_regions=missing_security_hub_regions,
        missing_aws_config_regions=missing_aws_config_regions,
        missing_access_analyzer_regions=missing_access_analyzer_regions,
        missing_inspector_regions=missing_inspector_regions,
        regions=region_results,
    )
