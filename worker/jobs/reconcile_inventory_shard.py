"""
Inventory reconciliation shard job.

Phase-2 semantics:
- cover controls that are not fully eventable
- reconcile missed/late/noisy events against current resource state
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.models import AwsAccount
from worker.config import settings
from worker.database import session_scope
from worker.services.aws import assume_role
from worker.services.control_plane_events import evaluate_s3_control, evaluate_security_group_control
from worker.services.shadow_state import upsert_shadow_state

logger = logging.getLogger("worker.jobs.reconcile_inventory_shard")

MAX_SECURITY_GROUPS_PER_JOB = 500


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _extract_bucket_name(value: str) -> str:
    if value.startswith("arn:aws:s3:::"):
        return value.replace("arn:aws:s3:::", "", 1)
    return value


def _list_security_group_ids(session_boto: Any, region: str, limit: int) -> list[str]:
    ec2 = session_boto.client("ec2", region_name=region)
    paginator = ec2.get_paginator("describe_security_groups")
    out: list[str] = []
    for page in paginator.paginate(PaginationConfig={"PageSize": 200}):
        groups = page.get("SecurityGroups") or []
        for g in groups:
            gid = str(g.get("GroupId") or "")
            if not gid.startswith("sg-"):
                continue
            out.append(gid)
            if len(out) >= limit:
                return out
    return out


def execute_reconcile_inventory_shard_job(job: dict) -> None:
    tenant_id_raw = job.get("tenant_id")
    account_id = job.get("account_id")
    region = job.get("region")
    service = str(job.get("service") or "").strip().lower()
    resource_ids_raw = job.get("resource_ids")
    resource_ids = resource_ids_raw if isinstance(resource_ids_raw, list) else None

    if not tenant_id_raw or not account_id or not region or not service:
        raise ValueError("job missing tenant_id/account_id/region/service")

    try:
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except ValueError as exc:
        raise ValueError(f"invalid tenant_id: {tenant_id_raw}") from exc

    source = (settings.CONTROL_PLANE_SOURCE or "").strip() or "event_monitor_shadow"
    reconcile_time = _utcnow()

    with session_scope() as session:
        account = (
            session.query(AwsAccount)
            .filter(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
            .first()
        )
        if account is None:
            raise ValueError(f"aws_account not found tenant_id={tenant_id} account_id={account_id}")

        assumed = assume_role(role_arn=account.role_read_arn, external_id=account.external_id)
        evaluations = []

        if service == "ec2":
            sg_ids = [str(v) for v in (resource_ids or []) if str(v).startswith("sg-")]
            if not sg_ids:
                sg_ids = _list_security_group_ids(assumed, region, MAX_SECURITY_GROUPS_PER_JOB)
            for sg_id in sg_ids:
                evaluations.append(evaluate_security_group_control(assumed, region, sg_id, "InventoryReconcile"))
        elif service == "s3":
            bucket_names = [_extract_bucket_name(str(v)) for v in (resource_ids or []) if str(v).strip()]
            if not bucket_names:
                logger.info(
                    "Skipping broad S3 shard reconcile without explicit resource_ids tenant_id=%s account_id=%s region=%s",
                    tenant_id,
                    account_id,
                    region,
                )
            for bucket_name in bucket_names:
                evaluations.append(evaluate_s3_control(assumed, region, bucket_name, "InventoryReconcile"))
        else:
            logger.info(
                "Ignoring unsupported inventory service=%s tenant_id=%s account_id=%s region=%s",
                service,
                tenant_id,
                account_id,
                region,
            )
            return

        applied = 0
        for evaluation in evaluations:
            did_apply, _changed = upsert_shadow_state(
                session=session,
                tenant_id=tenant_id,
                account_id=account_id,
                region=region,
                event_time=reconcile_time,
                source=source,
                evaluation=evaluation,
            )
            if did_apply:
                applied += 1

        logger.info(
            "reconcile_inventory_shard complete tenant_id=%s account_id=%s region=%s service=%s evaluated=%d applied=%d",
            tenant_id,
            account_id,
            region,
            service,
            len(evaluations),
            applied,
        )
