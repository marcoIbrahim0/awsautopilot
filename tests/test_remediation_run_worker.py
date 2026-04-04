"""
Unit tests for worker/jobs/remediation_run.py direct_fix path (Step 8.3).

Tests cover:
- direct_fix with WriteRole: assume_role + run_direct_fix called, run updated
- direct_fix without WriteRole: run failed with clear message
- direct_fix with assume_role failure: run failed
- direct_fix with executor success/failure
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.models.enums import (
    ActionGroupExecutionStatus,
    ActionGroupRunStatus,
    RemediationRunExecutionPhase,
    RemediationRunExecutionStatus,
    RemediationRunMode,
    RemediationRunStatus,
)
from backend.services.direct_fix_approval import (
    DIRECT_FIX_APPROVAL_ARTIFACT_KEY,
    build_direct_fix_approval_metadata,
)
from backend.services.pr_bundle import PRBundleGenerationError
from backend.services.root_credentials_workflow import (
    MANUAL_HIGH_RISK_MARKER,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
)
from backend.workers.jobs import remediation_run
from backend.workers.jobs.remediation_run import (
    _build_reporting_replay_script as build_reporting_replay_script,
    _build_reporting_wrapper_script as build_reporting_wrapper_script,
    _sync_download_bundle_group_runs as sync_download_bundle_group_runs,
    execute_remediation_run_job,
)
from backend.workers.jobs.remediation_run_execution import (
    _sync_group_run_results,
    execute_pr_bundle_execution_job,
)
from backend.workers.services.direct_fix import DirectFixResult


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
    run.approved_by_user_id = None
    run.completed_at = None
    run.started_at = None

    action = MagicMock()
    action.id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = None if action_type == "s3_block_public_access" else "us-east-1"
    action.title = "Test action"
    action.control_id = "TEST.1"
    action.target_id = "test-target"
    action.resource_id = None

    run.action = action
    return run


def _grant_direct_fix_approval(run: MagicMock) -> None:
    approver_id = uuid.uuid4()
    run.mode = RemediationRunMode.direct_fix
    run.approved_by_user_id = approver_id
    run.artifacts = {
        DIRECT_FIX_APPROVAL_ARTIFACT_KEY: build_direct_fix_approval_metadata(
            approved_by_user_id=approver_id,
        )
    }


def _mock_account(role_write_arn: str | None = "arn:aws:iam::123456789012:role/WriteRole") -> MagicMock:
    acc = MagicMock()
    acc.role_write_arn = role_write_arn
    acc.external_id = "ext-tenant-123"
    acc.account_id = "123456789012"
    return acc


def _mock_group_action(
    *,
    action_type: str = "s3_bucket_block_public_access",
    target_id: str,
    title: str,
    control_id: str = "S3.2",
) -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = "us-east-1"
    action.title = title
    action.control_id = control_id
    action.target_id = target_id
    action.resource_id = target_id
    return action


def _mock_group_session(run: MagicMock, grouped_actions: list[MagicMock]) -> MagicMock:
    result_run = MagicMock()
    result_run.scalar_one_or_none.return_value = run
    result_actions = MagicMock()
    result_actions.scalars.return_value.all.return_value = grouped_actions
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result_run, result_actions]
    mock_session.flush = MagicMock()
    return mock_session


def _group_action_resolution_payload(
    *,
    action_id: uuid.UUID,
    strategy_id: str,
    strategy_inputs: dict | None = None,
    support_tier: str = "deterministic_bundle",
    profile_id: str | None = None,
    finding_coverage: dict | None = None,
    decision_rationale: str = "",
    missing_inputs: list[str] | None = None,
    missing_defaults: list[str] | None = None,
    blocked_reasons: list[str] | None = None,
    preservation_summary: dict | None = None,
) -> dict:
    inputs = dict(strategy_inputs or {})
    resolved_profile_id = profile_id or strategy_id
    return {
        "action_id": str(action_id),
        "strategy_id": strategy_id,
        "profile_id": resolved_profile_id,
        "strategy_inputs": inputs,
        "resolution": {
            "strategy_id": strategy_id,
            "profile_id": resolved_profile_id,
            "support_tier": support_tier,
            "resolved_inputs": dict(inputs),
            "missing_inputs": list(missing_inputs or []),
            "missing_defaults": list(missing_defaults or []),
            "blocked_reasons": list(blocked_reasons or []),
            "rejected_profiles": [],
            "finding_coverage": dict(finding_coverage or {}),
            "preservation_summary": dict(preservation_summary or {}),
            "decision_rationale": decision_rationale,
            "decision_version": "resolver/v1",
        },
    }


def _bundle_files_by_path(run: MagicMock) -> dict[str, str]:
    assert isinstance(run.artifacts, dict)
    pr_bundle = run.artifacts.get("pr_bundle")
    assert isinstance(pr_bundle, dict)
    files = pr_bundle.get("files")
    assert isinstance(files, list)
    result: dict[str, str] = {}
    for file_item in files:
        if not isinstance(file_item, dict):
            continue
        path = file_item.get("path")
        if not isinstance(path, str):
            continue
        result[path] = str(file_item.get("content") or "")
    return result


def _mock_execution_session(
    execution: MagicMock,
    *,
    account: MagicMock | None = None,
    grouped_actions: list[MagicMock] | None = None,
    claim_rowcount: int = 1,
) -> MagicMock:
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    claim_result = MagicMock()
    claim_result.rowcount = claim_rowcount
    side_effects: list[MagicMock] = [exec_result, claim_result]
    if grouped_actions is not None:
        group_result = MagicMock()
        group_result.scalars.return_value.all.return_value = grouped_actions
        side_effects.append(group_result)
    if account is not None:
        account_result = MagicMock()
        account_result.scalar_one_or_none.return_value = account
        side_effects.append(account_result)
    session = MagicMock()
    session.execute.side_effect = side_effects
    session.flush = MagicMock()
    return session


def _mock_query_one_or_none(value: object) -> MagicMock:
    query = MagicMock()
    filtered = MagicMock()
    filtered.one_or_none.return_value = value
    query.filter.return_value = filtered
    return query


def _mock_download_bundle_group_run_session(*rows: MagicMock) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(rows)
    session = MagicMock()
    session.execute.return_value = result
    return session


@pytest.fixture(autouse=True)
def _stub_download_bundle_group_run_sync():
    """
    Keep this suite focused on remediation run behavior under test.
    Group-run lifecycle sync is covered separately and adds extra execute() calls.
    """
    with patch("backend.workers.jobs.remediation_run._sync_download_bundle_group_runs", return_value=None):
        with patch("backend.workers.jobs.remediation_run.build_control_mapping_rows", return_value=[]):
            yield


def test_sync_download_bundle_group_runs_callback_managed_success_stays_started() -> None:
    started_at = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 3, 15, 12, 5, tzinfo=timezone.utc)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = uuid.uuid4()
    run.status = RemediationRunStatus.success
    run.started_at = started_at
    run.completed_at = completed_at
    run.artifacts = {
        "group_bundle": {
            "reporting": {
                "callback_url": "https://api.example.com/api/internal/group-runs/report",
                "token": "signed-token",
            }
        }
    }
    group_run = MagicMock()
    group_run.status = ActionGroupRunStatus.queued
    group_run.started_at = None
    group_run.finished_at = None
    group_run.report_token_jti = None

    session = _mock_download_bundle_group_run_session(group_run)

    sync_download_bundle_group_runs(session, run)

    assert group_run.status == ActionGroupRunStatus.started
    assert group_run.started_at == started_at
    assert group_run.finished_at is None


def test_sync_download_bundle_group_runs_legacy_success_finishes_immediately() -> None:
    started_at = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 3, 15, 12, 5, tzinfo=timezone.utc)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = uuid.uuid4()
    run.status = RemediationRunStatus.success
    run.started_at = started_at
    run.completed_at = completed_at
    run.artifacts = {}
    group_run = MagicMock()
    group_run.status = ActionGroupRunStatus.queued
    group_run.started_at = None
    group_run.finished_at = None
    group_run.report_token_jti = None

    session = _mock_download_bundle_group_run_session(group_run)

    sync_download_bundle_group_runs(session, run)

    assert group_run.status == ActionGroupRunStatus.finished
    assert group_run.started_at == started_at
    assert group_run.finished_at == completed_at


def test_sync_download_bundle_group_runs_failure_still_fails_immediately() -> None:
    started_at = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 3, 15, 12, 5, tzinfo=timezone.utc)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = uuid.uuid4()
    run.status = RemediationRunStatus.failed
    run.started_at = started_at
    run.completed_at = completed_at
    run.artifacts = {
        "group_bundle": {
            "reporting": {
                "callback_url": "https://api.example.com/api/internal/group-runs/report",
                "token": "signed-token",
            }
        }
    }
    group_run = MagicMock()
    group_run.status = ActionGroupRunStatus.started
    group_run.started_at = started_at
    group_run.finished_at = None
    group_run.report_token_jti = "token-jti"

    session = _mock_download_bundle_group_run_session(group_run)

    sync_download_bundle_group_runs(session, run)

    assert group_run.status == ActionGroupRunStatus.failed
    assert group_run.started_at == started_at
    assert group_run.finished_at == completed_at


def test_direct_fix_success() -> None:
    """direct_fix: WriteRole present, assume + executor succeed, run updated to success."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action("s3_block_public_access")
    _grant_direct_fix_approval(run)
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

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.assume_role") as mock_assume:
            mock_assume.return_value = MagicMock()

            with patch("backend.workers.jobs.remediation_run.run_direct_fix", return_value=fix_result):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "S3 Block Public Access enabled at account level"
    assert "Assuming WriteRole" in (run.logs or "")
    assert isinstance(run.artifacts, dict)
    direct_fix_artifact = run.artifacts.get("direct_fix")
    assert isinstance(direct_fix_artifact, dict)
    assert direct_fix_artifact.get("outcome") == "S3 Block Public Access enabled at account level"
    assert direct_fix_artifact.get("post_check_passed") is True
    assert direct_fix_artifact.get("log_count") == 3
    assert direct_fix_artifact.get("log_excerpt") == ["Pre-check", "Apply", "Post-check"]
    assert isinstance(direct_fix_artifact.get("recorded_at"), str)
    mock_assume.assert_called_once_with(
        role_arn=account.role_write_arn,
        external_id=account.external_id,
    )


def test_direct_fix_no_write_role() -> None:
    """direct_fix: role_write_arn is None -> run failed with clear message."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    _grant_direct_fix_approval(run)
    account = _mock_account(role_write_arn=None)

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.assume_role") as mock_assume:
            execute_remediation_run_job(job)
            mock_assume.assert_not_called()

    assert run.status == RemediationRunStatus.failed
    assert "WriteRole not configured" in (run.outcome or "")


def test_direct_fix_assume_role_fails() -> None:
    """direct_fix: assume_role raises ClientError -> run failed."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    _grant_direct_fix_approval(run)
    account = _mock_account()

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.assume_role") as mock_assume:
            mock_assume.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Not allowed"}},
                "AssumeRole",
            )

            with patch("backend.workers.jobs.remediation_run.run_direct_fix") as mock_fix:
                with patch("backend.workers.jobs.remediation_run.emit_worker_dispatch_error") as mock_emit:
                    execute_remediation_run_job(job)
                    mock_fix.assert_not_called()
                    assert mock_emit.call_count >= 1

    assert run.status == RemediationRunStatus.failed
    assert "Failed to assume WriteRole" in (run.outcome or "")


