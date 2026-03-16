"""Phase 3 P1.3 regression coverage for repo-aware PR automation artifacts."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.models.enums import RemediationRunStatus
from backend.services.pr_automation import build_pr_automation_artifacts
from backend.services.remediation_handoff import build_run_artifact_metadata
from backend.utils.sqs import build_remediation_run_job_payload
from backend.workers.jobs.remediation_run import execute_remediation_run_job

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _action() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        action_type="sg_restrict_public_ports",
        account_id="123456789012",
        region="us-east-1",
        title="Restrict public admin ports",
        control_id="EC2.53",
        target_id="sg-0abc1234def567890",
        resource_id="sg-0abc1234def567890",
    )


def _config_action() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        action_type="aws_config_enabled",
        account_id="123456789012",
        region="eu-north-1",
        title="Enable AWS Config",
        control_id="Config.1",
        target_id="123456789012|eu-north-1|AWS::::Account:123456789012|Config.1",
        resource_id="123456789012",
    )


def _repo_target() -> dict[str, str]:
    return {
        "provider": "gitlab",
        "repository": "acme/infrastructure-live",
        "base_branch": "main",
        "head_branch": "autopilot/ec2-53-fix",
        "root_path": "terraform/network/security",
    }


def _control_rows() -> list[dict[str, str]]:
    return [
        {
            "control_id": "EC2.53",
            "framework_name": "CIS AWS Foundations Benchmark",
            "framework_control_code": "5.2",
            "control_title": "Ensure no security groups allow ingress from 0.0.0.0/0 to remote server administration ports",
            "description": "Restrict SSH and RDP exposure to trusted networks only.",
        },
        {
            "control_id": "EC2.53",
            "framework_name": "SOC 2",
            "framework_control_code": "CC6.6",
            "control_title": "Logical access restrictions",
            "description": "Network access to administrative interfaces is restricted and reviewed.",
        },
    ]


def _base_bundle() -> dict[str, object]:
    return {
        "format": "terraform",
        "files": [
            {"path": "providers.tf", "content": "# provider\n"},
            {
                "path": "sg_restrict_public_ports.tf",
                "content": 'resource "aws_security_group_rule" "lockdown" {}\n',
            },
        ],
        "steps": ["review", "apply"],
    }


def _snapshot_name(name: str) -> Path:
    return _FIXTURES_DIR / name


def _assert_snapshot(name: str, value: object) -> None:
    actual = json.loads(json.dumps(value, indent=2, sort_keys=True))
    expected = json.loads(_snapshot_name(name).read_text(encoding="utf-8"))
    assert actual == expected


def _make_job() -> dict[str, str]:
    return {
        "job_type": "remediation_run",
        "run_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "mode": "pr_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_run() -> MagicMock:
    run = MagicMock()
    run.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    run.tenant_id = uuid.uuid4()
    run.status = RemediationRunStatus.pending
    run.action_id = uuid.uuid4()
    run.outcome = None
    run.logs = None
    run.artifacts = None
    run.approved_by_user_id = None
    run.completed_at = None
    run.started_at = None
    run.action = _action()
    return run


@pytest.fixture(autouse=True)
def _stub_group_run_sync() -> None:
    with patch("backend.workers.jobs.remediation_run._sync_download_bundle_group_runs", return_value=None):
        yield


def test_build_remediation_run_job_payload_includes_repo_target() -> None:
    payload = build_remediation_run_job_payload(
        run_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        action_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        mode="pr_only",
        created_at="2026-03-12T08:00:00+00:00",
        repo_target=_repo_target(),
    )

    assert payload["repo_target"]["repository"] == "acme/infrastructure-live"
    assert payload["repo_target"]["base_branch"] == "main"


def test_repo_aware_pr_payload_matches_snapshot() -> None:
    _bundle, artifacts = build_pr_automation_artifacts(
        run_id="22222222-2222-2222-2222-222222222222",
        actions=[_action()],
        bundle=_base_bundle(),
        repo_target=_repo_target(),
        strategy_id=None,
        control_mapping_rows=_control_rows(),
    )

    _assert_snapshot("phase3_p1_3_pr_payload_snapshot.json", artifacts["pr_payload"])


def test_repo_aware_artifact_bundle_matches_snapshot() -> None:
    bundle, _artifacts = build_pr_automation_artifacts(
        run_id="22222222-2222-2222-2222-222222222222",
        actions=[_action()],
        bundle=_base_bundle(),
        repo_target=_repo_target(),
        strategy_id=None,
        control_mapping_rows=_control_rows(),
    )

    _assert_snapshot("phase3_p1_3_artifact_bundle_snapshot.json", bundle)


def test_repo_aware_worker_run_persists_payload_and_handoff_metadata() -> None:
    job = _make_job()
    run = _mock_run()
    run.artifacts = {"repo_target": _repo_target()}

    result_run = MagicMock()
    result_run.scalar_one_or_none.return_value = run
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result_run]
    mock_session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=_base_bundle()):
            with patch(
                "backend.workers.jobs.remediation_run.build_control_mapping_rows",
                return_value=_control_rows(),
            ):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert isinstance(run.artifacts, dict)
    assert run.artifacts["pr_payload"]["repo_target"]["repository"] == "acme/infrastructure-live"
    assert run.artifacts["diff_summary"]["file_count"] == 2
    assert run.artifacts["control_mapping_context"]["mapped_control_ids"] == ["EC2.53"]

    files = run.artifacts["pr_bundle"]["files"]
    paths = [item["path"] for item in files if isinstance(item, dict)]
    assert "pr_automation/pr_payload.json" in paths
    assert "pr_automation/control_mapping_context.json" in paths

    metadata = build_run_artifact_metadata(
        run_id=run.id,
        mode="pr_only",
        status="success",
        artifacts=run.artifacts,
        outcome=run.outcome,
        logs=run.logs,
        action_status="open",
    )
    implementation_keys = [artifact.key for artifact in metadata.implementation_artifacts]
    evidence_keys = {pointer.key for pointer in metadata.evidence_pointers}
    assert implementation_keys[:2] == ["pr_bundle", "pr_payload"]
    assert {"diff_summary", "rollback_notes", "control_mapping_context"} <= evidence_keys


def test_non_repo_bundle_flow_still_generates_bundle_without_pr_payload() -> None:
    job = _make_job()
    run = _mock_run()

    result_run = MagicMock()
    result_run.scalar_one_or_none.return_value = run
    mock_session = MagicMock()
    mock_session.execute.side_effect = [result_run]
    mock_session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.generate_pr_bundle", return_value=_base_bundle()):
            with patch(
                "backend.workers.jobs.remediation_run.build_control_mapping_rows",
                return_value=_control_rows(),
            ):
                execute_remediation_run_job(job)

    assert run.status == RemediationRunStatus.success
    assert isinstance(run.artifacts, dict)
    assert "pr_payload" not in run.artifacts
    assert run.artifacts["diff_summary"]["repo_target_configured"] is False
    assert run.artifacts["rollback_notes"]["entry_count"] == 1
    files = run.artifacts["pr_bundle"]["files"]
    paths = [item["path"] for item in files if isinstance(item, dict)]
    assert "providers.tf" in paths
    assert "pr_automation/diff_summary.json" in paths


def test_repo_aware_rollback_notes_use_bundle_specific_grouped_config_restore_path() -> None:
    action = _config_action()
    grouped_path = "executable/actions/01-config/rollback/aws_config_restore.py"
    bundle = {
        "format": "terraform",
        "files": [
            {"path": "bundle_manifest.json", "content": "{}\n"},
            {"path": grouped_path, "content": "# restore\n"},
        ],
        "steps": ["review", "apply"],
        "metadata": {
            "bundle_rollback_entries": {
                str(action.id): {
                    "path": grouped_path,
                    "runner": "python3",
                }
            }
        },
    }

    _bundle, artifacts = build_pr_automation_artifacts(
        run_id="22222222-2222-2222-2222-222222222222",
        actions=[action],
        bundle=bundle,
        repo_target=_repo_target(),
        strategy_id="config_enable_account_local_delivery",
        control_mapping_rows=_control_rows(),
    )

    assert artifacts["rollback_notes"]["entries"][0]["rollback_command"] == f"python3 ./{grouped_path}"
