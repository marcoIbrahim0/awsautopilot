from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.models.app_notification import AppNotification
from backend.models.app_notification_user_state import AppNotificationUserState
from backend.models.governance_notification import GovernanceNotification
from backend.models.user import User

JOB_SOURCE = "background_job"
GOVERNANCE_SOURCE = "governance"
ACTIVE_JOB_STATUSES = {"queued", "running", "partial"}
JOB_STALE_AFTER = timedelta(minutes=20)


def default_job_severity(status: str) -> str:
    if status in {"error", "timed_out"}:
        return "error"
    if status in {"success"}:
        return "success"
    if status in {"partial", "canceled"}:
        return "warning"
    return "info"


def governance_severity(status: str, stage: str) -> str:
    if status == "failed":
        return "error"
    if stage == "completion":
        return "success"
    if stage == "action_required":
        return "warning"
    return "info"


def governance_status(status: str, stage: str) -> str:
    if status in {"failed", "skipped"}:
        return status
    return stage


def extract_action_url(payload: dict | None) -> str | None:
    webhook = payload.get("webhook") if isinstance(payload, dict) else None
    if not isinstance(webhook, dict):
        return None
    value = webhook.get("action_url")
    return value.strip() if isinstance(value, str) and value.strip() else None


def extract_detail(payload: dict | None) -> str | None:
    webhook = payload.get("webhook") if isinstance(payload, dict) else None
    if not isinstance(webhook, dict):
        return None
    value = webhook.get("detail")
    return value.strip() if isinstance(value, str) and value.strip() else None


