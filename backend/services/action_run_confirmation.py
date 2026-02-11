from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.models.action_finding import ActionFinding
from backend.models.action_group_action_state import ActionGroupActionState
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.enums import (
    ActionGroupConfirmationSource,
    ActionGroupExecutionStatus,
    ActionGroupStatusBucket,
)
from backend.models.finding import Finding

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _max_ts(*values: datetime | None) -> datetime | None:
    normalized = [v for v in (_to_utc(value) for value in values) if v is not None]
    if not normalized:
        return None
    return max(normalized)


def _get_membership(session: Session, action_id: uuid.UUID) -> ActionGroupMembership | None:
    return (
        session.query(ActionGroupMembership)
        .filter(ActionGroupMembership.action_id == action_id)
        .one_or_none()
    )


def _get_or_create_state(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    action_id: uuid.UUID,
) -> ActionGroupActionState:
    state = (
        session.query(ActionGroupActionState)
        .filter(
            ActionGroupActionState.tenant_id == tenant_id,
            ActionGroupActionState.group_id == group_id,
            ActionGroupActionState.action_id == action_id,
        )
        .one_or_none()
    )
    if state is not None:
        return state

    state = ActionGroupActionState(
        tenant_id=tenant_id,
        group_id=group_id,
        action_id=action_id,
        latest_run_status_bucket=ActionGroupStatusBucket.not_run_yet,
    )
    session.add(state)
    return state


def record_execution_attempt(
    session: Session,
    *,
    action_id: uuid.UUID,
    latest_run_id: uuid.UUID | None,
    attempted_at: datetime | None = None,
) -> ActionGroupActionState | None:
    """
    Record a run attempt. Any attempt moves bucket away from `not_run_yet`.

    This does not mark success; AWS confirmation is required.
    """
    membership = _get_membership(session, action_id=action_id)
    if membership is None:
        logger.debug("record_execution_attempt skipped: no membership action_id=%s", action_id)
        return None

    state = _get_or_create_state(
        session,
        tenant_id=membership.tenant_id,
        group_id=membership.group_id,
        action_id=membership.action_id,
    )
    state.latest_run_id = latest_run_id
    state.last_attempt_at = _to_utc(attempted_at) or _utcnow()
    state.latest_run_status_bucket = ActionGroupStatusBucket.run_not_successful
    logger.info(
        "action_run_confirmation attempt action_id=%s group_id=%s run_id=%s bucket=%s",
        action_id,
        membership.group_id,
        latest_run_id,
        state.latest_run_status_bucket.value,
    )
    return state


