from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, noload

from backend.models.action import Action
from backend.models.action_group import ActionGroup
from backend.models.action_group_action_state import ActionGroupActionState
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.enums import ActionGroupStatusBucket
from backend.services.action_run_confirmation import derive_action_run_status

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PendingGroup:
    tenant_id: uuid.UUID
    action_type: str
    account_id: str
    region: str | None
    group_key: str


def _normalized_region(region: str | None) -> str:
    value = (region or "").strip()
    return value if value else "global"


def build_group_key(
    tenant_id: uuid.UUID,
    action_type: str,
    account_id: str,
    region: str | None,
) -> str:
    """Stable deterministic group key; excludes mutable status fields."""
    return f"{tenant_id}|{action_type}|{account_id}|{_normalized_region(region)}"


def resolve_group_for_action(session: Session, action: Action) -> ActionGroup:
    """
    Resolve or create immutable group bucket for an action.

    Grouping basis is fixed: tenant + action_type + account_id + region.
    """
    group = _groups_by_key(session, [build_group_key(action.tenant_id, action.action_type, action.account_id, action.region)])
    if group:
        return next(iter(group.values()))
    _ensure_groups(
        session,
        [_pending_group_for_action(action)],
    )
    return resolve_group_for_action(session, action)


def _ensure_action_state_projection(
    session: Session,
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    action_id: uuid.UUID,
) -> None:
    existing = (
        session.query(ActionGroupActionState)
        .filter(
            ActionGroupActionState.tenant_id == tenant_id,
            ActionGroupActionState.group_id == group_id,
            ActionGroupActionState.action_id == action_id,
        )
        .one_or_none()
    )
    if existing is not None:
        return

    session.add(
        ActionGroupActionState(
            tenant_id=tenant_id,
            group_id=group_id,
            action_id=action_id,
            latest_run_status_bucket=ActionGroupStatusBucket.not_run_yet,
        )
    )


def _pending_group_for_action(action: Action) -> _PendingGroup:
    return _PendingGroup(
        tenant_id=action.tenant_id,
        action_type=action.action_type,
        account_id=action.account_id,
        region=action.region,
        group_key=build_group_key(action.tenant_id, action.action_type, action.account_id, action.region),
    )


def _normalized_source(source: str) -> str:
    normalized = (source or "ingest").strip()[:32]
    return normalized or "ingest"


def _dedupe_actions(actions: Sequence[Action] | Iterable[Action]) -> list[Action]:
    ordered: list[Action] = []
    seen: set[uuid.UUID] = set()
    for action in actions:
        action_id = getattr(action, "id", None)
        if action_id is None or action_id in seen:
            continue
        seen.add(action_id)
        ordered.append(action)
    return ordered


def _groups_by_key(session: Session, group_keys: Iterable[str]) -> dict[str, ActionGroup]:
    keys = [key for key in group_keys if key]
    if not keys:
        return {}
    result = session.execute(
        select(ActionGroup)
        .options(
            noload(ActionGroup.memberships),
            noload(ActionGroup.runs),
            noload(ActionGroup.action_states),
        )
        .where(ActionGroup.group_key.in_(keys))
    )
    return {row.group_key: row for row in result.scalars().all()}


def _memberships_by_action_id(
    session: Session,
    action_ids: Iterable[uuid.UUID],
) -> dict[uuid.UUID, ActionGroupMembership]:
    ids = list(action_ids)
    if not ids:
        return {}
    result = session.execute(
        select(ActionGroupMembership)
        .options(
            noload(ActionGroupMembership.group),
            noload(ActionGroupMembership.action),
        )
        .where(ActionGroupMembership.action_id.in_(ids))
    )
    return {row.action_id: row for row in result.scalars().all()}


def _existing_state_keys(
    session: Session,
    action_ids: Iterable[uuid.UUID],
) -> set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    ids = list(action_ids)
    if not ids:
        return set()
    result = session.execute(
        select(
            ActionGroupActionState.tenant_id,
            ActionGroupActionState.group_id,
            ActionGroupActionState.action_id,
        ).where(ActionGroupActionState.action_id.in_(ids))
    )
    return set(result.all())


