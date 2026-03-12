"""Phase 3 P1.4 approval-gate enforcement regressions."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import RemediationRunMode, RemediationRunStatus
from backend.services.direct_fix_approval import (
    DIRECT_FIX_APPROVAL_ARTIFACT_KEY,
    DIRECT_FIX_APPROVAL_PATH_API_CREATE,
    build_direct_fix_approval_metadata,
)
from backend.services.remediation_audit import AUDIT_EVENT_REMEDIATION_MUTATION_BLOCKED
from backend.workers.jobs.remediation_run import execute_remediation_run_job
from backend.workers.services.direct_fix import DirectFixResult


@pytest.fixture(autouse=True)
def _stub_download_bundle_group_run_sync():
    with patch("backend.workers.jobs.remediation_run._sync_download_bundle_group_runs", return_value=None):
        yield


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "approver@example.com"
    return user


def _mock_action(action_type: str = "enable_security_hub") -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.tenant_id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = "us-east-1"
    return action


def _mock_account() -> MagicMock:
    account = MagicMock()
    account.account_id = "123456789012"
    account.role_write_arn = "arn:aws:iam::123456789012:role/WriteRole"
    account.external_id = "ext-123"
    return account


def _mock_run(
    *,
    mode: RemediationRunMode,
    action_type: str = "s3_block_public_access",
    artifacts: dict | None = None,
) -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = uuid.uuid4()
    run.action_id = uuid.uuid4()
    run.mode = mode
    run.status = RemediationRunStatus.pending
    run.outcome = None
    run.logs = None
    run.artifacts = artifacts
    run.started_at = None
    run.completed_at = None
    run.updated_at = datetime.now(timezone.utc)
    run.approved_by_user_id = uuid.uuid4()

    action = MagicMock()
    action.id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = None if action_type == "s3_block_public_access" else "us-east-1"
    run.action = action
    return run


def _direct_fix_approval(
    *,
    approver_id: uuid.UUID,
    approval_path: str = DIRECT_FIX_APPROVAL_PATH_API_CREATE,
) -> dict[str, dict[str, str]]:
    return {
        DIRECT_FIX_APPROVAL_ARTIFACT_KEY: build_direct_fix_approval_metadata(
            approved_by_user_id=approver_id,
            approval_path=approval_path,
        )
    }


def _audit_event_types(session: MagicMock) -> list[str]:
    return [getattr(call.args[0], "event_type", "") for call in session.add.call_args_list if call.args]


def test_create_direct_fix_run_persists_allowlisted_approval_metadata(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant_id
    account = _mock_account()

    action_result = MagicMock()
    action_result.scalar_one_or_none.return_value = action
    account_result = MagicMock()
    account_result.scalar_one_or_none.return_value = account
    duplicate_result = MagicMock()
    duplicate_result.scalars.return_value.all.return_value = []

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[action_result, account_result, duplicate_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(run_obj: MagicMock) -> None:
        run_obj.created_at = datetime.now(timezone.utc)
        run_obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-approval-gate"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.routers.remediation_runs.probe_direct_fix_permissions",
                return_value=(True, None),
            ):
                try:
                    response = client.post(
                        "/api/remediation-runs",
                        json={
                            "action_id": str(action.id),
                            "mode": "direct_fix",
                            "strategy_id": "security_hub_enable_direct_fix",
                            "risk_acknowledged": True,
                        },
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 201
    created_run = session.add.call_args.args[0]
    approval = created_run.artifacts[DIRECT_FIX_APPROVAL_ARTIFACT_KEY]
    assert approval["approval_path"] == DIRECT_FIX_APPROVAL_PATH_API_CREATE
    assert approval["mode"] == "direct_fix"
    assert approval["approved_by_user_id"] == str(user.id)


def test_worker_blocks_spoofed_pr_only_run_from_direct_mutation_and_logs_audit() -> None:
    job = {
        "job_type": "remediation_run",
        "run_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "mode": "direct_fix",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    run = _mock_run(mode=RemediationRunMode.pr_only, artifacts={"pr_bundle": {"files": []}})

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    session = MagicMock()
    session.execute.side_effect = [run_result]
    session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.assume_role") as mock_assume:
            with patch("backend.workers.jobs.remediation_run.run_direct_fix") as mock_direct_fix:
                execute_remediation_run_job(job)

    assert mock_assume.call_count == 0
    assert mock_direct_fix.call_count == 0
    assert run.status == RemediationRunStatus.failed
    assert "run_mode_mismatch" in str(run.outcome or "")
    assert AUDIT_EVENT_REMEDIATION_MUTATION_BLOCKED in _audit_event_types(session)


def test_worker_blocks_unallowlisted_direct_fix_path_and_logs_audit() -> None:
    job = {
        "job_type": "remediation_run",
        "run_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "mode": "direct_fix",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    run = _mock_run(
        mode=RemediationRunMode.direct_fix,
        artifacts=_direct_fix_approval(
            approver_id=uuid.uuid4(),
            approval_path="api.remediation_runs.create_pr_only",
        ),
    )
    run.approved_by_user_id = uuid.UUID(
        run.artifacts[DIRECT_FIX_APPROVAL_ARTIFACT_KEY]["approved_by_user_id"]
    )

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    session = MagicMock()
    session.execute.side_effect = [run_result]
    session.flush = MagicMock()

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.assume_role") as mock_assume:
            with patch("backend.workers.jobs.remediation_run.run_direct_fix") as mock_direct_fix:
                execute_remediation_run_job(job)

    assert mock_assume.call_count == 0
    assert mock_direct_fix.call_count == 0
    assert run.status == RemediationRunStatus.failed
    assert "approval_path_not_allowlisted" in str(run.outcome or "")
    assert AUDIT_EVENT_REMEDIATION_MUTATION_BLOCKED in _audit_event_types(session)


def test_worker_executes_allowlisted_direct_fix_path_successfully() -> None:
    job = {
        "job_type": "remediation_run",
        "run_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "mode": "direct_fix",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    approver_id = uuid.uuid4()
    run = _mock_run(
        mode=RemediationRunMode.direct_fix,
        artifacts=_direct_fix_approval(approver_id=approver_id),
    )
    run.approved_by_user_id = approver_id
    account = _mock_account()

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    account_result = MagicMock()
    account_result.scalar_one_or_none.return_value = account
    session = MagicMock()
    session.execute.side_effect = [run_result, account_result]
    session.flush = MagicMock()

    fix_result = DirectFixResult(
        success=True,
        outcome="S3 Block Public Access enabled at account level",
        logs=["Pre-check", "Apply", "Post-check"],
    )

    with patch("backend.workers.jobs.remediation_run.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx
        with patch("backend.workers.jobs.remediation_run.assume_role", return_value=MagicMock()) as mock_assume:
            with patch("backend.workers.jobs.remediation_run.run_direct_fix", return_value=fix_result) as mock_direct_fix:
                execute_remediation_run_job(job)

    assert mock_assume.call_count == 1
    assert mock_direct_fix.call_count == 1
    assert run.status == RemediationRunStatus.success
    assert run.artifacts["direct_fix"]["post_check_passed"] is True
    assert AUDIT_EVENT_REMEDIATION_MUTATION_BLOCKED not in _audit_event_types(session)
