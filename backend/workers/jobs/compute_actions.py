"""
Compute actions job handler.
Runs the action engine for a tenant (optionally scoped to account/region).
"""
from __future__ import annotations

import logging
import uuid

from backend.services.action_engine import compute_actions_for_tenant
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

    with session_scope() as session:
        result = compute_actions_for_tenant(
            session,
            tenant_id,
            account_id=account_id,
            region=region,
        )

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
