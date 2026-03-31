"""
Public control-plane intake endpoints.

These endpoints are designed to be called by AWS EventBridge API Destinations
deployed in customer accounts (per account/region).

Authentication: per-tenant API key header (X-Control-Plane-Token),
validated against stored token hashes.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Annotated, Any

import boto3
import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import hash_control_plane_token
from backend.config import settings
from backend.database import get_db
from backend.models.aws_account import AwsAccount
from backend.models.control_plane_event_ingest_status import ControlPlaneEventIngestStatus
from backend.models.tenant import Tenant
from backend.services.control_plane_intake import is_supported_control_plane_event
from backend.utils.sqs import build_ingest_control_plane_events_job_payload, parse_queue_region

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/control-plane", tags=["control-plane"])

_ACCOUNT_ID_RE = re.compile(r"^\d{12}$")


class ControlPlaneIntakeResponse(BaseModel):
    enqueued: int = Field(..., description="Number of events enqueued to events-fast-lane queue")
    dropped: int = Field(..., description="Number of events dropped before enqueue")
    drop_reasons: dict[str, int] = Field(default_factory=dict, description="Drop reason counters")


def _parse_event_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _extract_event_fields(event: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    event_id = str(event.get("id") or "").strip() or str((event.get("detail") or {}).get("eventID") or "").strip()
    event_time = str(event.get("time") or "").strip() or str((event.get("detail") or {}).get("eventTime") or "").strip()
    account_id = str(event.get("account") or "").strip() or str(
        ((event.get("detail") or {}).get("userIdentity") or {}).get("accountId") or ""
    ).strip()
    region = str(event.get("region") or "").strip() or str((event.get("detail") or {}).get("awsRegion") or "").strip()
    return event_id or None, event_time or None, account_id or None, region or None


async def _get_tenant_for_token(db: AsyncSession, token: str) -> Tenant | None:
    token_hash = hash_control_plane_token(token)
    now = datetime.now(timezone.utc)
    stmt = select(Tenant).where(
        Tenant.control_plane_token_revoked_at.is_(None),
        sa.or_(
            Tenant.control_plane_token == token_hash,
            sa.and_(
                Tenant.control_plane_previous_token == token_hash,
                Tenant.control_plane_previous_token_expires_at.is_not(None),
                Tenant.control_plane_previous_token_expires_at > now,
            ),
        ),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@router.post(
    "/events",
    response_model=ControlPlaneIntakeResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a single control-plane event",
)
async def ingest_control_plane_event(
    body: Annotated[dict[str, Any], Body(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_control_plane_token: Annotated[str | None, Header(alias="X-Control-Plane-Token")] = None,
) -> ControlPlaneIntakeResponse:
    """
    Accept a single EventBridge event payload and enqueue it for fast-lane processing.

    Expected caller: EventBridge API Destination (per tenant/account/region).
    """
    token = (x_control_plane_token or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing X-Control-Plane-Token.")

    tenant = await _get_tenant_for_token(db, token)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid control-plane token.")

    queue_url = (settings.SQS_EVENTS_FAST_LANE_QUEUE_URL or "").strip()
    if not queue_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Events fast-lane queue URL not configured. Set SQS_EVENTS_FAST_LANE_QUEUE_URL.",
        )

    # Allow both {"event": {...}} and raw event bodies.
    event: dict[str, Any]
    if isinstance(body.get("event"), dict):
        event = body["event"]
    else:
        event = body

    supported, reason = is_supported_control_plane_event(event)
    if not supported:
        return ControlPlaneIntakeResponse(enqueued=0, dropped=1, drop_reasons={reason or "unsupported": 1})

    event_id, event_time, account_id, region = _extract_event_fields(event)
    if not event_id or not event_time or not account_id or not region:
        return ControlPlaneIntakeResponse(enqueued=0, dropped=1, drop_reasons={"missing_required_fields": 1})
    if not _ACCOUNT_ID_RE.match(account_id):
        return ControlPlaneIntakeResponse(enqueued=0, dropped=1, drop_reasons={"invalid_account_id": 1})

    # Ensure the account is registered for this tenant (avoid token abuse across tenants).
    stmt = select(AwsAccount).where(AwsAccount.tenant_id == tenant.id, AwsAccount.account_id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        return ControlPlaneIntakeResponse(enqueued=0, dropped=1, drop_reasons={"unknown_account": 1})

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Enqueue the fast-lane job.
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    payload = build_ingest_control_plane_events_job_payload(
        tenant_id=tenant.id,
        account_id=account_id,
        region=region,
        event=event,
        event_id=event_id,
        event_time=event_time,
        intake_time=now_iso,
        created_at=now_iso,
    )
    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except Exception as exc:
        logger.exception("Failed to enqueue control-plane event job: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to enqueue control-plane event job.",
        ) from exc

    # Update ingest status for tenant-facing validation.
    last_event_dt = _parse_event_datetime(event_time)
    upsert = (
        insert(ControlPlaneEventIngestStatus)
        .values(
            tenant_id=tenant.id,
            account_id=account_id,
            region=region,
            last_event_time=last_event_dt,
            last_intake_time=now,
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "account_id", "region"],
            set_={
                "last_event_time": last_event_dt,
                "last_intake_time": now,
                "updated_at": sa.func.now(),
            },
        )
    )
    await db.execute(upsert)
    await db.commit()

    return ControlPlaneIntakeResponse(enqueued=1, dropped=0, drop_reasons={})