def _ensure_groups(session: Session, groups: Sequence[_PendingGroup]) -> dict[str, ActionGroup]:
    pending = {group.group_key: group for group in groups}
    existing = _groups_by_key(session, pending)
    missing = [group for key, group in pending.items() if key not in existing]
    if missing:
        session.execute(
            pg_insert(ActionGroup.__table__)
            .values(
                [
                    {
                        "tenant_id": group.tenant_id,
                        "action_type": group.action_type,
                        "account_id": group.account_id,
                        "region": group.region,
                        "group_key": group.group_key,
                        "metadata": {"source": "auto_assign"},
                    }
                    for group in missing
                ]
            )
            .on_conflict_do_nothing(index_elements=[ActionGroup.__table__.c.group_key])
        )
        existing = _groups_by_key(session, pending)
    return existing


def _ensure_memberships(
    session: Session,
    actions: Sequence[Action],
    groups_by_key: dict[str, ActionGroup],
    source: str,
) -> dict[uuid.UUID, ActionGroupMembership]:
    existing = _memberships_by_action_id(session, [action.id for action in actions])
    missing_rows = []
    for action in actions:
        if action.id in existing:
            continue
        group = groups_by_key[_pending_group_for_action(action).group_key]
        missing_rows.append(
            {
                "id": uuid.uuid4(),
                "tenant_id": action.tenant_id,
                "group_id": group.id,
                "action_id": action.id,
                "source": source,
            }
        )
    if missing_rows:
        session.execute(
            pg_insert(ActionGroupMembership.__table__)
            .values(missing_rows)
            .on_conflict_do_nothing(index_elements=[ActionGroupMembership.__table__.c.action_id])
        )
        existing = _memberships_by_action_id(session, [action.id for action in actions])
    return existing


def _ensure_action_states(
    session: Session,
    memberships: Sequence[ActionGroupMembership],
) -> None:
    existing = _existing_state_keys(session, [membership.action_id for membership in memberships])
    missing_rows = []
    for membership in memberships:
        state_key = (membership.tenant_id, membership.group_id, membership.action_id)
        if state_key in existing:
            continue
        missing_rows.append(
            {
                "tenant_id": membership.tenant_id,
                "group_id": membership.group_id,
                "action_id": membership.action_id,
                "latest_run_status_bucket": ActionGroupStatusBucket.not_run_yet.value,
            }
        )
    if missing_rows:
        session.execute(
            pg_insert(ActionGroupActionState.__table__)
            .values(missing_rows)
            .on_conflict_do_nothing(
                index_elements=[
                    ActionGroupActionState.__table__.c.tenant_id,
                    ActionGroupActionState.__table__.c.group_id,
                    ActionGroupActionState.__table__.c.action_id,
                ]
            )
        )


def assign_action_to_group_once(
    session: Session,
    action: Action,
    source: str = "ingest",
) -> ActionGroupMembership:
    """
    Immutable one-time assignment.

    If membership already exists, it is returned unchanged.
    """
    memberships = ensure_membership_for_actions(session, [action], source=source)
    if not memberships:
        raise ValueError("action must have a persisted id before group assignment")
    return memberships[0]


def ensure_membership_for_actions(
    session: Session,
    actions: Sequence[Action] | Iterable[Action],
    source: str = "ingest",
) -> list[ActionGroupMembership]:
    """Idempotently ensure immutable membership for each action."""
    ordered_actions = _dedupe_actions(actions)
    if not ordered_actions:
        return []

    groups_by_key = _ensure_groups(session, [_pending_group_for_action(action) for action in ordered_actions])
    memberships_by_action = _ensure_memberships(session, ordered_actions, groups_by_key, _normalized_source(source))
    memberships = [memberships_by_action[action.id] for action in ordered_actions if action.id in memberships_by_action]
    _ensure_action_states(session, memberships)
    return memberships


