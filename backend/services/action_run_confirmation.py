from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, lazyload, load_only

from backend.models.action_finding import ActionFinding
from backend.models.action_group_action_state import ActionGroupActionState
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.action_group_run_result import ActionGroupRunResult
from backend.models.enums import (
    ActionGroupConfirmationSource,
    ActionGroupExecutionStatus,
    ActionGroupStatusBucket,
)
from backend.models.finding import Finding
from backend.models.remediation_run import RemediationRun

logger = logging.getLogger(__name__)

PENDING_CONFIRMATION_WINDOW = timedelta(hours=12)
PENDING_CONFIRMATION_INFO_MESSAGE = (
    "This fix was applied successfully. AWS source-of-truth checks like Security Hub can take up to 12 hours "
    "to confirm the finding is resolved."
)
PENDING_CONFIRMATION_WARNING_MESSAGE = (
    "The fix was applied successfully, but AWS source-of-truth confirmation has not arrived after 12 hours. "
    "Check Security Hub/reconciliation and investigate why the resolved state has not propagated."
)
SUCCESS_NEEDS_FOLLOWUP_MESSAGE = (
    "The fix was applied successfully. Restricted access was added, but unrestricted public access is still present. "
    "Remove the unrestricted rule to resolve this finding."
)
SUCCESS_NEEDS_FOLLOWUP_KIND = "unrestricted_public_access_retained"


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
    stmt = (
        select(ActionGroupMembership)
        .options(
            lazyload("*"),
            load_only(
                ActionGroupMembership.tenant_id,
                ActionGroupMembership.group_id,
                ActionGroupMembership.action_id,
            ),
        )
        .where(ActionGroupMembership.action_id == action_id)
    )
    return session.execute(stmt).scalar_one_or_none()


def _is_non_executable_status(value: str | None) -> bool:
    return (value or "").strip().lower() in {"", "unknown"}


def _is_metadata_only_result(raw_result: object) -> bool:
    if not isinstance(raw_result, dict):
        return False
    result_type = str(raw_result.get("result_type") or "").strip()
    if result_type == "non_executable":
        return True
    return str(raw_result.get("reason") or "").strip() == "review_required_metadata_only"


def _parse_execution_status(
    value: ActionGroupExecutionStatus | str | None,
) -> ActionGroupExecutionStatus | None:
    if value is None:
        return None
    if isinstance(value, ActionGroupExecutionStatus):
        return value
    return ActionGroupExecutionStatus(str(value))


def _extract_strategy_context(
    remediation_artifacts: dict | None,
    raw_result: dict | None,
) -> tuple[str | None, dict[str, object]]:
    artifacts = remediation_artifacts if isinstance(remediation_artifacts, dict) else {}
    result = raw_result if isinstance(raw_result, dict) else {}
    selected_strategy = str(artifacts.get("selected_strategy") or result.get("strategy_id") or "").strip() or None
    strategy_inputs = artifacts.get("strategy_inputs")
    if not isinstance(strategy_inputs, dict):
        strategy_inputs = result.get("strategy_inputs")
    return selected_strategy, dict(strategy_inputs or {})


def _is_non_closing_success(
    *,
    selected_strategy: str | None,
    strategy_inputs: dict[str, object],
) -> tuple[bool, str | None]:
    if selected_strategy != "sg_restrict_public_ports_guided":
        return False, None
    access_mode = str(strategy_inputs.get("access_mode") or "").strip()
    if access_mode == "close_public":
        return True, SUCCESS_NEEDS_FOLLOWUP_KIND
    return False, None


def _successful_unconfirmed_bucket(
    *,
    remediation_artifacts: dict | None,
    raw_result: dict | None,
) -> ActionGroupStatusBucket:
    selected_strategy, strategy_inputs = _extract_strategy_context(remediation_artifacts, raw_result)
    is_non_closing, _ = _is_non_closing_success(
        selected_strategy=selected_strategy,
        strategy_inputs=strategy_inputs,
    )
    if is_non_closing:
        return ActionGroupStatusBucket.run_successful_needs_followup
    return ActionGroupStatusBucket.run_successful_pending_confirmation


