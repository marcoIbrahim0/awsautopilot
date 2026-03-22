"""
Inventory reconciliation shard job.

Phase-2 semantics:
- cover controls that are not fully eventable
- reconcile missed/late/noisy events against current resource state
"""
from __future__ import annotations

import logging
import json
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from backend.models import AwsAccount
from backend.models.action_finding import ActionFinding
from backend.models.finding import Finding
from backend.services.action_run_confirmation import reevaluate_confirmation_for_actions
from backend.services.canonicalization import build_resource_key, canonicalize_control_id
from backend.services.tenant_reconciliation import (
    classify_reconcile_exception,
    mark_reconcile_shard_finished,
    mark_reconcile_shard_running,
)
from backend.utils.sqs import build_compute_actions_job_payload, parse_queue_region
from backend.workers.config import settings
from backend.workers.database import session_scope
from backend.workers.services.aws import (
    WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)
from backend.workers.services.inventory_assets import upsert_inventory_asset
from backend.workers.services.inventory_reconcile import (
    INVENTORY_SERVICES_DEFAULT,
    collect_inventory_snapshots,
)
from backend.workers.services.shadow_state import upsert_shadow_state

logger = logging.getLogger("worker.jobs.reconcile_inventory_shard")

RESOURCE_SCOPED_SERVICES = {"ec2", "s3", "rds", "eks"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_sweep_mode(value: str | None) -> str:
    mode = (value or "").strip().lower()
    return mode if mode in {"targeted", "global"} else "targeted"


def _normalize_max_resources(value: object) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except Exception:
        parsed = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)
    return parsed if parsed > 0 else int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)


