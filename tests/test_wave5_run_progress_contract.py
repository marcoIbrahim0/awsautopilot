"""
Wave 5 Test 15 contract tests for remediation run execution progress payloads.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import (
    RemediationRunExecutionPhase,
    RemediationRunExecutionStatus,
    RemediationRunMode,
    RemediationRunStatus,
)


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "wave5@example.com"
    return user


def _mock_run(tenant_id: uuid.UUID, status: RemediationRunStatus) -> MagicMock:
    now = datetime.now(timezone.utc)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant_id
    run.action_id = uuid.uuid4()
    run.mode = RemediationRunMode.pr_only
    run.status = status
    run.outcome = "Run finished"
    run.started_at = now
    run.completed_at = now if status in {RemediationRunStatus.success, RemediationRunStatus.failed} else None
    run.created_at = now
    run.updated_at = now
    return run


def test_get_run_execution_returns_fallback_payload_for_completed_run(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(tenant_id, RemediationRunStatus.success)

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    execution_result = MagicMock()
    execution_result.scalars.return_value.first.return_value = None

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=[run_result, execution_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    response = client.get(f"/api/remediation-runs/{run.id}/execution")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "run_fallback"
    assert payload["status"] == "success"
    assert payload["current_step"] == "completed"
    assert payload["progress_percent"] == 100
    assert payload["completed_steps"] == 3
    assert payload["total_steps"] == 3
    assert payload["run_id"] == str(run.id)


def test_get_run_execution_returns_live_execution_progress_fields(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(tenant_id, RemediationRunStatus.running)

    now = datetime.now(timezone.utc)
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.run_id = run.id
    execution.phase = RemediationRunExecutionPhase.apply
    execution.status = RemediationRunExecutionStatus.running
    execution.workspace_manifest = {"fail_fast": True}
    execution.results = {"folders": []}
    execution.logs_ref = None
    execution.error_summary = None
    execution.started_at = now
    execution.completed_at = None
    execution.created_at = now
    execution.updated_at = now

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    execution_result = MagicMock()
    execution_result.scalars.return_value.first.return_value = execution

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=[run_result, execution_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    response = client.get(f"/api/remediation-runs/{run.id}/execution")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "execution"
    assert payload["id"] == str(execution.id)
    assert payload["status"] == "running"
    assert payload["current_step"] == "apply_running"
    assert payload["progress_percent"] == 60
    assert payload["completed_steps"] == 1
    assert payload["total_steps"] == 3


def test_get_run_execution_returns_404_for_out_of_tenant_run(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = None

    db_session = MagicMock()
    db_session.execute = AsyncMock(return_value=run_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    response = client.get(f"/api/remediation-runs/{uuid.uuid4()}/execution")

    assert response.status_code == 404
    detail = response.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Remediation run not found"


def test_get_run_execution_requires_authentication(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    app.dependency_overrides[get_db] = mock_get_db
    response = client.get(f"/api/remediation-runs/{uuid.uuid4()}/execution")
    assert response.status_code == 401
