"""
Compute actions job handler.
Runs the action engine for a tenant (optionally scoped to account/region).
"""
from __future__ import annotations

import logging
import uuid

from backend.services.action_engine import compute_actions_for_tenant
from backend.services.integration_sync import dispatch_sync_tasks, plan_action_sync_tasks
from backend.workers.database import session_scope

logger = logging.getLogger("worker.jobs.compute_actions")


def execute_compute_actions_job(job: dict) -> None:
    """
    Process a compute_actions job: run action engine for tenant (optional account/region scope).

    Args:
        job: Payload with tenant_id, job_type; optional account_id, region.
             Omit account_id/region for tenant-wide computation.
    """
    tenant_id_str = job.get("tenant_id")
    if not tenant_id_str:
        raise ValueError("job missing tenant_id")

    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except (TypeError, ValueError):
        raise ValueError(f"invalid tenant_id: {tenant_id_str}")

    account_id = job.get("account_id")
    region = job.get("region")
    sync_task_ids: list[uuid.UUID] = []

    with session_scope() as session:
        result = compute_actions_for_tenant(
            session,
            tenant_id,
            account_id=account_id,
            region=region,
        )
        sync_task_ids = plan_action_sync_tasks(
            session,
            tenant_id=tenant_id,
            action_ids=_task_action_ids(result),
            reopened_action_ids=_task_reopened_ids(result),
            trigger="worker.compute_actions",
        )

    dispatch_sync_tasks(sync_task_ids, tenant_id=tenant_id)

    logger.info(
        "compute_actions complete tenant_id=%s scope=(account=%s region=%s) created=%d updated=%d resolved=%d links=%d",
        tenant_id,
        account_id,
        region,
        result["actions_created"],
        result["actions_updated"],
        result["actions_resolved"],
        result["action_findings_linked"],
    )


def _task_action_ids(result: dict) -> list[uuid.UUID]:
    raw_items = (
        list(result.get("created_action_ids") or [])
        + list(result.get("updated_action_ids") or [])
        + list(result.get("resolved_action_ids") or [])
        + list(result.get("reopened_action_ids") or [])
    )
    seen: set[str] = set()
    ordered: list[uuid.UUID] = []
    for item in raw_items:
        value = str(item)
        if value in seen:
            continue
        seen.add(value)
        ordered.append(uuid.UUID(value))
    return ordered


def _task_reopened_ids(result: dict) -> set[uuid.UUID]:
    return {uuid.UUID(str(item)) for item in list(result.get("reopened_action_ids") or [])}
