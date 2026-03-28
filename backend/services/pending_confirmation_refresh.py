from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.action import Action
from backend.models.action_group_action_state import ActionGroupActionState
from backend.models.enums import ActionGroupStatusBucket
from backend.services.action_run_confirmation import (
    clear_confirmation_refresh_schedule,
    mark_confirmation_refresh_enqueued,
)
from backend.utils.sqs import build_ingest_job_payload, parse_queue_region

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PendingConfirmationScope:
    tenant_id: uuid.UUID
    account_id: str
    region: str
    states: list[ActionGroupActionState]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_regions(regions: list[str] | None) -> set[str]:
    return {str(region).strip() for region in (regions or []) if str(region).strip()}


def _build_scope_map(
    rows: list[tuple[ActionGroupActionState, Action]],
) -> tuple[dict[tuple[uuid.UUID, str, str], PendingConfirmationScope], int]:
    scope_map: dict[tuple[uuid.UUID, str, str], PendingConfirmationScope] = {}
    invalid_scope_states = 0
    for state, action in rows:
        account_id = str(getattr(action, "account_id", "") or "").strip()
        region = str(getattr(action, "region", "") or "").strip()
        if not account_id or not region:
            state.confirmation_refresh_next_due_at = None
            invalid_scope_states += 1
            continue
        scope_key = (state.tenant_id, account_id, region)
        scope = scope_map.get(scope_key)
        if scope is None:
            scope = PendingConfirmationScope(
                tenant_id=state.tenant_id,
                account_id=account_id,
                region=region,
                states=[],
            )
            scope_map[scope_key] = scope
        scope.states.append(state)
    return scope_map, invalid_scope_states


async def enqueue_due_pending_confirmation_refreshes(
    db: AsyncSession,
    *,
    tenant_ids: list[uuid.UUID] | None = None,
    account_ids: list[str] | None = None,
    regions: list[str] | None = None,
    limit: int = 200,
    now: datetime | None = None,
) -> dict[str, object]:
    if not settings.has_ingest_queue:
        raise RuntimeError("Ingest queue URL not configured. Set SQS_INGEST_QUEUE_URL.")

    current_time = now or _utcnow()
    account_filter = {str(account_id).strip() for account_id in (account_ids or []) if str(account_id).strip()}
    region_filter = _coerce_regions(regions)

    stmt = (
        select(ActionGroupActionState, Action)
        .join(Action, Action.id == ActionGroupActionState.action_id)
        .where(
            ActionGroupActionState.latest_run_status_bucket
            == ActionGroupStatusBucket.run_successful_pending_confirmation,
            ActionGroupActionState.last_confirmed_at.is_(None),
            ActionGroupActionState.confirmation_refresh_next_due_at.is_not(None),
            ActionGroupActionState.confirmation_refresh_next_due_at <= current_time,
        )
        .order_by(ActionGroupActionState.confirmation_refresh_next_due_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    if tenant_ids:
        stmt = stmt.where(ActionGroupActionState.tenant_id.in_(list(tenant_ids)))
    if account_filter:
        stmt = stmt.where(Action.account_id.in_(sorted(account_filter)))
    if region_filter:
        stmt = stmt.where(Action.region.in_(sorted(region_filter)))

    rows = list((await db.execute(stmt)).all())
    due_states = len(rows)
    scope_map, invalid_scope_states = _build_scope_map(rows)

    queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    created_at = current_time.isoformat()

    message_ids: list[str] = []
    scopes_payload: list[dict[str, object]] = []
    for scope in scope_map.values():
        payload = build_ingest_job_payload(
            scope.tenant_id,
            scope.account_id,
            scope.region,
            created_at,
        )
        response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
        message_ids.append(str(response.get("MessageId") or ""))
        scopes_payload.append(
            {
                "tenant_id": str(scope.tenant_id),
                "account_id": scope.account_id,
                "region": scope.region,
                "state_count": len(scope.states),
            }
        )
        for state in scope.states:
            mark_confirmation_refresh_enqueued(state, enqueued_at=current_time)

    for state, _ in rows:
        if state.latest_run_status_bucket != ActionGroupStatusBucket.run_successful_pending_confirmation:
            clear_confirmation_refresh_schedule(state)

    logger.info(
        "pending_confirmation_refresh enqueue complete due_states=%s enqueued_scopes=%s invalid_scope_states=%s",
        due_states,
        len(scope_map),
        invalid_scope_states,
    )
    return {
        "evaluated_states": due_states,
        "due_states": due_states,
        "enqueued_scopes": len(scope_map),
        "invalid_scope_states": invalid_scope_states,
        "message_ids": message_ids,
        "scopes": scopes_payload,
    }
