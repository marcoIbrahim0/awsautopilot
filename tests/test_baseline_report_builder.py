"""
Unit tests for baseline report builder.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.models.enums import RemediationRunStatus
from backend.services.baseline_report_builder import build_baseline_report_data


def _finding_result(findings: list[MagicMock]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = findings
    return result


def _rows_result(rows: list[tuple[uuid.UUID, uuid.UUID]]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


def _scalars_result(rows: list[MagicMock]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def test_build_baseline_report_data_empty_findings() -> None:
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    session.execute.return_value = _finding_result([])

    data = build_baseline_report_data(
        session=session,
        tenant_id=tenant_id,
        account_ids=None,
        tenant_name="Acme",
        current_report_requested_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
    )
    assert data.summary.total_finding_count == 0
    assert data.summary.open_count == 0
    assert data.top_risks == []
    assert data.next_actions == []
    assert data.confidence_gaps == []
    assert data.closure_proof == []
    assert data.tenant_name == "Acme"


def test_build_baseline_report_data_with_actions_and_delta() -> None:
    session = MagicMock()
    tenant_id = str(uuid.uuid4())

    f1 = MagicMock()
    f1.id = uuid.uuid4()
    f1.title = "S3 public access"
    f1.severity_label = "CRITICAL"
    f1.severity_normalized = 100
    f1.account_id = "123456789012"
    f1.region = "us-east-1"
    f1.status = "NEW"
    f1.resource_id = "arn:aws:s3:::bucket-a"
    f1.control_id = "S3.1"
    f1.raw_json = {"status_branch": "access_denied"}
    f1.finding_id = "finding-1"
    f1.created_at = datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc)
    f1.first_observed_at = datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc)
    f1.updated_at = datetime(2026, 3, 1, 11, 5, 0, tzinfo=timezone.utc)
    f1.resolved_at = None
    f1.shadow_status_reason = "inventory_access_denied_s3_get_bucket_public_posture"
    f1.shadow_status_normalized = "OPEN"

    f2 = MagicMock()
    f2.id = uuid.uuid4()
    f2.title = "GuardDuty disabled"
    f2.severity_label = "HIGH"
    f2.severity_normalized = 75
    f2.account_id = "123456789012"
    f2.region = "us-west-2"
    f2.status = "RESOLVED"
    f2.resource_id = None
    f2.control_id = "GuardDuty.1"
    f2.raw_json = {"status_branch": "ok"}
    f2.finding_id = "finding-2"
    f2.created_at = datetime(2026, 2, 27, 9, 0, 0, tzinfo=timezone.utc)
    f2.first_observed_at = datetime(2026, 2, 27, 9, 0, 0, tzinfo=timezone.utc)
    f2.updated_at = datetime(2026, 3, 2, 8, 0, 0, tzinfo=timezone.utc)
    f2.resolved_at = datetime(2026, 3, 2, 8, 0, 0, tzinfo=timezone.utc)
    f2.shadow_status_reason = "inventory_confirmed_compliant"
    f2.shadow_status_normalized = "RESOLVED"

    action = MagicMock()
    action.id = uuid.uuid4()
    action.action_type = "s3_bucket_block_public_access"
    action.status = "open"
    action.priority = 88
    action.title = "Restrict S3 bucket public access"
    action.control_id = "S3.1"
    action.target_id = "bucket-a"
    action.account_id = "123456789012"
    action.region = "us-east-1"

    run = MagicMock()
    run.id = uuid.uuid4()
    run.action_id = action.id
    run.status = RemediationRunStatus.failed
    run.completed_at = datetime(2026, 3, 2, 7, 45, 0, tzinfo=timezone.utc)
    run.created_at = datetime(2026, 3, 2, 7, 45, 0, tzinfo=timezone.utc)

    session.execute.side_effect = [
        _finding_result([f1, f2]),
        _rows_result([(action.id, f1.id), (action.id, f2.id)]),
        _scalars_result([action]),
        _scalars_result([run]),
        _scalars_result([]),
    ]

    data = build_baseline_report_data(
        session=session,
        tenant_id=tenant_id,
        account_ids=None,
        tenant_name="Acme",
        current_report_requested_at=datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc),
        previous_report_requested_at=datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert data.summary.total_finding_count == 2
    assert data.summary.critical_count == 1
    assert data.summary.high_count == 1
    assert len(data.top_risks) == 2
    assert data.top_risks[0].title == "S3 public access"
    assert data.top_risks[0].business_impact is not None
    assert data.top_risks[0].action_id == str(action.id)
    assert data.next_actions
    assert data.next_actions[0].readiness in {"needs_attention", "ready", "in_progress", "blocked_by_exception"}
    assert data.change_delta is not None
    assert data.change_delta.compared_to_report_at is not None
    assert data.change_delta.new_open_count >= 0
    assert data.change_delta.closed_count >= 0
    assert data.confidence_gaps
    assert any(gap.category == "access_denied" for gap in data.confidence_gaps)
    assert data.closure_proof
    assert data.recommendations

