"""
Reconcile resources touched by recent control-plane events.

This job narrows reconciliation scope to resources with recent changes so
state correctness improves quickly without full-account scans.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_

from backend.utils.sqs import RECONCILE_INVENTORY_SHARD_JOB_TYPE
from backend.models.control_plane_event import ControlPlaneEvent
from worker.config import settings
from worker.database import session_scope
from worker.jobs.reconcile_inventory_shard import execute_reconcile_inventory_shard_job
from worker.services.control_plane_events import (
    S3_EVENT_NAMES,
    SG_EVENT_NAMES,
    extract_s3_bucket_names,
    extract_security_group_ids,
)

logger = logging.getLogger("worker.jobs.reconcile_recently_touched_resources")

MAX_RESOURCES_PER_KEY = 500


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def execute_reconcile_recently_touched_resources_job(job: dict) -> None:
    tenant_id_raw = job.get("tenant_id")
    lookback_raw = job.get("lookback_minutes")
    if not tenant_id_raw:
        raise ValueError("job missing tenant_id")

    try:
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except ValueError as exc:
        raise ValueError(f"invalid tenant_id: {tenant_id_raw}") from exc

    lookback_minutes = (
        int(lookback_raw)
        if lookback_raw is not None
        else int(settings.CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES or 60)
    )
    if lookback_minutes <= 0:
        lookback_minutes = 60

    since = _utcnow() - timedelta(minutes=lookback_minutes)

    # Key: (account_id, region, service) -> set(resource_ids)
    targets: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    with session_scope() as session:
        rows = (
            session.query(ControlPlaneEvent)
            .filter(
                and_(
                    ControlPlaneEvent.tenant_id == tenant_id,
                    ControlPlaneEvent.event_time >= since,
                )
            )
            .all()
        )

        for row in rows:
            event_name = str(row.event_name or "").strip()
            raw_event = row.raw_event if isinstance(row.raw_event, dict) else {}
            if event_name in SG_EVENT_NAMES:
                key = (row.account_id, row.region, "ec2")
                for sg_id in extract_security_group_ids(raw_event):
                    targets[key].add(sg_id)
            elif event_name in S3_EVENT_NAMES:
                key = (row.account_id, row.region, "s3")
                for bucket in extract_s3_bucket_names(raw_event):
                    targets[key].add(bucket)

    jobs_dispatched = 0
    for (account_id, region, service), resource_set in targets.items():
        if not resource_set:
            continue
        resource_ids = sorted(resource_set)[:MAX_RESOURCES_PER_KEY]
        execute_reconcile_inventory_shard_job(
            {
                "tenant_id": str(tenant_id),
                "account_id": account_id,
                "region": region,
                "service": service,
                "resource_ids": resource_ids,
                "job_type": RECONCILE_INVENTORY_SHARD_JOB_TYPE,
                "created_at": _utcnow().isoformat(),
            }
        )
        jobs_dispatched += 1

    logger.info(
        "reconcile_recently_touched_resources complete tenant_id=%s lookback_minutes=%s target_groups=%d",
        tenant_id,
        lookback_minutes,
        jobs_dispatched,
    )
