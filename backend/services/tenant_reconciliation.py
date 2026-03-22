from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.aws_account import AwsAccount
from backend.models.tenant import Tenant
from backend.models.tenant_reconcile_run import TenantReconcileRun
from backend.models.tenant_reconcile_run_shard import TenantReconcileRunShard
from backend.models.user import User
from backend.services.aws import (
    API_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)
from backend.services.aws_config_probe import (
    CONFIG_COMPLIANCE_SUMMARY_PERMISSION,
    describe_non_compliant_config_rule_summary,
)
from backend.utils.sqs import build_reconcile_inventory_shard_job_payload, parse_queue_region

logger = logging.getLogger(__name__)

_ACCESS_DENIED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedAccess",
    "UnauthorizedOperation",
}

_SERVICE_PERMISSION_HINTS: dict[str, list[str]] = {
    "ec2": ["ec2:DescribeSecurityGroups"],
    "s3": [
        "s3:ListAllMyBuckets",
        "s3:GetBucketPublicAccessBlock",
        "s3:GetBucketPolicyStatus",
        "s3:GetBucketPolicy",
        "s3:GetBucketLocation",
        "s3:GetEncryptionConfiguration",
        "s3:GetBucketLogging",
        "s3:GetLifecycleConfiguration",
    ],
    "cloudtrail": ["cloudtrail:DescribeTrails"],
    "config": [
        "config:DescribeConfigurationRecorders",
        "config:DescribeDeliveryChannels",
        "config:DescribeConfigRules",
        CONFIG_COMPLIANCE_SUMMARY_PERMISSION,
        "config:GetComplianceDetailsByConfigRule",
    ],
    "iam": ["iam:ListAccountAliases"],
    "ebs": ["ec2:DescribeVolumes"],
    "rds": ["rds:DescribeDBInstances"],
    "eks": ["eks:ListClusters"],
    "ssm": ["ssm:DescribeInstanceInformation"],
    "guardduty": ["guardduty:ListDetectors"],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _extract_error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "ClientError")
    return type(exc).__name__


def _is_access_denied(code: str) -> bool:
    return code in _ACCESS_DENIED_CODES


def _dedup(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def ensure_tenant_reconciliation_enabled(tenant_id: uuid.UUID) -> None:
    if settings.TENANT_RECONCILIATION_ENABLED:
        return
    if str(tenant_id) in settings.tenant_reconciliation_pilot_tenants_list:
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Tenant reconciliation is not enabled for this tenant.",
    )


def normalize_services(services: list[str] | None) -> list[str]:
    allowed = settings.control_plane_inventory_services_list
    allowed_set = set(allowed)
    if not services:
        selected = list(allowed)
    else:
        selected = []
        for raw in services:
            token = str(raw).strip().lower()
            if not token:
                continue
            if token not in allowed_set:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported service '{token}'. Allowed services: {', '.join(sorted(allowed_set))}",
                )
            selected.append(token)
        selected = _dedup(selected)
    if not selected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one service is required.")
    if len(selected) > int(settings.TENANT_RECONCILIATION_MAX_SERVICES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {settings.TENANT_RECONCILIATION_MAX_SERVICES} services are allowed per run.",
        )
    return selected


def normalize_regions(regions: list[str] | None, account_regions: list[str] | None) -> list[str]:
    account_region_set = {str(region).strip() for region in (account_regions or []) if str(region).strip()}
    if not account_region_set:
        account_region_set = {settings.AWS_REGION}

    if not regions:
        return sorted(account_region_set)

    selected = _dedup([str(region).strip() for region in regions if str(region).strip()])
    invalid = sorted([region for region in selected if region not in account_region_set])
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Selected regions are not configured on this account: "
                f"{', '.join(invalid)}. Allowed: {', '.join(sorted(account_region_set))}"
            ),
        )
    return selected


def normalize_sweep_mode(raw_value: str | None) -> str:
    mode = str(raw_value or "").strip().lower()
    return mode if mode in {"targeted", "global"} else "global"


