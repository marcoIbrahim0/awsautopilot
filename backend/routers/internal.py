"""
Internal API for cron/scheduled jobs (Step 11.1).

Endpoints are protected by shared secrets (e.g. DIGEST_CRON_SECRET).
Used by EventBridge or an external scheduler to trigger weekly digest per tenant.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

import boto3
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import AwsAccount
from backend.models.tenant import Tenant
from backend.services.control_plane_intake import is_supported_control_plane_event
from backend.utils.sqs import (
    build_ingest_control_plane_events_job_payload,
    build_reconcile_inventory_shard_job_payload,
    build_reconcile_recently_touched_resources_job_payload,
    build_weekly_digest_job_payload,
    parse_queue_region,
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

    account_ids_filter = {aid.strip() for aid in (body.account_ids or []) if aid and aid.strip()}
    stmt = select(AwsAccount).where(AwsAccount.tenant_id == body.tenant_id)
    if account_ids_filter:
        stmt = stmt.where(AwsAccount.account_id.in_(sorted(account_ids_filter)))
    result = await db.execute(stmt)
    accounts = list(result.scalars().all())

    enqueued = 0
    accounts_considered = 0
    accounts_skipped_disabled = 0
    for account in accounts:
        status_value = _status_value(account.status).lower()
        if status_value == "disabled":
            accounts_skipped_disabled += 1
            continue
        accounts_considered += 1

        account_regions = _normalized_regions(
            body.regions if body.regions is not None else account.regions,
            settings.AWS_REGION,
        )
        for region in account_regions:
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

    return {
        "enqueued": enqueued,
        "accounts_considered": accounts_considered,
        "accounts_skipped_disabled": accounts_skipped_disabled,
        "services": services,
    }
