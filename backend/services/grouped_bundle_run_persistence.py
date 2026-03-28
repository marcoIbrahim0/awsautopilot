from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.action_group_run import ActionGroupRun
from backend.models.enums import ActionGroupRunStatus, RemediationRunMode, RemediationRunStatus
from backend.models.remediation_run import RemediationRun
from backend.utils.sqs import (
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
    build_remediation_run_job_payload,
    parse_queue_region,
)

logger = logging.getLogger(__name__)


async def persist_group_bundle_run(
    db: AsyncSession,
    *,
    group_run: ActionGroupRun,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    representative_action_id: str,
    artifacts: dict[str, Any],
) -> RemediationRun:
    remediation_run = RemediationRun(
        tenant_id=tenant_id,
        action_id=uuid.UUID(representative_action_id),
        mode=RemediationRunMode.pr_only,
        status=RemediationRunStatus.pending,
        approved_by_user_id=user_id,
        artifacts=artifacts,
    )
    db.add(group_run)
    db.add(remediation_run)
    await db.flush()
    group_run.remediation_run_id = remediation_run.id
    await db.commit()
    await db.refresh(group_run)
    await db.refresh(remediation_run)
    return remediation_run


async def mark_group_bundle_run_failed(
    db: AsyncSession,
    *,
    group_run: ActionGroupRun,
    remediation_run: RemediationRun,
) -> None:
    now = datetime.now(timezone.utc)
    group_run.status = ActionGroupRunStatus.failed
    group_run.finished_at = now
    remediation_run.status = RemediationRunStatus.failed
    remediation_run.outcome = "Queue enqueue failed for bundle generation."
    await db.commit()


async def enqueue_group_bundle_run_or_503(
    *,
    db: AsyncSession,
    plan: Any,
    group_run: ActionGroupRun,
    remediation_run: RemediationRun,
    tenant_id: uuid.UUID,
    representative_action_id: str | None = None,
    client_factory=boto3.client,
    error_detail: str = "Could not enqueue group bundle run job.",
) -> None:
    queue_fields = plan.queue_payload_fields_for_schema(REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2)
    payload = build_remediation_run_job_payload(
        run_id=remediation_run.id,
        tenant_id=tenant_id,
        action_id=uuid.UUID(representative_action_id or plan.representative_action_id),
        mode=remediation_run.mode.value,
        created_at=datetime.now(timezone.utc).isoformat(),
        pr_bundle_variant=queue_fields.get("pr_bundle_variant"),
        strategy_id=queue_fields.get("strategy_id"),
        strategy_inputs=queue_fields.get("strategy_inputs"),
        risk_acknowledged=bool(queue_fields.get("risk_acknowledged")),
        group_action_ids=queue_fields.get("group_action_ids"),
        repo_target=queue_fields.get("repo_target"),
        action_resolutions=queue_fields.get("action_resolutions"),
        schema_version=REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
    )
    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    sqs = client_factory("sqs", region_name=parse_queue_region(queue_url))
    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    except Exception as exc:
        logger.exception("SQS send_message failed for group bundle run enqueue: %s", exc)
        await mark_group_bundle_run_failed(
            db,
            group_run=group_run,
            remediation_run=remediation_run,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail,
        ) from exc
