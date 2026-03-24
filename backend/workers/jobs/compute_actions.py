"""
Compute actions job handler.
Runs the action engine for a tenant (optionally scoped to account/region).
"""
from __future__ import annotations

import logging
import time
import uuid

from backend.services.attack_path_materialized import maybe_schedule_attack_path_refresh
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
    started = time.perf_counter()

    logger.info(
        "compute_actions start tenant_id=%s scope=(account=%s region=%s)",
        tenant_id,
        account_id,
        region,
    )
    with session_scope() as session:
        compute_started = time.perf_counter()
        result = compute_actions_for_tenant(
            session,
            tenant_id,
            account_id=account_id,
            region=region,
        )
        compute_elapsed_ms = int((time.perf_counter() - compute_started) * 1000)
        logger.info(
            "compute_actions phase=compute_core tenant_id=%s scope=(account=%s region=%s) elapsed_ms=%d",
            tenant_id,
            account_id,
            region,
            compute_elapsed_ms,
        )

        planning_started = time.perf_counter()
        sync_task_ids = plan_action_sync_tasks(
            session,
            tenant_id=tenant_id,
            action_ids=_task_action_ids(result),
            reopened_action_ids=_task_reopened_ids(result),
            trigger="worker.compute_actions",
        )
        logger.info(
            "compute_actions phase=plan_sync tenant_id=%s scope=(account=%s region=%s) tasks=%d elapsed_ms=%d",
            tenant_id,
            account_id,
            region,
            len(sync_task_ids),
            int((time.perf_counter() - planning_started) * 1000),
        )

    dispatch_started = time.perf_counter()
    logger.info(
        "compute_actions phase=dispatch_sync start tenant_id=%s scope=(account=%s region=%s) tasks=%d",
        tenant_id,
        account_id,
        region,
        len(sync_task_ids),
    )
    dispatch_result = dispatch_sync_tasks(sync_task_ids, tenant_id=tenant_id)
    logger.info(
        "compute_actions phase=dispatch_sync complete tenant_id=%s scope=(account=%s region=%s) enqueued=%d failed=%d elapsed_ms=%d",
        tenant_id,
        account_id,
        region,
        int(dispatch_result.get("enqueued") or 0),
        int(dispatch_result.get("failed") or 0),
        int((time.perf_counter() - dispatch_started) * 1000),
    )

    attack_path_started = time.perf_counter()
    logger.info(
        "compute_actions phase=attack_path_enqueue start tenant_id=%s scope=(account=%s region=%s)",
        tenant_id,
        account_id,
        region,
    )
    attack_path_scheduled = maybe_schedule_attack_path_refresh(
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
    )
    logger.info(
        "compute_actions phase=attack_path_enqueue complete tenant_id=%s scope=(account=%s region=%s) scheduled=%s elapsed_ms=%d",
        tenant_id,
        account_id,
        region,
        attack_path_scheduled,
        int((time.perf_counter() - attack_path_started) * 1000),
    )

    logger.info(
        "compute_actions complete tenant_id=%s scope=(account=%s region=%s) created=%d updated=%d resolved=%d links=%d elapsed_ms=%d",
        tenant_id,
        account_id,
        region,
        result["actions_created"],
        result["actions_updated"],
        result["actions_resolved"],
        result["action_findings_linked"],
        int((time.perf_counter() - started) * 1000),
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