def normalize_max_resources(max_resources: int | None) -> int:
    default_value = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)
    if max_resources is None:
        value = default_value
    else:
        value = int(max_resources)
    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_resources must be greater than zero.",
        )
    cap = int(settings.TENANT_RECONCILIATION_MAX_RESOURCES_CAP or 5000)
    if value > cap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"max_resources exceeds tenant cap ({cap}).",
        )
    return value


async def run_preflight_for_services(
    *,
    account: AwsAccount,
    tenant: Tenant,
    services: list[str],
    regions: list[str],
) -> dict[str, Any]:
    """
    Best-effort IAM/service preflight for selected reconciliation services.

    Returns:
    - ok: bool
    - assume_role_ok: bool
    - assume_role_error: str | None
    - missing_permissions: list[str]
    - warnings: list[str]
    - service_checks: list[dict]
    """

    probe_region = (regions or [settings.AWS_REGION])[0]

    def _run() -> dict[str, Any]:
        warnings: list[str] = []
        missing_permissions: list[str] = []
        service_checks: list[dict[str, Any]] = []

        try:
            session = assume_role(
                role_arn=account.role_read_arn,
                external_id=tenant.external_id,
                source_identity=API_ASSUME_ROLE_SOURCE_IDENTITY,
                tags=build_assume_role_tags(service_component="api", tenant_id=tenant.id),
            )
        except Exception as exc:
            return {
                "ok": False,
                "assume_role_ok": False,
                "assume_role_error": _extract_error_code(exc),
                "missing_permissions": [],
                "warnings": [str(exc)],
                "service_checks": [],
            }

        def _add_service_check(service: str, ok: bool, service_missing: list[str], service_warnings: list[str]) -> None:
            service_checks.append(
                {
                    "service": service,
                    "ok": ok,
                    "missing_permissions": _dedup(service_missing),
                    "warnings": _dedup(service_warnings),
                }
            )

        for service in services:
            service_missing: list[str] = []
            service_warnings: list[str] = []

            try:
                if service == "ec2":
                    session.client("ec2", region_name=probe_region).describe_security_groups(MaxResults=5)
                elif service == "s3":
                    s3_client = session.client("s3", region_name=probe_region)
                    buckets = s3_client.list_buckets().get("Buckets") or []
                    if buckets:
                        bucket_name = str((buckets[0] or {}).get("Name") or "").strip()
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
                                    getattr(s3_client, call_name)(Bucket=bucket_name)
                                except ClientError as exc:
                                    code = _extract_error_code(exc)
                                    if _is_access_denied(code):
                                        service_missing.append(required_action)
                                    elif code not in ignored_codes:
                                        service_warnings.append(f"{call_name}:{code}")
                    else:
                        service_warnings.append("No buckets found to probe bucket-level permissions.")
                elif service == "cloudtrail":
                    session.client("cloudtrail", region_name=probe_region).describe_trails(includeShadowTrails=False)
                elif service == "config":
                    config_client = session.client("config", region_name=probe_region)
                    config_client.describe_configuration_recorders()
                    config_client.describe_delivery_channels()
                    config_rules = config_client.describe_config_rules().get("ConfigRules") or []
                    compliance_probe = describe_non_compliant_config_rule_summary(config_client, limit=1)
                    if compliance_probe.unavailable_reason:
                        service_missing.append(CONFIG_COMPLIANCE_SUMMARY_PERMISSION)
                        service_warnings.append(compliance_probe.unavailable_reason)
                    if config_rules:
                        first_rule_name = str((config_rules[0] or {}).get("ConfigRuleName") or "").strip()
                        if first_rule_name:
                            config_client.get_compliance_details_by_config_rule(
                                ConfigRuleName=first_rule_name,
                                ComplianceTypes=["NON_COMPLIANT"],
                                Limit=1,
                            )
                    else:
                        service_warnings.append("No AWS Config rules found to probe config:GetComplianceDetailsByConfigRule.")
                elif service == "iam":
                    session.client("iam").list_account_aliases(MaxItems=5)
                elif service == "ebs":
                    session.client("ec2", region_name=probe_region).describe_volumes(MaxResults=5)
                elif service == "rds":
                    session.client("rds", region_name=probe_region).describe_db_instances(MaxRecords=5)
                elif service == "eks":
                    session.client("eks", region_name=probe_region).list_clusters(maxResults=5)
                elif service == "ssm":
                    session.client("ssm", region_name=probe_region).describe_instance_information(MaxResults=5)
                elif service == "guardduty":
                    session.client("guardduty", region_name=probe_region).list_detectors(MaxResults=5)
                else:
                    service_warnings.append(f"No preflight probe implemented for {service}.")
            except ClientError as exc:
                code = _extract_error_code(exc)
                required_actions = _SERVICE_PERMISSION_HINTS.get(service, [])
                if _is_access_denied(code) and required_actions:
                    service_missing.extend(required_actions)
                else:
                    service_warnings.append(code)
            except Exception as exc:  # pragma: no cover - defensive guard
                service_warnings.append(type(exc).__name__)

            missing_permissions.extend(service_missing)
            warnings.extend(service_warnings)
            _add_service_check(
                service=service,
                ok=len(service_missing) == 0,
                service_missing=service_missing,
                service_warnings=service_warnings,
            )

        missing_permissions = _dedup(missing_permissions)
        warnings = _dedup(warnings)
        return {
            "ok": len(missing_permissions) == 0,
            "assume_role_ok": True,
            "assume_role_error": None,
            "missing_permissions": missing_permissions,
            "warnings": warnings,
            "service_checks": service_checks,
        }

    from asyncio import to_thread

    return await to_thread(_run)


