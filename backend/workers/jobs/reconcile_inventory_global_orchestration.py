"""
Worker orchestration job for global inventory reconciliation fan-out.

This moves account/region/service shard expansion out of the API request path.
Checkpoint state is persisted on the orchestration record so retries can resume.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.models.aws_account import AwsAccount
from backend.models.control_plane_reconcile_job import ControlPlaneReconcileJob
from backend.models.enums import AwsAccountStatus
from backend.models.tenant import Tenant
from backend.services.reconciliation_prereqs import (
    collect_reconciliation_queue_snapshot,
    evaluate_reconciliation_prereqs,
)
from backend.utils.sqs import build_reconcile_inventory_shard_job_payload, parse_queue_region
from backend.workers.config import settings
from backend.workers.database import session_scope
from backend.workers.services.aws import (
    WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)

logger = logging.getLogger("worker.jobs.reconcile_inventory_global_orchestration")

MAX_PREREQ_FAILURES_CAPTURE = 200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


def _is_access_denied_code(code: str) -> bool:
    return code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "UnauthorizedAccess"}


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


def _normalize_max_resources(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)
    if parsed <= 0:
        return int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)
    return parsed


def _default_checkpoint() -> dict[str, int]:
    return {
        "account_index": 0,
        "region_index": 0,
        "service_index": 0,
    }


def _default_stats() -> dict[str, Any]:
    return {
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
    }


def _normalize_checkpoint(checkpoint: Any) -> dict[str, int]:
    if not isinstance(checkpoint, dict):
        return _default_checkpoint()

    def _to_non_negative_int(raw: Any) -> int:
        try:
            value = int(raw)
        except Exception:
            return 0
        return value if value >= 0 else 0

    return {
        "account_index": _to_non_negative_int(checkpoint.get("account_index")),
        "region_index": _to_non_negative_int(checkpoint.get("region_index")),
        "service_index": _to_non_negative_int(checkpoint.get("service_index")),
    }


def _advance_to_next_account(checkpoint: dict[str, int]) -> None:
    checkpoint["account_index"] = int(checkpoint.get("account_index", 0)) + 1
    checkpoint["region_index"] = 0
    checkpoint["service_index"] = 0


def _advance_to_next_region(checkpoint: dict[str, int], *, total_regions: int) -> None:
    checkpoint["region_index"] = int(checkpoint.get("region_index", 0)) + 1
    checkpoint["service_index"] = 0
    if checkpoint["region_index"] >= max(0, total_regions):
        _advance_to_next_account(checkpoint)


def _advance_to_next_service(
    checkpoint: dict[str, int],
    *,
    total_regions: int,
    total_services: int,
) -> None:
    checkpoint["service_index"] = int(checkpoint.get("service_index", 0)) + 1
    if checkpoint["service_index"] >= max(1, total_services):
        _advance_to_next_region(checkpoint, total_regions=total_regions)


def _assume_role_precheck(account: AwsAccount, tenant_external_id: str) -> tuple[bool, str | None]:
    try:
        session = assume_role(
            role_arn=account.role_read_arn,
            external_id=tenant_external_id,
            source_identity=WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=build_assume_role_tags(service_component="worker", tenant_id=account.tenant_id),
        )
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        caller = str(identity.get("Account") or "")
        if caller and caller != str(account.account_id):
            return False, f"AccountMismatch:{caller}"
        return True, None
    except Exception as exc:
        return False, _extract_error_code(exc)


def _authoritative_permissions_precheck(
    account: AwsAccount,
    tenant_external_id: str,
    region: str,
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    try:
        session = assume_role(
            role_arn=account.role_read_arn,
            external_id=tenant_external_id,
            source_identity=WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=build_assume_role_tags(service_component="worker", tenant_id=account.tenant_id),
        )
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


def _load_orchestration_context(
    tenant_id: uuid.UUID,
    orchestration_job_id: uuid.UUID,
    job: dict,
) -> tuple[dict[str, Any], str, list[AwsAccount]]:
    with session_scope() as session:
        tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is None:
            raise ValueError(f"tenant not found: {tenant_id}")

        record = (
            session.query(ControlPlaneReconcileJob)
            .filter(
                ControlPlaneReconcileJob.id == orchestration_job_id,
                ControlPlaneReconcileJob.tenant_id == tenant_id,
            )
            .first()
        )
        if record is None:
            raise ValueError(
                f"control_plane_reconcile_job not found tenant_id={tenant_id} orchestration_job_id={orchestration_job_id}"
            )

        payload_summary = dict(record.payload_summary) if isinstance(record.payload_summary, dict) else {}
        payload_summary.setdefault("account_ids_filter", job.get("account_ids") or [])
        payload_summary.setdefault("regions_filter", job.get("regions") or [])
        payload_summary.setdefault("services", job.get("services") or settings.control_plane_inventory_services_list)
        payload_summary.setdefault("max_resources", job.get("max_resources"))
        payload_summary.setdefault("precheck_assume_role", bool(job.get("precheck_assume_role")))
        payload_summary.setdefault(
            "quarantine_on_assume_role_failure",
            bool(job.get("quarantine_on_assume_role_failure")),
        )
        payload_summary["checkpoint"] = _normalize_checkpoint(payload_summary.get("checkpoint"))
        stats = payload_summary.get("stats")
        payload_summary["stats"] = dict(stats) if isinstance(stats, dict) else _default_stats()

        record.status = "running"
        record.error_message = None
        record.payload_summary = payload_summary

        account_ids_filter = {
            str(v).strip()
            for v in (payload_summary.get("account_ids_filter") or [])
            if str(v).strip()
        }

        query = session.query(AwsAccount).filter(AwsAccount.tenant_id == tenant_id)
        if account_ids_filter:
            query = query.filter(AwsAccount.account_id.in_(sorted(account_ids_filter)))
        accounts = list(query.order_by(AwsAccount.account_id.asc()).all())

        return payload_summary, str(getattr(tenant, "external_id", "") or "").strip(), accounts


def _persist_orchestration_state(
    tenant_id: uuid.UUID,
    orchestration_job_id: uuid.UUID,
    payload_summary: dict[str, Any],
    *,
    status: str,
    error_message: str | None = None,
) -> None:
    with session_scope() as session:
        record = (
            session.query(ControlPlaneReconcileJob)
            .filter(
                ControlPlaneReconcileJob.id == orchestration_job_id,
                ControlPlaneReconcileJob.tenant_id == tenant_id,
            )
            .first()
        )
        if record is None:
            return

        record.status = status
        record.error_message = str(error_message or "").strip()[:4000] or None
        record.payload_summary = payload_summary


def _disable_account(tenant_id: uuid.UUID, account_id: str) -> None:
    with session_scope() as session:
        account = (
            session.query(AwsAccount)
            .filter(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
            .first()
        )
        if account is None:
            return
        status_value = _status_value(account.status).lower()
        if status_value == "disabled":
            return
        account.status = AwsAccountStatus.disabled


def _append_prereq_failure(stats: dict[str, Any], item: dict[str, Any]) -> None:
    failures = stats.get("prereq_failures")
    if not isinstance(failures, list):
        failures = []
        stats["prereq_failures"] = failures
    if len(failures) >= MAX_PREREQ_FAILURES_CAPTURE:
        return
    failures.append(item)


def execute_reconcile_inventory_global_orchestration_job(job: dict) -> None:
    tenant_id_raw = job.get("tenant_id")
    orchestration_job_id_raw = job.get("orchestration_job_id")
    if not tenant_id_raw or not orchestration_job_id_raw:
        raise ValueError("job missing tenant_id/orchestration_job_id")

    try:
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except ValueError as exc:
        raise ValueError(f"invalid tenant_id: {tenant_id_raw}") from exc

    try:
        orchestration_job_id = uuid.UUID(str(orchestration_job_id_raw))
    except ValueError as exc:
        raise ValueError(f"invalid orchestration_job_id: {orchestration_job_id_raw}") from exc

    queue_url = str(getattr(settings, "SQS_INVENTORY_RECONCILE_QUEUE_URL", "") or "").strip()
    if not queue_url:
        raise ValueError("SQS_INVENTORY_RECONCILE_QUEUE_URL is unset")

    payload_summary, tenant_external_id, accounts = _load_orchestration_context(
        tenant_id,
        orchestration_job_id,
        job,
    )

    checkpoint = _normalize_checkpoint(payload_summary.get("checkpoint"))
    payload_summary["checkpoint"] = checkpoint
    stats = payload_summary.get("stats")
    if not isinstance(stats, dict):
        stats = _default_stats()
        payload_summary["stats"] = stats

    services_raw = payload_summary.get("services")
    if isinstance(services_raw, list):
        services = [str(service).strip().lower() for service in services_raw if str(service).strip()]
    else:
        services = []
    services = services or list(settings.control_plane_inventory_services_list)
    payload_summary["services"] = services

    max_resources = _normalize_max_resources(payload_summary.get("max_resources"))
    payload_summary["max_resources"] = max_resources

    precheck_assume_role = bool(payload_summary.get("precheck_assume_role"))
    do_quarantine = bool(payload_summary.get("quarantine_on_assume_role_failure"))

    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    queue_snapshot = collect_reconciliation_queue_snapshot()

    if checkpoint["account_index"] >= len(accounts):
        payload_summary["completed_at"] = _utcnow().isoformat()
        _persist_orchestration_state(
            tenant_id,
            orchestration_job_id,
            payload_summary,
            status="succeeded",
        )
        return

    resume_account_index = checkpoint["account_index"]
    resume_region_index = checkpoint["region_index"]
    resume_service_index = checkpoint["service_index"]

    try:
        for account_idx in range(resume_account_index, len(accounts)):
            account = accounts[account_idx]
            status_value = _status_value(getattr(account, "status", None)).lower()

            checkpoint["account_index"] = account_idx
            if account_idx != resume_account_index:
                checkpoint["region_index"] = 0
                checkpoint["service_index"] = 0

            if status_value == "disabled":
                stats["accounts_skipped_disabled"] = int(stats.get("accounts_skipped_disabled") or 0) + 1
                _advance_to_next_account(checkpoint)
                _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                continue

            account_external_id = str(getattr(account, "external_id", "") or "").strip()
            if tenant_external_id and account_external_id and tenant_external_id != account_external_id:
                stats["accounts_skipped_external_id_mismatch"] = int(stats.get("accounts_skipped_external_id_mismatch") or 0) + 1
                if do_quarantine:
                    _disable_account(tenant_id, account.account_id)
                    stats["accounts_quarantined"] = int(stats.get("accounts_quarantined") or 0) + 1
                _advance_to_next_account(checkpoint)
                _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                continue

            if precheck_assume_role:
                ok, reason = _assume_role_precheck(account, tenant_external_id)
                if not ok:
                    stats["accounts_skipped_assume_role"] = int(stats.get("accounts_skipped_assume_role") or 0) + 1
                    if reason:
                        reasons = list(stats.get("assume_role_error_codes") or [])
                        reasons.append(reason)
                        stats["assume_role_error_codes"] = _dedup(reasons)
                    if do_quarantine:
                        _disable_account(tenant_id, account.account_id)
                        stats["accounts_quarantined"] = int(stats.get("accounts_quarantined") or 0) + 1
                    _advance_to_next_account(checkpoint)
                    _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                    continue

            regions_filter = payload_summary.get("regions_filter")
            account_regions = _normalized_regions(
                regions_filter if isinstance(regions_filter, list) and regions_filter else account.regions,
                settings.AWS_REGION,
            )

            if not settings.CONTROL_PLANE_SHADOW_MODE and status_value != "validated":
                stats["authoritative_mode_blocked"] = int(stats.get("authoritative_mode_blocked") or 0) + 1
                _advance_to_next_account(checkpoint)
                _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                continue

            if not settings.CONTROL_PLANE_SHADOW_MODE:
                allowed, missing_permissions = _authoritative_permissions_precheck(
                    account,
                    tenant_external_id,
                    account_regions[0],
                )
                if not allowed:
                    stats["authoritative_mode_blocked"] = int(stats.get("authoritative_mode_blocked") or 0) + 1
                    reasons = list(stats.get("assume_role_error_codes") or [])
                    reasons.extend([f"missing_permission:{perm}" for perm in missing_permissions])
                    stats["assume_role_error_codes"] = _dedup(reasons)
                    _advance_to_next_account(checkpoint)
                    _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                    continue

            stats["accounts_considered"] = int(stats.get("accounts_considered") or 0) + 1

            region_start = resume_region_index if account_idx == resume_account_index else 0
            if region_start >= len(account_regions):
                _advance_to_next_account(checkpoint)
                _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                continue

            for region_idx in range(region_start, len(account_regions)):
                region = account_regions[region_idx]
                checkpoint["region_index"] = region_idx
                service_start = (
                    resume_service_index
                    if (account_idx == resume_account_index and region_idx == resume_region_index)
                    else 0
                )
                checkpoint["service_index"] = service_start
                if service_start >= len(services):
                    _advance_to_next_region(checkpoint, total_regions=len(account_regions))
                    _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                    continue

                with session_scope() as session:
                    prereq_result = evaluate_reconciliation_prereqs(
                        session,
                        tenant_id=tenant_id,
                        account_id=account.account_id,
                        region=region,
                        queue_snapshot=queue_snapshot,
                    )

                if not bool(prereq_result.get("ok")):
                    stats["skipped_prereq"] = int(stats.get("skipped_prereq") or 0) + 1
                    reason_codes = [str(code) for code in (prereq_result.get("reasons") or [])]
                    prior_reasons = list(stats.get("prereq_reasons") or [])
                    prior_reasons.extend(reason_codes)
                    stats["prereq_reasons"] = _dedup(prior_reasons)
                    _append_prereq_failure(
                        stats,
                        {
                            "tenant_id": str(tenant_id),
                            "account_id": account.account_id,
                            "region": region,
                            "reasons": reason_codes,
                            "snapshot": prereq_result.get("snapshot") or {},
                        },
                    )
                    _advance_to_next_region(checkpoint, total_regions=len(account_regions))
                    _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")
                    continue

                for service_idx in range(service_start, len(services)):
                    service = services[service_idx]
                    checkpoint["service_index"] = service_idx
                    payload = build_reconcile_inventory_shard_job_payload(
                        tenant_id=tenant_id,
                        account_id=account.account_id,
                        region=region,
                        service=service,
                        created_at=_utcnow().isoformat(),
                        sweep_mode="global",
                        max_resources=max_resources,
                    )
                    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
                    stats["enqueued"] = int(stats.get("enqueued") or 0) + 1

                    _advance_to_next_service(
                        checkpoint,
                        total_regions=len(account_regions),
                        total_services=len(services),
                    )
                    _persist_orchestration_state(tenant_id, orchestration_job_id, payload_summary, status="running")

        checkpoint["account_index"] = len(accounts)
        checkpoint["region_index"] = 0
        checkpoint["service_index"] = 0
        payload_summary["completed_at"] = _utcnow().isoformat()
        _persist_orchestration_state(
            tenant_id,
            orchestration_job_id,
            payload_summary,
            status="succeeded",
        )
    except Exception as exc:
        payload_summary["last_error_code"] = _extract_error_code(exc)
        payload_summary["last_error_at"] = _utcnow().isoformat()
        _persist_orchestration_state(
            tenant_id,
            orchestration_job_id,
            payload_summary,
            status="error",
            error_message=str(exc),
        )
        raise

    logger.info(
        "reconcile_inventory_global_orchestration complete tenant_id=%s orchestration_job_id=%s enqueued=%s accounts_considered=%s",
        tenant_id,
        orchestration_job_id,
        int(stats.get("enqueued") or 0),
        int(stats.get("accounts_considered") or 0),
    )
