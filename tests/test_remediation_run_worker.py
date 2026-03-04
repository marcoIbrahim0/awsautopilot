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

from backend.models.enums import (
    RemediationRunExecutionPhase,
    RemediationRunExecutionStatus,
    RemediationRunMode,
    RemediationRunStatus,
)
from backend.services.pr_bundle import PRBundleGenerationError
from backend.services.root_credentials_workflow import (
    MANUAL_HIGH_RISK_MARKER,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
)
from backend.workers.jobs.remediation_run import execute_remediation_run_job
from backend.workers.jobs.remediation_run_execution import execute_pr_bundle_execution_job
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


def _mock_account(role_write_arn: str | None = "arn:aws:iam::123456789012:role/WriteRole") -> MagicMock:
    acc = MagicMock()
    acc.role_write_arn = role_write_arn
    acc.external_id = "ext-tenant-123"
    acc.account_id = "123456789012"
    return acc


@pytest.fixture(autouse=True)
def _stub_download_bundle_group_run_sync():
    """
    Keep this suite focused on remediation run behavior under test.
    Group-run lifecycle sync is covered separately and adds extra execute() calls.
    """
    with patch("backend.workers.jobs.remediation_run._sync_download_bundle_group_runs", return_value=None):
        yield


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
    assert runner_template_source.startswith(("embedded", "s3://"))
    runner_template_version = str(metadata.get("runner_template_version") or "")
    assert runner_template_version
    assert metadata.get("requested_action_count") == 2
    assert metadata.get("generated_action_count") == 2
    assert metadata.get("skipped_action_count") == 0
    assert metadata.get("skipped_actions") == []
    group_bundle = run.artifacts.get("group_bundle")
    assert isinstance(group_bundle, dict)
    group_runner_template_source = str(group_bundle.get("runner_template_source") or "")
    assert group_runner_template_source.startswith(("embedded", "s3://"))
    assert group_bundle.get("runner_template_version") == runner_template_version
    assert group_bundle.get("generated_action_count") == 2
    assert group_bundle.get("skipped_action_count") == 0
    readme_group = next(
        f for f in files if isinstance(f, dict) and f.get("path") == "README_GROUP.txt"
    )
    readme_content = str(readme_group.get("content") or "")
    assert "chmod +x ./run_all.sh" in readme_content
    assert "./run_all.sh" in readme_content


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


def test_group_bundle_runner_template_uses_s3_when_configured() -> None:
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"
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

    bundle_one = {"format": "terraform", "files": [{"path": "providers.tf", "content": "# one"}], "steps": ["step one"]}
    bundle_two = {"format": "terraform", "files": [{"path": "providers.tf", "content": "# two"}], "steps": ["step two"]}

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", side_effect=[bundle_one, bundle_two]):
            with patch("backend.workers.jobs.remediation_run.settings") as mock_settings:
                mock_settings.SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI = "s3://central-templates/run-all/latest.sh"
                mock_settings.SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION = "v9.9.9"
                mock_settings.SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS = 300
                with patch("backend.workers.jobs.remediation_run.boto3.client") as mock_boto_client:
                    mock_s3 = MagicMock()
                    body = MagicMock()
                    body.read.return_value = b"#!/usr/bin/env bash\necho central-template\n"
                    mock_s3.get_object.return_value = {"Body": body, "ETag": '"abc123"'}
                    mock_boto_client.return_value = mock_s3
                    execute_remediation_run_job(job)

    pr_bundle = run.artifacts.get("pr_bundle")
    assert isinstance(pr_bundle, dict)
    metadata = pr_bundle.get("metadata")
    assert isinstance(metadata, dict)
    assert metadata.get("runner_template_source") == "s3://central-templates/run-all/latest.sh"
    assert metadata.get("runner_template_version") == "v9.9.9"
    files = pr_bundle.get("files")
    assert isinstance(files, list)
    run_all = next(f for f in files if isinstance(f, dict) and f.get("path") == "run_all.sh")
    assert "central-template" in str(run_all.get("content") or "")


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


def test_group_pr_bundle_strategy_fields_forwarded_to_each_action_generation() -> None:
    """Group PR bundle generation forwards strategy_id/strategy_inputs per action and preserves artifacts."""
    job = _make_job(mode="pr_only")
    run = _mock_run_with_action("s3_bucket_block_public_access")
    run.action.resource_id = "arn:aws:s3:::bucket-one"
    run.action.target_id = "arn:aws:s3:::bucket-one"

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
    job["strategy_id"] = "s3_migrate_cloudfront_oac_private"
    job["strategy_inputs"] = {"exempt_principals": ["arn:aws:iam::123456789012:role/legacy"]}
    job["risk_acknowledged"] = True

    result_run = MagicMock()
    result_run.scalar_one_or_none.return_value = run
    result_actions = MagicMock()
    result_actions.scalars.return_value.all.return_value = [run.action, second_action]

    mock_session = MagicMock()
    mock_session.execute.side_effect = [result_run, result_actions]
    mock_session.flush = MagicMock()

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