async def list_groups_with_counters(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str | None = None,
    region: str | None = None,
    action_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    """List persistent groups with aggregate status buckets."""
    filters = [ActionGroup.tenant_id == tenant_id]
    if account_id:
        filters.append(ActionGroup.account_id == account_id.strip())
    if region is not None:
        if region:
            filters.append(ActionGroup.region == region.strip())
        else:
            filters.append(ActionGroup.region.is_(None))
    if action_type:
        filters.append(ActionGroup.action_type == action_type.strip())

    run_successful_expr = func.coalesce(
        func.sum(
            case(
                (
                    ActionGroupActionState.latest_run_status_bucket.in_(
                        [
                            ActionGroupStatusBucket.run_successful_pending_confirmation,
                            ActionGroupStatusBucket.run_successful_needs_followup,
                            ActionGroupStatusBucket.run_successful_confirmed,
                        ]
                    ),
                    1,
                ),
                else_=0,
            )
        ),
        0,
    )
    run_not_successful_expr = func.coalesce(
        func.sum(
            case(
                (ActionGroupActionState.latest_run_status_bucket == ActionGroupStatusBucket.run_not_successful, 1),
                else_=0,
            )
        ),
        0,
    )
    metadata_only_expr = func.coalesce(
        func.sum(
            case(
                (
                    ActionGroupActionState.latest_run_status_bucket == ActionGroupStatusBucket.run_finished_metadata_only,
                    1,
                ),
                else_=0,
            )
        ),
        0,
    )
    not_run_yet_expr = func.coalesce(
        func.sum(
            case(
                (ActionGroupActionState.latest_run_status_bucket == ActionGroupStatusBucket.not_run_yet, 1),
                else_=0,
            )
        ),
        0,
    )
    total_actions_expr = func.count(ActionGroupMembership.action_id)

    grouped = (
        select(
            ActionGroup.id.label("id"),
            ActionGroup.group_key.label("group_key"),
            ActionGroup.action_type.label("action_type"),
            ActionGroup.account_id.label("account_id"),
            ActionGroup.region.label("region"),
            ActionGroup.created_at.label("created_at"),
            ActionGroup.updated_at.label("updated_at"),
            ActionGroup.metadata_json.label("metadata"),
            run_successful_expr.label("run_successful"),
            run_not_successful_expr.label("run_not_successful"),
            metadata_only_expr.label("metadata_only"),
            not_run_yet_expr.label("not_run_yet"),
            total_actions_expr.label("total_actions"),
        )
        .select_from(ActionGroup)
        .join(
            ActionGroupMembership,
            (ActionGroupMembership.group_id == ActionGroup.id)
            & (ActionGroupMembership.tenant_id == ActionGroup.tenant_id),
        )
        .outerjoin(
            ActionGroupActionState,
            (ActionGroupActionState.tenant_id == ActionGroupMembership.tenant_id)
            & (ActionGroupActionState.group_id == ActionGroupMembership.group_id)
            & (ActionGroupActionState.action_id == ActionGroupMembership.action_id),
        )
        .where(*filters)
        .group_by(ActionGroup.id)
    )

    total_query = select(func.count()).select_from(grouped.order_by(None).subquery())
    total_result = await db.execute(total_query)
    total = int(total_result.scalar() or 0)

    rows_result = await db.execute(
        grouped.order_by(ActionGroup.created_at.desc(), ActionGroup.id.desc()).limit(limit).offset(offset)
    )
    items = []
    for row in rows_result:
        items.append(
            {
                "id": str(row.id),
                "group_key": row.group_key,
                "action_type": row.action_type,
                "account_id": row.account_id,
                "region": row.region,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": row.metadata or {},
                "run_successful": int(row.run_successful or 0),
                "run_not_successful": int(row.run_not_successful or 0),
                "metadata_only": int(row.metadata_only or 0),
                "not_run_yet": int(row.not_run_yet or 0),
                "total_actions": int(row.total_actions or 0),
            }
        )

    return {"items": items, "total": total}


async def get_group_detail(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
) -> dict[str, object] | None:
    """Return one persistent group with member-level state and latest run links."""
    group_result = await db.execute(
        select(ActionGroup).where(ActionGroup.tenant_id == tenant_id, ActionGroup.id == group_id)
    )
    group = group_result.scalar_one_or_none()
    if group is None:
        return None

    members_result = await db.execute(
        select(
            ActionGroupMembership.action_id.label("action_id"),
            ActionGroupMembership.assigned_at.label("assigned_at"),
            Action.status.label("action_status"),
            Action.title.label("title"),
            Action.control_id.label("control_id"),
            Action.resource_id.label("resource_id"),
            Action.priority.label("priority"),
            Action.updated_at.label("action_updated_at"),
            ActionGroupActionState.latest_run_status_bucket.label("status_bucket"),
            ActionGroupActionState.latest_run_id.label("latest_run_id"),
            ActionGroupActionState.last_attempt_at.label("last_attempt_at"),
            ActionGroupActionState.last_confirmed_at.label("last_confirmed_at"),
            ActionGroupActionState.last_confirmation_source.label("last_confirmation_source"),
            ActionGroupRun.status.label("latest_run_status"),
            ActionGroupRun.started_at.label("latest_run_started_at"),
            ActionGroupRun.finished_at.label("latest_run_finished_at"),
        )
        .select_from(ActionGroupMembership)
        .join(
            Action,
            (Action.id == ActionGroupMembership.action_id)
            & (Action.tenant_id == ActionGroupMembership.tenant_id),
        )
        .outerjoin(
            ActionGroupActionState,
            (ActionGroupActionState.tenant_id == ActionGroupMembership.tenant_id)
            & (ActionGroupActionState.group_id == ActionGroupMembership.group_id)
            & (ActionGroupActionState.action_id == ActionGroupMembership.action_id),
        )
        .outerjoin(
            ActionGroupRun,
            (ActionGroupRun.id == ActionGroupActionState.latest_run_id)
            & (ActionGroupRun.tenant_id == ActionGroupMembership.tenant_id),
        )
        .where(
            ActionGroupMembership.tenant_id == tenant_id,
            ActionGroupMembership.group_id == group_id,
        )
        .order_by(Action.priority.desc(), Action.updated_at.desc().nullslast(), Action.id.asc())
    )

    members: list[dict[str, object]] = []
    counters = {
        "run_successful": 0,
        "run_not_successful": 0,
        "metadata_only": 0,
        "not_run_yet": 0,
        "total_actions": 0,
    }
    for row in members_result:
        bucket = (
            row.status_bucket.value
            if row.status_bucket is not None and hasattr(row.status_bucket, "value")
            else str(row.status_bucket or ActionGroupStatusBucket.not_run_yet.value)
        )
        if bucket in {
            ActionGroupStatusBucket.run_successful_pending_confirmation.value,
            ActionGroupStatusBucket.run_successful_needs_followup.value,
            ActionGroupStatusBucket.run_successful_confirmed.value,
        }:
            counters["run_successful"] += 1
        elif bucket == ActionGroupStatusBucket.run_finished_metadata_only.value:
            counters["metadata_only"] += 1
        elif bucket == ActionGroupStatusBucket.run_not_successful.value:
            counters["run_not_successful"] += 1
        else:
            counters["not_run_yet"] += 1
        counters["total_actions"] += 1

        members.append(
            {
                "action_id": str(row.action_id),
                "assigned_at": row.assigned_at,
                "action_status": row.action_status,
                "title": row.title,
                "control_id": row.control_id,
                "resource_id": row.resource_id,
                "priority": int(row.priority or 0),
                "action_updated_at": row.action_updated_at,
                "status_bucket": bucket,
                "latest_run_id": str(row.latest_run_id) if row.latest_run_id else None,
                "last_attempt_at": row.last_attempt_at,
                "last_confirmed_at": row.last_confirmed_at,
                "last_confirmation_source": (
                    row.last_confirmation_source.value
                    if row.last_confirmation_source is not None and hasattr(row.last_confirmation_source, "value")
                    else str(row.last_confirmation_source) if row.last_confirmation_source is not None else None
                ),
                "latest_run_status": (
                    row.latest_run_status.value
                    if row.latest_run_status is not None and hasattr(row.latest_run_status, "value")
                    else str(row.latest_run_status) if row.latest_run_status is not None else None
                ),
                "latest_run_started_at": row.latest_run_started_at,
                "latest_run_finished_at": row.latest_run_finished_at,
                **derive_action_run_status(
                    status_bucket=bucket,
                    latest_run_status=(
                        row.latest_run_status.value
                        if row.latest_run_status is not None and hasattr(row.latest_run_status, "value")
                        else str(row.latest_run_status) if row.latest_run_status is not None else None
                    ),
                    latest_run_finished_at=row.latest_run_finished_at,
                    last_confirmed_at=row.last_confirmed_at,
                ),
            }
        )

    return {
        "group": {
            "id": str(group.id),
            "tenant_id": str(group.tenant_id),
            "action_type": group.action_type,
            "account_id": group.account_id,
            "region": group.region,
            "group_key": group.group_key,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "metadata": group.metadata_json or {},
        },
        "counters": counters,
        "members": members,
    }
