"""
Internal API for cron/scheduled jobs (Step 11.1).

Endpoints are protected by shared secrets (e.g. DIGEST_CRON_SECRET).
Used by EventBridge or an external scheduler to trigger weekly digest per tenant.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Annotated

import boto3
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.tenant import Tenant
from backend.utils.sqs import build_weekly_digest_job_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


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
