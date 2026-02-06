"""
Unit tests for worker/jobs/remediation_run.py direct_fix path (Step 8.3).

Tests cover:
- direct_fix with WriteRole: assume_role + run_direct_fix called, run updated
- direct_fix without WriteRole: run failed with clear message
- direct_fix with assume_role failure: run failed
- direct_fix with executor success/failure
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.models.enums import RemediationRunStatus
from worker.jobs.remediation_run import execute_remediation_run_job
from worker.services.direct_fix import DirectFixResult


def _make_job(mode: str = "direct_fix") -> dict:
    return {
        "job_type": "remediation_run",
        "run_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_run_with_action(action_type: str = "s3_block_public_access") -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = uuid.uuid4()
    run.status = RemediationRunStatus.pending
    run.action_id = uuid.uuid4()
    run.outcome = None
    run.logs = None
    run.artifacts = None
    run.completed_at = None
    run.started_at = None

    action = MagicMock()
    action.id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = None if action_type == "s3_block_public_access" else "us-east-1"

    run.action = action
    return run


def _mock_account(role_write_arn: str | None = "arn:aws:iam::123456789012:role/WriteRole") -> MagicMock:
    acc = MagicMock()
    acc.role_write_arn = role_write_arn
    acc.external_id = "ext-tenant-123"
    acc.account_id = "123456789012"
    return acc


def test_direct_fix_success() -> None:
    """direct_fix: WriteRole present, assume + executor succeed, run updated to success."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action("s3_block_public_access")
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    fix_result = DirectFixResult(
        success=True,
        outcome="S3 Block Public Access enabled at account level",
        logs=["Pre-check", "Apply", "Post-check"],
    )

    with patch("worker.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.remediation_run.assume_role") as mock_assume:
            mock_assume.return_value = MagicMock()

            with patch("worker.jobs.remediation_run.run_direct_fix", return_value=fix_result):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "S3 Block Public Access enabled at account level"
    assert "Assuming WriteRole" in (run.logs or "")
    mock_assume.assert_called_once_with(
        role_arn=account.role_write_arn,
        external_id=account.external_id,
    )


def test_direct_fix_no_write_role() -> None:
    """direct_fix: role_write_arn is None -> run failed with clear message."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    account = _mock_account(role_write_arn=None)

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    with patch("worker.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.remediation_run.assume_role") as mock_assume:
            execute_remediation_run_job(job)
            mock_assume.assert_not_called()

    assert run.status == RemediationRunStatus.failed
    assert "WriteRole not configured" in (run.outcome or "")


def test_direct_fix_assume_role_fails() -> None:
    """direct_fix: assume_role raises ClientError -> run failed."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    account = _mock_account()

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    with patch("worker.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.remediation_run.assume_role") as mock_assume:
            mock_assume.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Not allowed"}},
                "AssumeRole",
            )

            with patch("worker.jobs.remediation_run.run_direct_fix") as mock_fix:
                execute_remediation_run_job(job)
                mock_fix.assert_not_called()

    assert run.status == RemediationRunStatus.failed
    assert "Failed to assume WriteRole" in (run.outcome or "")


def test_direct_fix_executor_fails() -> None:
    """direct_fix: run_direct_fix returns success=False -> run failed."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    account = _mock_account()

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    fix_result = DirectFixResult(
        success=False,
        outcome="Apply failed: AccessDenied",
        logs=["Pre-check", "Apply failed"],
    )

    with patch("worker.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.remediation_run.assume_role", return_value=MagicMock()):
            with patch("worker.jobs.remediation_run.run_direct_fix", return_value=fix_result):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.failed
    assert run.outcome == "Apply failed: AccessDenied"


def test_direct_fix_already_compliant() -> None:
    """direct_fix: executor returns success with 'Already compliant' -> run success, no artifacts key."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    account = _mock_account()

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    fix_result = DirectFixResult(
        success=True,
        outcome="Already compliant; no change needed",
        logs=["Pre-check", "Already compliant"],
    )

    with patch("worker.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.remediation_run.assume_role", return_value=MagicMock()):
            with patch("worker.jobs.remediation_run.run_direct_fix", return_value=fix_result):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "Already compliant; no change needed"
    # direct_fix artifact only added when outcome != "Already compliant"
    assert run.artifacts is None or "direct_fix" not in (run.artifacts or {})


def test_direct_fix_account_not_found() -> None:
    """direct_fix: AWS account not found -> run failed."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None  # No account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    with patch("worker.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.remediation_run.assume_role") as mock_assume:
            execute_remediation_run_job(job)
            mock_assume.assert_not_called()

    assert run.status == RemediationRunStatus.failed
    assert "AWS account not found" in (run.outcome or "")