def extract_message(payload: dict | None, fallback: str) -> str:
    value = payload.get("message") if isinstance(payload, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def extract_title(payload: dict | None, fallback: str) -> str:
    value = payload.get("title") if isinstance(payload, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()[:255]
    return fallback[:255]


def stale_detail(detail: str | None) -> str:
    if detail:
        return detail
    return "No status update was received for a long time. Refresh or retry if needed."


def is_stale_job(notification: AppNotification, now: datetime) -> bool:
    if notification.source != JOB_SOURCE:
        return False
    if notification.status not in ACTIVE_JOB_STATUSES:
        return False
    updated_at = notification.updated_at
    return isinstance(updated_at, datetime) and now - updated_at > JOB_STALE_AFTER


def notification_scope(current_user: User) -> list:
    return [
        AppNotification.tenant_id == current_user.tenant_id,
        or_(AppNotification.actor_user_id.is_(None), AppNotification.actor_user_id == current_user.id),
    ]


def base_state_query(current_user: User) -> tuple[type[AppNotificationUserState], Select]:
    state = aliased(AppNotificationUserState)
    query = select(AppNotification, state).outerjoin(
        state,
        and_(state.notification_id == AppNotification.id, state.user_id == current_user.id),
    )
    return state, query.where(*notification_scope(current_user))


def apply_archive_filter(query: Select, state) -> Select:
    return query.where(or_(state.archived_at.is_(None), state.notification_id.is_(None)))


async def count_notifications(db: AsyncSession, query: Select) -> int:
    result = await db.execute(select(func.count()).select_from(query.subquery()))
    return int(result.scalar() or 0)


async def fetch_notification_rows(
    db: AsyncSession,
    *,
    current_user: User,
    limit: int,
    offset: int,
    include_archived: bool,
) -> tuple[list[tuple[AppNotification, AppNotificationUserState | None]], int, int]:
    state, base = base_state_query(current_user)
    visible = base if include_archived else apply_archive_filter(base, state)
    unread = apply_archive_filter(base, state).where(or_(state.read_at.is_(None), state.notification_id.is_(None)))
    rows = await db.execute(visible.order_by(AppNotification.created_at.desc()).limit(limit).offset(offset))
    return rows.all(), await count_notifications(db, visible), await count_notifications(db, unread)


def serialize_notification(
    notification: AppNotification,
    state: AppNotificationUserState | None,
    now: datetime,
) -> dict[str, object | None]:
    status = notification.status
    severity = notification.severity
    progress = notification.progress
    detail = notification.detail
    updated_at = notification.updated_at
    if is_stale_job(notification, now):
        status = "timed_out"
        severity = "error"
        progress = max(progress or 0, 100)
        detail = stale_detail(detail)
    return {
        "id": str(notification.id),
        "kind": notification.kind,
        "source": notification.source,
        "severity": severity,
        "status": status,
        "title": notification.title,
        "message": notification.message,
        "detail": detail,
        "progress": progress,
        "action_url": notification.action_url,
        "target_type": notification.target_type,
        "target_id": str(notification.target_id) if notification.target_id else None,
        "client_key": notification.client_key,
        "created_at": notification.created_at.isoformat(),
        "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else None,
        "read_at": state.read_at.isoformat() if state and state.read_at else None,
        "archived_at": state.archived_at.isoformat() if state and state.archived_at else None,
    }


async def mirror_governance_notification(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    governance_notification: GovernanceNotification,
) -> AppNotification:
    existing = await db.execute(
        select(AppNotification).where(
            AppNotification.tenant_id == tenant_id,
            AppNotification.governance_notification_id == governance_notification.id,
        )
    )
    item = existing.scalar_one_or_none()
    payload = governance_notification.payload if isinstance(governance_notification.payload, dict) else {}
    if item is None:
        item = AppNotification(
            tenant_id=tenant_id,
            governance_notification_id=governance_notification.id,
            kind="governance",
            source=GOVERNANCE_SOURCE,
            severity=governance_severity(governance_notification.status, governance_notification.stage),
            status=governance_status(governance_notification.status, governance_notification.stage),
            title=extract_title(payload, governance_notification.stage.replace("_", " ").title()),
            message=extract_message(payload, "Governance notification"),
            detail=extract_detail(payload),
            action_url=extract_action_url(payload),
            target_type=governance_notification.target_type,
            target_id=governance_notification.target_id,
        )
        db.add(item)
        await db.flush()
        return item
    item.severity = governance_severity(governance_notification.status, governance_notification.stage)
    item.status = governance_status(governance_notification.status, governance_notification.stage)
    item.title = extract_title(payload, item.title)
    item.message = extract_message(payload, item.message)
    item.detail = extract_detail(payload)
    item.action_url = extract_action_url(payload)
    return item


async def upsert_job_notification(
    db: AsyncSession,
    *,
    current_user: User,
    client_key: str,
    payload: dict[str, object | None],
) -> AppNotification:
    result = await db.execute(
        select(AppNotification).where(
            AppNotification.tenant_id == current_user.tenant_id,
            AppNotification.client_key == client_key,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = AppNotification(
            tenant_id=current_user.tenant_id,
            actor_user_id=current_user.id,
            kind="job",
            source=JOB_SOURCE,
            client_key=client_key,
            severity=str(payload.get("severity") or default_job_severity(str(payload.get("status") or "running"))),
            status=str(payload.get("status") or "running"),
            title=str(payload.get("title") or "Background task")[:255],
            message=str(payload.get("message") or ""),
        )
        db.add(item)
    item.actor_user_id = current_user.id
    item.severity = str(payload.get("severity") or default_job_severity(str(payload.get("status") or item.status)))
    item.status = str(payload.get("status") or item.status)
    item.title = str(payload.get("title") or item.title)[:255]
    item.message = str(payload.get("message") or item.message)
    item.detail = str(payload["detail"]) if payload.get("detail") is not None else None
    item.progress = int(payload["progress"]) if payload.get("progress") is not None else None
    item.action_url = str(payload["action_url"]) if payload.get("action_url") is not None else None
    item.target_type = str(payload["target_type"]) if payload.get("target_type") is not None else None
    item.target_id = uuid.UUID(str(payload["target_id"])) if payload.get("target_id") else None
    await db.flush()
    return item


async def load_state_rows(
    db: AsyncSession,
    *,
    current_user: User,
    notification_ids: list[uuid.UUID],
) -> dict[uuid.UUID, AppNotificationUserState]:
    result = await db.execute(
        select(AppNotificationUserState).where(
            AppNotificationUserState.user_id == current_user.id,
            AppNotificationUserState.notification_id.in_(notification_ids),
        )
    )
    rows = result.scalars().all()
    return {row.notification_id: row for row in rows}


async def fetch_visible_notifications(
    db: AsyncSession,
    *,
    current_user: User,
    ids: list[uuid.UUID] | None,
) -> list[AppNotification]:
    query = select(AppNotification).where(*notification_scope(current_user))
    if ids:
        query = query.where(AppNotification.id.in_(ids))
    result = await db.execute(query)
    return result.scalars().all()


def set_state_value(row: AppNotificationUserState, *, action: str, now: datetime) -> None:
    if action == "read":
        row.read_at = now
    if action == "unread":
        row.read_at = None
    if action == "archive":
        row.read_at = row.read_at or now
        row.archived_at = now


async def apply_state_action(
    db: AsyncSession,
    *,
    current_user: User,
    action: str,
    ids: list[uuid.UUID] | None,
) -> int:
    notifications = await fetch_visible_notifications(db, current_user=current_user, ids=ids)
    if action == "mark_all_read":
        notifications = [item for item in notifications if True]
    notification_ids = [item.id for item in notifications]
    if not notification_ids:
        return 0
    states = await load_state_rows(db, current_user=current_user, notification_ids=notification_ids)
    now = datetime.now(timezone.utc)
    updated = 0
    for notification in notifications:
        row = states.get(notification.id)
        if row is None:
            row = AppNotificationUserState(notification_id=notification.id, user_id=current_user.id)
            db.add(row)
            states[notification.id] = row
        if action == "mark_all_read":
            row.read_at = now
            updated += 1
            continue
        set_state_value(row, action=action, now=now)
        updated += 1
    await db.flush()
    return updated
