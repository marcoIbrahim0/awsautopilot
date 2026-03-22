"""Worker job for reconciling drifted external remediation states."""
from __future__ import annotations

import logging
import uuid

from backend.services.attack_path_materialized import maybe_schedule_attack_path_refresh
from backend.services.action_remediation_sync import reconcile_drifted_sync_states
from backend.services.integration_sync import dispatch_sync_tasks
from backend.workers.database import session_scope

logger = logging.getLogger("worker.jobs.reconcile_action_remediation_sync")


def execute_reconcile_action_remediation_sync_job(job: dict) -> None:
    tenant_id = _parse_uuid(job.get("tenant_id"))
    action_ids = _parse_action_ids(job.get("action_ids"))
    provider = _string(job.get("provider"))
    limit = _int(job.get("limit"), default=100)
    with session_scope() as session:
        result = reconcile_drifted_sync_states(
            session,
            tenant_id=tenant_id,
            provider=provider,
            action_ids=action_ids,
            limit=limit,
        )
    dispatched = 0
    for dispatch_tenant_id, task_ids in result.task_ids_by_tenant.items():
        dispatched += int(dispatch_sync_tasks(task_ids, tenant_id=dispatch_tenant_id).get("enqueued") or 0)
    if tenant_id is not None:
        maybe_schedule_attack_path_refresh(tenant_id=tenant_id)
    logger.info(
        "reconcile_action_remediation_sync complete tenant_id=%s provider=%s scanned=%s planned=%s dispatched=%s skipped=%s",
        tenant_id,
        provider,
        result.scanned,
        result.planned_tasks,
        dispatched,
        result.skipped,
    )


def _parse_uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def _parse_action_ids(value: object) -> list[uuid.UUID]:
    if not isinstance(value, list):
        return []
    parsed: list[uuid.UUID] = []
    for raw in value:
        item = _parse_uuid(raw)
        if item is not None:
            parsed.append(item)
    return parsed


def _string(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int(value: object, *, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default
