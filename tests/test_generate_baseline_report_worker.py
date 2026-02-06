"""
Unit tests for generate_baseline_report worker (Step 13.2).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.models.enums import BaselineReportStatus
from backend.utils.sqs import (
    GENERATE_BASELINE_REPORT_JOB_TYPE,
    build_generate_baseline_report_job_payload,
)
from worker.jobs.generate_baseline_report import execute_generate_baseline_report_job


def test_build_generate_baseline_report_job_payload() -> None:
    """build_generate_baseline_report_job_payload returns correct shape."""
    report_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    created_at = "2026-02-03T12:00:00Z"
    payload = build_generate_baseline_report_job_payload(
        report_id=report_id,
        tenant_id=tenant_id,
        created_at=created_at,
    )
    assert payload["job_type"] == GENERATE_BASELINE_REPORT_JOB_TYPE
    assert payload["report_id"] == str(report_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["created_at"] == created_at
    assert "account_ids" not in payload


def test_build_generate_baseline_report_job_payload_with_account_ids() -> None:
    """build_generate_baseline_report_job_payload includes account_ids when provided."""
    report_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    created_at = "2026-02-03T12:00:00Z"
    payload = build_generate_baseline_report_job_payload(
        report_id=report_id,
        tenant_id=tenant_id,
        created_at=created_at,
        account_ids=["123456789012", "111111111111"],
    )
    assert payload["account_ids"] == ["123456789012", "111111111111"]


def test_execute_generate_baseline_report_job_idempotent_skip_when_success() -> None:
    """execute_generate_baseline_report_job skips when report is already success."""
    job = {
        "job_type": GENERATE_BASELINE_REPORT_JOB_TYPE,
        "report_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    report = MagicMock()
    report.id = uuid.UUID(job["report_id"])
    report.tenant_id = uuid.UUID(job["tenant_id"])
    report.status = BaselineReportStatus.success
    report.outcome = None

    result = MagicMock()
    result.scalar_one_or_none.return_value = report
    mock_session = MagicMock()
    mock_session.execute.return_value = result
    mock_session.flush = MagicMock()

    with patch("worker.jobs.generate_baseline_report.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        execute_generate_baseline_report_job(job)

    # Idempotent skip: handler returns without calling generate_baseline_report.
    # When status is already success, handler does not call flush after the skip branch.
    assert report.status == BaselineReportStatus.success


def test_execute_generate_baseline_report_job_sets_failed_when_service_raises() -> None:
    """execute_generate_baseline_report_job sets status=failed and outcome when service raises."""
    job = {
        "job_type": GENERATE_BASELINE_REPORT_JOB_TYPE,
        "report_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    report = MagicMock()
    report.id = uuid.UUID(job["report_id"])
    report.tenant_id = uuid.UUID(job["tenant_id"])
    report.status = BaselineReportStatus.pending
    report.outcome = None
    report.s3_bucket = None
    report.s3_key = None
    report.file_size_bytes = None
    report.completed_at = None

    result = MagicMock()
    result.scalar_one_or_none.return_value = report
    mock_session = MagicMock()
    mock_session.execute.return_value = result
    mock_session.flush = MagicMock()

    with patch("worker.jobs.generate_baseline_report.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch(
            "worker.jobs.generate_baseline_report.generate_baseline_report"
        ) as mock_gen:
            mock_gen.side_effect = RuntimeError("S3 upload failed")

            execute_generate_baseline_report_job(job)

    assert report.status == BaselineReportStatus.failed
    assert report.outcome == "S3 upload failed"
    assert report.completed_at is not None


def test_execute_generate_baseline_report_job_raises_when_missing_report_id() -> None:
    """execute_generate_baseline_report_job raises when job missing report_id."""
    job = {
        "job_type": GENERATE_BASELINE_REPORT_JOB_TYPE,
        "tenant_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with pytest.raises(ValueError, match="report_id"):
        execute_generate_baseline_report_job(job)
