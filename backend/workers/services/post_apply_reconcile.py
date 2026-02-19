"""Post-apply reconciliation enqueue helper for successful PR bundle applies."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.action import Action
from backend.models.remediation_run import RemediationRun
from backend.services.reconciliation_prereqs import (
    collect_reconciliation_queue_snapshot,
    evaluate_reconciliation_prereqs,
)
from backend.utils.sqs import build_reconcile_inventory_shard_job_payload, parse_queue_region

logger = logging.getLogger("worker.services.post_apply_reconcile")

_SERVICE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("s3_", "s3"),
    ("ec2_", "ec2"),
    ("iam_", "iam"),
    ("rds_", "rds"),
    ("ebs_", "ebs"),
    ("eks_", "eks"),
    ("ssm_", "ssm"),
    ("guardduty_", "guardduty"),
    ("cloudtrail_", "cloudtrail"),
    ("config_", "config"),
)


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _normalize_mode() -> str:
    direct = getattr(settings, "control_plane_post_apply_reconcile_mode", None)
    if isinstance(direct, str) and direct in {"targeted_then_global", "global_only"}:
        return direct
    raw = str(getattr(settings, "CONTROL_PLANE_POST_APPLY_RECONCILE_MODE", "") or "").strip().lower()
    if raw in {"targeted_then_global", "global_only"}:
        return raw
    return "targeted_then_global"


def _parse_group_action_ids(run: RemediationRun) -> list[uuid.UUID]:
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    group_bundle = artifacts.get("group_bundle")
    if not isinstance(group_bundle, dict):
        return []
    raw_ids = group_bundle.get("action_ids")
    if not isinstance(raw_ids, list):
        return []
    out: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            continue
        try:
            parsed = uuid.UUID(raw_id.strip())
        except ValueError:
            continue
        if parsed in seen:
            continue
        seen.add(parsed)
        out.append(parsed)
    return out


def _resolve_affected_actions(session: Session, run: RemediationRun) -> list[Action]:
    action_ids = _parse_group_action_ids(run)
    if action_ids:
        rows = session.execute(
            select(Action).where(
                Action.tenant_id == run.tenant_id,
                Action.id.in_(action_ids),
            )
        ).scalars().all()
        actions = list(rows)
        if actions:
            return actions
    if run.action is not None:
        return [run.action]
    action = session.execute(
        select(Action).where(Action.tenant_id == run.tenant_id, Action.id == run.action_id)
    ).scalar_one_or_none()
    return [action] if action is not None else []


def _service_for_action(action_type: object) -> str | None:
    token = str(action_type or "").strip().lower()
    if not token:
        return None
    for prefix, service in _SERVICE_PREFIXES:
        if token.startswith(prefix):
            return service
    return None


def _resource_id_for_action(action: Action) -> str | None:
    resource_id = str(getattr(action, "resource_id", "") or "").strip()
    if resource_id:
        return resource_id
    target_id = str(getattr(action, "target_id", "") or "").strip()
    return target_id or None


def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "control_plane_age_minutes",
        "control_plane_max_staleness_minutes",
        "missing_canonical_keys",
        "missing_resource_keys",
        "inventory_queue_depth",
        "inventory_queue_depth_threshold",
        "inventory_dlq_depth",
        "inventory_dlq_depth_threshold",
        "queue_check_error",
    )
    return {k: snapshot.get(k) for k in keys if k in snapshot}


def enqueue_post_apply_reconcile(
    session: Session,
    run: RemediationRun,
) -> dict[str, Any]:
    if not bool(getattr(settings, "CONTROL_PLANE_POST_APPLY_RECONCILE_ENABLED", True)):
        return {"status": "disabled", "enqueued": 0}

    queue_url = str(getattr(settings, "SQS_INVENTORY_RECONCILE_QUEUE_URL", "") or "").strip()
    if not queue_url:
        logger.info(
            "post_apply_reconcile_skip tenant_id=%s run_id=%s reason=inventory_queue_url_unset",
            run.tenant_id,
            run.id,
        )
        return {"status": "queue_unset", "enqueued": 0}

    actions = _resolve_affected_actions(session, run)
    if not actions:
        logger.info(
            "post_apply_reconcile_skip tenant_id=%s run_id=%s reason=no_affected_actions",
            run.tenant_id,
            run.id,
        )
        return {"status": "no_actions", "enqueued": 0}

    account_id = str(getattr(actions[0], "account_id", "") or "").strip()
    region = str(getattr(actions[0], "region", "") or "").strip() or str(getattr(settings, "AWS_REGION", "us-east-1"))
    if not account_id:
        logger.info(
            "post_apply_reconcile_skip tenant_id=%s run_id=%s reason=missing_account_scope",
            run.tenant_id,
            run.id,
        )
        return {"status": "missing_scope", "enqueued": 0}

    queue_snapshot = collect_reconciliation_queue_snapshot()
    prereq = evaluate_reconciliation_prereqs(
        session,
        tenant_id=run.tenant_id,
        account_id=account_id,
        region=region,
        queue_snapshot=queue_snapshot,
    )
    if not bool(prereq.get("ok")):
        reasons = [str(code) for code in (prereq.get("reasons") or [])]
        snapshot = prereq.get("snapshot") if isinstance(prereq.get("snapshot"), dict) else {}
        logger.info(
            "post_apply_reconcile_prereq_skip tenant_id=%s account_id=%s region=%s reason_codes=%s snapshot=%s",
            run.tenant_id,
            account_id,
            region,
            reasons,
            json.dumps(_snapshot_summary(snapshot), sort_keys=True, default=str),
        )
        return {
            "status": "prereq_skip",
            "enqueued": 0,
            "reasons": reasons,
            "snapshot": snapshot,
        }

    affected_services: set[str] = set()
    targeted_resources: dict[str, set[str]] = defaultdict(set)
    unresolved_services = 0
    missing_resource_ids = 0

    for action in actions:
        service = _service_for_action(getattr(action, "action_type", None))
        if not service:
            unresolved_services += 1
            continue
        affected_services.add(service)
        resource_id = _resource_id_for_action(action)
        if resource_id:
            targeted_resources[service].add(resource_id)
        else:
            missing_resource_ids += 1

    mode = _normalize_mode()
    default_services = list(getattr(settings, "control_plane_inventory_services_list", []) or [])
    global_services: list[str] = []
    targeted_pairs: list[tuple[str, list[str]]] = []

    if mode != "global_only":
        for service in sorted(targeted_resources):
            resource_ids = sorted(targeted_resources[service])
            if resource_ids:
                targeted_pairs.append((service, resource_ids))

    targeted_complete = (
        bool(affected_services)
        and unresolved_services == 0
        and missing_resource_ids == 0
        and affected_services == {service for service, _ in targeted_pairs}
    )

    if mode == "global_only":
        global_services = sorted(affected_services) if affected_services else sorted(default_services)
    elif not targeted_complete:
        if affected_services:
            global_services = sorted(affected_services)
        else:
            global_services = sorted(default_services)

    max_resources = _coerce_int(getattr(settings, "CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD", 500), 500)
    now_iso = datetime.now(timezone.utc).isoformat()
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)

    enqueued = 0
    enqueue_errors: list[str] = []

    for service, resource_ids in targeted_pairs:
        payload = build_reconcile_inventory_shard_job_payload(
            tenant_id=run.tenant_id,
            account_id=account_id,
            region=region,
            service=service,
            resource_ids=resource_ids,
            sweep_mode="targeted",
            max_resources=max_resources,
            created_at=now_iso,
        )
        try:
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            enqueued += 1
            logger.info(
                "post_apply_reconcile_enqueue_success tenant_id=%s account_id=%s region=%s service=%s sweep_mode=%s count=%d",
                run.tenant_id,
                account_id,
                region,
                service,
                "targeted",
                len(resource_ids),
            )
        except Exception as exc:
            enqueue_errors.append(type(exc).__name__)
            logger.exception(
                "post_apply_reconcile_enqueue_error tenant_id=%s account_id=%s region=%s service=%s sweep_mode=targeted: %s",
                run.tenant_id,
                account_id,
                region,
                service,
                exc,
            )

    for service in global_services:
        payload = build_reconcile_inventory_shard_job_payload(
            tenant_id=run.tenant_id,
            account_id=account_id,
            region=region,
            service=service,
            sweep_mode="global",
            max_resources=max_resources,
            created_at=now_iso,
        )
        try:
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            enqueued += 1
            logger.info(
                "post_apply_reconcile_enqueue_success tenant_id=%s account_id=%s region=%s service=%s sweep_mode=%s count=%d",
                run.tenant_id,
                account_id,
                region,
                service,
                "global",
                1,
            )
        except Exception as exc:
            enqueue_errors.append(type(exc).__name__)
            logger.exception(
                "post_apply_reconcile_enqueue_error tenant_id=%s account_id=%s region=%s service=%s sweep_mode=global: %s",
                run.tenant_id,
                account_id,
                region,
                service,
                exc,
            )

    return {
        "status": "enqueued" if not enqueue_errors else "enqueue_error",
        "enqueued": enqueued,
        "targeted_enqueued": len(targeted_pairs),
        "global_enqueued": len(global_services),
        "enqueue_error_codes": sorted(set(enqueue_errors)),
        "mode": mode,
    }


__all__ = ["enqueue_post_apply_reconcile"]
