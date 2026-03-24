#!/usr/bin/env python3
"""Reproject action_group_action_state for a tenant/account/action-type scope."""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from backend.models.action import Action
from backend.models.action_group_action_state import ActionGroupActionState
from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.action_group_run_result import ActionGroupRunResult
from backend.models.enums import ActionGroupExecutionStatus, ActionGroupRunStatus, ActionGroupStatusBucket
from backend.services.action_run_confirmation import evaluate_confirmation_for_action
from backend.workers.database import session_scope


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reproject grouped action state for one tenant/account/action-type scope")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--account-id", required=True, help="AWS account ID (12 digits)")
    parser.add_argument("--action-type", action="append", required=True, help="Action type to reproject; repeatable")
    parser.add_argument(
        "--repair-stuck-runs",
        action="store_true",
        help="Repair started group runs that already have terminal-looking per-action result rows before reprojecting state.",
    )
    return parser.parse_args()


def _latest_result_map(session, tenant_id: uuid.UUID, group_id: uuid.UUID) -> dict[uuid.UUID, ActionGroupRunResult]:
    run_rows = (
        session.execute(
            select(ActionGroupRun)
            .where(
                ActionGroupRun.tenant_id == tenant_id,
                ActionGroupRun.group_id == group_id,
            )
            .order_by(ActionGroupRun.created_at.desc(), ActionGroupRun.id.desc())
        )
    ).scalars().all()
    result_by_action: dict[uuid.UUID, ActionGroupRunResult] = {}
    for run in run_rows:
        results = (
            session.execute(
                select(ActionGroupRunResult)
                .where(
                    ActionGroupRunResult.tenant_id == tenant_id,
                    ActionGroupRunResult.group_run_id == run.id,
                )
            )
        ).scalars().all()
        for result in results:
            result_by_action.setdefault(result.action_id, result)
    return result_by_action


def _derive_terminal_status(results: list[ActionGroupRunResult]) -> ActionGroupRunStatus:
    statuses = {result.execution_status for result in results}
    if ActionGroupExecutionStatus.failed in statuses:
        return ActionGroupRunStatus.failed
    if ActionGroupExecutionStatus.cancelled in statuses:
        return ActionGroupRunStatus.cancelled
    return ActionGroupRunStatus.finished


def _repair_stuck_group_runs(session, tenant_id: uuid.UUID, group_ids: set[uuid.UUID]) -> list[dict[str, str]]:
    repaired: list[dict[str, str]] = []
    for group_id in sorted(group_ids, key=str):
        membership_action_ids = {
            action_id
            for action_id in session.execute(
                select(ActionGroupMembership.action_id).where(
                    ActionGroupMembership.tenant_id == tenant_id,
                    ActionGroupMembership.group_id == group_id,
                )
            ).scalars().all()
        }
        run_rows = (
            session.execute(
                select(ActionGroupRun)
                .where(
                    ActionGroupRun.tenant_id == tenant_id,
                    ActionGroupRun.group_id == group_id,
                    ActionGroupRun.status == ActionGroupRunStatus.started,
                    ActionGroupRun.finished_at.is_(None),
                )
                .order_by(ActionGroupRun.created_at.desc(), ActionGroupRun.id.desc())
            )
        ).scalars().all()
        for run in run_rows:
            results = (
                session.execute(
                    select(ActionGroupRunResult).where(
                        ActionGroupRunResult.tenant_id == tenant_id,
                        ActionGroupRunResult.group_run_id == run.id,
                    )
                )
            ).scalars().all()
            if not results:
                continue
            result_action_ids = {result.action_id for result in results}
            if result_action_ids != membership_action_ids:
                continue
            terminal_status = _derive_terminal_status(results)
            finished_candidates = [result.execution_finished_at for result in results if result.execution_finished_at is not None]
            started_candidates = [result.execution_started_at for result in results if result.execution_started_at is not None]
            run.status = terminal_status
            run.started_at = run.started_at or min(started_candidates or finished_candidates or [datetime.now(timezone.utc)])
            run.finished_at = max(finished_candidates or [datetime.now(timezone.utc)])
            repaired.append(
                {
                    "group_id": str(group_id),
                    "group_run_id": str(run.id),
                    "status": run.status.value,
                }
            )
    return repaired