def test_direct_fix_executor_fails() -> None:
    """direct_fix: run_direct_fix returns success=False -> run failed."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    _grant_direct_fix_approval(run)
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

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run.run_direct_fix", return_value=fix_result):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.failed
    assert run.outcome == "Apply failed: AccessDenied"


def test_direct_fix_already_compliant() -> None:
    """direct_fix: executor returns success with 'Already compliant' -> run success, no direct_fix artifact."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    _grant_direct_fix_approval(run)
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

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run.run_direct_fix", return_value=fix_result):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "Already compliant; no change needed"
    # direct_fix artifact only added when outcome != "Already compliant"
    assert run.artifacts is None or "direct_fix" not in (run.artifacts or {})


def test_direct_fix_account_not_found() -> None:
    """direct_fix: AWS account not found -> run failed."""
    job = _make_job(mode="direct_fix")
    run = _mock_run_with_action()
    _grant_direct_fix_approval(run)

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None  # No account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1, result2]
    mock_session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.assume_role") as mock_assume:
            execute_remediation_run_job(job)
            mock_assume.assert_not_called()

    assert run.status == RemediationRunStatus.failed
    assert "AWS account not found" in (run.outcome or "")


def test_pr_only_variant_generates_cloudfront_oac_bundle() -> None:
    """pr_only with variant forwards variant to generate_pr_bundle and stores it on artifacts."""
    job = _make_job(mode="pr_only")
    job["pr_bundle_variant"] = "cloudfront_oac_private_s3"
    run = _mock_run_with_action("s3_bucket_block_public_access")

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1]
    mock_session.flush = MagicMock()

    bundle = {
        "format": "terraform",
        "files": [{"path": "s3_cloudfront_oac_private_s3.tf", "content": "# test"}],
        "steps": ["step"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle) as mock_generate:
            execute_remediation_run_job(job)
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert kwargs.get("variant") == "cloudfront_oac_private_s3"

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "PR bundle generated"
    assert isinstance(run.artifacts, dict)
    assert run.artifacts.get("pr_bundle_variant") == "cloudfront_oac_private_s3"
    assert "pr_bundle" in run.artifacts


def test_pr_only_non_executable_resolution_is_forwarded_and_sets_guidance_outcome() -> None:
    job = _make_job(mode="pr_only")
    job["resolution"] = {
        "strategy_id": "s3_enforce_ssl_strict_deny",
        "profile_id": "s3_enforce_ssl_strict_deny",
        "support_tier": "review_required_bundle",
        "blocked_reasons": ["Bucket policy merge safety has not been proven."],
        "preservation_summary": {"merge_safe_policy_available": False},
        "decision_rationale": "Needs review.",
    }
    run = _mock_run_with_action("s3_bucket_require_ssl")
    run.artifacts = {"selected_strategy": "s3_enforce_ssl_strict_deny"}

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1]
    mock_session.flush = MagicMock()

    bundle = {
        "format": "terraform",
        "files": [{"path": "decision.json", "content": "{}"}],
        "steps": ["step"],
        "metadata": {"non_executable_bundle": True},
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle) as mock_generate:
            execute_remediation_run_job(job)
            _, kwargs = mock_generate.call_args
            assert kwargs.get("resolution", {}).get("support_tier") == "review_required_bundle"

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "Non-executable remediation guidance bundle generated"
    assert "Non-executable remediation guidance bundle generated" in (run.logs or "")


def test_pr_only_apply_time_merge_resolution_generates_executable_s3_ssl_bundle() -> None:
    job = _make_job(mode="pr_only")
    job["strategy_id"] = "s3_enforce_ssl_strict_deny"
    job["resolution"] = {
        "strategy_id": "s3_enforce_ssl_strict_deny",
        "profile_id": "s3_enforce_ssl_strict_deny",
        "support_tier": "deterministic_bundle",
        "blocked_reasons": [],
        "preservation_summary": {
            "apply_time_merge": True,
            "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
        },
        "decision_rationale": "Apply-time merge is allowed.",
    }
    run = _mock_run_with_action("s3_bucket_require_ssl")
    run.action.region = "us-east-1"
    run.action.control_id = "S3.5"
    run.action.target_id = "123456789012|us-east-1|arn:aws:s3:::ssl-bucket|S3.5"
    run.action.resource_id = "arn:aws:s3:::ssl-bucket"
    run.artifacts = {"selected_strategy": "s3_enforce_ssl_strict_deny"}

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1]
    mock_session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "PR bundle generated"
    files_by_path = _bundle_files_by_path(run)
    assert "s3_bucket_require_ssl.tf" in files_by_path
    assert "terraform.auto.tfvars.json" not in files_by_path
    assert "scripts/s3_policy_fetch.py" in files_by_path
    assert "scripts/s3_policy_capture.py" in files_by_path
    assert 'data "external" "existing_policy"' in files_by_path["s3_bucket_require_ssl.tf"]


def test_pr_only_apply_time_merge_resolution_generates_executable_s3_11_bundle() -> None:
    job = _make_job(mode="pr_only")
    job["strategy_id"] = "s3_enable_abort_incomplete_uploads"
    job["resolution"] = {
        "strategy_id": "s3_enable_abort_incomplete_uploads",
        "profile_id": "s3_enable_abort_incomplete_uploads",
        "support_tier": "deterministic_bundle",
        "blocked_reasons": [],
        "preservation_summary": {
            "apply_time_merge": True,
            "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
        },
        "decision_rationale": "Apply-time lifecycle merge is allowed.",
    }
    run = _mock_run_with_action("s3_bucket_lifecycle_configuration")
    run.action.region = "us-east-1"
    run.action.control_id = "S3.11"
    run.action.target_id = "123456789012|us-east-1|arn:aws:s3:::lifecycle-bucket|S3.11"
    run.action.resource_id = "arn:aws:s3:::lifecycle-bucket"
    run.artifacts = {"selected_strategy": "s3_enable_abort_incomplete_uploads"}

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1]
    mock_session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "PR bundle generated"
    files_by_path = _bundle_files_by_path(run)
    assert "s3_bucket_lifecycle_configuration.tf" in files_by_path
    assert "scripts/s3_lifecycle_merge.py" in files_by_path
    assert "rollback/s3_lifecycle_restore.py" in files_by_path
    assert 'resource "terraform_data" "security_autopilot"' in files_by_path["s3_bucket_lifecycle_configuration.tf"]


def test_pr_only_generation_structured_error_persists_error_artifact() -> None:
    """PR bundle generation errors are stored as structured artifacts and mark run failed."""
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("iam_root_access_key_absent")

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1]
    mock_session.flush = MagicMock()

    error = PRBundleGenerationError(
        {
            "code": "unsupported_format_for_action_type",
            "detail": "cloudformation format is not supported for iam_root_access_key_absent.",
            "action_type": "iam_root_access_key_absent",
            "format": "cloudformation",
            "strategy_id": "iam_root_key_disable",
            "variant": "",
        }
    )

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=error):
            execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.failed
    assert run.outcome == "PR bundle generation failed: unsupported_format_for_action_type"
    assert isinstance(run.artifacts, dict)
    pr_bundle_error = run.artifacts.get("pr_bundle_error")
    assert isinstance(pr_bundle_error, dict)
    assert pr_bundle_error.get("code") == "unsupported_format_for_action_type"
    assert pr_bundle_error.get("action_type") == "iam_root_access_key_absent"


def test_pr_only_s3_policy_preservation_guard_error_is_visible_in_outcome_and_artifacts() -> None:
    """S3 migration preservation guard failures must surface in run outcome/log artifacts."""
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1]
    mock_session.flush = MagicMock()

    error = PRBundleGenerationError(
        {
            "code": "existing_bucket_policy_preservation_required",
            "detail": (
                "Existing bucket policy contains non-empty statements, but no preservation input was provided."
            ),
            "action_type": "s3_bucket_block_public_access",
            "format": "terraform",
            "strategy_id": "s3_migrate_cloudfront_oac_private",
            "variant": "cloudfront_oac_private_s3",
        }
    )

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=error):
            execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.failed
    assert run.outcome == "PR bundle generation failed: existing_bucket_policy_preservation_required"
    assert isinstance(run.artifacts, dict)
    pr_bundle_error = run.artifacts.get("pr_bundle_error")
    assert isinstance(pr_bundle_error, dict)
    assert pr_bundle_error.get("code") == "existing_bucket_policy_preservation_required"
    assert "non-empty statements" in str(pr_bundle_error.get("detail", ""))
    assert "existing_bucket_policy_preservation_required" in (run.logs or "")