def _load_latest_run_context(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    latest_run_id: uuid.UUID | None,
) -> tuple[ActionGroupExecutionStatus | None, str | None, dict | None, datetime | None, dict | None]:
    if latest_run_id is None:
        return None, None, None, None, None
    stmt = (
        select(
            ActionGroupRunResult.execution_status,
            ActionGroupRunResult.raw_result,
            ActionGroupRun.status.label("run_status"),
            ActionGroupRun.started_at.label("run_started_at"),
            RemediationRun.artifacts.label("remediation_artifacts"),
        )
        .select_from(ActionGroupRunResult)
        .join(
            ActionGroupRun,
            (ActionGroupRun.id == ActionGroupRunResult.group_run_id)
            & (ActionGroupRun.tenant_id == ActionGroupRunResult.tenant_id),
        )
        .outerjoin(RemediationRun, RemediationRun.id == ActionGroupRun.remediation_run_id)
        .where(
            ActionGroupRunResult.tenant_id == tenant_id,
            ActionGroupRunResult.action_id == action_id,
            ActionGroupRunResult.group_run_id == latest_run_id,
        )
    )
    row = session.execute(stmt).one_or_none()
    if row is None:
        return None, None, None, None, None
    return (
        _parse_execution_status(row.execution_status),
        row.run_status.value if hasattr(row.run_status, "value") else str(row.run_status),
        row.raw_result if isinstance(row.raw_result, dict) else None,
        _to_utc(row.run_started_at),
        row.remediation_artifacts if isinstance(row.remediation_artifacts, dict) else None,
    )