def execute_reconcile_inventory_shard_job(job: dict) -> None:
    tenant_id_raw = job.get("tenant_id")
    account_id = job.get("account_id")
    region = job.get("region")
    service = str(job.get("service") or "").strip().lower()
    run_shard_id = job.get("run_shard_id")
    resource_ids_raw = job.get("resource_ids")
    resource_ids = resource_ids_raw if isinstance(resource_ids_raw, list) else None
    sweep_mode = _normalize_sweep_mode(str(job.get("sweep_mode") or ""))
    max_resources = _normalize_max_resources(job.get("max_resources"))

    if not tenant_id_raw or not account_id or not region or not service:
        raise ValueError("job missing tenant_id/account_id/region/service")

    try:
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except ValueError as exc:
        raise ValueError(f"invalid tenant_id: {tenant_id_raw}") from exc

    if run_shard_id:
        with session_scope() as tracking_session:
            mark_reconcile_shard_running(tracking_session, run_shard_id)

    if service not in INVENTORY_SERVICES_DEFAULT:
        logger.info(
            "Ignoring unsupported inventory service=%s tenant_id=%s account_id=%s region=%s",
            service,
            tenant_id,
            account_id,
            region,
        )
        if run_shard_id:
            with session_scope() as tracking_session:
                mark_reconcile_shard_finished(tracking_session, run_shard_id, status_value="succeeded")
        return

    if (
        sweep_mode == "targeted"
        and service in RESOURCE_SCOPED_SERVICES
        and not resource_ids
    ):
        logger.info(
            "Skipping targeted reconcile with empty resource_ids tenant_id=%s account_id=%s region=%s service=%s",
            tenant_id,
            account_id,
            region,
            service,
        )
        if run_shard_id:
            with session_scope() as tracking_session:
                mark_reconcile_shard_finished(tracking_session, run_shard_id, status_value="succeeded")
        return

    changed_status = 0
    impacted_action_ids: set[uuid.UUID] = set()
    try:
        source = (settings.CONTROL_PLANE_SOURCE or "").strip() or "event_monitor_shadow"
        reconcile_time = _utcnow()

        with session_scope() as session:
            account = (
                session.query(AwsAccount)
                .filter(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
                .first()
            )
            if account is None:
                raise ValueError(f"aws_account not found tenant_id={tenant_id} account_id={account_id}")

            assumed = assume_role(
                role_arn=account.role_read_arn,
                external_id=account.external_id,
                source_identity=WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
                tags=build_assume_role_tags(service_component="worker", tenant_id=tenant_id),
            )

            snapshots = collect_inventory_snapshots(
                session_boto=assumed,
                account_id=account_id,
                region=region,
                service=service,
                resource_ids=[str(v) for v in resource_ids] if resource_ids else None,
                max_resources=max_resources,
            )

            assets_created = 0
            assets_changed = 0
            evaluations_total = 0
            applied = 0
            for snapshot in snapshots:
                created, changed_hash = upsert_inventory_asset(
                    session=session,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    region=region,
                    sweep_mode=sweep_mode,
                    snapshot=snapshot,
                )
                if created:
                    assets_created += 1
                if changed_hash:
                    assets_changed += 1

                for evaluation in snapshot.evaluations:
                    evaluations_total += 1
                    did_apply, did_change = upsert_shadow_state(
                        session=session,
                        tenant_id=tenant_id,
                        account_id=account_id,
                        region=region,
                        event_time=reconcile_time,
                        source=source,
                        evaluation=evaluation,
                    )
                    if did_apply:
                        applied += 1
                    if did_change:
                        changed_status += 1
                    if did_apply:
                        canonical_control_id = canonicalize_control_id(getattr(evaluation, "control_id", None))
                        resource_key = build_resource_key(
                            account_id=account_id,
                            region=region,
                            resource_id=getattr(evaluation, "resource_id", None),
                            resource_type=getattr(evaluation, "resource_type", None),
                        )
                        if canonical_control_id and resource_key:
                            action_rows = (
                                session.query(ActionFinding.action_id)
                                .join(Finding, Finding.id == ActionFinding.finding_id)
                                .filter(
                                    Finding.tenant_id == tenant_id,
                                    Finding.account_id == account_id,
                                    Finding.region == region,
                                    Finding.canonical_control_id == canonical_control_id,
                                    Finding.resource_key == resource_key,
                                )
                                .all()
                            )
                            for row in action_rows:
                                if row and row[0] is not None:
                                    impacted_action_ids.add(row[0])

            if impacted_action_ids:
                reevaluate_confirmation_for_actions(session, action_ids=list(impacted_action_ids))
                logger.info(
                    "reconcile_inventory_shard confirmation re-evaluation tenant_id=%s account_id=%s region=%s impacted_actions=%d",
                    tenant_id,
                    account_id,
                    region,
                    len(impacted_action_ids),
                )

            logger.info(
                "reconcile_inventory_shard complete tenant_id=%s account_id=%s region=%s service=%s sweep_mode=%s "
                "snapshots=%d assets_created=%d assets_changed=%d evaluations=%d applied=%d changed_status=%d",
                tenant_id,
                account_id,
                region,
                service,
                sweep_mode,
                len(snapshots),
                assets_created,
                assets_changed,
                evaluations_total,
                applied,
                changed_status,
            )
        if run_shard_id:
            with session_scope() as tracking_session:
                mark_reconcile_shard_finished(tracking_session, run_shard_id, status_value="succeeded")
    except Exception as exc:
        if run_shard_id:
            error_code, error_message = classify_reconcile_exception(exc)
            with session_scope() as tracking_session:
                mark_reconcile_shard_finished(
                    tracking_session,
                    run_shard_id,
                    status_value="failed",
                    error_code=error_code,
                    error_message=error_message,
                )
        raise

    # When control-plane is authoritative, reconciliation can flip canonical finding.status.
    # Enqueue compute_actions so Actions reflect the latest finding state without manual recompute.
    if not settings.CONTROL_PLANE_SHADOW_MODE and changed_status and settings.has_ingest_queue:
        try:
            queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
            queue_region = parse_queue_region(queue_url)
            sqs = boto3.client("sqs", region_name=queue_region)
            payload = build_compute_actions_job_payload(
                tenant_id=tenant_id,
                created_at=_utcnow().isoformat(),
                account_id=account_id,
                region=region,
            )
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            logger.info(
                "Enqueued compute_actions after reconcile_inventory_shard tenant_id=%s account_id=%s region=%s changed_status=%d",
                tenant_id,
                account_id,
                region,
                changed_status,
            )
        except ClientError as exc:  # pragma: no cover - best effort
            logger.warning(
                "Failed to enqueue compute_actions after reconcile_inventory_shard tenant_id=%s account_id=%s region=%s: %s",
                tenant_id,
                account_id,
                region,
                exc,
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning(
                "Failed to enqueue compute_actions after reconcile_inventory_shard tenant_id=%s account_id=%s region=%s: %s",
                tenant_id,
                account_id,
                region,
                exc,
            )