def test_pr_only_root_run_persists_manual_high_risk_marker_in_artifacts_and_logs() -> None:
    """Root-key PR runs persist manual/high-risk markers in artifacts and worker logs."""
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("iam_root_access_key_absent")

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = run
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result1]
    mock_session.flush = MagicMock()

    bundle = {
        "format": "terraform",
        "files": [{"path": "iam_root_access_key_absent.tf", "content": "# root"}],
        "steps": ["step one"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle):
            execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert isinstance(run.artifacts, dict)
    marker = run.artifacts.get("manual_high_risk")
    assert isinstance(marker, dict)
    assert marker.get("marker") == MANUAL_HIGH_RISK_MARKER
    assert marker.get("requires_root_credentials") is True
    assert marker.get("runbook_url") == ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH
    assert MANUAL_HIGH_RISK_MARKER in (run.logs or "")
    assert ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH in (run.logs or "")


def test_pr_only_group_bundle_generates_single_combined_bundle() -> None:
    """pr_only with group_action_ids generates one combined bundle artifact for the group."""
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    run.action.control_id = "S3.2"
    run.action.title = "Bucket one hardening"

    second_action = MagicMock()
    second_action.id = uuid.uuid4()
    second_action.action_type = "s3_bucket_block_public_access"
    second_action.account_id = "123456789012"
    second_action.region = "us-east-1"
    second_action.title = "Bucket two hardening"
    second_action.control_id = "S3.2"
    second_action.target_id = "arn:aws:s3:::bucket-two"
    second_action.resource_id = "arn:aws:s3:::bucket-two"

    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]

    result_run = MagicMock()
    result_run.scalar_one_or_none.return_value = run

    result_actions = MagicMock()
    result_actions.scalars.return_value.all.return_value = [run.action, second_action]

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result_run, result_actions]
    mock_session.flush = MagicMock()

    bundle_one = {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider one"},
            {"path": "s3_bucket_block_public_access.tf", "content": "# bucket one"},
        ],
        "steps": ["step one"],
    }
    bundle_two = {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider two"},
            {"path": "s3_bucket_block_public_access.tf", "content": "# bucket two"},
        ],
        "steps": ["step two"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=[bundle_one, bundle_two]) as mock_generate:
            execute_remediation_run_job(job)
            assert mock_generate.call_count == 2

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "Group PR bundle generated (2 actions)"
    assert isinstance(run.artifacts, dict)
    pr_bundle = run.artifacts.get("pr_bundle")
    assert isinstance(pr_bundle, dict)
    files = pr_bundle.get("files")
    assert isinstance(files, list)
    paths = [f.get("path") for f in files if isinstance(f, dict)]
    assert "README_GROUP.txt" in paths
    assert "run_all.sh" in paths
    assert "run_all.command" not in paths
    assert "UNBLOCK_MAC.command" not in paths
    assert any(isinstance(path, str) and path.startswith("actions/") for path in paths)
    run_all = next(
        f for f in files if isinstance(f, dict) and f.get("path") == "run_all.sh"
    )
    content = str(run_all.get("content") or "")
    assert "set -euo pipefail" in content
    assert "render_progress()" in content
    assert "if [ -t 1 ] && [ -z \"${CI:-}\" ]" in content
    assert "apply_with_duplicate_tolerance" in content
    assert "run_terraform_init_with_retry" in content
    assert "write_tfrc_with_cache_only" in content
    assert "write_tfrc_with_mirror" in content
    assert "has_cached_aws_provider" in content
    assert "has_mirrored_aws_provider" in content
    assert "has_preferred_mirrored_aws_provider" in content
    assert "AWS_PROVIDER_LOCKFILE" in content
    assert "seed_canonical_aws_lockfile" in content
    assert 'find -L "${TF_PLUGIN_CACHE_DIR}/registry.terraform.io/hashicorp/aws/${AWS_PROVIDER_VERSION}" -type f' in content
    assert "terraform-provider-aws_v*_x5" in content
    assert 'find -L "${mirror_dir}/registry.terraform.io/hashicorp/aws/${AWS_PROVIDER_VERSION}" -type f' in content
    assert "filesystem_mirror" in content
    assert 'export TF_PROVIDER_MIRROR_DIR="${CACHE_ROOT}/provider-mirror"' in content
    assert 'PREFERRED_TF_PROVIDER_MIRROR_DIR="${HOME}/.terraform.d/plugin-cache"' in content
    assert 'path    = "${mirror_dir}"' in content
    assert 'terraform providers mirror "${ACTIVE_TF_PROVIDER_MIRROR_DIR}"' in content
    assert 'terraform providers lock -fs-mirror="${ACTIVE_TF_PROVIDER_MIRROR_DIR}"' in content
    assert 'cp .terraform.lock.hcl "${AWS_PROVIDER_LOCKFILE}"' in content
    assert "terraform_init_with_lockfile_fallback" in content
    assert 'terraform init -input=false -lockfile=readonly' in content
    assert 'grep -q "Provider dependency changes detected" "$log_file"' in content
    assert "refreshing lockfile." in content
    assert 'CLOUDFRONT_OAC_ACTION_TIMEOUT_SECS="${CLOUDFRONT_OAC_ACTION_TIMEOUT_SECS:-1800}"' in content
    assert "bundle_uses_cloudfront_oac()" in content
    assert "bundle_timeout_secs()" in content
    assert 'cloudfront_oac_bundles=${HAS_CLOUDFRONT_OAC_BUNDLES}' in content
    assert "prepare_action_workspace" in content
    assert "cleanup_action_workspace" in content
    assert "prepare_s3_access_logging_tfvars" in content
    assert "prepare_cloudfront_oac_tfvars" in content
    assert "merge_cloudfront_oac_tfvars_json" in content
    assert "cloudfront_reuse_query.json" in content
    assert "adopt_existing_log_bucket" in content
    assert "aws s3api get-bucket-location --bucket" in content
    assert "aws-security-autopilot-tf-" in content
    assert 'include = ["registry.terraform.io/hashicorp/aws"]' in content
    assert 'version = "= 5.100.0"' in content
    assert "5.100.0" in content
    assert "${!ACTION_DIRS[@]}" not in content
    assert ("while IFS= read -r dir; do" in content) or ("for dir in \"${ACTION_DIRS[@]}\"; do" in content)
    assert "InvalidPermission" in content
    assert "EntityAlreadyExists" in content
    assert "WARNING: duplicate/already-existing resource detected; continuing without failure." in content
    assert "Bundle run completed." in content
    assert "Failed folders summary:" in content
    metadata = pr_bundle.get("metadata")
    assert isinstance(metadata, dict)
    runner_template_source = str(metadata.get("runner_template_source") or "")
    assert runner_template_source == "repo:infrastructure/templates/run_all.sh"
    runner_template_version = str(metadata.get("runner_template_version") or "")
    assert runner_template_version.startswith("sha256:")
    assert metadata.get("requested_action_count") == 2
    assert metadata.get("generated_action_count") == 2
    assert metadata.get("skipped_action_count") == 0
    assert metadata.get("skipped_actions") == []
    group_bundle = run.artifacts.get("group_bundle")
    assert isinstance(group_bundle, dict)
    group_runner_template_source = str(group_bundle.get("runner_template_source") or "")
    assert group_runner_template_source == "repo:infrastructure/templates/run_all.sh"
    assert group_bundle.get("runner_template_version") == runner_template_version
    assert group_bundle.get("generated_action_count") == 2
    assert group_bundle.get("skipped_action_count") == 0
    readme_group = next(
        f for f in files if isinstance(f, dict) and f.get("path") == "README_GROUP.txt"
    )
    readme_content = str(readme_group.get("content") or "")
    assert "chmod +x ./run_all.sh" in readme_content
    assert "./run_all.sh" in readme_content
    assert "local mirror" in readme_content


def test_pr_only_group_bundle_skips_generation_errors_and_keeps_valid_actions() -> None:
    """Group bundle skips action-level generation failures and records explicit metadata."""
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_encryption_kms")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    run.action.control_id = "S3.15"
    run.action.title = "Bucket one SSE-KMS"

    second_action = MagicMock()
    second_action.id = uuid.uuid4()
    second_action.action_type = "s3_bucket_encryption_kms"
    second_action.account_id = "123456789012"
    second_action.region = "us-east-1"
    second_action.title = "Account-scoped S3.15"
    second_action.control_id = "S3.15"
    second_action.target_id = "123456789012|us-east-1|AWS::::Account:123456789012|S3.15"
    second_action.resource_id = "AWS::::Account:123456789012"

    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]

    result_run = MagicMock()
    result_run.scalar_one_or_none.return_value = run
    result_actions = MagicMock()
    result_actions.scalars.return_value.all.return_value = [run.action, second_action]

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result_run, result_actions]
    mock_session.flush = MagicMock()

    bundle_one = {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider one"},
            {"path": "s3_bucket_encryption_kms.tf", "content": "# bucket one"},
        ],
        "steps": ["step one"],
    }
    error = PRBundleGenerationError(
        {
            "code": "unresolved_placeholder_token",
            "detail": "Generated bundle contains unresolved placeholder token 'REPLACE_BUCKET_NAME'.",
            "action_type": "s3_bucket_encryption_kms",
            "format": "terraform",
            "strategy_id": "",
            "variant": "",
        }
    )

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=[bundle_one, error]):
            execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "Group PR bundle generated (1 actions; 1 skipped)"
    assert isinstance(run.artifacts, dict)
    pr_bundle = run.artifacts.get("pr_bundle")
    assert isinstance(pr_bundle, dict)
    metadata = pr_bundle.get("metadata")
    assert isinstance(metadata, dict)
    assert metadata.get("requested_action_count") == 2
    assert metadata.get("generated_action_count") == 1
    assert metadata.get("skipped_action_count") == 1
    skipped_actions = metadata.get("skipped_actions")
    assert isinstance(skipped_actions, list) and len(skipped_actions) == 1
    assert skipped_actions[0].get("code") == "unresolved_placeholder_token"
    group_bundle = run.artifacts.get("group_bundle")
    assert isinstance(group_bundle, dict)
    assert group_bundle.get("generated_action_count") == 1
    assert group_bundle.get("skipped_action_count") == 1
    files = pr_bundle.get("files")
    assert isinstance(files, list)
    paths = [f.get("path") for f in files if isinstance(f, dict)]
    assert any(isinstance(path, str) and path.startswith("actions/") for path in paths)
    assert any(isinstance(path, str) and path.startswith("errors/") for path in paths)
    readme_group = next(f for f in files if isinstance(f, dict) and f.get("path") == "README_GROUP.txt")
    readme = str(readme_group.get("content") or "")
    assert "SKIPPED (unresolved_placeholder_token)" in readme
    assert "errors/*.txt" in readme


def test_load_default_runner_script_reads_repo_template_file() -> None:
    fallback = "#!/usr/bin/env bash\necho embedded-fallback\n"

    with patch("backend.workers.jobs.remediation_run.Path.is_file", return_value=True):
        with patch("backend.workers.jobs.remediation_run.Path.read_text", return_value="#!/usr/bin/env bash\necho repo-template\n"):
            script, source, version = remediation_run._load_default_runner_script(fallback)

    assert "repo-template" in script
    assert source == "repo:infrastructure/templates/run_all.sh"
    assert version.startswith("sha256:")


def test_pr_only_strategy_fields_forwarded_to_generator_and_artifacts() -> None:
    """Single-action PR runs forward strategy fields and persist risk snapshot evidence."""
    job = _make_job(mode="pr_only")
    job["strategy_id"] = "config_enable_centralized_delivery"
    job["strategy_inputs"] = {"delivery_bucket": "central-config-bucket"}
    job["risk_acknowledged"] = True

    run = _mock_run_with_action("aws_config_enabled")
    run.artifacts = {
        "risk_snapshot": {
            "checks": [{"code": "config_cost_impact", "status": "warn", "message": "cost impact"}],
            "warnings": ["cost impact"],
            "recommendation": "ack_required",
        }
    }

    result_run = MagicMock()
    result_run.scalar_one_or_none.return_value = run

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result_run]
    mock_session.flush = MagicMock()

    bundle = {
        "format": "terraform",
        "files": [{"path": "aws_config_enabled.tf", "content": "# config"}],
        "steps": ["step one"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle) as mock_generate:
            execute_remediation_run_job(job)
            _, kwargs = mock_generate.call_args
            assert kwargs.get("strategy_id") == "config_enable_centralized_delivery"
            assert kwargs.get("strategy_inputs") == {"delivery_bucket": "central-config-bucket"}
            assert isinstance(kwargs.get("risk_snapshot"), dict)

    assert run.status == RemediationRunStatus.success
    assert isinstance(run.artifacts, dict)
    assert run.artifacts.get("selected_strategy") == "config_enable_centralized_delivery"
    assert run.artifacts.get("strategy_inputs") == {"delivery_bucket": "central-config-bucket"}
    assert run.artifacts.get("risk_acknowledged") is True
    assert isinstance(run.artifacts.get("risk_snapshot"), dict)


def test_group_pr_bundle_uses_artifact_action_resolutions_when_present() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    run.action.title = "Bucket one hardening"

    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two hardening",
    )
    job["group_action_ids"] = [str(second_action.id), str(run.action.id)]
    run.artifacts = {
        "selected_strategy": "s3_bucket_block_public_access_standard",
        "strategy_inputs": {"legacy": "ignored"},
        "group_bundle": {
            "action_resolutions": [
                _group_action_resolution_payload(
                    action_id=run.action.id,
                    strategy_id="s3_bucket_block_public_access_standard",
                ),
                _group_action_resolution_payload(
                    action_id=second_action.id,
                    strategy_id="s3_migrate_cloudfront_oac_private",
                    strategy_inputs={"exempt_principals": ["arn:aws:iam::123456789012:role/cdn"]},
                ),
            ]
        },
    }
    mock_session = _mock_group_session(run, [run.action, second_action])

    bundle_one = {"format": "terraform", "files": [{"path": "providers.tf", "content": "# one"}], "steps": ["one"]}
    bundle_two = {"format": "terraform", "files": [{"path": "providers.tf", "content": "# two"}], "steps": ["two"]}

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=[bundle_one, bundle_two]) as mock_generate:
            execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert [call.args[0].id for call in mock_generate.call_args_list] == [second_action.id, run.action.id]
    assert [call.kwargs.get("strategy_id") for call in mock_generate.call_args_list] == [
        "s3_migrate_cloudfront_oac_private",
        "s3_bucket_block_public_access_standard",
    ]
    assert [call.kwargs.get("strategy_inputs") for call in mock_generate.call_args_list] == [
        {"exempt_principals": ["arn:aws:iam::123456789012:role/cdn"]},
        {},
    ]