def derive_action_run_status(
    *,
    status_bucket: ActionGroupStatusBucket | str | None,
    latest_run_status: ActionGroupExecutionStatus | str | None,
    latest_run_finished_at: datetime | None,
    last_confirmed_at: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    bucket_value = (
        status_bucket.value
        if status_bucket is not None and hasattr(status_bucket, "value")
        else str(status_bucket or ActionGroupStatusBucket.not_run_yet.value)
    )
    run_status_value = (
        latest_run_status.value
        if latest_run_status is not None and hasattr(latest_run_status, "value")
        else str(latest_run_status or "")
    )
    finished_at = _to_utc(latest_run_finished_at)
    confirmed_at = _to_utc(last_confirmed_at)

    if (
        bucket_value != ActionGroupStatusBucket.run_successful_pending_confirmation.value
        or confirmed_at is not None
        or run_status_value not in {"finished", "success"}
        or finished_at is None
    ):
        base_state = {
            "pending_confirmation": False,
            "pending_confirmation_started_at": None,
            "pending_confirmation_deadline_at": None,
            "pending_confirmation_message": None,
            "pending_confirmation_severity": None,
            "status_message": None,
            "status_severity": None,
            "followup_kind": None,
        }
        if bucket_value == ActionGroupStatusBucket.run_successful_needs_followup.value:
            return {
                **base_state,
                "status_message": SUCCESS_NEEDS_FOLLOWUP_MESSAGE,
                "status_severity": "warning",
                "followup_kind": SUCCESS_NEEDS_FOLLOWUP_KIND,
            }
        return base_state

    current_time = _to_utc(now) or _utcnow()
    deadline_at = finished_at + PENDING_CONFIRMATION_WINDOW
    escalated = current_time >= deadline_at
    return {
        "pending_confirmation": True,
        "pending_confirmation_started_at": finished_at,
        "pending_confirmation_deadline_at": deadline_at,
        "pending_confirmation_message": (
            PENDING_CONFIRMATION_WARNING_MESSAGE if escalated else PENDING_CONFIRMATION_INFO_MESSAGE
        ),
        "pending_confirmation_severity": "warning" if escalated else "info",
        "status_message": PENDING_CONFIRMATION_WARNING_MESSAGE if escalated else PENDING_CONFIRMATION_INFO_MESSAGE,
        "status_severity": "warning" if escalated else "info",
        "followup_kind": "awaiting_aws_confirmation",
    }


def derive_pending_confirmation_state(
    *,
    status_bucket: ActionGroupStatusBucket | str | None,
    latest_run_status: ActionGroupExecutionStatus | str | None,
    latest_run_finished_at: datetime | None,
    last_confirmed_at: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    return derive_action_run_status(
        status_bucket=status_bucket,
        latest_run_status=latest_run_status,
        latest_run_finished_at=latest_run_finished_at,
        last_confirmed_at=last_confirmed_at,
        now=now,
    )


def _get_or_create_state(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    action_id: uuid.UUID,
) -> ActionGroupActionState:
    stmt = (
        select(ActionGroupActionState)
        .options(
            lazyload("*"),
            load_only(
                ActionGroupActionState.tenant_id,
                ActionGroupActionState.group_id,
                ActionGroupActionState.action_id,
                ActionGroupActionState.latest_run_status_bucket,
                ActionGroupActionState.latest_run_id,
                ActionGroupActionState.last_attempt_at,
                ActionGroupActionState.last_confirmed_at,
                ActionGroupActionState.last_confirmation_source,
            ),
        )
        .where(
            ActionGroupActionState.tenant_id == tenant_id,
            ActionGroupActionState.group_id == group_id,
            ActionGroupActionState.action_id == action_id,
        )
    )
    state = session.execute(stmt).scalar_one_or_none()
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
    membership = _get_membership(session, action_id=action_id)
    state = record_execution_attempt(
        session,
        action_id=action_id,
        latest_run_id=latest_run_id,
        attempted_at=attempted_at or finished_at,
    )
    if state is None or membership is None:
        return None

    # Execution success is distinct from AWS/source-of-truth confirmation.
    if parsed_status == ActionGroupExecutionStatus.success:
        _, _, raw_result, _, remediation_artifacts = _load_latest_run_context(
            session,
            tenant_id=membership.tenant_id,
            action_id=membership.action_id,
            latest_run_id=latest_run_id,
        )
        state.latest_run_status_bucket = _successful_unconfirmed_bucket(
            remediation_artifacts=remediation_artifacts,
            raw_result=raw_result,
        )
    else:
        state.latest_run_status_bucket = ActionGroupStatusBucket.run_not_successful
    logger.info(
        "action_run_confirmation result action_id=%s run_id=%s execution_status=%s bucket=%s",
        action_id,
        latest_run_id,
        parsed_status.value,
        state.latest_run_status_bucket.value,
    )
    return state


def record_non_executable_result(
    session: Session,
    *,
    action_id: uuid.UUID,
    latest_run_id: uuid.UUID | None,
    attempted_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ActionGroupActionState | None:
    membership = _get_membership(session, action_id=action_id)
    if membership is None:
        logger.debug("record_non_executable_result skipped: no membership action_id=%s", action_id)
        return None

    state = _get_or_create_state(
        session,
        tenant_id=membership.tenant_id,
        group_id=membership.group_id,
        action_id=membership.action_id,
    )
    state.latest_run_id = latest_run_id
    state.last_attempt_at = _to_utc(attempted_at) or _to_utc(finished_at) or _utcnow()
    state.latest_run_status_bucket = ActionGroupStatusBucket.run_finished_metadata_only
    logger.info(
        "action_run_confirmation metadata_only action_id=%s run_id=%s bucket=%s",
        action_id,
        latest_run_id,
        state.latest_run_status_bucket.value,
    )
    return state


def _find_confirmation_signal(
    findings: Iterable[object],
    *,
    since_run_started: datetime,
) -> tuple[bool, ActionGroupConfirmationSource | None, datetime | None]:
    since = _to_utc(since_run_started)
    if since is None:
        return False, None, None

    security_hub_confirmed_at: datetime | None = None
    control_plane_confirmed_at: datetime | None = None
    for finding in findings:
        status = getattr(finding, "status", None)
        last_observed_at = getattr(finding, "last_observed_at", None)
        updated_at = getattr(finding, "updated_at", None)
        shadow_status_normalized = getattr(finding, "shadow_status_normalized", None)
        shadow_last_observed_event_time = getattr(finding, "shadow_last_observed_event_time", None)
        shadow_last_evaluated_at = getattr(finding, "shadow_last_evaluated_at", None)

        sh_time = _max_ts(last_observed_at, updated_at)
        if status == "RESOLVED" and sh_time is not None and sh_time >= since:
            security_hub_confirmed_at = sh_time if security_hub_confirmed_at is None else max(security_hub_confirmed_at, sh_time)

        cp_time = _max_ts(
            shadow_last_observed_event_time,
            shadow_last_evaluated_at,
        )
        if shadow_status_normalized == "RESOLVED" and cp_time is not None and cp_time >= since:
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
    execution_status: ActionGroupExecutionStatus | str | None = None,
    latest_run_status: str | None = None,
    raw_result: dict | None = None,
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
    (
        persisted_execution_status,
        persisted_run_status,
        persisted_raw_result,
        persisted_started_at,
        remediation_artifacts,
    ) = _load_latest_run_context(
        session,
        tenant_id=membership.tenant_id,
        action_id=membership.action_id,
        latest_run_id=state.latest_run_id,
    )
    parsed_execution_status = _parse_execution_status(execution_status) or persisted_execution_status
    run_status_value = (latest_run_status or persisted_run_status or "").strip().lower()
    effective_raw_result = raw_result if isinstance(raw_result, dict) else persisted_raw_result
    threshold = _to_utc(since_run_started) or persisted_started_at or _to_utc(state.last_attempt_at)
    if threshold is None:
        state.latest_run_status_bucket = ActionGroupStatusBucket.not_run_yet
        return {"action_id": str(action_id), "confirmed": False, "reason": "no_attempt"}

    findings_stmt = (
        select(
            Finding.status,
            Finding.last_observed_at,
            Finding.updated_at,
            Finding.shadow_status_normalized,
            Finding.shadow_last_observed_event_time,
            Finding.shadow_last_evaluated_at,
        )
        .join(ActionFinding, ActionFinding.finding_id == Finding.id)
        .where(ActionFinding.action_id == action_id, Finding.tenant_id == membership.tenant_id)
    )
    findings = [
        type(
            "FindingSignalRow",
            (),
            {
                "status": row.status,
                "last_observed_at": row.last_observed_at,
                "updated_at": row.updated_at,
                "shadow_status_normalized": row.shadow_status_normalized,
                "shadow_last_observed_event_time": row.shadow_last_observed_event_time,
                "shadow_last_evaluated_at": row.shadow_last_evaluated_at,
            },
        )()
        for row in session.execute(findings_stmt).all()
    ]
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
        if (
            run_status_value == "finished"
            and _is_non_executable_status(parsed_execution_status.value if parsed_execution_status else None)
            and _is_metadata_only_result(effective_raw_result)
        ) or state.latest_run_status_bucket == ActionGroupStatusBucket.run_finished_metadata_only:
            state.latest_run_status_bucket = ActionGroupStatusBucket.run_finished_metadata_only
        if (
            state.latest_run_status_bucket != ActionGroupStatusBucket.run_finished_metadata_only
            and (
                parsed_execution_status == ActionGroupExecutionStatus.success
                or state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_pending_confirmation
                or state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_needs_followup
            )
        ):
            state.latest_run_status_bucket = _successful_unconfirmed_bucket(
                remediation_artifacts=remediation_artifacts,
                raw_result=effective_raw_result,
            )
        elif state.latest_run_status_bucket != ActionGroupStatusBucket.run_finished_metadata_only:
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
    execution_status: ActionGroupExecutionStatus | str | None = None,
    latest_run_status: str | None = None,
    raw_result: dict | None = None,
) -> dict[str, object]:
    def _run(sync_session: Session) -> dict[str, object]:
        return evaluate_confirmation_for_action(
            sync_session,
            action_id=action_id,
            since_run_started=since_run_started,
            execution_status=execution_status,
            latest_run_status=latest_run_status,
            raw_result=raw_result,
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


async def record_non_executable_result_async(
    db: AsyncSession,
    *,
    action_id: uuid.UUID,
    latest_run_id: uuid.UUID | None,
    attempted_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    def _run(sync_session: Session) -> None:
        record_non_executable_result(
            sync_session,
            action_id=action_id,
            latest_run_id=latest_run_id,
            attempted_at=attempted_at,
            finished_at=finished_at,
        )

    await db.run_sync(_run)
