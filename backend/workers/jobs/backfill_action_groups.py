"""
Backfill immutable action group memberships and legacy group-run records.

This job is idempotent and chunked. It can be safely retried/replayed.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import boto3
from sqlalchemy import and_
from sqlalchemy.orm import load_only

from backend.models.action import Action
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.action_group_run_result import ActionGroupRunResult
from backend.models.enums import (
    ActionGroupExecutionStatus,
    ActionGroupRunStatus,
    RemediationRunMode,
    RemediationRunStatus,
)
from backend.models.remediation_run import RemediationRun
from backend.services.action_groups import ensure_membership_for_actions
from backend.services.action_run_confirmation import evaluate_confirmation_for_action, record_execution_result
from backend.utils.sqs import build_backfill_action_groups_job_payload, parse_queue_region
from backend.workers.config import settings
from backend.workers.database import session_scope

logger = logging.getLogger("worker.jobs.backfill_action_groups")


def _normalize_chunk_size(value: object) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except Exception:
        parsed = 500
    return max(50, min(parsed, 2000))


def _normalize_max_chunks(value: object) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except Exception:
        parsed = 10
    return max(1, min(parsed, 200))


def _normalize_uuid(value: object, field_name: str) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:  # pragma: no cover - defensive parsing
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _parse_group_action_ids(artifacts: dict | None) -> list[uuid.UUID]:
    if not isinstance(artifacts, dict):
        return []
    group_bundle = artifacts.get("group_bundle")
    if not isinstance(group_bundle, dict):
        return []
    raw_ids = group_bundle.get("action_ids")
    if not isinstance(raw_ids, list):
        return []
    parsed: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for raw in raw_ids:
        if not isinstance(raw, str):
            continue
        try:
            action_id = uuid.UUID(raw.strip())
        except ValueError:
            continue
        if action_id in seen:
            continue
        seen.add(action_id)
        parsed.append(action_id)
    return parsed


def _map_legacy_run_status(status_value: RemediationRunStatus | str) -> ActionGroupRunStatus:
    status_str = status_value.value if hasattr(status_value, "value") else str(status_value)
    if status_str == RemediationRunStatus.pending.value:
        return ActionGroupRunStatus.queued
    if status_str in {RemediationRunStatus.running.value, RemediationRunStatus.awaiting_approval.value}:
        return ActionGroupRunStatus.started
    if status_str == RemediationRunStatus.success.value:
        return ActionGroupRunStatus.finished
    if status_str == RemediationRunStatus.cancelled.value:
        return ActionGroupRunStatus.cancelled
    return ActionGroupRunStatus.failed


def _ensure_legacy_group_run_backfill(
    *,
    tenant_id: uuid.UUID | None,
    account_id: str | None,
    region: str | None,
) -> tuple[int, int]:
    created_runs = 0
    created_results = 0

    with session_scope() as session:
        query = (
            session.query(RemediationRun)
            .join(
                Action,
                and_(
                    Action.id == RemediationRun.action_id,
                    Action.tenant_id == RemediationRun.tenant_id,
                ),
            )
            .filter(RemediationRun.mode == RemediationRunMode.pr_only)
            .order_by(RemediationRun.created_at.asc())
            .limit(500)
        )
        if tenant_id is not None:
            query = query.filter(RemediationRun.tenant_id == tenant_id)
        if account_id is not None:
            query = query.filter(Action.account_id == account_id)
        if region is not None:
            query = query.filter(Action.region == region)

        legacy_runs = query.all()
        for legacy in legacy_runs:
            existing = (
                session.query(ActionGroupRun)
                .filter(
                    ActionGroupRun.tenant_id == legacy.tenant_id,
                    ActionGroupRun.remediation_run_id == legacy.id,
                )
                .one_or_none()
            )
            if existing is not None:
                continue

            action_ids = _parse_group_action_ids(legacy.artifacts if isinstance(legacy.artifacts, dict) else None)
            if not action_ids:
                continue

            memberships = (
                session.query(ActionGroupMembership)
                .filter(
                    ActionGroupMembership.tenant_id == legacy.tenant_id,
                    ActionGroupMembership.action_id.in_(action_ids),
                )
                .all()
            )
            if not memberships:
                continue

            group_ids = {membership.group_id for membership in memberships}
            if len(group_ids) != 1:
                # Ambiguous legacy mapping: preserve history without guessing one group.
                logger.info(
                    "legacy group run mapping ambiguous run_id=%s tenant_id=%s groups=%d",
                    legacy.id,
                    legacy.tenant_id,
                    len(group_ids),
                )
                continue

            group_id = next(iter(group_ids))
            group_run = ActionGroupRun(
                tenant_id=legacy.tenant_id,
                group_id=group_id,
                remediation_run_id=legacy.id,
                initiated_by_user_id=legacy.approved_by_user_id,
                mode="download_bundle",
                status=_map_legacy_run_status(legacy.status),
                started_at=legacy.started_at,
                finished_at=legacy.completed_at,
                reporting_source="system",
            )
            session.add(group_run)
            session.flush()
            created_runs += 1

            member_action_ids = [membership.action_id for membership in memberships]
            for action_id in member_action_ids:
                existing_result = (
                    session.query(ActionGroupRunResult)
                    .filter(
                        ActionGroupRunResult.group_run_id == group_run.id,
                        ActionGroupRunResult.action_id == action_id,
                    )
                    .one_or_none()
                )
                if existing_result is not None:
                    continue

                session.add(
                    ActionGroupRunResult(
                        tenant_id=legacy.tenant_id,
                        group_run_id=group_run.id,
                        action_id=action_id,
                        execution_status=ActionGroupExecutionStatus.unknown,
                        raw_result={"source": "legacy_backfill", "legacy_run_id": str(legacy.id)},
                        execution_started_at=legacy.started_at,
                        execution_finished_at=legacy.completed_at,
                    )
                )
                created_results += 1
                record_execution_result(
                    session,
                    action_id=action_id,
                    latest_run_id=group_run.id,
                    execution_status=ActionGroupExecutionStatus.unknown,
                    attempted_at=legacy.started_at or legacy.created_at,
                    finished_at=legacy.completed_at,
                )
                evaluate_confirmation_for_action(
                    session,
                    action_id=action_id,
                    since_run_started=legacy.started_at or legacy.created_at,
                )

    return created_runs, created_results


def _maybe_enqueue_continuation(
    *,
    tenant_id: uuid.UUID | None,
    account_id: str | None,
    region: str | None,
    chunk_size: int,
    max_chunks: int,
    start_after_action_id: uuid.UUID,
) -> None:
    queue_url = (settings.SQS_INGEST_QUEUE_URL or "").strip()
    if not queue_url:
        logger.warning("backfill_action_groups continuation skipped: SQS_INGEST_QUEUE_URL unset")
        return

    payload = build_backfill_action_groups_job_payload(
        created_at=datetime.now(timezone.utc).isoformat(),
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
        chunk_size=chunk_size,
        max_chunks=max_chunks,
        auto_continue=True,
        start_after_action_id=str(start_after_action_id),
    )
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))


def execute_backfill_action_groups_job(job: dict) -> None:
    tenant_id = _normalize_uuid(job.get("tenant_id"), "tenant_id")
    account_id_raw = str(job.get("account_id") or "").strip()
    account_id = account_id_raw if account_id_raw else None
    region_raw = str(job.get("region") or "").strip()
    region = region_raw if region_raw else None
    chunk_size = _normalize_chunk_size(job.get("chunk_size"))
    max_chunks = _normalize_max_chunks(job.get("max_chunks"))
    auto_continue = bool(job.get("auto_continue", True))
    start_after_action_id = _normalize_uuid(job.get("start_after_action_id"), "start_after_action_id")

    logger.info(
        "backfill_action_groups start tenant_id=%s account_id=%s region=%s chunk_size=%s max_chunks=%s start_after_action_id=%s",
        tenant_id,
        account_id,
        region,
        chunk_size,
        max_chunks,
        start_after_action_id,
    )

    scanned = 0
    assigned = 0
    chunks_processed = 0
    cursor = start_after_action_id
    has_more = False

    with session_scope() as session:
        filters = []
        if tenant_id is not None:
            filters.append(Action.tenant_id == tenant_id)
        if account_id is not None:
            filters.append(Action.account_id == account_id)
        if region is not None:
            filters.append(Action.region == region)

        while chunks_processed < max_chunks:
            query_filters = list(filters)
            if cursor is not None:
                query_filters.append(Action.id > cursor)

            rows = (
                session.query(Action)
                .options(
                    load_only(
                        Action.id,
                        Action.tenant_id,
                        Action.action_type,
                        Action.account_id,
                        Action.region,
                    )
                )
                .filter(*query_filters)
                .order_by(Action.id.asc())
                .limit(chunk_size)
                .all()
            )
            if not rows:
                has_more = False
                break

            has_more = len(rows) == chunk_size
            chunks_processed += 1
            scanned += len(rows)
            cursor = rows[-1].id

            before_count = (
                session.query(ActionGroupMembership.action_id)
                .filter(ActionGroupMembership.action_id.in_([row.id for row in rows]))
                .count()
            )
            ensure_membership_for_actions(session, rows, source="backfill")
            session.flush()
            after_count = (
                session.query(ActionGroupMembership.action_id)
                .filter(ActionGroupMembership.action_id.in_([row.id for row in rows]))
                .count()
            )
            assigned += max(0, after_count - before_count)

    created_runs, created_results = _ensure_legacy_group_run_backfill(
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
    )

    continued = False
    if auto_continue and has_more and cursor is not None:
        _maybe_enqueue_continuation(
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            chunk_size=chunk_size,
            max_chunks=max_chunks,
            start_after_action_id=cursor,
        )
        continued = True

    logger.info(
        "backfill_action_groups complete tenant_id=%s account_id=%s region=%s scanned=%d assigned=%d chunks=%d continued=%s legacy_runs=%d legacy_results=%d",
        tenant_id,
        account_id,
        region,
        scanned,
        assigned,
        chunks_processed,
        continued,
        created_runs,
        created_results,
    )