def test_group_pr_bundle_uses_queue_action_resolutions_when_present() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"

    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two hardening",
    )
    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_bucket_block_public_access_standard",
        ),
        _group_action_resolution_payload(
            action_id=second_action.id,
            strategy_id="s3_migrate_cloudfront_oac_private",
            strategy_inputs={"exempt_principals": ["arn:aws:iam::123456789012:role/queue"]},
        ),
    ]
    run.artifacts = {
        "pr_bundle_variant": "cloudfront_oac_private_s3",
        "selected_strategy": "s3_bucket_block_public_access_standard",
        "group_bundle": {
            "action_resolutions": [
                _group_action_resolution_payload(
                    action_id=run.action.id,
                    strategy_id="s3_migrate_cloudfront_oac_private",
                    strategy_inputs={"exempt_principals": ["arn:aws:iam::123456789012:role/artifact"]},
                ),
                _group_action_resolution_payload(
                    action_id=second_action.id,
                    strategy_id="s3_bucket_block_public_access_standard",
                ),
            ]
        },
    }
    mock_session = _mock_group_session(run, [run.action, second_action])

    bundle_one = {
        "format": "terraform",
        "files": [{"path": "providers.tf", "content": "# provider one"}],
        "steps": ["step one"],
    }
    bundle_two = {
        "format": "terraform",
        "files": [{"path": "providers.tf", "content": "# provider two"}],
        "steps": ["step two"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=[bundle_one, bundle_two]) as mock_generate:
            execute_remediation_run_job(job)
            assert mock_generate.call_count == 2

    assert run.status == RemediationRunStatus.success
    assert [call.kwargs.get("strategy_id") for call in mock_generate.call_args_list] == [
        "s3_bucket_block_public_access_standard",
        "s3_migrate_cloudfront_oac_private",
    ]
    assert [call.kwargs.get("strategy_inputs") for call in mock_generate.call_args_list] == [
        {},
        {"exempt_principals": ["arn:aws:iam::123456789012:role/queue"]},
    ]
    assert [call.kwargs.get("variant") for call in mock_generate.call_args_list] == [None, None]


@pytest.mark.parametrize("case_name", ["missing_action_id", "outside_group", "duplicate", "missing_resolution"])
def test_group_pr_bundle_malformed_action_resolutions_fail_closed(case_name: str) -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two hardening",
    )
    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]
    valid_entries = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_bucket_block_public_access_standard",
        ),
        _group_action_resolution_payload(
            action_id=second_action.id,
            strategy_id="s3_migrate_cloudfront_oac_private",
        ),
    ]
    if case_name == "missing_action_id":
        malformed = dict(valid_entries[0])
        malformed.pop("action_id")
        job["action_resolutions"] = [malformed, valid_entries[1]]
    elif case_name == "outside_group":
        job["action_resolutions"] = [
            _group_action_resolution_payload(
                action_id=uuid.uuid4(),
                strategy_id="s3_bucket_block_public_access_standard",
            ),
            valid_entries[1],
        ]
    elif case_name == "missing_resolution":
        malformed = dict(valid_entries[0])
        malformed.pop("resolution")
        job["action_resolutions"] = [malformed, valid_entries[1]]
    else:
        job["action_resolutions"] = [valid_entries[0], dict(valid_entries[0])]
    run.artifacts = {
        "selected_strategy": "s3_bucket_block_public_access_standard",
        "group_bundle": {"action_resolutions": valid_entries},
    }
    mock_session = _mock_group_session(run, [run.action, second_action])

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle") as mock_generate:
            execute_remediation_run_job(job)
            mock_generate.assert_not_called()

    assert run.status == RemediationRunStatus.failed
    assert run.outcome == "PR bundle generation failed: invalid_grouped_action_resolutions"
    assert isinstance(run.artifacts, dict)
    pr_bundle_error = run.artifacts.get("pr_bundle_error")
    assert isinstance(pr_bundle_error, dict)
    assert pr_bundle_error.get("code") == "invalid_grouped_action_resolutions"


def test_group_pr_bundle_mixed_tier_layout_for_executable_and_review_required_actions() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    run.action.title = "Bucket one hardening"
    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two hardening",
    )
    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_bucket_block_public_access_standard",
            support_tier="deterministic_bundle",
            finding_coverage={"finding_ids": ["finding-1"]},
            decision_rationale="Safe deterministic bundle",
        ),
        _group_action_resolution_payload(
            action_id=second_action.id,
            strategy_id="s3_migrate_cloudfront_oac_private",
            support_tier="review_required_bundle",
            decision_rationale="Needs operator review",
        ),
    ]
    run.artifacts = {"selected_strategy": "s3_bucket_block_public_access_standard"}
    mock_session = _mock_group_session(run, [run.action, second_action])
    bundle = {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider"},
            {"path": "main.tf", "content": "resource \"aws_s3_bucket_public_access_block\" \"this\" {}"},
        ],
        "steps": ["step one"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle) as mock_generate:
            execute_remediation_run_job(job)
            mock_generate.assert_called_once()

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "Group PR bundle generated (2 actions)"
    files_by_path = _bundle_files_by_path(run)
    assert "bundle_manifest.json" in files_by_path
    assert "decision_log.md" in files_by_path
    assert "finding_coverage.json" in files_by_path
    assert "README_GROUP.txt" in files_by_path
    assert "run_all.sh" in files_by_path
    assert any(path.startswith("executable/actions/") and path.endswith(".tf") for path in files_by_path)
    assert not any(path.startswith("review_required/actions/") and path.endswith(".tf") for path in files_by_path)
    manifest = json.loads(files_by_path["bundle_manifest.json"])
    assert manifest["layout_version"] == "grouped_bundle_mixed_tier/v1"
    assert manifest["execution_root"] == "executable/actions"
    assert manifest["grouped_actions"] == [str(run.action.id), str(second_action.id)]
    executable_entry = next(item for item in manifest["actions"] if item["action_id"] == str(run.action.id))
    review_entry = next(item for item in manifest["actions"] if item["action_id"] == str(second_action.id))
    assert executable_entry["tier_root"] == "executable/actions"
    assert executable_entry["outcome"] == "executable_bundle_generated"
    assert executable_entry["has_runnable_terraform"] is True
    assert review_entry["tier_root"] == "review_required/actions"
    assert review_entry["outcome"] == "review_required_metadata_only"
    assert review_entry["has_runnable_terraform"] is False
    run_all = files_by_path["run_all.sh"]
    assert 'EXECUTION_ROOT="${EXECUTION_ROOT:-executable/actions}"' in run_all
    assert "prepare_action_workspace" in run_all
    assert "review_required/actions" not in run_all
    assert "manual_guidance/actions" not in run_all
    decision_log = files_by_path["decision_log.md"]
    assert str(run.action.id) in decision_log
    assert str(second_action.id) in decision_log
    assert "Safe deterministic bundle" in decision_log
    assert "Needs operator review" in decision_log
    finding_coverage = json.loads(files_by_path["finding_coverage.json"])
    assert [item["action_id"] for item in finding_coverage["actions"]] == [
        str(run.action.id),
        str(second_action.id),
    ]
    assert finding_coverage["actions"][0]["finding_coverage"] == {"finding_ids": ["finding-1"]}
    assert finding_coverage["actions"][1]["finding_coverage"] == {}
    assert "Only executable Terraform lives under executable/actions/." in files_by_path["README_GROUP.txt"]
    assert "Review-required actions:" in files_by_path["README_GROUP.txt"]
    assert "Manual-guidance actions:" in files_by_path["README_GROUP.txt"]
    group_bundle = run.artifacts.get("group_bundle")
    assert isinstance(group_bundle, dict)
    assert group_bundle.get("layout_version") == "grouped_bundle_mixed_tier/v1"
    assert group_bundle.get("execution_root") == "executable/actions"


def test_group_pr_bundle_mixed_tier_preserves_prefixed_config_rollback_entry_metadata() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("aws_config_enabled")
    run.action.region = "eu-north-1"
    run.action.control_id = "Config.1"
    run.action.target_id = "123456789012|eu-north-1|AWS::::Account:123456789012|Config.1"
    run.action.resource_id = run.action.target_id
    review_action = _mock_group_action(
        action_type="aws_config_enabled",
        target_id="123456789012|eu-north-1|AWS::::Account:123456789012|Config.1-review",
        title="Config review action",
        control_id="Config.1",
    )
    job["group_action_ids"] = [str(run.action.id), str(review_action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="config_enable_account_local_delivery",
            support_tier="deterministic_bundle",
            decision_rationale="Exact rollback bundle",
        ),
        _group_action_resolution_payload(
            action_id=review_action.id,
            strategy_id="config_keep_exception",
            support_tier="review_required_bundle",
            decision_rationale="Metadata-only review action",
        ),
    ]
    run.artifacts = {"selected_strategy": "config_enable_account_local_delivery"}
    mock_session = _mock_group_session(run, [run.action, review_action])
    bundle = {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider"},
            {"path": "aws_config_enabled.tf", "content": 'resource "null_resource" "config" {}'},
            {"path": "rollback/aws_config_restore.py", "content": "# restore"},
        ],
        "steps": ["step one"],
        "metadata": {
            "bundle_rollback_entries": {
                str(run.action.id): {
                    "path": "rollback/aws_config_restore.py",
                    "runner": "python3",
                }
            }
        },
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle):
            execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert isinstance(run.artifacts, dict)
    pr_bundle = run.artifacts["pr_bundle"]
    metadata = pr_bundle["metadata"]
    rollback_entry = metadata["bundle_rollback_entries"][str(run.action.id)]
    assert rollback_entry["runner"] == "python3"
    assert rollback_entry["path"].startswith("executable/actions/")
    assert rollback_entry["path"].endswith("/rollback/aws_config_restore.py")
    manifest = json.loads(_bundle_files_by_path(run)["bundle_manifest.json"])
    action_entry = next(item for item in manifest["actions"] if item["action_id"] == str(run.action.id))
    assert action_entry["bundle_rollback_command"].startswith("python3 ./executable/actions/")
    assert action_entry["bundle_rollback_command"].endswith("/rollback/aws_config_restore.py")


def test_group_pr_bundle_places_s3_ssl_apply_time_merge_under_executable_actions() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_require_ssl")
    run.action.region = "us-east-1"
    run.action.control_id = "S3.5"
    run.action.target_id = "123456789012|us-east-1|arn:aws:s3:::ssl-bucket|S3.5"
    run.action.resource_id = "arn:aws:s3:::ssl-bucket"
    job["group_action_ids"] = [str(run.action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_enforce_ssl_strict_deny",
            support_tier="deterministic_bundle",
            decision_rationale="Apply-time merge is allowed.",
            preservation_summary={
                "apply_time_merge": True,
                "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
            },
        )
    ]
    run.artifacts = {"selected_strategy": "s3_enforce_ssl_strict_deny"}
    mock_session = _mock_group_session(run, [run.action])

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    files_by_path = _bundle_files_by_path(run)
    executable_paths = [path for path in files_by_path if path.startswith("executable/actions/")]
    assert any(path.endswith("/s3_bucket_require_ssl.tf") for path in executable_paths)
    assert not any(path.endswith("terraform.auto.tfvars.json") for path in executable_paths)
    manifest = json.loads(files_by_path["bundle_manifest.json"])
    assert manifest["actions"][0]["tier_root"] == "executable/actions"
    assert manifest["actions"][0]["has_runnable_terraform"] is True


