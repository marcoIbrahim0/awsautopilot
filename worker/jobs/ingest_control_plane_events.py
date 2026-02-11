"""
Control-plane event ingestion job (phase 1).

Pipeline:
1) validate + de-duplicate event
2) synchronous enrichment reads
3) deterministic shadow finding-state upsert
4) telemetry capture for freshness SLOs
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import boto3
from backend.models import AwsAccount
from backend.models.action_finding import ActionFinding
from backend.models.control_plane_event import ControlPlaneEvent
from backend.models.finding import Finding
from backend.services.action_run_confirmation import reevaluate_confirmation_for_actions
from backend.services.canonicalization import build_resource_key, canonicalize_control_id
from backend.utils.sqs import build_compute_actions_job_payload, parse_queue_region
from worker.config import settings
from worker.database import session_scope
from worker.services.aws import assume_role
from worker.services.control_plane_events import (
    SHADOW_STATUS_RESOLVED,
    derive_control_evaluations,
    is_supported_management_event,
    parse_iso_datetime,
)
from worker.services.shadow_state import upsert_shadow_state

logger = logging.getLogger("worker.jobs.ingest_control_plane_events")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ms(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds() * 1000
    return int(delta if delta > 0 else 0)


def _maybe_enqueue_compute_actions(
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
) -> None:
    if settings.CONTROL_PLANE_SHADOW_MODE:
        return
    if not settings.has_ingest_queue:
        return
    try:
        queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
        queue_region = parse_queue_region(queue_url)
        sqs = boto3.client("sqs", region_name=queue_region)
        now = _utcnow().isoformat()
        payload = build_compute_actions_job_payload(
            tenant_id=tenant_id,
            created_at=now,
            account_id=account_id,
            region=region,
        )
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning(
            "Failed to enqueue compute_actions after control-plane event tenant_id=%s account_id=%s region=%s: %s",
            tenant_id,
            account_id,
            region,
            exc,
        )


def execute_ingest_control_plane_events_job(job: dict) -> None:
    tenant_id_raw = job.get("tenant_id")
    account_id = job.get("account_id")
    region = job.get("region")
    event = job.get("event")
    event_id = str(job.get("event_id") or "").strip()
    event_time = parse_iso_datetime(str(job.get("event_time") or ""))
    intake_time = parse_iso_datetime(str(job.get("intake_time") or ""))
    enqueued_at = parse_iso_datetime(str(job.get("created_at") or ""))
    handler_started_at = _utcnow()

    if not tenant_id_raw or not account_id or not region or not isinstance(event, dict):
        raise ValueError("job missing tenant_id/account_id/region/event")
    if not event_id:
        raise ValueError("job missing event_id")
    if event_time is None:
        raise ValueError("job missing or invalid event_time")

    try:
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except ValueError as exc:
        raise ValueError(f"invalid tenant_id: {tenant_id_raw}") from exc

    source = (settings.CONTROL_PLANE_SOURCE or "").strip() or "event_monitor_shadow"

    with session_scope() as session:
        existing = (
            session.query(ControlPlaneEvent)
            .filter(
                ControlPlaneEvent.tenant_id == tenant_id,
                ControlPlaneEvent.event_id == event_id,
                ControlPlaneEvent.account_id == account_id,
                ControlPlaneEvent.region == region,
            )
            .first()
        )
        if existing:
            existing.duplicate_count = int(existing.duplicate_count or 0) + 1
            logger.info(
                "Skipping duplicate control-plane event tenant_id=%s account_id=%s region=%s event_id=%s duplicates=%s",
                tenant_id,
                account_id,
                region,
                event_id,
                existing.duplicate_count,
            )
            return

        detail = event.get("detail") or {}
        control_plane_event = ControlPlaneEvent(
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            event_id=event_id,
            source=str(event.get("source") or "unknown"),
            detail_type=str(event.get("detail-type") or ""),
            event_name=str(detail.get("eventName") or "") or None,
            event_category=str(detail.get("eventCategory") or "") or None,
            processing_status="processing",
            duplicate_count=0,
            event_time=event_time,
            intake_time=intake_time,
            queue_enqueued_at=enqueued_at,
            handler_started_at=handler_started_at,
            raw_event=event,
        )
        session.add(control_plane_event)

        supported, drop_reason = is_supported_management_event(event)
        if not supported:
            completed = _utcnow()
            control_plane_event.processing_status = "dropped"
            control_plane_event.drop_reason = drop_reason
            control_plane_event.upsert_completed_at = completed
            control_plane_event.api_visible_at = completed
            control_plane_event.cloudtrail_delivery_lag_ms = _ms(event_time, intake_time)
            control_plane_event.queue_lag_ms = _ms(enqueued_at, handler_started_at)
            control_plane_event.handler_latency_ms = _ms(handler_started_at, completed)
            control_plane_event.end_to_end_lag_ms = _ms(event_time, completed)
            logger.info(
                "Dropped unsupported control-plane event tenant_id=%s account_id=%s region=%s event_id=%s reason=%s",
                tenant_id,
                account_id,
                region,
                event_id,
                drop_reason,
            )
            return

        account = (
            session.query(AwsAccount)
            .filter(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
            .first()
        )
        if account is None:
            raise ValueError(f"aws_account not found tenant_id={tenant_id} account_id={account_id}")

        assumed = assume_role(role_arn=account.role_read_arn, external_id=account.external_id)
        evaluations = derive_control_evaluations(
            session_boto=assumed,
            account_id=account_id,
            region=region,
            event=event,
        )

        if not evaluations:
            completed = _utcnow()
            control_plane_event.processing_status = "dropped"
            control_plane_event.drop_reason = "no_supported_targets_after_enrichment"
            control_plane_event.upsert_completed_at = completed
            control_plane_event.api_visible_at = completed
            control_plane_event.cloudtrail_delivery_lag_ms = _ms(event_time, intake_time)
            control_plane_event.queue_lag_ms = _ms(enqueued_at, handler_started_at)
            control_plane_event.handler_latency_ms = _ms(handler_started_at, completed)
            control_plane_event.end_to_end_lag_ms = _ms(event_time, completed)
            logger.info(
                "Dropped control-plane event with no targets tenant_id=%s account_id=%s region=%s event_id=%s",
                tenant_id,
                account_id,
                region,
                event_id,
            )
            return

        applied_any = False
        resolved_any = False
        impacted_action_ids: set[uuid.UUID] = set()
        for evaluation in evaluations:
            applied, changed = upsert_shadow_state(
                session=session,
                tenant_id=tenant_id,
                account_id=account_id,
                region=region,
                event_time=event_time,
                source=source,
                evaluation=evaluation,
            )
            applied_any = applied_any or applied
            if applied and changed and evaluation.status == SHADOW_STATUS_RESOLVED:
                resolved_any = True
            if not applied:
                continue
            canonical_control_id = canonicalize_control_id(getattr(evaluation, "control_id", None))
            resource_key = build_resource_key(
                account_id=account_id,
                region=region,
                resource_id=getattr(evaluation, "resource_id", None),
                resource_type=getattr(evaluation, "resource_type", None),
            )
            if not canonical_control_id or not resource_key:
                continue
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
                "control-plane confirmation re-evaluation tenant_id=%s account_id=%s region=%s impacted_actions=%d",
                tenant_id,
                account_id,
                region,
                len(impacted_action_ids),
            )

        completed = _utcnow()
        control_plane_event.processing_status = "success" if applied_any else "dropped"
        if not applied_any:
            control_plane_event.drop_reason = "out_of_order_or_no_state_change"
        control_plane_event.upsert_completed_at = completed
        control_plane_event.api_visible_at = completed
        control_plane_event.cloudtrail_delivery_lag_ms = _ms(event_time, intake_time)
        control_plane_event.queue_lag_ms = _ms(enqueued_at, handler_started_at)
        control_plane_event.handler_latency_ms = _ms(handler_started_at, completed)
        control_plane_event.end_to_end_lag_ms = _ms(event_time, completed)
        if resolved_any:
            control_plane_event.resolution_freshness_ms = _ms(event_time, completed)

        logger.info(
            "control-plane event processed tenant_id=%s account_id=%s region=%s event_id=%s status=%s evaluations=%d",
            tenant_id,
            account_id,
            region,
            event_id,
            control_plane_event.processing_status,
            len(evaluations),
        )

    _maybe_enqueue_compute_actions(tenant_id=tenant_id, account_id=account_id, region=region)
