from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.models.enums import (
    RemediationRunExecutionPhase,
    RemediationRunExecutionStatus,
    RemediationRunMode,
    RemediationRunStatus,
)
from backend.workers.jobs.remediation_run_execution import execute_pr_bundle_execution_job


def _build_apply_execution(action_type: str, target_id: str | None = None, resource_id: str | None = None):
    tenant_id = uuid.uuid4()
    action = MagicMock()
    action.id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = "us-east-1"
    action.target_id = target_id
    action.resource_id = resource_id

    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant_id
    run.action_id = action.id
    run.action = action
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.pending
    run.logs = None
    run.outcome = None
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": 'terraform {}'}]}}

    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run = run
    execution.run_id = run.id
    execution.tenant_id = tenant_id
    execution.phase = RemediationRunExecutionPhase.apply
    execution.status = RemediationRunExecutionStatus.queued
    execution.workspace_manifest = {"fail_fast": True}
    execution.results = None
    execution.logs_ref = None
    execution.error_summary = None

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = execution
    claim_result = MagicMock()
    claim_result.rowcount = 1

    account = MagicMock()
    account.role_write_arn = "arn:aws:iam::123456789012:role/WriteRole"
    account.external_id = "tenant-ext-1"
    account.account_id = "123456789012"
    account_result = MagicMock()
    account_result.scalar_one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.execute.side_effect = [exec_result, claim_result, account_result]
    mock_session.flush = MagicMock()

    job = {
        "job_type": "execute_pr_bundle_apply",
        "execution_id": str(execution.id),
        "run_id": str(run.id),
        "tenant_id": str(tenant_id),
        "phase": "apply",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return run, execution, mock_session, job


def _run_apply_job(
    run: MagicMock,
    execution: MagicMock,
    mock_session: MagicMock,
    job: dict,
    *,
    reconcile_mode: str,
    prereq_result: dict,
) -> MagicMock:
    helper_settings = SimpleNamespace(
        CONTROL_PLANE_POST_APPLY_RECONCILE_ENABLED=True,
        CONTROL_PLANE_POST_APPLY_RECONCILE_MODE=reconcile_mode,
        SQS_INVENTORY_RECONCILE_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123/inventory",
        AWS_REGION="us-east-1",
        control_plane_inventory_services_list=["ec2", "s3"],
        CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD=500,
    )
    mock_sqs = MagicMock()

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
                    {"command": "terraform apply", "returncode": 0, "stdout": "", "stderr": ""},
                ]
                with patch("backend.workers.services.post_apply_reconcile.settings", helper_settings):
                    with patch(
                        "backend.workers.services.post_apply_reconcile.collect_reconciliation_queue_snapshot",
                        return_value={
                            "inventory_queue_depth": 0,
                            "inventory_queue_depth_threshold": 100,
                            "inventory_dlq_depth": 0,
                            "inventory_dlq_depth_threshold": 0,
                        },
                    ):
                        with patch(
                            "backend.workers.services.post_apply_reconcile.evaluate_reconciliation_prereqs",
                            return_value=prereq_result,
                        ):
                            with patch("backend.workers.services.post_apply_reconcile.boto3") as helper_boto3:
                                helper_boto3.client.return_value = mock_sqs
                                execute_pr_bundle_execution_job(job)

    assert execution.status == RemediationRunExecutionStatus.success
    assert run.status == RemediationRunStatus.success
    assert run.outcome == "SaaS apply completed successfully."
    return mock_sqs


def test_apply_success_targeted_derivable_enqueues_targeted_reconcile() -> None:
    run, execution, mock_session, job = _build_apply_execution(
        "s3_bucket_block_public_access",
        target_id="arn:aws:s3:::critical-bucket",
        resource_id=None,
    )
    mock_sqs = _run_apply_job(
        run,
        execution,
        mock_session,
        job,
        reconcile_mode="targeted_then_global",
        prereq_result={"ok": True, "reasons": [], "snapshot": {}},
    )

    assert mock_sqs.send_message.call_count == 1
    payload = json.loads(mock_sqs.send_message.call_args_list[0][1]["MessageBody"])
    assert payload["sweep_mode"] == "targeted"
    assert payload["service"] == "s3"
    assert payload["resource_ids"] == ["arn:aws:s3:::critical-bucket"]


