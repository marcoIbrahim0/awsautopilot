"""
Shared prerequisite checks for inventory reconciliation enqueue paths.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

import boto3
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.control_plane_event_ingest_status import ControlPlaneEventIngestStatus
from backend.models.finding import Finding
from backend.utils.sqs import parse_queue_region

REASON_CONTROL_PLANE_STALE = "control_plane_stale"
REASON_MISSING_CANONICAL_KEYS = "missing_canonical_keys"
REASON_MISSING_RESOURCE_KEYS = "missing_resource_keys"
REASON_INVENTORY_QUEUE_BACKLOG = "inventory_queue_backlog"
REASON_INVENTORY_DLQ_BACKLOG = "inventory_dlq_backlog"
REASON_PREREQUISITE_CHECK_ERROR = "prerequisite_check_error"


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _coerce_depth(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return None


def _ensure_utc(dt: object) -> datetime | None:
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dedup(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _queue_depth(queue_url: str, sqs_client: Any | None = None) -> int:
    client = sqs_client or boto3.client("sqs", region_name=parse_queue_region(queue_url))
    attrs = (
        client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ],
        ).get("Attributes")
        or {}
    )
    visible = _coerce_depth(attrs.get("ApproximateNumberOfMessages")) or 0
    not_visible = _coerce_depth(attrs.get("ApproximateNumberOfMessagesNotVisible")) or 0
    delayed = _coerce_depth(attrs.get("ApproximateNumberOfMessagesDelayed")) or 0
    return int(visible + not_visible + delayed)


def collect_reconciliation_queue_snapshot(
    sqs_client: Any | None = None,
) -> dict[str, Any]:
    queue_threshold = _coerce_int(getattr(settings, "CONTROL_PLANE_PREREQ_MAX_QUEUE_DEPTH", 100), 100)
    dlq_threshold = _coerce_int(getattr(settings, "CONTROL_PLANE_PREREQ_MAX_DLQ_DEPTH", 0), 0)
    queue_url = str(getattr(settings, "SQS_INVENTORY_RECONCILE_QUEUE_URL", "") or "").strip()
    dlq_url = str(getattr(settings, "SQS_INVENTORY_RECONCILE_DLQ_URL", "") or "").strip()

    snapshot: dict[str, Any] = {
        "inventory_queue_depth": None,
        "inventory_queue_depth_threshold": queue_threshold,
        "inventory_dlq_depth": None,
        "inventory_dlq_depth_threshold": dlq_threshold,
        "inventory_queue_url_configured": bool(queue_url),
        "inventory_dlq_url_configured": bool(dlq_url),
    }

    errors: list[str] = []
    if queue_url:
        try:
            snapshot["inventory_queue_depth"] = _queue_depth(queue_url, sqs_client=sqs_client)
        except Exception as exc:
            errors.append(f"inventory_queue_depth_error:{type(exc).__name__}")
    else:
        errors.append("inventory_queue_url_unset")

    if dlq_url:
        try:
            snapshot["inventory_dlq_depth"] = _queue_depth(dlq_url, sqs_client=sqs_client)
        except Exception as exc:
            errors.append(f"inventory_dlq_depth_error:{type(exc).__name__}")
    else:
        # If DLQ URL is not configured, treat it as empty for threshold checks.
        snapshot["inventory_dlq_depth"] = 0

    if errors:
        snapshot["queue_check_error"] = ",".join(errors)
    return snapshot


def _finding_filters(
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
) -> list[Any]:
    return [
        Finding.tenant_id == tenant_id,
        Finding.account_id == account_id,
        Finding.region == region,
        Finding.source == "security_hub",
        Finding.in_scope.is_(True),
    ]


def _build_snapshot(
    *,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    last_intake_time: datetime | None,
    age_minutes: float | None,
    max_staleness_minutes: int,
    missing_canonical_keys: int,
    missing_resource_keys: int,
    queue_snapshot: dict[str, Any],
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "account_id": account_id,
        "region": region,
        "control_plane_last_intake_time": last_intake_time.isoformat() if last_intake_time else None,
        "control_plane_age_minutes": age_minutes,
        "control_plane_max_staleness_minutes": max_staleness_minutes,
        "missing_canonical_keys": missing_canonical_keys,
        "missing_resource_keys": missing_resource_keys,
        "inventory_queue_depth": queue_snapshot.get("inventory_queue_depth"),
        "inventory_queue_depth_threshold": queue_snapshot.get("inventory_queue_depth_threshold"),
        "inventory_dlq_depth": queue_snapshot.get("inventory_dlq_depth"),
        "inventory_dlq_depth_threshold": queue_snapshot.get("inventory_dlq_depth_threshold"),
    }
    if queue_snapshot.get("queue_check_error"):
        snapshot["queue_check_error"] = queue_snapshot.get("queue_check_error")
    return snapshot


def _evaluate_reasons(
    *,
    last_intake_time: datetime | None,
    now_utc: datetime,
    max_staleness_minutes: int,
    missing_canonical_keys: int,
    missing_resource_keys: int,
    queue_snapshot: dict[str, Any],
) -> tuple[list[str], float | None]:
    reasons: list[str] = []
    age_minutes: float | None = None

    normalized_intake = _ensure_utc(last_intake_time)
    if normalized_intake is not None:
        age_minutes = max(0.0, (now_utc - normalized_intake).total_seconds() / 60.0)
        age_minutes = round(age_minutes, 2)
    if age_minutes is None or age_minutes > float(max_staleness_minutes):
        reasons.append(REASON_CONTROL_PLANE_STALE)

    if missing_canonical_keys > 0:
        reasons.append(REASON_MISSING_CANONICAL_KEYS)
    if missing_resource_keys > 0:
        reasons.append(REASON_MISSING_RESOURCE_KEYS)

    queue_depth = _coerce_depth(queue_snapshot.get("inventory_queue_depth"))
    queue_threshold = _coerce_int(queue_snapshot.get("inventory_queue_depth_threshold"), 100)
    if queue_depth is None:
        reasons.append(REASON_PREREQUISITE_CHECK_ERROR)
    elif queue_depth > queue_threshold:
        reasons.append(REASON_INVENTORY_QUEUE_BACKLOG)

    dlq_depth = _coerce_depth(queue_snapshot.get("inventory_dlq_depth"))
    dlq_threshold = _coerce_int(queue_snapshot.get("inventory_dlq_depth_threshold"), 0)
    if dlq_depth is None:
        reasons.append(REASON_PREREQUISITE_CHECK_ERROR)
    elif dlq_depth > dlq_threshold:
        reasons.append(REASON_INVENTORY_DLQ_BACKLOG)

    if queue_snapshot.get("queue_check_error"):
        reasons.append(REASON_PREREQUISITE_CHECK_ERROR)

    return _dedup(reasons), age_minutes


def evaluate_reconciliation_prereqs(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    queue_snapshot: dict[str, Any] | None = None,
    sqs_client: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_utc = _ensure_utc(now) or datetime.now(timezone.utc)
    max_staleness = _coerce_int(getattr(settings, "CONTROL_PLANE_PREREQ_MAX_STALENESS_MINUTES", 30), 30)
    queue_data = dict(queue_snapshot) if isinstance(queue_snapshot, dict) else collect_reconciliation_queue_snapshot(sqs_client=sqs_client)

    base_snapshot: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "account_id": account_id,
        "region": region,
        "control_plane_max_staleness_minutes": max_staleness,
        "inventory_queue_depth_threshold": queue_data.get("inventory_queue_depth_threshold"),
        "inventory_dlq_depth_threshold": queue_data.get("inventory_dlq_depth_threshold"),
    }

    try:
        last_intake = session.execute(
            select(ControlPlaneEventIngestStatus.last_intake_time).where(
                ControlPlaneEventIngestStatus.tenant_id == tenant_id,
                ControlPlaneEventIngestStatus.account_id == account_id,
                ControlPlaneEventIngestStatus.region == region,
            )
        ).scalar_one_or_none()

        filters = _finding_filters(tenant_id, account_id, region)
        missing_canonical_keys = int(
            (
                session.execute(
                    select(func.count()).select_from(Finding).where(*filters, Finding.canonical_control_id.is_(None))
                ).scalar()
            )
            or 0
        )
        missing_resource_keys = int(
            (
                session.execute(
                    select(func.count()).select_from(Finding).where(*filters, Finding.resource_key.is_(None))
                ).scalar()
            )
            or 0
        )

        reasons, age_minutes = _evaluate_reasons(
            last_intake_time=last_intake,
            now_utc=now_utc,
            max_staleness_minutes=max_staleness,
            missing_canonical_keys=missing_canonical_keys,
            missing_resource_keys=missing_resource_keys,
            queue_snapshot=queue_data,
        )
        snapshot = _build_snapshot(
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            last_intake_time=_ensure_utc(last_intake),
            age_minutes=age_minutes,
            max_staleness_minutes=max_staleness,
            missing_canonical_keys=missing_canonical_keys,
            missing_resource_keys=missing_resource_keys,
            queue_snapshot=queue_data,
        )
        return {"ok": len(reasons) == 0, "reasons": reasons, "snapshot": snapshot}
    except Exception as exc:
        base_snapshot["error_type"] = type(exc).__name__
        base_snapshot["error"] = str(exc)[:240]
        return {
            "ok": False,
            "reasons": [REASON_PREREQUISITE_CHECK_ERROR],
            "snapshot": base_snapshot,
        }


async def evaluate_reconciliation_prereqs_async(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    queue_snapshot: dict[str, Any] | None = None,
    sqs_client: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_utc = _ensure_utc(now) or datetime.now(timezone.utc)
    max_staleness = _coerce_int(getattr(settings, "CONTROL_PLANE_PREREQ_MAX_STALENESS_MINUTES", 30), 30)
    queue_data = dict(queue_snapshot) if isinstance(queue_snapshot, dict) else collect_reconciliation_queue_snapshot(sqs_client=sqs_client)

    base_snapshot: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "account_id": account_id,
        "region": region,
        "control_plane_max_staleness_minutes": max_staleness,
        "inventory_queue_depth_threshold": queue_data.get("inventory_queue_depth_threshold"),
        "inventory_dlq_depth_threshold": queue_data.get("inventory_dlq_depth_threshold"),
    }

    try:
        last_intake = (
            await db.execute(
                select(ControlPlaneEventIngestStatus.last_intake_time).where(
                    ControlPlaneEventIngestStatus.tenant_id == tenant_id,
                    ControlPlaneEventIngestStatus.account_id == account_id,
                    ControlPlaneEventIngestStatus.region == region,
                )
            )
        ).scalar_one_or_none()

        filters = _finding_filters(tenant_id, account_id, region)
        missing_canonical_keys = int(
            (
                await db.execute(
                    select(func.count()).select_from(Finding).where(*filters, Finding.canonical_control_id.is_(None))
                )
            ).scalar()
            or 0
        )
        missing_resource_keys = int(
            (
                await db.execute(
                    select(func.count()).select_from(Finding).where(*filters, Finding.resource_key.is_(None))
                )
            ).scalar()
            or 0
        )

        reasons, age_minutes = _evaluate_reasons(
            last_intake_time=last_intake,
            now_utc=now_utc,
            max_staleness_minutes=max_staleness,
            missing_canonical_keys=missing_canonical_keys,
            missing_resource_keys=missing_resource_keys,
            queue_snapshot=queue_data,
        )
        snapshot = _build_snapshot(
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            last_intake_time=_ensure_utc(last_intake),
            age_minutes=age_minutes,
            max_staleness_minutes=max_staleness,
            missing_canonical_keys=missing_canonical_keys,
            missing_resource_keys=missing_resource_keys,
            queue_snapshot=queue_data,
        )
        return {"ok": len(reasons) == 0, "reasons": reasons, "snapshot": snapshot}
    except Exception as exc:
        base_snapshot["error_type"] = type(exc).__name__
        base_snapshot["error"] = str(exc)[:240]
        return {
            "ok": False,
            "reasons": [REASON_PREREQUISITE_CHECK_ERROR],
            "snapshot": base_snapshot,
        }


__all__ = [
    "REASON_CONTROL_PLANE_STALE",
    "REASON_MISSING_CANONICAL_KEYS",
    "REASON_MISSING_RESOURCE_KEYS",
    "REASON_INVENTORY_QUEUE_BACKLOG",
    "REASON_INVENTORY_DLQ_BACKLOG",
    "REASON_PREREQUISITE_CHECK_ERROR",
    "collect_reconciliation_queue_snapshot",
    "evaluate_reconciliation_prereqs",
    "evaluate_reconciliation_prereqs_async",
]
