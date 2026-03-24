from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from backend.models.enums import RemediationRunMode, RemediationRunStatus
from backend.services.remediation_run_retirement import stale_active_run_reason
from backend.services.remediation_run_queue_contract import (
    grouped_run_signatures_match,
    normalize_grouped_run_artifact_signature,
)


@dataclass(frozen=True, slots=True)
class GroupedBundleRunRecord:
    run_id: str
    action_id: str
    mode: str | None
    status: str | None
    created_at: datetime | None
    artifacts: Mapping[str, Any] | None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    group_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class GroupedBundleConflict:
    reason: str
    detail: str
    run_id: str
    run_status: str | None
    group_run_id: str | None = None


def _is_pr_only(record: GroupedBundleRunRecord) -> bool:
    return record.mode == RemediationRunMode.pr_only.value


def _is_active(record: GroupedBundleRunRecord) -> bool:
    return record.status in {
        RemediationRunStatus.pending.value,
        RemediationRunStatus.running.value,
        RemediationRunStatus.awaiting_approval.value,
    }


def _is_success(record: GroupedBundleRunRecord) -> bool:
    return record.status == RemediationRunStatus.success.value


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _matches_signature(record: GroupedBundleRunRecord, request_signature: Mapping[str, Any]) -> bool:
    if not _is_pr_only(record):
        return False
    existing_signature = normalize_grouped_run_artifact_signature(record.artifacts)
    return grouped_run_signatures_match(existing_signature, request_signature)


def filter_active_group_duplicate_runs(
    records: Sequence[GroupedBundleRunRecord],
    *,
    now: datetime,
) -> list[GroupedBundleRunRecord]:
    return [record for record in records if _is_active(record) and stale_active_run_reason(record, now=now) is None]


def find_active_grouped_duplicate(
    records: Sequence[GroupedBundleRunRecord],
    *,
    request_signature: Mapping[str, Any],
    now: datetime,
) -> GroupedBundleConflict | None:
    for record in filter_active_group_duplicate_runs(records, now=now):
        if _matches_signature(record, request_signature):
            return GroupedBundleConflict(
                reason="duplicate_pending_group_run",
                detail="A pending group PR bundle run already exists for this execution group.",
                run_id=record.run_id,
                run_status=record.status,
                group_run_id=record.group_run_id,
            )
    return None


def find_latest_successful_grouped_duplicate(
    records: Sequence[GroupedBundleRunRecord],
    *,
    request_signature: Mapping[str, Any],
) -> GroupedBundleConflict | None:
    successful = [record for record in records if _is_success(record) and _matches_signature(record, request_signature)]
    if not successful:
        return None
    latest = max(successful, key=lambda record: (_as_utc(record.created_at) or datetime.min.replace(tzinfo=timezone.utc)))
    return GroupedBundleConflict(
        reason="grouped_bundle_already_created_no_changes",
        detail=(
            "A PR bundle was already created successfully for this exact group. "
            "No changes were made since the previous bundle generation."
        ),
        run_id=latest.run_id,
        run_status=latest.status,
        group_run_id=latest.group_run_id,
    )
