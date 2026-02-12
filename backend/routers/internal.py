"""
Internal API for cron/scheduled jobs (Step 11.1).

Endpoints are protected by shared secrets (e.g. DIGEST_CRON_SECRET).
Used by EventBridge or an external scheduler to trigger weekly digest per tenant.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import AwsAccount
from backend.models.action import Action
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.action_group_run_result import ActionGroupRunResult
from backend.models.aws_account_reconcile_settings import AwsAccountReconcileSettings
from backend.models.control_plane_reconcile_job import ControlPlaneReconcileJob
from backend.models.enums import AwsAccountStatus
from backend.models.enums import ActionGroupExecutionStatus, ActionGroupRunStatus
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.services.action_run_confirmation import (
    evaluate_confirmation_for_action_async,
    record_execution_result_async,
)
from backend.services.bundle_reporting_tokens import verify_group_run_reporting_token
from backend.services.aws import assume_role
from backend.services.control_plane_intake import is_supported_control_plane_event
from backend.services.reconciliation_prereqs import (
    collect_reconciliation_queue_snapshot,
    evaluate_reconciliation_prereqs_async,
)
from backend.services.tenant_reconciliation import (
    create_reconciliation_run,
    ensure_tenant_reconciliation_enabled,
    normalize_max_resources,
    normalize_regions,
    normalize_services,
    normalize_sweep_mode,
)
from backend.utils.sqs import (
    build_backfill_action_groups_job_payload,
    build_backfill_finding_keys_job_payload,
    build_ingest_control_plane_events_job_payload,
    build_reconcile_inventory_global_orchestration_job_payload,
    build_reconcile_inventory_shard_job_payload,
    build_reconcile_recently_touched_resources_job_payload,
    build_weekly_digest_job_payload,
    parse_queue_region,
    RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_JOB_TYPE,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


class ControlPlaneEventEnvelope(BaseModel):
    tenant_id: uuid.UUID = Field(..., description="Tenant UUID")
    account_id: str = Field(..., pattern=r"^\d{12}$")
    region: str = Field(..., min_length=1, max_length=32)
    event: dict = Field(..., description="Raw EventBridge event payload")
    event_id: str | None = Field(default=None, max_length=128)
    intake_time: str | None = Field(default=None, description="ISO timestamp for intake")


class ControlPlaneEventsIngestRequest(BaseModel):
    events: list[ControlPlaneEventEnvelope] = Field(default_factory=list, min_length=1)


class InventoryShardRequest(BaseModel):
    tenant_id: uuid.UUID
    account_id: str = Field(..., pattern=r"^\d{12}$")
    region: str = Field(..., min_length=1, max_length=32)
    service: str = Field(..., min_length=1, max_length=32)
    resource_ids: list[str] | None = None
    sweep_mode: str | None = Field(default=None, pattern=r"^(targeted|global)$")
    max_resources: int | None = Field(default=None, ge=1, le=5000)


class ReconcileInventoryRequest(BaseModel):
    shards: list[InventoryShardRequest] = Field(default_factory=list, min_length=1)


class ReconcileRecentRequest(BaseModel):
    tenant_id: uuid.UUID
    lookback_minutes: int | None = Field(default=None, ge=1, le=1440)
    services: list[str] | None = None
    max_resources: int | None = Field(default=None, ge=1, le=5000)


class ReconcileGlobalRequest(BaseModel):
    tenant_id: uuid.UUID
    account_ids: list[str] | None = None
    regions: list[str] | None = None
    services: list[str] | None = None
    max_resources: int | None = Field(default=None, ge=1, le=5000)
    precheck_assume_role: bool = False
    quarantine_on_assume_role_failure: bool = False


class ReconcileGlobalAllTenantsRequest(BaseModel):
    tenant_ids: list[uuid.UUID] | None = None
    account_ids: list[str] | None = None
    regions: list[str] | None = None
    services: list[str] | None = None
    max_resources: int | None = Field(default=None, ge=1, le=5000)
    precheck_assume_role: bool = False
    quarantine_on_assume_role_failure: bool = False


class BackfillFindingKeysRequest(BaseModel):
    tenant_id: uuid.UUID | None = None
    account_id: str | None = Field(default=None, pattern=r"^\d{12}$")
    region: str | None = Field(default=None, min_length=1, max_length=32)
    enqueue_per_tenant: bool = True
    chunk_size: int = Field(default=1000, ge=50, le=5000)
    max_chunks: int = Field(default=10, ge=1, le=200)
    include_stale: bool = True
    auto_continue: bool = True


class BackfillActionGroupsRequest(BaseModel):
    tenant_id: uuid.UUID | None = None
    account_id: str | None = Field(default=None, pattern=r"^\d{12}$")
    region: str | None = Field(default=None, min_length=1, max_length=32)
    enqueue_per_tenant: bool = True
    chunk_size: int = Field(default=500, ge=50, le=2000)
    max_chunks: int = Field(default=10, ge=1, le=200)
    auto_continue: bool = True


class ReconciliationScheduleTickRequest(BaseModel):
    tenant_ids: list[uuid.UUID] | None = None
    account_ids: list[str] | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    dry_run: bool = False


class GroupRunActionResult(BaseModel):
    action_id: uuid.UUID
    execution_status: str = Field(default="unknown")
    execution_error_code: str | None = Field(default=None, max_length=128)
    execution_error_message: str | None = None
    execution_started_at: str | None = None
    execution_finished_at: str | None = None
    raw_result: dict | None = None


class GroupRunReportRequest(BaseModel):
    token: str
    event: str = Field(pattern=r"^(started|finished)$")
    reporting_source: str | None = Field(default="bundle_callback", max_length=64)
    started_at: str | None = None
    finished_at: str | None = None
    action_results: list[GroupRunActionResult] = Field(default_factory=list)


def _verify_digest_cron_secret(x_digest_cron_secret: str | None) -> None:
    """Raise 403 if secret is not configured or does not match."""
    secret = (settings.DIGEST_CRON_SECRET or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weekly digest cron is not configured (DIGEST_CRON_SECRET unset).",
        )
    if not x_digest_cron_secret or x_digest_cron_secret.strip() != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Digest-Cron-Secret.",
        )


def _verify_control_plane_secret(x_control_plane_secret: str | None) -> None:
    secret = (settings.CONTROL_PLANE_EVENTS_SECRET or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Control-plane event intake is not configured (CONTROL_PLANE_EVENTS_SECRET unset).",
        )
    if not x_control_plane_secret or x_control_plane_secret.strip() != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Control-Plane-Secret.",
        )


def _verify_reconciliation_scheduler_secret(x_reconciliation_scheduler_secret: str | None) -> None:
    secret = (settings.RECONCILIATION_SCHEDULER_SECRET or "").strip() or (settings.CONTROL_PLANE_EVENTS_SECRET or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Reconciliation scheduler is not configured "
                "(RECONCILIATION_SCHEDULER_SECRET and CONTROL_PLANE_EVENTS_SECRET unset)."
            ),
        )
    if not x_reconciliation_scheduler_secret or x_reconciliation_scheduler_secret.strip() != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Reconciliation-Scheduler-Secret.",
        )


def _is_supported_control_plane_event(event: dict) -> tuple[bool, str | None]:
    # Back-compat wrapper for older tests/imports.
    return is_supported_control_plane_event(event)


def _normalized_services(value: list[str] | None) -> list[str]:
    allowed_services = settings.control_plane_inventory_services_list
    allowed_set = set(allowed_services)
    if not value:
        return allowed_services
    services: list[str] = []
    seen: set[str] = set()
    for item in value:
        svc = str(item).strip().lower()
        if not svc or svc in seen or svc not in allowed_set:
            continue
        seen.add(svc)
        services.append(svc)
    return services or allowed_services


def _normalized_regions(value: list[str] | None, fallback_region: str) -> list[str]:
    if not value or not isinstance(value, list):
        return [fallback_region]
    regions: list[str] = []
    seen: set[str] = set()
    for item in value:
        region = str(item).strip()
        if not region or region in seen:
            continue
        seen.add(region)
        regions.append(region)
    return regions or [fallback_region]


def _status_value(raw: object) -> str:
    if raw is None:
        return ""
    value = getattr(raw, "value", None)
    if isinstance(value, str):
        return value
    return str(raw)


def _extract_error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "ClientError")
    return type(exc).__name__


def _parse_iso_utc(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce_execution_status(raw: str) -> ActionGroupExecutionStatus:
    text = (raw or "").strip().lower() or ActionGroupExecutionStatus.unknown.value
    try:
        return ActionGroupExecutionStatus(text)
    except ValueError:
        return ActionGroupExecutionStatus.unknown


async def _assume_role_precheck(account: AwsAccount, tenant_external_id: str) -> tuple[bool, str | None]:
    def _run() -> tuple[bool, str | None]:
        try:
            session = assume_role(role_arn=account.role_read_arn, external_id=tenant_external_id)
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            caller = str(identity.get("Account") or "")
            if caller and caller != str(account.account_id):
                return False, f"AccountMismatch:{caller}"
            return True, None
        except Exception as exc:
            return False, _extract_error_code(exc)

    return await asyncio.to_thread(_run)


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


def _is_access_denied_code(code: str) -> bool:
    return code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "UnauthorizedAccess"}


async def _authoritative_permissions_precheck(
    account: AwsAccount,
    tenant_external_id: str,
    region: str,
) -> tuple[bool, list[str]]:
    def _run() -> tuple[bool, list[str]]:
        missing: list[str] = []
        try:
            session = assume_role(role_arn=account.role_read_arn, external_id=tenant_external_id)
        except Exception as exc:
            return False, [f"assume_role:{_extract_error_code(exc)}"]

        try:
            session.client("securityhub", region_name=region).get_findings(MaxResults=1)
        except ClientError as exc:
            if _is_access_denied_code(_extract_error_code(exc)):
                missing.append("securityhub:GetFindings")

        try:
            session.client("ec2", region_name=region).describe_security_groups(MaxResults=5)
        except ClientError as exc:
            if _is_access_denied_code(_extract_error_code(exc)):
                missing.append("ec2:DescribeSecurityGroups")

        buckets: list[dict] = []
        try:
            buckets = session.client("s3", region_name=region).list_buckets().get("Buckets") or []
        except ClientError as exc:
            if _is_access_denied_code(_extract_error_code(exc)):
                missing.append("s3:ListAllMyBuckets")
        if buckets:
            s3 = session.client("s3", region_name=region)
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
                        getattr(s3, call_name)(Bucket=bucket_name)
                    except ClientError as exc:
                        code = _extract_error_code(exc)
                        if _is_access_denied_code(code):
                            missing.append(required_action)
                        elif code in ignored_codes:
                            continue

        missing = _dedup(missing)
        return (len(missing) == 0, missing)

    return await asyncio.to_thread(_run)


@router.post(
    "/weekly-digest",
    status_code=status.HTTP_200_OK,
    summary="Trigger weekly digest jobs for all tenants",
    description="Lists all tenants and enqueues one weekly_digest job per tenant. "
    "Protected by X-Digest-Cron-Secret. Call from EventBridge (cron) or similar.",
)
async def trigger_weekly_digest(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_digest_cron_secret: Annotated[str | None, Header(alias="X-Digest-Cron-Secret")] = None,
) -> dict:
    """
    Enqueue one weekly_digest job per tenant.
    Requires header: X-Digest-Cron-Secret with value equal to DIGEST_CRON_SECRET.
    """
    _verify_digest_cron_secret(x_digest_cron_secret)

    if not settings.SQS_INGEST_QUEUE_URL or not settings.SQS_INGEST_QUEUE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
        )

    result = await db.execute(select(Tenant))
    tenants = list(result.scalars().all())
    now_iso = datetime.now(timezone.utc).isoformat()
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    enqueued = 0
    for tenant in tenants:
        payload = build_weekly_digest_job_payload(tenant.id, now_iso)
        try:
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            enqueued += 1
        except Exception as e:
            logger.exception("SQS send_message failed for weekly_digest tenant_id=%s: %s", tenant.id, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to enqueue digest job for tenant {tenant.id}: {e}",
            ) from e

    logger.info("weekly_digest trigger enqueued %s jobs for %s tenants", enqueued, len(tenants))
    return {"enqueued": enqueued, "tenants": len(tenants)}


@router.post(
    "/control-plane-events",
    status_code=status.HTTP_200_OK,
    summary="Enqueue control-plane event jobs",
    description=(
        "Accepts EventBridge 'AWS API Call via CloudTrail' management events and "
        "enqueues ingest_control_plane_events jobs to the events-fast-lane queue."
    ),
)
async def enqueue_control_plane_events(
    body: ControlPlaneEventsIngestRequest,
    x_control_plane_secret: Annotated[str | None, Header(alias="X-Control-Plane-Secret")] = None,
) -> dict:
    _verify_control_plane_secret(x_control_plane_secret)

    queue_url = (settings.SQS_EVENTS_FAST_LANE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Events fast-lane queue URL not configured. Set SQS_EVENTS_FAST_LANE_QUEUE_URL.",
        )
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    now_iso = datetime.now(timezone.utc).isoformat()
    enqueued = 0
    dropped = 0
    drop_reasons: dict[str, int] = {}
    for envelope in body.events:
        supported, reason = _is_supported_control_plane_event(envelope.event)
        if not supported:
            dropped += 1
            key = reason or "unsupported"
            drop_reasons[key] = int(drop_reasons.get(key, 0)) + 1
            continue

        event_id = envelope.event_id or str(envelope.event.get("id") or "").strip()
        event_time = str(envelope.event.get("time") or "").strip()
        if not event_id or not event_time:
            dropped += 1
            key = "missing_event_id_or_time"
            drop_reasons[key] = int(drop_reasons.get(key, 0)) + 1
            continue

        payload = build_ingest_control_plane_events_job_payload(
            tenant_id=envelope.tenant_id,
            account_id=envelope.account_id,
            region=envelope.region,
            event=envelope.event,
            event_id=event_id,
            event_time=event_time,
            intake_time=envelope.intake_time or now_iso,
            created_at=now_iso,
        )
        try:
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            enqueued += 1
        except Exception as exc:
            logger.exception(
                "Failed to enqueue control-plane event tenant_id=%s account_id=%s region=%s event_id=%s: %s",
                envelope.tenant_id,
                envelope.account_id,
                envelope.region,
                event_id,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to enqueue event {event_id}: {exc}",
            ) from exc

    return {"enqueued": enqueued, "dropped": dropped, "drop_reasons": drop_reasons}


@router.post(
    "/reconcile-inventory-shard",
    status_code=status.HTTP_200_OK,
    summary="Enqueue inventory reconciliation shard jobs",
    description="Queues reconcile_inventory_shard jobs to the inventory queue.",
)
async def enqueue_inventory_reconcile(
    body: ReconcileInventoryRequest,
    x_control_plane_secret: Annotated[str | None, Header(alias="X-Control-Plane-Secret")] = None,
) -> dict:
    _verify_control_plane_secret(x_control_plane_secret)
    queue_url = (settings.SQS_INVENTORY_RECONCILE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory reconcile queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
        )
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now_iso = datetime.now(timezone.utc).isoformat()

    enqueued = 0
    for shard in body.shards:
        payload = build_reconcile_inventory_shard_job_payload(
            tenant_id=shard.tenant_id,
            account_id=shard.account_id,
            region=shard.region,
            service=shard.service,
            resource_ids=shard.resource_ids,
            sweep_mode=shard.sweep_mode,
            max_resources=shard.max_resources,
            created_at=now_iso,
        )
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        enqueued += 1
    return {"enqueued": enqueued}


@router.post(
    "/reconcile-recently-touched",
    status_code=status.HTTP_200_OK,
    summary="Enqueue targeted reconciliation for recently touched resources",
)
async def enqueue_recent_reconcile(
    body: ReconcileRecentRequest,
    x_control_plane_secret: Annotated[str | None, Header(alias="X-Control-Plane-Secret")] = None,
) -> dict:
    _verify_control_plane_secret(x_control_plane_secret)
    queue_url = (settings.SQS_INVENTORY_RECONCILE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory reconcile queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
        )
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = build_reconcile_recently_touched_resources_job_payload(
        tenant_id=body.tenant_id,
        created_at=now_iso,
        lookback_minutes=body.lookback_minutes,
        services=body.services,
        max_resources=body.max_resources,
    )
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    return {"enqueued": 1}


@router.post(
    "/group-runs/report",
    status_code=status.HTTP_200_OK,
    summary="Bundle callback endpoint for group run lifecycle reporting",
    description=(
        "Accepts signed token-based lifecycle callbacks from downloaded remediation bundles. "
        "Supported events: started, finished."
    ),
)
async def report_group_run_event(
    body: GroupRunReportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        claims = verify_group_run_reporting_token(body.token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid reporting token: {exc}",
        ) from exc

    try:
        tenant_id = uuid.UUID(str(claims["tenant_id"]))
        group_id = uuid.UUID(str(claims["group_id"]))
        group_run_id = uuid.UUID(str(claims["group_run_id"]))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed token UUID claims") from exc
    token_jti = str(claims.get("jti") or "").strip()
    allowed_action_ids: set[uuid.UUID] = set()
    for raw_action_id in claims.get("allowed_action_ids") or []:
        try:
            allowed_action_ids.add(uuid.UUID(str(raw_action_id)))
        except ValueError:
            continue
    if not allowed_action_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has no allowed_action_ids")

    run = (
        await db.execute(
            select(ActionGroupRun).where(
                ActionGroupRun.id == group_run_id,
                ActionGroupRun.tenant_id == tenant_id,
                ActionGroupRun.group_id == group_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="action_group_run not found")
    if (run.report_token_jti or "") != token_jti:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Token jti does not match run")

    membership_rows = (
        await db.execute(
            select(ActionGroupMembership.action_id).where(
                ActionGroupMembership.tenant_id == tenant_id,
                ActionGroupMembership.group_id == group_id,
                ActionGroupMembership.action_id.in_(list(allowed_action_ids)),
            )
        )
    ).all()
    membership_action_ids = {row[0] for row in membership_rows if row and row[0] is not None}
    if membership_action_ids != allowed_action_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Token action set does not match group membership")

    reporting_source = (body.reporting_source or "bundle_callback").strip()[:64] or "bundle_callback"
    started_at = _parse_iso_utc(body.started_at) or datetime.now(timezone.utc)

    if body.event == "started":
        if run.status == ActionGroupRunStatus.queued:
            run.status = ActionGroupRunStatus.started
        if run.started_at is None:
            run.started_at = started_at
        run.reporting_source = reporting_source
        for action_id in list(allowed_action_ids):
            await record_execution_result_async(
                db,
                action_id=action_id,
                latest_run_id=run.id,
                execution_status=ActionGroupExecutionStatus.unknown,
                attempted_at=run.started_at,
            )
        await db.commit()
        return {"status": "accepted", "event": "started", "group_run_id": str(run.id)}

    # finished event
    finished_at = _parse_iso_utc(body.finished_at) or datetime.now(timezone.utc)
    if run.started_at is None:
        run.started_at = started_at
    run.finished_at = finished_at
    run.reporting_source = reporting_source

    provided_results = body.action_results or []
    if provided_results:
        invalid_ids = [str(item.action_id) for item in provided_results if item.action_id not in allowed_action_ids]
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"action_id not allowed by token: {', '.join(invalid_ids)}",
            )
    else:
        provided_results = [
            GroupRunActionResult(action_id=action_id, execution_status=ActionGroupExecutionStatus.unknown.value)
            for action_id in list(allowed_action_ids)
        ]

    has_failed = False
    has_cancelled = False
    for item in provided_results:
        exec_status = _coerce_execution_status(item.execution_status)
        if exec_status == ActionGroupExecutionStatus.failed:
            has_failed = True
        if exec_status == ActionGroupExecutionStatus.cancelled:
            has_cancelled = True

        result_row = (
            await db.execute(
                select(ActionGroupRunResult).where(
                    ActionGroupRunResult.tenant_id == tenant_id,
                    ActionGroupRunResult.group_run_id == run.id,
                    ActionGroupRunResult.action_id == item.action_id,
                )
            )
        ).scalar_one_or_none()
        if result_row is None:
            result_row = ActionGroupRunResult(
                tenant_id=tenant_id,
                group_run_id=run.id,
                action_id=item.action_id,
            )
            db.add(result_row)

        result_row.execution_status = exec_status
        result_row.execution_error_code = item.execution_error_code
        result_row.execution_error_message = item.execution_error_message
        result_row.execution_started_at = _parse_iso_utc(item.execution_started_at) or run.started_at
        result_row.execution_finished_at = _parse_iso_utc(item.execution_finished_at) or finished_at
        result_row.raw_result = item.raw_result

        await record_execution_result_async(
            db,
            action_id=item.action_id,
            latest_run_id=run.id,
            execution_status=exec_status,
            attempted_at=result_row.execution_started_at or run.started_at,
            finished_at=result_row.execution_finished_at or finished_at,
        )
        await evaluate_confirmation_for_action_async(
            db,
            action_id=item.action_id,
            since_run_started=result_row.execution_started_at or run.started_at,
        )

    if has_failed:
        run.status = ActionGroupRunStatus.failed
    elif has_cancelled:
        run.status = ActionGroupRunStatus.cancelled
    else:
        run.status = ActionGroupRunStatus.finished

    await db.commit()
    return {"status": "accepted", "event": "finished", "group_run_id": str(run.id)}


@router.post(
    "/reconcile-inventory-global",
    status_code=status.HTTP_200_OK,
    summary="Enqueue global inventory reconciliation sweeps",
    description="Builds and enqueues (account, region, service) global reconciliation shards for a tenant.",
)
async def enqueue_global_inventory_reconcile(
    body: ReconcileGlobalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_control_plane_secret: Annotated[str | None, Header(alias="X-Control-Plane-Secret")] = None,
) -> dict:
    _verify_control_plane_secret(x_control_plane_secret)
    queue_url = (settings.SQS_INVENTORY_RECONCILE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory reconcile queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
        )

    services = _normalized_services(body.services)
    now_iso = datetime.now(timezone.utc).isoformat()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    tenant_row = (
        await db.execute(select(Tenant).where(Tenant.id == body.tenant_id))
    ).scalar_one_or_none()
    if tenant_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    account_ids_filter = {aid.strip() for aid in (body.account_ids or []) if aid and aid.strip()}
    stmt = select(AwsAccount).where(AwsAccount.tenant_id == body.tenant_id)
    if account_ids_filter:
        stmt = stmt.where(AwsAccount.account_id.in_(sorted(account_ids_filter)))
    result = await db.execute(stmt)
    accounts = list(result.scalars().all())

    enqueued = 0
    accounts_considered = 0
    accounts_skipped_disabled = 0
    accounts_skipped_external_id_mismatch = 0
    accounts_skipped_assume_role = 0
    accounts_quarantined = 0
    authoritative_mode_blocked = 0
    assume_role_errors: list[str] = []
    skipped_prereq = 0
    prereq_reasons: list[str] = []
    prereq_failures: list[dict] = []
    queue_snapshot = collect_reconciliation_queue_snapshot()
    do_quarantine = bool(body.quarantine_on_assume_role_failure)
    for account in accounts:
        status_value = _status_value(account.status).lower()
        if status_value == "disabled":
            accounts_skipped_disabled += 1
            continue

        tenant_external_id = str(getattr(tenant_row, "external_id", "") or "").strip()
        account_external_id = str(getattr(account, "external_id", "") or "").strip()
        if tenant_external_id and account_external_id and tenant_external_id != account_external_id:
            accounts_skipped_external_id_mismatch += 1
            if do_quarantine:
                account.status = AwsAccountStatus.disabled
                accounts_quarantined += 1
            continue

        if body.precheck_assume_role:
            ok, reason = await _assume_role_precheck(account, tenant_external_id)
            if not ok:
                accounts_skipped_assume_role += 1
                if reason:
                    assume_role_errors.append(reason)
                if do_quarantine:
                    account.status = AwsAccountStatus.disabled
                    accounts_quarantined += 1
                continue

        account_regions = _normalized_regions(
            body.regions if body.regions is not None else account.regions,
            settings.AWS_REGION,
        )

        if not settings.CONTROL_PLANE_SHADOW_MODE and status_value != "validated":
            authoritative_mode_blocked += 1
            continue
        if not settings.CONTROL_PLANE_SHADOW_MODE:
            probe_region = account_regions[0]
            allowed, missing_permissions = await _authoritative_permissions_precheck(
                account,
                tenant_external_id,
                probe_region,
            )
            if not allowed:
                authoritative_mode_blocked += 1
                assume_role_errors.extend([f"missing_permission:{perm}" for perm in missing_permissions])
                continue

        accounts_considered += 1

        for region in account_regions:
            prereq_result = await evaluate_reconciliation_prereqs_async(
                db,
                tenant_id=body.tenant_id,
                account_id=account.account_id,
                region=region,
                queue_snapshot=queue_snapshot,
            )
            if not bool(prereq_result.get("ok")):
                skipped_prereq += 1
                reasons = [str(code) for code in (prereq_result.get("reasons") or [])]
                prereq_reasons.extend(reasons)
                prereq_failures.append(
                    {
                        "tenant_id": str(body.tenant_id),
                        "account_id": account.account_id,
                        "region": region,
                        "reasons": reasons,
                        "snapshot": prereq_result.get("snapshot") or {},
                    }
                )
                continue
            for service in services:
                payload = build_reconcile_inventory_shard_job_payload(
                    tenant_id=body.tenant_id,
                    account_id=account.account_id,
                    region=region,
                    service=service,
                    created_at=now_iso,
                    sweep_mode="global",
                    max_resources=body.max_resources,
                )
                sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
                enqueued += 1

    if accounts_quarantined:
        await db.commit()

    response = {
        "enqueued": enqueued,
        "accounts_considered": accounts_considered,
        "accounts_skipped_disabled": accounts_skipped_disabled,
        "accounts_skipped_external_id_mismatch": accounts_skipped_external_id_mismatch,
        "accounts_skipped_assume_role": accounts_skipped_assume_role,
        "accounts_quarantined": accounts_quarantined,
        "authoritative_mode_blocked": authoritative_mode_blocked,
        "assume_role_error_codes": _dedup(assume_role_errors),
        "skipped_prereq": skipped_prereq,
        "prereq_reasons": _dedup(prereq_reasons),
        "services": services,
    }
    if prereq_failures:
        response["prereq_failures"] = prereq_failures
    return response


@router.post(
    "/reconcile-inventory-global-all-tenants",
    status_code=status.HTTP_200_OK,
    summary="Enqueue global inventory reconciliation sweeps for all tenants",
    description=(
        "Builds and enqueues (tenant, account, region, service) global reconciliation shards "
        "for all active tenants. Designed for EventBridge/cron scheduling."
    ),
)
async def enqueue_global_inventory_reconcile_all_tenants(
    body: ReconcileGlobalAllTenantsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_control_plane_secret: Annotated[str | None, Header(alias="X-Control-Plane-Secret")] = None,
) -> dict:
    _verify_control_plane_secret(x_control_plane_secret)
    queue_url = (settings.SQS_INVENTORY_RECONCILE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory reconcile queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
        )

    services = _normalized_services(body.services)
    now = datetime.now(timezone.utc)
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    tenant_ids_filter = set(body.tenant_ids or [])
    tenant_stmt = select(Tenant)
    if tenant_ids_filter:
        tenant_stmt = tenant_stmt.where(Tenant.id.in_(sorted(tenant_ids_filter)))
    result = await db.execute(tenant_stmt)
    tenants = list(result.scalars().all())

    account_ids_filter = sorted(
        {aid.strip() for aid in (body.account_ids or []) if aid and aid.strip()}
    )

    enqueued = 0
    enqueue_failed = 0
    job_ids: list[str] = []
    failed_tenant_ids: list[str] = []
    for tenant in tenants:
        payload_summary: dict = {
            "account_ids_filter": account_ids_filter,
            "regions_filter": [str(region).strip() for region in (body.regions or []) if str(region).strip()],
            "services": services,
            "max_resources": body.max_resources,
            "precheck_assume_role": bool(body.precheck_assume_role),
            "quarantine_on_assume_role_failure": bool(body.quarantine_on_assume_role_failure),
            "checkpoint": {
                "account_index": 0,
                "region_index": 0,
                "service_index": 0,
            },
            "stats": {
                "enqueued": 0,
                "accounts_considered": 0,
                "accounts_skipped_disabled": 0,
                "accounts_skipped_external_id_mismatch": 0,
                "accounts_skipped_assume_role": 0,
                "accounts_quarantined": 0,
                "authoritative_mode_blocked": 0,
                "assume_role_error_codes": [],
                "skipped_prereq": 0,
                "prereq_reasons": [],
                "prereq_failures": [],
            },
        }
        orchestration_record = ControlPlaneReconcileJob(
            tenant_id=tenant.id,
            job_type=RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_JOB_TYPE,
            status="queued",
            payload_summary=payload_summary,
            submitted_at=now,
        )
        db.add(orchestration_record)
        await db.flush()

        payload = build_reconcile_inventory_global_orchestration_job_payload(
            tenant_id=tenant.id,
            orchestration_job_id=orchestration_record.id,
            created_at=now.isoformat(),
            account_ids=account_ids_filter or None,
            regions=body.regions,
            services=services,
            max_resources=body.max_resources,
            precheck_assume_role=bool(body.precheck_assume_role),
            quarantine_on_assume_role_failure=bool(body.quarantine_on_assume_role_failure),
        )
        try:
            sqs_response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            orchestration_record.queue_message_id = str(sqs_response.get("MessageId") or "")
            orchestration_record.status = "enqueued"
            job_ids.append(str(orchestration_record.id))
            enqueued += 1
        except Exception as exc:
            orchestration_record.status = "error"
            orchestration_record.error_message = str(exc)[:4000]
            enqueue_failed += 1
            failed_tenant_ids.append(str(tenant.id))

    await db.commit()

    response: dict[str, object] = {
        "enqueued": enqueued,
        "tenants_considered": len(tenants),
        "services": services,
        "orchestration_jobs_enqueued": enqueued,
        "orchestration_jobs_failed": enqueue_failed,
        "job_ids": job_ids,
        # Backward-compatible counters previously reported by synchronous fan-out path.
        "accounts_considered": 0,
        "accounts_skipped_disabled": 0,
        "accounts_skipped_external_id_mismatch": 0,
        "accounts_skipped_assume_role": 0,
        "accounts_quarantined": 0,
        "authoritative_mode_blocked": 0,
        "assume_role_error_codes": [],
        "skipped_prereq": 0,
        "prereq_reasons": [],
    }
    if failed_tenant_ids:
        response["failed_tenant_ids"] = failed_tenant_ids
    return response


@router.post(
    "/reconciliation/schedule-tick",
    status_code=status.HTTP_200_OK,
    summary="Enqueue due tenant reconciliation schedules",
    description=(
        "Evaluates enabled aws_account_reconcile_settings rows and enqueues due runs. "
        "Designed for EventBridge/cron invocation."
    ),
)
async def run_reconciliation_schedule_tick(
    body: ReconciliationScheduleTickRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_reconciliation_scheduler_secret: Annotated[str | None, Header(alias="X-Reconciliation-Scheduler-Secret")] = None,
) -> dict:
    _verify_reconciliation_scheduler_secret(x_reconciliation_scheduler_secret)

    query = (
        select(AwsAccountReconcileSettings, AwsAccount, Tenant)
        .join(
            AwsAccount,
            and_(
                AwsAccount.tenant_id == AwsAccountReconcileSettings.tenant_id,
                AwsAccount.account_id == AwsAccountReconcileSettings.account_id,
            ),
        )
        .join(Tenant, Tenant.id == AwsAccountReconcileSettings.tenant_id)
        .where(AwsAccountReconcileSettings.enabled.is_(True))
        .order_by(AwsAccountReconcileSettings.updated_at.asc())
        .limit(body.limit)
    )

    tenant_filter = set(body.tenant_ids or [])
    account_filter = {str(account_id).strip() for account_id in (body.account_ids or []) if str(account_id).strip()}
    if tenant_filter:
        query = query.where(AwsAccountReconcileSettings.tenant_id.in_(sorted(tenant_filter)))
    if account_filter:
        query = query.where(AwsAccountReconcileSettings.account_id.in_(sorted(account_filter)))

    rows = (await db.execute(query)).all()
    now = datetime.now(timezone.utc)

    evaluated = 0
    enqueued = 0
    would_enqueue = 0
    skipped_not_due = 0
    skipped_status = 0
    skipped_feature_disabled = 0
    skipped_cooldown = 0
    failed = 0
    failures: list[str] = []

    for settings_row, account, tenant in rows:
        evaluated += 1
        try:
            ensure_tenant_reconciliation_enabled(tenant.id)
        except HTTPException:
            skipped_feature_disabled += 1
            continue

        account_status = _status_value(account.status).lower()
        if account_status != "validated":
            skipped_status += 1
            continue

        minimum_interval = max(1, int(settings.TENANT_RECONCILIATION_SCHEDULE_MIN_INTERVAL_MINUTES or 60))
        interval_minutes = max(minimum_interval, int(settings_row.interval_minutes or minimum_interval))
        due_at = (
            (settings_row.last_enqueued_at + timedelta(minutes=interval_minutes))
            if settings_row.last_enqueued_at is not None
            else None
        )
        if due_at is not None and due_at > now:
            skipped_not_due += 1
            continue

        try:
            services = normalize_services([str(value) for value in (settings_row.services or [])])
            regions = normalize_regions(
                [str(value) for value in (settings_row.regions or [])] if settings_row.regions else None,
                account.regions,
            )
            max_resources = normalize_max_resources(settings_row.max_resources)
            sweep_mode = normalize_sweep_mode(settings_row.sweep_mode)
        except HTTPException as exc:
            failed += 1
            failures.append(
                f"{tenant.id}:{account.account_id}:settings_invalid:{exc.detail}"
            )
            continue

        if body.dry_run:
            would_enqueue += 1
            continue

        cooldown_seconds = max(0, int(settings_row.cooldown_minutes or 0) * 60)
        try:
            run = await create_reconciliation_run(
                db=db,
                tenant=tenant,
                account=account,
                requested_by=None,
                trigger_type="scheduled",
                services=services,
                regions=regions,
                sweep_mode=sweep_mode,
                max_resources=max_resources,
                cooldown_seconds=cooldown_seconds,
            )
            settings_row.last_enqueued_at = now
            settings_row.last_run_id = run.id
            await db.commit()
            enqueued += 1
        except HTTPException as exc:
            await db.rollback()
            if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                skipped_cooldown += 1
                continue
            failed += 1
            failures.append(f"{tenant.id}:{account.account_id}:http_{exc.status_code}:{exc.detail}")
        except Exception as exc:  # pragma: no cover - defensive guard
            await db.rollback()
            failed += 1
            failures.append(f"{tenant.id}:{account.account_id}:{type(exc).__name__}")

    return {
        "evaluated": evaluated,
        "enqueued": enqueued,
        "would_enqueue": would_enqueue,
        "skipped_not_due": skipped_not_due,
        "skipped_status": skipped_status,
        "skipped_feature_disabled": skipped_feature_disabled,
        "skipped_cooldown": skipped_cooldown,
        "failed": failed,
        "dry_run": bool(body.dry_run),
        "failures": failures[:20],
    }


@router.post(
    "/backfill-finding-keys",
    status_code=status.HTTP_200_OK,
    summary="Enqueue canonical key backfill jobs for Security Hub findings",
    description=(
        "Queues chunked backfill_finding_keys jobs. Optional filters: tenant/account/region. "
        "Designed for daily or every-6h cron until missing key counts stabilize at zero."
    ),
)
async def enqueue_backfill_finding_keys(
    body: BackfillFindingKeysRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_control_plane_secret: Annotated[str | None, Header(alias="X-Control-Plane-Secret")] = None,
) -> dict:
    _verify_control_plane_secret(x_control_plane_secret)
    queue_url = (settings.SQS_INVENTORY_RECONCILE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory reconcile queue URL not configured. Set SQS_INVENTORY_RECONCILE_QUEUE_URL.",
        )
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now_iso = datetime.now(timezone.utc).isoformat()

    tenant_targets: list[uuid.UUID | None]
    if body.tenant_id is not None:
        tenant_targets = [body.tenant_id]
    elif body.enqueue_per_tenant:
        stmt = select(Finding.tenant_id).where(Finding.source == "security_hub")
        if body.account_id:
            stmt = stmt.where(Finding.account_id == body.account_id)
        if body.region:
            stmt = stmt.where(Finding.region == body.region)
        rows = (await db.execute(stmt.distinct())).all()
        tenant_targets = [row[0] for row in rows if row and row[0] is not None]
    else:
        tenant_targets = [None]

    if not tenant_targets:
        return {
            "enqueued": 0,
            "tenant_jobs": 0,
            "chunk_size": body.chunk_size,
            "max_chunks": body.max_chunks,
            "include_stale": body.include_stale,
            "auto_continue": body.auto_continue,
        }

    enqueued = 0
    for tenant_id in tenant_targets:
        payload = build_backfill_finding_keys_job_payload(
            created_at=now_iso,
            tenant_id=tenant_id,
            account_id=body.account_id,
            region=body.region,
            chunk_size=body.chunk_size,
            max_chunks=body.max_chunks,
            include_stale=body.include_stale,
            auto_continue=body.auto_continue,
        )
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        enqueued += 1

    return {
        "enqueued": enqueued,
        "tenant_jobs": len(tenant_targets),
        "chunk_size": body.chunk_size,
        "max_chunks": body.max_chunks,
        "include_stale": body.include_stale,
        "auto_continue": body.auto_continue,
    }


@router.post(
    "/backfill-action-groups",
    status_code=status.HTTP_200_OK,
    summary="Enqueue immutable action-group backfill jobs",
    description=(
        "Queues chunked backfill_action_groups jobs. Optional filters: tenant/account/region. "
        "Safe to rerun; membership assignment is append-only and idempotent."
    ),
)
async def enqueue_backfill_action_groups(
    body: BackfillActionGroupsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_control_plane_secret: Annotated[str | None, Header(alias="X-Control-Plane-Secret")] = None,
) -> dict:
    _verify_control_plane_secret(x_control_plane_secret)
    queue_url = (settings.SQS_INGEST_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL.",
        )
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    now_iso = datetime.now(timezone.utc).isoformat()

    tenant_targets: list[uuid.UUID | None]
    if body.tenant_id is not None:
        tenant_targets = [body.tenant_id]
    elif body.enqueue_per_tenant:
        stmt = select(Action.tenant_id)
        if body.account_id:
            stmt = stmt.where(Action.account_id == body.account_id)
        if body.region:
            stmt = stmt.where(Action.region == body.region)
        rows = (await db.execute(stmt.distinct())).all()
        tenant_targets = [row[0] for row in rows if row and row[0] is not None]
    else:
        tenant_targets = [None]

    if not tenant_targets:
        return {
            "enqueued": 0,
            "tenant_jobs": 0,
            "chunk_size": body.chunk_size,
            "max_chunks": body.max_chunks,
            "auto_continue": body.auto_continue,
        }

    enqueued = 0
    for tenant_id in tenant_targets:
        payload = build_backfill_action_groups_job_payload(
            created_at=now_iso,
            tenant_id=tenant_id,
            account_id=body.account_id,
            region=body.region,
            chunk_size=body.chunk_size,
            max_chunks=body.max_chunks,
            auto_continue=body.auto_continue,
        )
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        enqueued += 1

    return {
        "enqueued": enqueued,
        "tenant_jobs": len(tenant_targets),
        "chunk_size": body.chunk_size,
        "max_chunks": body.max_chunks,
        "auto_continue": body.auto_continue,
    }