def record_execution_result(
    session: Session,
    *,
    action_id: uuid.UUID,
    latest_run_id: uuid.UUID | None,
    execution_status: ActionGroupExecutionStatus | str,
    attempted_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ActionGroupActionState | None:
    """
    Record the execution outcome and keep bucket non-success until AWS confirmation.
    """
    parsed_status = (
        execution_status
        if isinstance(execution_status, ActionGroupExecutionStatus)
        else ActionGroupExecutionStatus(str(execution_status))
    )
    state = record_execution_attempt(
        session,
        action_id=action_id,
        latest_run_id=latest_run_id,
        attempted_at=attempted_at or finished_at,
    )
    if state is None:
        return None

    # Never set run_successful_confirmed from execution outcome alone.
    state.latest_run_status_bucket = ActionGroupStatusBucket.run_not_successful
    logger.info(
        "action_run_confirmation result action_id=%s run_id=%s execution_status=%s bucket=%s",
        action_id,
        latest_run_id,
        parsed_status.value,
        state.latest_run_status_bucket.value,
    )
    return state


def _find_confirmation_signal(
    findings: list[Finding],
    *,
    since_run_started: datetime,
) -> tuple[bool, ActionGroupConfirmationSource | None, datetime | None]:
    since = _to_utc(since_run_started)
    if since is None:
        return False, None, None

    security_hub_confirmed_at: datetime | None = None
    control_plane_confirmed_at: datetime | None = None
    for finding in findings:
        sh_time = _max_ts(getattr(finding, "last_observed_at", None), getattr(finding, "updated_at", None))
        if finding.status == "RESOLVED" and sh_time is not None and sh_time >= since:
            security_hub_confirmed_at = sh_time if security_hub_confirmed_at is None else max(security_hub_confirmed_at, sh_time)

        cp_time = _max_ts(
            getattr(finding, "shadow_last_observed_event_time", None),
            getattr(finding, "shadow_last_evaluated_at", None),
        )
        if finding.shadow_status_normalized == "RESOLVED" and cp_time is not None and cp_time >= since:
            control_plane_confirmed_at = (
                cp_time if control_plane_confirmed_at is None else max(control_plane_confirmed_at, cp_time)
            )

    # Prefer Security Hub when both are available for the same window.
    if security_hub_confirmed_at is not None:
        return True, ActionGroupConfirmationSource.security_hub, security_hub_confirmed_at
    if control_plane_confirmed_at is not None:
        return True, ActionGroupConfirmationSource.control_plane_reconcile, control_plane_confirmed_at
    return False, None, None


def evaluate_confirmation_for_action(
    session: Session,
    *,
    action_id: uuid.UUID,
    since_run_started: datetime | None = None,
) -> dict[str, object]:
    """
    Evaluate trusted AWS confirmations and update immutable state bucket.

    Apply/bundle success alone never flips to successful-confirmed.
    """
    membership = _get_membership(session, action_id=action_id)
    if membership is None:
        return {"action_id": str(action_id), "confirmed": False, "reason": "no_membership"}

    state = _get_or_create_state(
        session,
        tenant_id=membership.tenant_id,
        group_id=membership.group_id,
        action_id=membership.action_id,
    )
    threshold = _to_utc(since_run_started) or _to_utc(state.last_attempt_at)
    if threshold is None:
        state.latest_run_status_bucket = ActionGroupStatusBucket.not_run_yet
        return {"action_id": str(action_id), "confirmed": False, "reason": "no_attempt"}

    findings = (
        session.query(Finding)
        .join(ActionFinding, ActionFinding.finding_id == Finding.id)
        .filter(ActionFinding.action_id == action_id, Finding.tenant_id == membership.tenant_id)
        .all()
    )
    confirmed, source, confirmed_at = _find_confirmation_signal(findings, since_run_started=threshold)
    if confirmed:
        state.latest_run_status_bucket = ActionGroupStatusBucket.run_successful_confirmed
        state.last_confirmed_at = confirmed_at or _utcnow()
        state.last_confirmation_source = source
        logger.info(
            "action_run_confirmation confirmed action_id=%s group_id=%s source=%s confirmed_at=%s",
            action_id,
            membership.group_id,
            source.value if source else None,
            state.last_confirmed_at.isoformat() if state.last_confirmed_at else None,
        )
    else:
        state.latest_run_status_bucket = ActionGroupStatusBucket.run_not_successful
        logger.debug(
            "action_run_confirmation pending action_id=%s group_id=%s since=%s",
            action_id,
            membership.group_id,
            threshold.isoformat(),
        )

    return {
        "action_id": str(action_id),
        "confirmed": bool(confirmed),
        "source": source.value if source else None,
        "confirmed_at": confirmed_at.isoformat() if confirmed_at else None,
        "bucket": state.latest_run_status_bucket.value,
    }


def reevaluate_confirmation_for_actions(
    session: Session,
    *,
    action_ids: Iterable[uuid.UUID],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for action_id in action_ids:
        results.append(evaluate_confirmation_for_action(session, action_id=action_id))
    return results


async def evaluate_confirmation_for_action_async(
    db: AsyncSession,
    *,
    action_id: uuid.UUID,
    since_run_started: datetime | None = None,
) -> dict[str, object]:
    def _run(sync_session: Session) -> dict[str, object]:
        return evaluate_confirmation_for_action(
            sync_session,
            action_id=action_id,
            since_run_started=since_run_started,
        )

    return await db.run_sync(_run)


async def reevaluate_confirmation_for_actions_async(
    db: AsyncSession,
    *,
    action_ids: Iterable[uuid.UUID],
) -> list[dict[str, object]]:
    action_ids_list = list(action_ids)

    def _run(sync_session: Session) -> list[dict[str, object]]:
        return reevaluate_confirmation_for_actions(sync_session, action_ids=action_ids_list)

    return await db.run_sync(_run)


async def record_execution_result_async(
    db: AsyncSession,
    *,
    action_id: uuid.UUID,
    latest_run_id: uuid.UUID | None,
    execution_status: ActionGroupExecutionStatus | str,
    attempted_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    def _run(sync_session: Session) -> None:
        record_execution_result(
            sync_session,
            action_id=action_id,
            latest_run_id=latest_run_id,
            execution_status=execution_status,
            attempted_at=attempted_at,
            finished_at=finished_at,
        )

    await db.run_sync(_run)
