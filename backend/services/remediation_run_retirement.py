from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from backend.models.enums import RemediationRunMode, RemediationRunStatus

STALE_PENDING_RUN_MINUTES = 10
STALE_RUNNING_PR_ONLY_MINUTES = 90
STALE_RUNNING_DIRECT_FIX_MINUTES = 360
STALE_RUN_OUTCOME = "stale_active_run_retired"
STALE_RUN_ARTIFACT_KEY = "auto_retired_stale_run"


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reference_time(run: Any) -> datetime | None:
    for name in ("updated_at", "started_at", "created_at"):
        value = _as_utc(getattr(run, name, None))
        if value is not None:
            return value
    return None


def _running_stale_after(run: Any) -> timedelta:
    mode = _enum_value(getattr(run, "mode", None))
    minutes = STALE_RUNNING_PR_ONLY_MINUTES
    if mode == RemediationRunMode.direct_fix.value:
        minutes = STALE_RUNNING_DIRECT_FIX_MINUTES
    return timedelta(minutes=minutes)


def stale_active_run_reason(run: Any, *, now: datetime) -> str | None:
    status = _enum_value(getattr(run, "status", None))
    reference = _reference_time(run)
    if reference is None:
        return None
    if status == RemediationRunStatus.pending.value:
        if (now - reference) >= timedelta(minutes=STALE_PENDING_RUN_MINUTES):
            return "stale_pending_no_progress"
        return None
    if status == RemediationRunStatus.running.value:
        if (now - reference) >= _running_stale_after(run):
            return "stale_running_no_progress"
    return None


def _retirement_artifact(run: Any, *, reason: str, now: datetime) -> dict[str, str]:
    return {
        "retired_at": now.isoformat(),
        "reason": reason,
        "previous_status": _enum_value(getattr(run, "status", None)) or "",
    }


def retire_stale_active_runs(runs: Iterable[Any], *, now: datetime) -> list[Any]:
    retired: list[Any] = []
    for run in runs:
        reason = stale_active_run_reason(run, now=now)
        if reason is None:
            continue
        artifacts = getattr(run, "artifacts", None)
        artifact_map = dict(artifacts) if isinstance(artifacts, dict) else {}
        artifact_map[STALE_RUN_ARTIFACT_KEY] = _retirement_artifact(run, reason=reason, now=now)
        run.artifacts = artifact_map
        run.status = RemediationRunStatus.failed
        run.outcome = STALE_RUN_OUTCOME
        if getattr(run, "completed_at", None) is None:
            run.completed_at = now
        retired.append(run)
    return retired
