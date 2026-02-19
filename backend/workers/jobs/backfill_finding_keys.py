"""
Backfill canonical control/resource keys for existing Security Hub findings.

The job is intentionally idempotent and chunked. It updates only rows that are
missing keys, or stale when include_stale=true.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import boto3
from sqlalchemy import func, or_
from sqlalchemy.orm import load_only

from backend.models.finding import Finding
from backend.services.canonicalization import build_resource_key, canonicalize_control_id
from backend.services.control_scope import ACTION_TYPE_DEFAULT, action_type_from_control
from backend.utils.sqs import build_backfill_finding_keys_job_payload, parse_queue_region
from backend.workers.config import settings
from backend.workers.database import session_scope

logger = logging.getLogger("worker.jobs.backfill_finding_keys")


def _normalize_chunk_size(value: object) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except Exception:
        parsed = 1000
    return max(50, min(parsed, 5000))


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


def _truncate(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    return value[:max_len] if len(value) > max_len else value


def _maybe_enqueue_continuation(
    *,
    tenant_id: uuid.UUID | None,
    account_id: str | None,
    region: str | None,
    chunk_size: int,
    max_chunks: int,
    include_stale: bool,
    start_after_id: uuid.UUID,
) -> None:
    queue_url = (settings.SQS_INVENTORY_RECONCILE_QUEUE_URL or "").strip()
    if not queue_url:
        logger.warning("backfill_finding_keys continuation skipped: SQS_INVENTORY_RECONCILE_QUEUE_URL is unset")
        return
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    payload = build_backfill_finding_keys_job_payload(
        created_at=datetime.now(timezone.utc).isoformat(),
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
        chunk_size=chunk_size,
        max_chunks=max_chunks,
        include_stale=include_stale,
        auto_continue=True,
        start_after_id=str(start_after_id),
    )
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))


def execute_backfill_finding_keys_job(job: dict) -> None:
    tenant_id = _normalize_uuid(job.get("tenant_id"), "tenant_id")
    account_id_raw = str(job.get("account_id") or "").strip()
    account_id = account_id_raw if account_id_raw else None
    region_raw = str(job.get("region") or "").strip()
    region = region_raw if region_raw else None
    chunk_size = _normalize_chunk_size(job.get("chunk_size"))
    max_chunks = _normalize_max_chunks(job.get("max_chunks"))
    include_stale = bool(job.get("include_stale", True))
    auto_continue = bool(job.get("auto_continue", True))
    start_after_id = _normalize_uuid(job.get("start_after_id"), "start_after_id")

    logger.info(
        "backfill_finding_keys start tenant_id=%s account_id=%s region=%s chunk_size=%s max_chunks=%s include_stale=%s start_after_id=%s",
        tenant_id,
        account_id,
        region,
        chunk_size,
        max_chunks,
        include_stale,
        start_after_id,
    )

    scanned = 0
    updated = 0
    chunks_processed = 0
    cursor = start_after_id
    has_more = False

    with session_scope() as session:
        base_filters = [Finding.source == "security_hub"]
        if tenant_id is not None:
            base_filters.append(Finding.tenant_id == tenant_id)
        if account_id is not None:
            base_filters.append(Finding.account_id == account_id)
        if region is not None:
            base_filters.append(Finding.region == region)
        if not include_stale:
            base_filters.append(
                or_(
                    Finding.canonical_control_id.is_(None),
                    Finding.resource_key.is_(None),
                )
            )

        while chunks_processed < max_chunks:
            filters = list(base_filters)
            if cursor is not None:
                filters.append(Finding.id > cursor)

            rows = (
                session.query(Finding)
                .options(
                    load_only(
                        Finding.id,
                        Finding.control_id,
                        Finding.canonical_control_id,
                        Finding.resource_id,
                        Finding.resource_type,
                        Finding.resource_key,
                        Finding.account_id,
                        Finding.region,
                        Finding.in_scope,
                    )
                )
                .filter(*filters)
                .order_by(Finding.id.asc())
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

            for finding in rows:
                expected_canonical = _truncate(
                    canonicalize_control_id(getattr(finding, "control_id", None)),
                    64,
                )
                expected_resource_key = _truncate(
                    build_resource_key(
                        account_id=str(getattr(finding, "account_id", "") or ""),
                        region=getattr(finding, "region", None),
                        resource_id=getattr(finding, "resource_id", None),
                        resource_type=getattr(finding, "resource_type", None),
                    ),
                    512,
                )
                expected_in_scope = (
                    action_type_from_control(getattr(finding, "control_id", None)) != ACTION_TYPE_DEFAULT
                )

                changed = False
                current_canonical = getattr(finding, "canonical_control_id", None)
                current_resource_key = getattr(finding, "resource_key", None)

                if current_canonical is None:
                    if expected_canonical is not None:
                        finding.canonical_control_id = expected_canonical
                        changed = True
                elif include_stale and current_canonical != expected_canonical:
                    finding.canonical_control_id = expected_canonical
                    changed = True

                if current_resource_key is None:
                    if expected_resource_key is not None:
                        finding.resource_key = expected_resource_key
                        changed = True
                elif include_stale and current_resource_key != expected_resource_key:
                    finding.resource_key = expected_resource_key
                    changed = True

                if bool(getattr(finding, "in_scope", False)) != bool(expected_in_scope):
                    finding.in_scope = bool(expected_in_scope)
                    changed = True

                if changed:
                    updated += 1

            session.flush()

        missing_count = int(
            (
                session.query(func.count(Finding.id))
                .filter(
                    *base_filters,
                    Finding.in_scope.is_(True),
                    or_(Finding.canonical_control_id.is_(None), Finding.resource_key.is_(None)),
                )
                .scalar()
            )
            or 0
        )

    if auto_continue and has_more and cursor is not None:
        _maybe_enqueue_continuation(
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            chunk_size=chunk_size,
            max_chunks=max_chunks,
            include_stale=include_stale,
            start_after_id=cursor,
        )
        continued = True
    else:
        continued = False

    logger.info(
        "backfill_finding_keys complete tenant_id=%s account_id=%s region=%s scanned=%d updated=%d chunks=%d continued=%s missing_in_scope=%d",
        tenant_id,
        account_id,
        region,
        scanned,
        updated,
        chunks_processed,
        continued,
        missing_count,
    )