def main() -> int:
    args = _parse_args()
    tenant_id = uuid.UUID(args.tenant_id)
    action_types = sorted({item.strip() for item in args.action_type if item and item.strip()})
    summary: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "account_id": args.account_id,
        "action_types": action_types,
        "repaired_runs": [],
        "updated": [],
    }

    with session_scope() as session:
        memberships = (
            session.execute(
                select(ActionGroupMembership, Action)
                .join(Action, Action.id == ActionGroupMembership.action_id)
                .where(
                    ActionGroupMembership.tenant_id == tenant_id,
                    Action.tenant_id == tenant_id,
                    Action.account_id == args.account_id,
                    Action.action_type.in_(action_types),
                )
            )
        ).all()
        group_ids = {membership.group_id for membership, _ in memberships}
        if args.repair_stuck_runs:
            summary["repaired_runs"] = _repair_stuck_group_runs(session, tenant_id, group_ids)

        result_cache: dict[uuid.UUID, dict[uuid.UUID, ActionGroupRunResult]] = {}
        for membership, action in memberships:
            result_by_action = result_cache.setdefault(
                membership.group_id,
                _latest_result_map(session, tenant_id, membership.group_id),
            )
            latest_result = result_by_action.get(membership.action_id)
            state = (
                session.query(ActionGroupActionState)
                .filter(
                    ActionGroupActionState.tenant_id == tenant_id,
                    ActionGroupActionState.group_id == membership.group_id,
                    ActionGroupActionState.action_id == membership.action_id,
                )
                .one_or_none()
            )
            if state is None:
                state = ActionGroupActionState(
                    tenant_id=tenant_id,
                    group_id=membership.group_id,
                    action_id=membership.action_id,
                    latest_run_status_bucket=ActionGroupStatusBucket.not_run_yet,
                )
                session.add(state)

            if latest_result is None:
                state.latest_run_id = None
                state.last_attempt_at = None
                state.latest_run_status_bucket = ActionGroupStatusBucket.not_run_yet
            else:
                state.latest_run_id = latest_result.group_run_id
                state.last_attempt_at = latest_result.execution_started_at or latest_result.execution_finished_at
                if (
                    latest_result.execution_status == ActionGroupExecutionStatus.unknown
                    and isinstance(latest_result.raw_result, dict)
                    and str(latest_result.raw_result.get("result_type") or "") == "non_executable"
                ):
                    state.latest_run_status_bucket = ActionGroupStatusBucket.run_finished_metadata_only
                elif latest_result.execution_status == ActionGroupExecutionStatus.success:
                    state.latest_run_status_bucket = ActionGroupStatusBucket.run_successful_pending_confirmation
                else:
                    state.latest_run_status_bucket = ActionGroupStatusBucket.run_not_successful

                latest_run = (
                    session.execute(
                        select(ActionGroupRun).where(
                            ActionGroupRun.tenant_id == tenant_id,
                            ActionGroupRun.id == latest_result.group_run_id,
                        )
                    )
                ).scalar_one_or_none()
                evaluate_confirmation_for_action(
                    session,
                    action_id=membership.action_id,
                    since_run_started=state.last_attempt_at,
                    execution_status=latest_result.execution_status,
                    latest_run_status=(
                        latest_run.status.value if latest_run is not None and hasattr(latest_run.status, "value") else None
                    ),
                    raw_result=latest_result.raw_result if isinstance(latest_result.raw_result, dict) else None,
                )

            summary["updated"].append(
                {
                    "action_id": str(membership.action_id),
                    "group_id": str(membership.group_id),
                    "action_type": action.action_type,
                    "bucket": state.latest_run_status_bucket.value,
                }
            )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
