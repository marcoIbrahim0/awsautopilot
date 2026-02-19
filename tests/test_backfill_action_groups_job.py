from __future__ import annotations

import uuid

from backend.models.enums import ActionGroupRunStatus, RemediationRunStatus
from backend.workers.jobs.backfill_action_groups import _map_legacy_run_status, _parse_group_action_ids


def test_parse_group_action_ids_dedup_and_invalid_entries() -> None:
    valid_id = uuid.uuid4()
    parsed = _parse_group_action_ids(
        {
            "group_bundle": {
                "action_ids": [str(valid_id), "not-a-uuid", str(valid_id), 123],
            }
        }
    )
    assert parsed == [valid_id]


def test_map_legacy_run_status_values() -> None:
    assert _map_legacy_run_status(RemediationRunStatus.pending) == ActionGroupRunStatus.queued
    assert _map_legacy_run_status(RemediationRunStatus.running) == ActionGroupRunStatus.started
    assert _map_legacy_run_status(RemediationRunStatus.awaiting_approval) == ActionGroupRunStatus.started
    assert _map_legacy_run_status(RemediationRunStatus.success) == ActionGroupRunStatus.finished
    assert _map_legacy_run_status(RemediationRunStatus.failed) == ActionGroupRunStatus.failed
    assert _map_legacy_run_status(RemediationRunStatus.cancelled) == ActionGroupRunStatus.cancelled