def test_group_pr_bundle_places_s3_11_apply_time_merge_under_executable_actions() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_lifecycle_configuration")
    run.action.region = "us-east-1"
    run.action.control_id = "S3.11"
    run.action.target_id = "123456789012|us-east-1|arn:aws:s3:::lifecycle-bucket|S3.11"
    run.action.resource_id = "arn:aws:s3:::lifecycle-bucket"
    job["group_action_ids"] = [str(run.action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_enable_abort_incomplete_uploads",
            support_tier="deterministic_bundle",
            decision_rationale="Apply-time lifecycle merge is allowed.",
            preservation_summary={
                "apply_time_merge": True,
                "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
            },
        )
    ]
    run.artifacts = {"selected_strategy": "s3_enable_abort_incomplete_uploads"}
    mock_session = _mock_group_session(run, [run.action])

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    files_by_path = _bundle_files_by_path(run)
    executable_paths = [path for path in files_by_path if path.startswith("executable/actions/")]
    assert any(path.endswith("/s3_bucket_lifecycle_configuration.tf") for path in executable_paths)
    assert any(path.endswith("/scripts/s3_lifecycle_merge.py") for path in executable_paths)
    assert any(path.endswith("/rollback/s3_lifecycle_restore.py") for path in executable_paths)
    manifest = json.loads(files_by_path["bundle_manifest.json"])
    assert manifest["actions"][0]["tier_root"] == "executable/actions"
    assert manifest["actions"][0]["has_runnable_terraform"] is True


def test_group_pr_bundle_reporting_wrapper_includes_non_executable_results() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two hardening",
    )
    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_bucket_block_public_access_standard",
            support_tier="deterministic_bundle",
        ),
        _group_action_resolution_payload(
            action_id=second_action.id,
            strategy_id="s3_migrate_cloudfront_oac_private",
            support_tier="review_required_bundle",
            blocked_reasons=["needs approval"],
        ),
    ]
    run.artifacts = {
        "group_bundle": {
            "reporting": {
                "callback_url": "https://api.example.com/api/internal/group-runs/report",
                "token": "signed-token",
            }
        }
    }
    mock_session = _mock_group_session(run, [run.action, second_action])
    bundle = {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider"},
            {"path": "main.tf", "content": "resource \"aws_s3_bucket_public_access_block\" \"this\" {}"},
        ],
        "steps": ["step one"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle):
            execute_remediation_run_job(job)

    files_by_path = _bundle_files_by_path(run)
    assert "run_all.sh" in files_by_path
    assert "replay_group_run_reports.sh" in files_by_path
    assert "run_actions.sh" in files_by_path
    assert "non_executable_results" in files_by_path["run_all.sh"]
    assert str(second_action.id) in files_by_path["run_all.sh"]
    assert "review_required_bundle" in files_by_path["run_all.sh"]
    assert "review_required_metadata_only" in files_by_path["run_all.sh"]
    assert 'STARTED_TEMPLATE={"token":' not in files_by_path["run_all.sh"]
    assert "STARTED_TEMPLATE='" in files_by_path["run_all.sh"]
    assert 'RUNNER="./run_actions.sh"' in files_by_path["run_all.sh"]
    assert "--retry-all-errors" in files_by_path["run_all.sh"]
    assert "--connect-timeout 5" in files_by_path["run_all.sh"]
    assert "group_run_report_replay" in files_by_path["replay_group_run_reports.sh"]
    assert 'EXECUTION_ROOT="${EXECUTION_ROOT:-executable/actions}"' in files_by_path["run_actions.sh"]
    assert "prepare_action_workspace" in files_by_path["run_actions.sh"]
    assert 'export TF_DATA_DIR="${dir}/.terraform-data"' in files_by_path["run_actions.sh"]