async def create_reconciliation_run(
    *,
    db: AsyncSession,
    tenant: Tenant,
    account: AwsAccount,
    requested_by: User | None,
    trigger_type: str,
    services: list[str],
    regions: list[str],
    sweep_mode: str,
    max_resources: int,
    cooldown_seconds: int,
) -> TenantReconcileRun:
    if not settings.has_inventory_reconcile_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory reconcile queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
        )

    now = _utcnow()
    if cooldown_seconds > 0:
        latest_run = (
            await db.execute(
                select(TenantReconcileRun)
                .where(
                    TenantReconcileRun.tenant_id == tenant.id,
                    TenantReconcileRun.account_id == account.account_id,
                )
                .order_by(desc(TenantReconcileRun.submitted_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest_run and latest_run.submitted_at:
            elapsed = (now - latest_run.submitted_at).total_seconds()
            if elapsed < cooldown_seconds:
                retry_after = int(max(1, cooldown_seconds - elapsed))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Reconciliation cooldown active for this account. "
                        f"Retry in about {retry_after} seconds."
                    ),
                )

    run = TenantReconcileRun(
        tenant_id=tenant.id,
        account_id=account.account_id,
        trigger_type=trigger_type,
        status="queued",
        requested_by_user_id=(requested_by.id if requested_by is not None else None),
        requested_by_email=(requested_by.email if requested_by is not None else None),
        regions=regions,
        services=services,
        sweep_mode=sweep_mode,
        max_resources=max_resources,
        total_shards=len(regions) * len(services),
        enqueued_shards=0,
        running_shards=0,
        succeeded_shards=0,
        failed_shards=0,
        submitted_at=now,
    )
    db.add(run)
    await db.flush()

    queue_url = settings.SQS_INVENTORY_RECONCILE_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    for region in regions:
        for service in services:
            shard = TenantReconcileRunShard(
                run_id=run.id,
                tenant_id=tenant.id,
                account_id=account.account_id,
                region=region,
                service=service,
                status="queued",
                attempt_count=0,
            )
            db.add(shard)
            await db.flush()

            payload = build_reconcile_inventory_shard_job_payload(
                tenant_id=tenant.id,
                account_id=account.account_id,
                region=region,
                service=service,
                created_at=now.isoformat(),
                sweep_mode=sweep_mode,
                max_resources=max_resources,
                run_id=run.id,
                run_shard_id=shard.id,
            )
            try:
                response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
                shard.queue_message_id = str(response.get("MessageId") or "")
                run.enqueued_shards += 1
            except Exception as exc:
                code = _extract_error_code(exc)
                shard.status = "failed"
                shard.error_code = code
                shard.error_message = str(exc)[:4000]
                shard.completed_at = now
                run.failed_shards += 1
                run.last_error = shard.error_message
                logger.exception(
                    "Failed to enqueue reconcile shard run_id=%s shard_id=%s tenant_id=%s account_id=%s region=%s service=%s: %s",
                    run.id,
                    shard.id,
                    tenant.id,
                    account.account_id,
                    region,
                    service,
                    exc,
                )

    if run.enqueued_shards == 0:
        run.status = "failed"
        run.completed_at = now
    elif run.failed_shards > 0:
        run.status = "partial_failed"
    else:
        run.status = "queued"

    await db.commit()
    await db.refresh(run)
    return run


def classify_reconcile_exception(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, ClientError):
        code = _extract_error_code(exc)
        operation = str(getattr(exc, "operation_name", "") or "").strip()
        if operation.lower() == "assumerole":
            return (f"AssumeRole:{code}", str(exc))
        return (code, str(exc))
    return (type(exc).__name__, str(exc))


def mark_reconcile_shard_running(session: Session, run_shard_id: str | uuid.UUID) -> None:
    now = _utcnow()
    try:
        shard_uuid = uuid.UUID(str(run_shard_id))
    except ValueError:
        return
    shard = session.query(TenantReconcileRunShard).filter(TenantReconcileRunShard.id == shard_uuid).first()
    if shard is None:
        return

    run = session.query(TenantReconcileRun).filter(TenantReconcileRun.id == shard.run_id).first()
    if run is None:
        return

    prior_status = str(shard.status or "").lower()
    if prior_status == "running":
        shard.attempt_count = int(shard.attempt_count or 0) + 1
        return

    if prior_status == "failed":
        run.failed_shards = max(0, int(run.failed_shards or 0) - 1)
    elif prior_status == "succeeded":
        run.succeeded_shards = max(0, int(run.succeeded_shards or 0) - 1)

    shard.status = "running"
    shard.started_at = shard.started_at or now
    shard.completed_at = None
    shard.attempt_count = int(shard.attempt_count or 0) + 1
    run.running_shards = int(run.running_shards or 0) + 1
    run.started_at = run.started_at or now
    run.status = "running"


def _recompute_run_status(run: TenantReconcileRun, now: datetime) -> None:
    total = int(run.total_shards or 0)
    running = int(run.running_shards or 0)
    succeeded = int(run.succeeded_shards or 0)
    failed = int(run.failed_shards or 0)
    done = succeeded + failed

    if total > 0 and done >= total:
        if failed == 0:
            run.status = "succeeded"
        elif succeeded == 0:
            run.status = "failed"
        else:
            run.status = "partial_failed"
        run.completed_at = now
        run.running_shards = 0
        return

    if running > 0 or done > 0:
        run.status = "running"
        run.started_at = run.started_at or now
        run.completed_at = None
        return

    run.status = "queued"


def mark_reconcile_shard_finished(
    session: Session,
    run_shard_id: str | uuid.UUID,
    *,
    status_value: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    now = _utcnow()
    try:
        shard_uuid = uuid.UUID(str(run_shard_id))
    except ValueError:
        return
    shard = session.query(TenantReconcileRunShard).filter(TenantReconcileRunShard.id == shard_uuid).first()
    if shard is None:
        return

    run = session.query(TenantReconcileRun).filter(TenantReconcileRun.id == shard.run_id).first()
    if run is None:
        return

    prior_status = str(shard.status or "").lower()
    next_status = "succeeded" if status_value == "succeeded" else "failed"

    if prior_status == "running":
        run.running_shards = max(0, int(run.running_shards or 0) - 1)
    elif prior_status == "failed":
        run.failed_shards = max(0, int(run.failed_shards or 0) - 1)
    elif prior_status == "succeeded":
        run.succeeded_shards = max(0, int(run.succeeded_shards or 0) - 1)

    shard.status = next_status
    shard.started_at = shard.started_at or now
    shard.completed_at = now
    shard.error_code = (error_code or "")[:128] or None
    shard.error_message = (error_message or "")[:4000] or None

    if next_status == "succeeded":
        run.succeeded_shards = int(run.succeeded_shards or 0) + 1
    else:
        run.failed_shards = int(run.failed_shards or 0) + 1
        if shard.error_message:
            run.last_error = shard.error_message

    _recompute_run_status(run, now)