def test_apply_success_includes_helper_bucket_inventory_in_targeted_reconcile() -> None:
    run, execution, mock_session, job = _build_apply_execution(
        "s3_bucket_access_logging",
        target_id="arn:aws:s3:::source-bucket",
        resource_id=None,
    )
    run.artifacts["pr_bundle"] = {
        "files": [{"path": "main.tf", "content": 'terraform {}'}],
        "metadata": {
            "helper_bucket_inventory": [
                {
                    "bucket_name": "source-bucket-access-logs",
                    "helper_bucket_role": "s3-access-logs",
                    "created": True,
                }
            ]
        },
    }
    mock_sqs = _run_apply_job(
        run,
        execution,
        mock_session,
        job,
        reconcile_mode="targeted_then_global",
        prereq_result={"ok": True, "reasons": [], "snapshot": {}},
    )

    assert mock_sqs.send_message.call_count == 1
    payload = json.loads(mock_sqs.send_message.call_args_list[0][1]["MessageBody"])
    assert payload["service"] == "s3"
    assert payload["sweep_mode"] == "targeted"
    assert payload["resource_ids"] == [
        "arn:aws:s3:::source-bucket",
        "source-bucket-access-logs",
    ]


def test_apply_success_unknown_derivation_falls_back_to_global_reconcile() -> None:
    run, execution, mock_session, job = _build_apply_execution(
        "custom_security_fix",
        target_id=None,
        resource_id=None,
    )
    mock_sqs = _run_apply_job(
        run,
        execution,
        mock_session,
        job,
        reconcile_mode="targeted_then_global",
        prereq_result={"ok": True, "reasons": [], "snapshot": {}},
    )

    assert mock_sqs.send_message.call_count == 2
    payloads = [json.loads(call[1]["MessageBody"]) for call in mock_sqs.send_message.call_args_list]
    services = sorted(payload["service"] for payload in payloads)
    assert services == ["ec2", "s3"]
    assert all(payload["sweep_mode"] == "global" for payload in payloads)
    assert all("resource_ids" not in payload for payload in payloads)


def test_apply_success_prereq_fail_skips_enqueue_and_keeps_apply_success() -> None:
    run, execution, mock_session, job = _build_apply_execution(
        "ec2_security_group_hardening",
        target_id="sg-1234",
        resource_id=None,
    )
    mock_sqs = _run_apply_job(
        run,
        execution,
        mock_session,
        job,
        reconcile_mode="targeted_then_global",
        prereq_result={
            "ok": False,
            "reasons": ["control_plane_stale"],
            "snapshot": {"control_plane_age_minutes": 87.0},
        },
    )

    assert mock_sqs.send_message.call_count == 0


def test_apply_success_persists_change_summary_artifact() -> None:
    run, execution, mock_session, job = _build_apply_execution(
        "sg_restrict_public_ports",
        target_id="sg-1234",
        resource_id="sg-1234",
    )
    run.approved_by = SimpleNamespace(email="ops@example.com")
    run.artifacts["strategy_inputs"] = {
        "access_mode": "close_and_revoke",
        "allowed_cidr": "10.0.0.0/24",
    }

    _run_apply_job(
        run,
        execution,
        mock_session,
        job,
        reconcile_mode="targeted_then_global",
        prereq_result={"ok": True, "reasons": [], "snapshot": {}},
    )

    assert isinstance(run.artifacts, dict)
    summary = run.artifacts.get("change_summary")
    assert isinstance(summary, dict)
    assert summary.get("run_id") == str(run.id)
    assert summary.get("applied_by") == "ops@example.com"
    assert isinstance(summary.get("applied_at"), str)
    changes = summary.get("changes")
    assert isinstance(changes, list)
    assert any(change.get("field") == "access mode" and change.get("after") == "close_and_revoke" for change in changes)
    assert any(change.get("field") == "allowed cidr" and change.get("after") == "10.0.0.0/24" for change in changes)