def test_reporting_wrapper_script_posts_shell_safe_json_payloads(tmp_path: Path) -> None:
    executable_action_id = uuid.uuid4()
    review_action_id = uuid.uuid4()
    payload_log = tmp_path / "payloads.jsonl"
    run_all_path = tmp_path / "run_all.sh"
    run_actions_path = tmp_path / "run_actions.sh"
    bin_dir = tmp_path / "bin"
    curl_path = bin_dir / "curl"

    bin_dir.mkdir()
    run_all_path.write_text(
        build_reporting_wrapper_script(
            callback_url="https://api.example.com/api/internal/group-runs/report",
            report_token="signed-token",
            action_ids=[executable_action_id],
            non_executable_results=[
                {
                    "action_id": str(review_action_id),
                    "support_tier": "review_required_bundle",
                    "profile_id": "s3_review_profile",
                    "strategy_id": "s3_review_strategy",
                    "reason": "review_required_metadata_only",
                    "blocked_reasons": ["operator's approval required"],
                }
            ],
        ),
        encoding="utf-8",
    )
    run_all_path.chmod(0o755)
    run_actions_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    run_actions_path.chmod(0o755)
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "payload=\"\"\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -d)\n"
        "      shift\n"
        "      payload=\"$1\"\n"
        "      ;;\n"
        "  esac\n"
        "  shift || true\n"
        "done\n"
        "printf '%s\\n' \"$payload\" >> \"$BUNDLE_TEST_PAYLOADS\"\n",
        encoding="utf-8",
    )
    curl_path.chmod(0o755)

    env = os.environ.copy()
    env["BUNDLE_TEST_PAYLOADS"] = str(payload_log)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    completed = subprocess.run(
        [str(run_all_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payloads = [json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines()]
    assert [payload["event"] for payload in payloads] == ["started", "finished"]
    assert payloads[0]["token"] == "signed-token"
    assert "started_at" in payloads[0]
    assert payloads[1]["action_results"] == [
        {
            "action_id": str(executable_action_id),
            "execution_status": "success",
        }
    ]
    assert payloads[1]["non_executable_results"] == [
        {
            "action_id": str(review_action_id),
            "support_tier": "review_required_bundle",
            "profile_id": "s3_review_profile",
            "strategy_id": "s3_review_strategy",
            "reason": "review_required_metadata_only",
            "blocked_reasons": ["operator's approval required"],
        }
    ]
    assert "finished_at" in payloads[1]


def test_reporting_wrapper_script_posts_finished_failed_on_runner_error(tmp_path: Path) -> None:
    executable_action_id = uuid.uuid4()
    payload_log = tmp_path / "payloads.jsonl"
    run_all_path = tmp_path / "run_all.sh"
    run_actions_path = tmp_path / "run_actions.sh"
    bin_dir = tmp_path / "bin"
    curl_path = bin_dir / "curl"

    bin_dir.mkdir()
    run_all_path.write_text(
        build_reporting_wrapper_script(
            callback_url="https://api.example.com/api/internal/group-runs/report",
            report_token="signed-token",
            action_ids=[executable_action_id],
        ),
        encoding="utf-8",
    )
    run_all_path.chmod(0o755)
    run_actions_path.write_text("#!/usr/bin/env bash\nexit 143\n", encoding="utf-8")
    run_actions_path.chmod(0o755)
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "payload=\"\"\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -d)\n"
        "      shift\n"
        "      payload=\"$1\"\n"
        "      ;;\n"
        "  esac\n"
        "  shift || true\n"
        "done\n"
        "printf '%s\\n' \"$payload\" >> \"$BUNDLE_TEST_PAYLOADS\"\n"
        "printf '200'\n",
        encoding="utf-8",
    )
    curl_path.chmod(0o755)

    env = os.environ.copy()
    env["BUNDLE_TEST_PAYLOADS"] = str(payload_log)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    completed = subprocess.run(
        [str(run_all_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 143
    payloads = [json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines()]
    assert [payload["event"] for payload in payloads] == ["started", "finished"]
    assert payloads[1]["action_results"] == [
        {
            "action_id": str(executable_action_id),
            "execution_status": "failed",
            "execution_error_code": "bundle_runner_failed",
            "execution_error_message": "run_actions.sh exited non-zero",
        }
    ]
    assert "finished_at" in payloads[1]


def test_reporting_wrapper_script_uses_execution_summary_for_partial_failures(tmp_path: Path) -> None:
    first_action_id = uuid.uuid4()
    second_action_id = uuid.uuid4()
    payload_log = tmp_path / "payloads.jsonl"
    run_all_path = tmp_path / "run_all.sh"
    run_actions_path = tmp_path / "run_actions.sh"
    bin_dir = tmp_path / "bin"
    curl_path = bin_dir / "curl"
    summary = {
        "action_results": [
            {
                "action_id": str(first_action_id),
                "execution_status": "success",
            },
            {
                "action_id": str(second_action_id),
                "execution_status": "failed",
                "execution_error_code": "bundle_runner_plan",
                "execution_error_message": "run_all.sh failed during plan for folder executable/actions/02-two",
            },
        ],
        "shared_execution_results": [],
    }

    bin_dir.mkdir()
    run_all_path.write_text(
        build_reporting_wrapper_script(
            callback_url="https://api.example.com/api/internal/group-runs/report",
            report_token="signed-token",
            action_ids=[first_action_id, second_action_id],
        ),
        encoding="utf-8",
    )
    run_all_path.chmod(0o755)
    run_actions_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat > .bundle-execution-summary.json <<'EOF'\n"
        f"{json.dumps(summary)}\n"
        "EOF\n"
        "exit 1\n",
        encoding="utf-8",
    )
    run_actions_path.chmod(0o755)
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "payload=\"\"\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -d)\n"
        "      shift\n"
        "      payload=\"$1\"\n"
        "      ;;\n"
        "  esac\n"
        "  shift || true\n"
        "done\n"
        "printf '%s\\n' \"$payload\" >> \"$BUNDLE_TEST_PAYLOADS\"\n"
        "printf '200'\n",
        encoding="utf-8",
    )
    curl_path.chmod(0o755)

    env = os.environ.copy()
    env["BUNDLE_TEST_PAYLOADS"] = str(payload_log)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    completed = subprocess.run(
        [str(run_all_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 1
    payloads = [json.loads(line) for line in payload_log.read_text(encoding="utf-8").splitlines()]
    assert [payload["event"] for payload in payloads] == ["started", "finished"]
    assert payloads[1]["action_results"] == summary["action_results"]
    assert "finished_at" in payloads[1]


def test_reporting_replay_script_replays_and_deletes_payloads(tmp_path: Path) -> None:
    replay_path = tmp_path / "replay_group_run_reports.sh"
    replay_dir = tmp_path / ".bundle-callback-replay"
    replay_dir.mkdir()
    payload = replay_dir / "finished-1.json"
    payload.write_text('{"token":"signed-token","event":"finished"}\n', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    curl_path = bin_dir / "curl"
    bin_dir.mkdir()
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "outfile=\"\"\n"
        "payload_file=\"\"\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -o)\n"
        "      shift\n"
        "      outfile=\"$1\"\n"
        "      ;;\n"
        "    -w)\n"
        "      shift\n"
        "      ;;\n"
        "    --data-binary)\n"
        "      shift\n"
        "      payload_file=\"$1\"\n"
        "      ;;\n"
        "  esac\n"
        "  shift || true\n"
        "done\n"
        "cat \"${payload_file#@}\" >/dev/null\n"
        "printf '{}' > \"$outfile\"\n"
        "printf '200'\n",
        encoding="utf-8",
    )
    curl_path.chmod(0o755)
    replay_path.write_text(
        build_reporting_replay_script(callback_url="https://api.example.com/api/internal/group-runs/report"),
        encoding="utf-8",
    )
    replay_path.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    completed = subprocess.run(
        [str(replay_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert not payload.exists()


def test_group_pr_bundle_run_actions_script_includes_timeout_guards() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    second_action = _mock_group_action(
        action_type="s3_bucket_block_public_access",
        target_id="arn:aws:s3:::bucket-2",
        title="Second action",
    )
    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_block_public_access_full",
            support_tier="deterministic_bundle",
        ),
        _group_action_resolution_payload(
            action_id=second_action.id,
            strategy_id="s3_migrate_cloudfront_oac_private",
            support_tier="review_required_bundle",
            blocked_reasons=["needs approval"],
        ),
    ]
    run.artifacts = {
        "group_bundle": {
            "reporting": {
                "callback_url": "https://api.example.com/api/internal/group-runs/report",
                "token": "signed-token",
            }
        }
    }
    mock_session = _mock_group_session(run, [run.action, second_action])
    bundle = {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider"},
            {"path": "main.tf", "content": "resource \"aws_s3_bucket_public_access_block\" \"this\" {}"},
        ],
        "steps": ["step one"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bundle):
                execute_remediation_run_job(job)

    files_by_path = _bundle_files_by_path(run)
    content = files_by_path["run_actions.sh"]
    assert 'ACTION_TIMEOUT_SECS="${ACTION_TIMEOUT_SECS:-300}"' in content
    assert 'CLOUDFRONT_OAC_ACTION_TIMEOUT_SECS="${CLOUDFRONT_OAC_ACTION_TIMEOUT_SECS:-1800}"' in content
    assert "bundle_timeout_secs()" in content
    assert "run_with_timeout()" in content
    assert 'timeout_secs=$(bundle_timeout_secs "$dir")' in content
    assert 'run_with_timeout "$timeout_secs" terraform plan -input=false' in content
    assert "apply_with_duplicate_tolerance" in content
    assert "prepare_cloudfront_oac_tfvars" in content
    assert "merge_cloudfront_oac_tfvars_json" in content
    assert '"$timeout_secs"' in content


def test_run_all_templates_keep_s3_9_owned_bucket_tolerance_but_fail_closed_for_oac_duplicates() -> None:
    worker_template = Path("backend/workers/jobs/run_all_template.sh").read_text(encoding="utf-8")
    infra_template = Path("infrastructure/templates/run_all.sh").read_text(encoding="utf-8")

    for content in (worker_template, infra_template):
        assert "OriginAccessControlAlreadyExists" in content
        assert "origin access control[^[:cntrl:]]*already exists" in content
        assert "WARNING: duplicate/already-existing resource detected; continuing without failure." in content

    assert "BucketAlreadyOwnedByYou" in worker_template
    assert "shared S3.9 destination bucket already exists and is owned" in worker_template


def test_infra_run_all_template_merges_cloudfront_oac_preflight_tfvars(tmp_path: Path) -> None:
    run_all_path = tmp_path / "run_all.sh"
    actions_dir = tmp_path / "actions" / "action-one"
    scripts_dir = actions_dir / "scripts"
    bin_dir = tmp_path / "bin"
    capture_path = tmp_path / "captured.auto.tfvars.json"
    terraform_log = tmp_path / "terraform.log"

    run_all_path.write_text(
        Path("infrastructure/templates/run_all.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    run_all_path.chmod(0o755)
    scripts_dir.mkdir(parents=True)
    bin_dir.mkdir()

    (actions_dir / "s3_cloudfront_oac_private_s3.tf").write_text("# oac bundle\n", encoding="utf-8")
    (actions_dir / "providers.tf").write_text("# providers\n", encoding="utf-8")
    (actions_dir / "terraform.auto.tfvars.json").write_text(
        json.dumps({"existing_bucket_policy_json": "{\"Version\":\"2012-10-17\"}"}) + "\n",
        encoding="utf-8",
    )
    (actions_dir / "security_autopilot.auto.tfvars.json").write_text(
        json.dumps({"preserve_me": "yes"}) + "\n",
        encoding="utf-8",
    )
    (actions_dir / "cloudfront_reuse_query.json").write_text(
        json.dumps({"bucket_name": "my-bucket"}) + "\n",
        encoding="utf-8",
    )
    (scripts_dir / "cloudfront_oac_discovery.py").write_text(
        (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import sys\n"
            "json.load(sys.stdin)\n"
            "print(json.dumps({\n"
            "  'cloudfront_reuse_mode': 'reuse_distribution',\n"
            "  'reuse_oac_id': 'OAC123',\n"
            "  'reuse_distribution_id': 'DIST123',\n"
            "  'reuse_distribution_arn': 'arn:aws:cloudfront::123456789012:distribution/DIST123',\n"
            "  'reuse_distribution_domain_name': 'd123.cloudfront.net'\n"
            "}))\n"
        ),
        encoding="utf-8",
    )
    (scripts_dir / "cloudfront_oac_discovery.py").chmod(0o755)

    (bin_dir / "aws").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (bin_dir / "aws").chmod(0o755)
    (bin_dir / "terraform").write_text(
        (
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import shutil\n"
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "args = sys.argv[1:]\n"
            "Path(os.environ['BUNDLE_TEST_TERRAFORM_LOG']).open('a', encoding='utf-8').write(' '.join(args) + '\\n')\n"
            "if args[:2] == ['providers', 'mirror']:\n"
            "    mirror_dir = Path(args[-1])\n"
            "    provider_dir = mirror_dir / 'registry.terraform.io/hashicorp/aws/5.100.0/test'\n"
            "    provider_dir.mkdir(parents=True, exist_ok=True)\n"
            "    (provider_dir / 'terraform-provider-aws_v5.100.0_x5').write_text('provider', encoding='utf-8')\n"
            "    sys.exit(0)\n"
            "if args[:2] == ['providers', 'lock']:\n"
            "    Path('.terraform.lock.hcl').write_text('# lock\\n', encoding='utf-8')\n"
            "    sys.exit(0)\n"
            "if args and args[0] == 'init':\n"
            "    sys.exit(0)\n"
            "if args and args[0] in {'plan', 'apply'}:\n"
            "    src = Path('security_autopilot.auto.tfvars.json')\n"
            "    if src.is_file() and os.environ.get('BUNDLE_TEST_CAPTURE_TFVARS'):\n"
            "        shutil.copyfile(src, os.environ['BUNDLE_TEST_CAPTURE_TFVARS'])\n"
            "    sys.exit(0)\n"
            "sys.exit(0)\n"
        ),
        encoding="utf-8",
    )
    (bin_dir / "terraform").chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["BUNDLE_TEST_CAPTURE_TFVARS"] = str(capture_path)
    env["BUNDLE_TEST_TERRAFORM_LOG"] = str(terraform_log)

    completed = subprocess.run(
        [str(run_all_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    merged = json.loads(capture_path.read_text(encoding="utf-8"))
    assert merged["preserve_me"] == "yes"
    assert merged["cloudfront_reuse_mode"] == "reuse_distribution"
    assert merged["reuse_oac_id"] == "OAC123"
    assert merged["reuse_distribution_id"] == "DIST123"
    assert merged["reuse_distribution_arn"].endswith("/DIST123")
    assert merged["reuse_distribution_domain_name"] == "d123.cloudfront.net"
    original_tfvars = json.loads((actions_dir / "terraform.auto.tfvars.json").read_text(encoding="utf-8"))
    assert original_tfvars["existing_bucket_policy_json"] == "{\"Version\":\"2012-10-17\"}"
    assert "INFO: CloudFront/OAC reuse preflight mode=reuse_distribution" in completed.stdout


def test_infra_run_all_template_fails_closed_when_cloudfront_oac_preflight_fails(tmp_path: Path) -> None:
    run_all_path = tmp_path / "run_all.sh"
    actions_dir = tmp_path / "actions" / "action-one"
    scripts_dir = actions_dir / "scripts"
    bin_dir = tmp_path / "bin"
    summary_path = tmp_path / ".bundle-execution-summary.json"
    terraform_log = tmp_path / "terraform.log"
    action_id = str(uuid.uuid4())

    run_all_path.write_text(
        Path("infrastructure/templates/run_all.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    run_all_path.chmod(0o755)
    scripts_dir.mkdir(parents=True)
    bin_dir.mkdir()
    (tmp_path / "bundle_manifest.json").write_text(
        json.dumps(
            {
                "actions": [
                    {
                        "action_id": action_id,
                        "folder": "actions/action-one",
                        "has_runnable_terraform": True,
                    }
                ],
                "shared_execution_folders": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (actions_dir / "s3_cloudfront_oac_private_s3.tf").write_text("# oac bundle\n", encoding="utf-8")
    (actions_dir / "cloudfront_reuse_query.json").write_text("{}\n", encoding="utf-8")
    (scripts_dir / "cloudfront_oac_discovery.py").write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.stderr.write('boom\\n')\nsys.exit(1)\n",
        encoding="utf-8",
    )
    (scripts_dir / "cloudfront_oac_discovery.py").chmod(0o755)

    (bin_dir / "aws").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (bin_dir / "aws").chmod(0o755)
    (bin_dir / "terraform").write_text(
        (
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "args = sys.argv[1:]\n"
            "Path(os.environ['BUNDLE_TEST_TERRAFORM_LOG']).open('a', encoding='utf-8').write(' '.join(args) + '\\n')\n"
            "if args[:2] == ['providers', 'mirror']:\n"
            "    mirror_dir = Path(args[-1])\n"
            "    provider_dir = mirror_dir / 'registry.terraform.io/hashicorp/aws/5.100.0/test'\n"
            "    provider_dir.mkdir(parents=True, exist_ok=True)\n"
            "    (provider_dir / 'terraform-provider-aws_v5.100.0_x5').write_text('provider', encoding='utf-8')\n"
            "    sys.exit(0)\n"
            "if args[:2] == ['providers', 'lock']:\n"
            "    Path('.terraform.lock.hcl').write_text('# lock\\n', encoding='utf-8')\n"
            "    sys.exit(0)\n"
            "if args and args[0] == 'init':\n"
            "    sys.exit(0)\n"
            "if args and args[0] in {'plan', 'apply'}:\n"
            "    sys.exit(0)\n"
            "sys.exit(0)\n"
        ),
        encoding="utf-8",
    )
    (bin_dir / "terraform").chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["BUNDLE_TEST_TERRAFORM_LOG"] = str(terraform_log)

    completed = subprocess.run(
        [str(run_all_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 1
    assert "CloudFront/OAC reuse preflight failed" in completed.stdout
    assert "cloudfront_oac_preflight" in completed.stdout
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["action_results"] == [
        {
            "action_id": action_id,
            "execution_status": "failed",
            "execution_error_code": "bundle_runner_cloudfront_oac_preflight",
            "execution_error_message": "run_all.sh failed during cloudfront_oac_preflight for folder actions/action-one",
        }
    ]
    if terraform_log.exists():
        terraform_invocations = terraform_log.read_text(encoding="utf-8").splitlines()
        assert not any(line.startswith("init") for line in terraform_invocations)
        assert not any(line.startswith("plan") for line in terraform_invocations)
        assert not any(line.startswith("apply") for line in terraform_invocations)


def test_group_pr_bundle_manual_guidance_metadata_only_and_zero_executable_success() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    run.action.title = "Bucket one review"
    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two manual guidance",
    )
    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_bucket_block_public_access_standard",
            support_tier="review_required_bundle",
            decision_rationale="Needs approval before execution",
        ),
        _group_action_resolution_payload(
            action_id=second_action.id,
            strategy_id="s3_migrate_cloudfront_oac_private",
            support_tier="manual_guidance_only",
            decision_rationale="Manual cloud changes required",
        ),
    ]
    mock_session = _mock_group_session(run, [run.action, second_action])

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle") as mock_generate:
            execute_remediation_run_job(job)
            mock_generate.assert_not_called()

    assert run.status == RemediationRunStatus.success
    assert run.outcome == "Group PR bundle generated (2 actions)"
    files_by_path = _bundle_files_by_path(run)
    assert not any(path.endswith(".tf") for path in files_by_path)
    assert any(path.startswith("review_required/actions/") and path.endswith("decision.json") for path in files_by_path)
    assert any(path.startswith("manual_guidance/actions/") and path.endswith("decision.json") for path in files_by_path)
    assert "No executable Terraform action folders found under ${EXECUTION_ROOT}/." in files_by_path["run_all.sh"]
    manifest = json.loads(files_by_path["bundle_manifest.json"])
    assert manifest["runnable_action_count"] == 0
    assert manifest["tier_counts"] == {
        "executable": 0,
        "review_required": 1,
        "manual_guidance": 1,
    }
    finding_coverage = json.loads(files_by_path["finding_coverage.json"])
    assert len(finding_coverage["actions"]) == 2
    assert all(isinstance(item["finding_coverage"], dict) for item in finding_coverage["actions"])
    assert "Needs approval before execution" in files_by_path["decision_log.md"]
    assert "Manual cloud changes required" in files_by_path["decision_log.md"]


def test_group_pr_bundle_invalid_executable_folder_layout_fails_closed() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
    job["group_action_ids"] = [str(run.action.id)]
    job["action_resolutions"] = [
        _group_action_resolution_payload(
            action_id=run.action.id,
            strategy_id="s3_bucket_block_public_access_standard",
            support_tier="deterministic_bundle",
        )
    ]
    mock_session = _mock_group_session(run, [run.action])
    bad_bundle = {
        "format": "terraform",
        "files": [{"path": "README.md", "content": "no terraform here"}],
        "steps": ["step one"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=bad_bundle):
            execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.failed
    assert run.outcome == "PR bundle generation failed: invalid_grouped_bundle_layout"
    assert isinstance(run.artifacts, dict)
    pr_bundle_error = run.artifacts.get("pr_bundle_error")
    assert isinstance(pr_bundle_error, dict)
    assert pr_bundle_error.get("code") == "invalid_grouped_bundle_layout"


def test_group_pr_bundle_schema_v1_falls_back_to_top_level_strategy_fields() -> None:
    """Schema-v1 grouped PR bundle generation keeps using the legacy shared strategy fallback."""
    job = _make_job(mode="pr_only")
    job["schema_version"] = 1
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"

    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two hardening",
    )
    job["group_action_ids"] = [str(run.action.id), str(second_action.id)]
    job["strategy_id"] = "s3_migrate_cloudfront_oac_private"
    job["strategy_inputs"] = {"exempt_principals": ["arn:aws:iam::123456789012:role/legacy"]}
    job["risk_acknowledged"] = True
    mock_session = _mock_group_session(run, [run.action, second_action])

    bundle_one = {
        "format": "terraform",
        "files": [{"path": "providers.tf", "content": "# provider one"}],
        "steps": ["step one"],
    }
    bundle_two = {
        "format": "terraform",
        "files": [{"path": "providers.tf", "content": "# provider two"}],
        "steps": ["step two"],
    }

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=[bundle_one, bundle_two]) as mock_generate:
            execute_remediation_run_job(job)
            assert mock_generate.call_count == 2
            for call in mock_generate.call_args_list:
                _, kwargs = call
                assert kwargs.get("strategy_id") == "s3_migrate_cloudfront_oac_private"
                assert kwargs.get("strategy_inputs") == {
                    "exempt_principals": ["arn:aws:iam::123456789012:role/legacy"]
                }

    assert run.status == RemediationRunStatus.success
    assert isinstance(run.artifacts, dict)
    assert run.artifacts.get("selected_strategy") == "s3_migrate_cloudfront_oac_private"
    assert run.artifacts.get("strategy_inputs") == {
        "exempt_principals": ["arn:aws:iam::123456789012:role/legacy"]
    }
    assert run.artifacts.get("risk_acknowledged") is True


def test_pr_bundle_execution_plan_success() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = None
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    account_result = MagicMock()
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account_result.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    claim_result = MagicMock()
    claim_result.rowcount = 1
    mock_session.execute.side_effect = [exec_result, claim_result, account_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                mock_run_cmd.side_effect = [
                    {"command": "terraform init", "returncode": 0, "stdout": "", "stderr": ""},
                    {"command": "terraform plan", "returncode": 0, "stdout": "", "stderr": ""},
                    {"command": "terraform show", "returncode": 0, "stdout": "plan", "stderr": ""},
                ]
                execute_pr_bundle_execution_job(job)

    assert execution.status == RemediationRunExecutionStatus.awaiting_approval
    assert run.status == RemediationRunStatus.awaiting_approval
    assert isinstance(execution.workspace_manifest, dict)
    assert isinstance(execution.results, dict)
    assert execution.workspace_manifest.get("target_kind") == "single_run_root"
    assert execution.workspace_manifest.get("execution_root") is None
    assert execution.workspace_manifest.get("folders") == ["."]
    assert execution.results.get("action_results") == [
        {
            "action_id": str(run.action.id),
            "folder": ".",
            "status": "success",
            "error": None,
        }
    ]


def test_pr_bundle_execution_mixed_tier_plan_executes_only_executable_folders() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    review_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two review",
    )
    run.artifacts = {
        "group_bundle": {"action_ids": [str(run.action.id), str(review_action.id)]},
        "pr_bundle": {
            "files": [
                {
                    "path": "bundle_manifest.json",
                    "content": json.dumps(
                        {
                            "layout_version": "grouped_bundle_mixed_tier/v1",
                            "execution_root": "executable/actions",
                            "actions": [
                                {
                                    "action_id": str(run.action.id),
                                    "folder": f"executable/actions/01-{str(run.action.id)[:8]}",
                                    "support_tier": "deterministic_bundle",
                                    "tier": "executable",
                                    "outcome": "executable_bundle_generated",
                                    "has_runnable_terraform": True,
                                },
                                {
                                    "action_id": str(review_action.id),
                                    "folder": f"review_required/actions/02-{str(review_action.id)[:8]}",
                                    "support_tier": "review_required_bundle",
                                    "tier": "review_required",
                                    "outcome": "review_required_metadata_only",
                                    "has_runnable_terraform": False,
                                },
                            ],
                        }
                    ),
                },
                {
                    "path": f"executable/actions/01-{str(run.action.id)[:8]}/main.tf",
                    "content": 'terraform {}',
                },
                {
                    "path": f"review_required/actions/02-{str(review_action.id)[:8]}/decision.json",
                    "content": "{}",
                },
            ]
        },
    }
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = None
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    mock_session = _mock_execution_session(
        execution,
        account=account,
        grouped_actions=[run.action, review_action],
    )
    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._sync_group_run_results", return_value=None):
                with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                    mock_run_cmd.side_effect = [
                        {"command": "terraform init", "returncode": 0, "stdout": "", "stderr": ""},
                        {"command": "terraform plan", "returncode": 0, "stdout": "", "stderr": ""},
                        {"command": "terraform show", "returncode": 0, "stdout": "plan", "stderr": ""},
                    ]
                    execute_pr_bundle_execution_job(job)

    assert mock_run_cmd.call_count == 3
    called_dirs = [str(call.args[1]) for call in mock_run_cmd.call_args_list]
    assert any("/executable/actions/" in path for path in called_dirs)
    assert not any("/review_required/actions/" in path for path in called_dirs)
    assert execution.status == RemediationRunExecutionStatus.awaiting_approval
    assert isinstance(execution.workspace_manifest, dict)
    assert execution.workspace_manifest.get("target_kind") == "mixed_tier_grouped"
    assert execution.workspace_manifest.get("layout_version") == "grouped_bundle_mixed_tier/v1"
    assert execution.workspace_manifest.get("execution_root") == "executable/actions"
    assert execution.workspace_manifest.get("non_executable_action_count") == 1
    assert isinstance(execution.results, dict)
    assert execution.results.get("folder_count") == 1
    assert execution.results.get("non_executable_action_count") == 1
    action_results = execution.results.get("action_results")
    assert isinstance(action_results, list)
    assert action_results == [
        {
            "action_id": str(run.action.id),
            "folder": f"executable/actions/01-{str(run.action.id)[:8]}",
            "status": "success",
            "error": None,
        }
    ]
    non_executable_results = execution.results.get("non_executable_results")
    assert non_executable_results == [
        {
            "action_id": str(review_action.id),
            "folder": f"review_required/actions/02-{str(review_action.id)[:8]}",
            "support_tier": "review_required_bundle",
            "profile_id": "",
            "strategy_id": "",
            "reason": "review_required_metadata_only",
            "blocked_reasons": [],
            "tier": "review_required",
            "outcome": "review_required_metadata_only",
        }
    ]


def test_sync_group_run_results_keeps_non_executable_actions_non_failing() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    review_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two review",
    )
    execution = MagicMock()
    execution.phase = RemediationRunExecutionPhase.apply
    execution.status = RemediationRunExecutionStatus.success
    execution.started_at = datetime.now(timezone.utc)
    execution.completed_at = datetime.now(timezone.utc)
    execution.results = {
        "action_results": [
            {
                "action_id": str(run.action.id),
                "folder": "executable/actions/01-primary",
                "status": "success",
                "error": None,
            }
        ],
        "non_executable_results": [
            {
                "action_id": str(review_action.id),
                "folder": "review_required/actions/02-review",
                "support_tier": "review_required_bundle",
                "profile_id": "s3_review_profile",
                "strategy_id": "s3_review_strategy",
                "reason": "review_required_metadata_only",
                "blocked_reasons": ["needs approval"],
            }
        ],
    }

    group_run = MagicMock()
    group_run.id = uuid.uuid4()
    group_run.status = ActionGroupRunStatus.started
    session = MagicMock()
    added_rows = []
    session.add = MagicMock(side_effect=lambda row: added_rows.append(row))
    session.query.side_effect = [
        _mock_query_one_or_none(None),
        _mock_query_one_or_none(None),
    ]

    with patch(
        "backend.workers.jobs.remediation_run_execution._resolve_group_run_for_execution",
        return_value=(group_run, [run.action.id, review_action.id]),
    ):
        with patch("backend.workers.jobs.remediation_run_execution.record_execution_result") as mock_record:
            with patch("backend.workers.jobs.remediation_run_execution.evaluate_confirmation_for_action") as mock_eval:
                _sync_group_run_results(
                    session,
                    run=run,
                    execution=execution,
                    folder_results=[
                        {
                            "folder": "executable/actions/01-primary",
                            "action_id": str(run.action.id),
                            "status": "success",
                        }
                    ],
                )

    assert group_run.status == ActionGroupRunStatus.finished
    assert mock_record.call_count == 2
    assert mock_eval.call_count == 2
    review_row = next(row for row in added_rows if row.action_id == review_action.id)
    assert review_row.execution_status == ActionGroupExecutionStatus.unknown
    assert review_row.execution_error_code is None
    assert review_row.raw_result == {
        "action_id": str(review_action.id),
        "folder": "review_required/actions/02-review",
        "support_tier": "review_required_bundle",
        "profile_id": "s3_review_profile",
        "strategy_id": "s3_review_strategy",
        "reason": "review_required_metadata_only",
        "blocked_reasons": ["needs approval"],
    }


def test_pr_bundle_execution_legacy_grouped_bundle_still_executes_actions_root() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    second_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two hardening",
    )
    run.artifacts = {
        "group_bundle": {"action_ids": [str(run.action.id), str(second_action.id)]},
        "pr_bundle": {
            "files": [
                {"path": "actions/a/main.tf", "content": 'terraform {}'},
                {"path": "actions/b/main.tf", "content": 'terraform {}'},
            ]
        },
    }
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = {"fail_fast": False}
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    mock_session = _mock_execution_session(
        execution,
        account=account,
        grouped_actions=[run.action, second_action],
    )
    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._sync_group_run_results", return_value=None):
                with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                    mock_run_cmd.side_effect = [
                        {"command": "terraform init", "returncode": 0, "stdout": "", "stderr": ""},
                        {"command": "terraform plan", "returncode": 0, "stdout": "", "stderr": ""},
                        {"command": "terraform show", "returncode": 0, "stdout": "plan", "stderr": ""},
                        {"command": "terraform init", "returncode": 0, "stdout": "", "stderr": ""},
                        {"command": "terraform plan", "returncode": 0, "stdout": "", "stderr": ""},
                        {"command": "terraform show", "returncode": 0, "stdout": "plan", "stderr": ""},
                    ]
                    execute_pr_bundle_execution_job(job)

    assert mock_run_cmd.call_count == 6
    assert execution.status == RemediationRunExecutionStatus.awaiting_approval
    assert execution.workspace_manifest.get("target_kind") == "legacy_grouped"
    assert execution.workspace_manifest.get("execution_root") == "actions"
    assert execution.workspace_manifest.get("folders") == ["actions/a", "actions/b"]


def test_pr_bundle_execution_plan_missing_terraform_dependency_fails() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = None
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    account_result = MagicMock()
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account_result.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    claim_result = MagicMock()
    claim_result.rowcount = 1
    mock_session.execute.side_effect = [exec_result, claim_result, account_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                mock_run_cmd.side_effect = FileNotFoundError(2, "No such file or directory", "terraform")
                execute_pr_bundle_execution_job(job)

    assert execution.status == RemediationRunExecutionStatus.failed
    assert execution.error_summary == "runtime_missing_dependency"
    assert run.status == RemediationRunStatus.failed
    assert "terraform" in str(run.outcome or "")


def test_pr_bundle_execution_plan_fail_fast_persists_partial_results_with_error_detail() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = {"fail_fast": True}
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    account_result = MagicMock()
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account_result.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    claim_result = MagicMock()
    claim_result.rowcount = 1
    mock_session.execute.side_effect = [exec_result, claim_result, account_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                mock_run_cmd.return_value = {
                    "command": "terraform init",
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "Failed to query available provider packages",
                }
                execute_pr_bundle_execution_job(job)

    assert execution.status == RemediationRunExecutionStatus.failed
    assert run.status == RemediationRunStatus.failed
    assert isinstance(execution.results, dict)
    assert execution.results.get("folder_count") == 1
    assert execution.results.get("failed_folder_count") == 1
    assert "terraform init failed for ." in str(execution.error_summary or "")
    assert "Failed to query available provider packages" in str(execution.error_summary or "")


def test_pr_bundle_execution_apply_duplicate_sg_rule_is_treated_as_success() -> None:
    run = _mock_run_with_action("sg_restrict_public_ports")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.apply
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = {"fail_fast": True}
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    account_result = MagicMock()
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account_result.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    claim_result = MagicMock()
    claim_result.rowcount = 1
    mock_session.execute.side_effect = [exec_result, claim_result, account_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_apply",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "apply",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    duplicate_stderr = (
        "Error: creating VPC Security Group Rule\\n"
        "operation error EC2: AuthorizeSecurityGroupIngress, "
        "api error InvalidPermission.Duplicate"
    )
    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                mock_run_cmd.side_effect = [
                    {"command": "terraform init", "returncode": 0, "stdout": "", "stderr": ""},
                    {"command": "terraform plan", "returncode": 0, "stdout": "", "stderr": ""},
                    {"command": "terraform apply", "returncode": 1, "stdout": "", "stderr": duplicate_stderr},
                ]
                with patch("backend.workers.jobs.remediation_run_execution.enqueue_post_apply_reconcile") as mock_reconcile:
                    execute_pr_bundle_execution_job(job)

    assert execution.status == RemediationRunExecutionStatus.success
    assert run.status == RemediationRunStatus.success
    assert run.outcome == "SaaS apply completed successfully."
    assert isinstance(execution.results, dict)
    assert execution.results.get("failed_folder_count") == 0
    assert mock_reconcile.call_count == 1


def test_pr_bundle_execution_root_credentials_required_fails_fast() -> None:
    """SaaS plan/apply worker rejects root-key runs before any terraform command executes."""
    run = _mock_run_with_action("iam_root_access_key_absent")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = None
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    mock_session = MagicMock()
    mock_session.execute.side_effect = [exec_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
            execute_pr_bundle_execution_job(job)

    assert mock_run_cmd.call_count == 0
    assert execution.status == RemediationRunExecutionStatus.failed
    assert execution.error_summary == "root_credentials_required"
    assert run.status == RemediationRunStatus.failed
    assert "Root credentials required" in str(run.outcome)
    assert isinstance(run.artifacts, dict)
    marker = run.artifacts.get("manual_high_risk")
    assert isinstance(marker, dict)
    assert marker.get("marker") == MANUAL_HIGH_RISK_MARKER
    assert MANUAL_HIGH_RISK_MARKER in str(run.logs or "")


def test_pr_bundle_execution_mixed_tier_zero_executable_fails_precisely() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    manual_action = _mock_group_action(
        target_id="arn:aws:s3:::bucket-two",
        title="Bucket two manual guidance",
    )
    run.artifacts = {
        "group_bundle": {"action_ids": [str(run.action.id), str(manual_action.id)]},
        "pr_bundle": {
            "files": [
                {
                    "path": "bundle_manifest.json",
                    "content": json.dumps(
                        {
                            "layout_version": "grouped_bundle_mixed_tier/v1",
                            "execution_root": "executable/actions",
                            "actions": [
                                {
                                    "action_id": str(run.action.id),
                                    "folder": f"review_required/actions/01-{str(run.action.id)[:8]}",
                                    "support_tier": "review_required_bundle",
                                    "tier": "review_required",
                                    "outcome": "review_required_metadata_only",
                                    "has_runnable_terraform": False,
                                },
                                {
                                    "action_id": str(manual_action.id),
                                    "folder": f"manual_guidance/actions/02-{str(manual_action.id)[:8]}",
                                    "support_tier": "manual_guidance_only",
                                    "tier": "manual_guidance",
                                    "outcome": "manual_guidance_metadata_only",
                                    "has_runnable_terraform": False,
                                },
                            ],
                        }
                    ),
                },
                {
                    "path": f"review_required/actions/01-{str(run.action.id)[:8]}/decision.json",
                    "content": "{}",
                },
                {
                    "path": f"manual_guidance/actions/02-{str(manual_action.id)[:8]}/decision.json",
                    "content": "{}",
                },
            ]
        },
    }
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = None
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    mock_session = _mock_execution_session(
        execution,
        account=account,
        grouped_actions=[run.action, manual_action],
    )
    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._sync_group_run_results", return_value=None):
                with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                    execute_pr_bundle_execution_job(job)

    assert mock_run_cmd.call_count == 0
    assert execution.status == RemediationRunExecutionStatus.failed
    assert "mixed-tier bundle has no executable folders" in str(execution.error_summary or "")
    assert run.status == RemediationRunStatus.failed
    assert "mixed-tier bundle has no executable folders" in str(run.outcome or "")
    assert isinstance(execution.workspace_manifest, dict)
    assert execution.workspace_manifest.get("layout_version") == "grouped_bundle_mixed_tier/v1"
    assert execution.workspace_manifest.get("execution_root") == "executable/actions"
    assert execution.workspace_manifest.get("folders") == []
    assert execution.workspace_manifest.get("non_executable_action_count") == 2
    assert isinstance(execution.results, dict)
    assert execution.results.get("folder_count") == 0
    assert execution.results.get("non_executable_action_count") == 2
    non_executable_results = execution.results.get("non_executable_results")
    assert isinstance(non_executable_results, list)
    assert {item.get("reason") for item in non_executable_results} == {
        "review_required_metadata_only",
        "manual_guidance_metadata_only",
    }


def test_pr_bundle_execution_apply_hash_mismatch_fails() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.apply
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = {"bundle_hash": "different"}
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    account_result = MagicMock()
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account_result.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    claim_result = MagicMock()
    claim_result.rowcount = 1
    mock_session.execute.side_effect = [exec_result, claim_result, account_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_apply",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "apply",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                mock_run_cmd.side_effect = [
                    {"command": "terraform init", "returncode": 0, "stdout": "", "stderr": ""},
                    {"command": "terraform plan", "returncode": 0, "stdout": "", "stderr": ""},
                ]
                execute_pr_bundle_execution_job(job)

    assert mock_run_cmd.call_count == 0
    assert execution.status == RemediationRunExecutionStatus.failed
    assert run.status == RemediationRunStatus.failed


def test_pr_bundle_execution_plan_non_fail_fast_continues_folders() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {
        "pr_bundle": {
            "files": [
                {"path": "actions/a/main.tf", "content": 'terraform {}'},
                {"path": "actions/b/main.tf", "content": 'terraform {}'},
            ]
        }
    }
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = {"fail_fast": False}
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    account_result = MagicMock()
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account_result.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    claim_result = MagicMock()
    claim_result.rowcount = 1
    mock_session.execute.side_effect = [exec_result, claim_result, account_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution.assume_role", return_value=MagicMock()):
            with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
                mock_run_cmd.side_effect = [
                    {"command": "terraform init", "returncode": 1, "stdout": "", "stderr": "init fail"},
                    {"command": "terraform init", "returncode": 0, "stdout": "", "stderr": ""},
                    {"command": "terraform plan", "returncode": 0, "stdout": "", "stderr": ""},
                    {"command": "terraform show", "returncode": 0, "stdout": "plan", "stderr": ""},
                ]
                execute_pr_bundle_execution_job(job)

    assert mock_run_cmd.call_count == 4
    assert execution.status == RemediationRunExecutionStatus.failed
    assert run.status == RemediationRunStatus.failed
    assert isinstance(execution.results, dict)
    assert execution.results.get("folder_count") == 2
    assert execution.results.get("failed_folder_count") == 1


def test_pr_bundle_execution_claim_lost_skips_duplicate_delivery() -> None:
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.mode = RemediationRunMode.pr_only
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = run.tenant_id
    execution.phase = RemediationRunExecutionPhase.plan
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = None
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    claim_result = MagicMock()
    claim_result.rowcount = 0

    mock_session = MagicMock()
    mock_session.execute.side_effect = [exec_result, claim_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_plan",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "phase": "plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("backend.workers.jobs.remediation_run_execution.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run_execution._run_cmd") as mock_run_cmd:
            execute_pr_bundle_execution_job(job)

    assert mock_run_cmd.call_count == 0
    assert execution.status == RemediationRunExecutionStatus.queued
