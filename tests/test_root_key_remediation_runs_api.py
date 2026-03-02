from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import (
    RootKeyExternalTaskStatus,
    RootKeyRemediationMode,
    RootKeyRemediationRunStatus,
    RootKeyRemediationState,
)
from backend.services.root_key_remediation_state_machine import (
    RootKeyErrorClassification,
    RootKeyErrorDisposition,
    RootKeyStateMachineError,
)


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_user(tenant_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        role="admin",
    )


def _mock_action(tenant_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_type="iam_root_access_key_absent",
        account_id="029037611564",
        region="eu-north-1",
        control_id="IAM.4",
    )


def _mock_run(
    *,
    state: RootKeyRemediationState,
    status: RootKeyRemediationRunStatus,
) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        control_id="IAM.4",
        action_id=uuid.uuid4(),
        finding_id=None,
        state=state,
        status=status,
        strategy_id="iam_root_key_disable",
        mode=RootKeyRemediationMode.manual,
        correlation_id="run-correlation",
        retry_count=0,
        lock_version=1,
        rollback_reason=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
        external_tasks=[],
        dependency_fingerprints=[],
        events=[],
        artifacts=[],
    )


def _mock_task(run_id: uuid.UUID, *, status: RootKeyExternalTaskStatus) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        run_id=run_id,
        task_type="await_manual_validation",
        status=status,
        due_at=None,
        completed_at=now if status == RootKeyExternalTaskStatus.completed else None,
        assigned_to_user_id=None,
        retry_count=0,
        rollback_reason=None,
        created_at=now,
        updated_at=now,
        task_result=None,
        actor_metadata=None,
    )


def _mock_dependency(run_id: uuid.UUID, *, unknown_dependency: bool) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        run_id=run_id,
        fingerprint_type="root_key_usage_cloudtrail",
        fingerprint_hash=uuid.uuid4().hex,
        status=SimpleNamespace(value="unknown" if unknown_dependency else "pass"),
        unknown_dependency=unknown_dependency,
        unknown_reason="unmanaged_cloudtrail_dependency" if unknown_dependency else None,
        fingerprint_payload={
            "service": "iam.amazonaws.com",
            "api_action": "UpdateAccessKey",
            "classification": "unknown" if unknown_dependency else "managed",
        },
        created_at=now,
        updated_at=now,
    )


def _mock_event(run_id: uuid.UUID, *, event_type: str, state: str) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        run_id=run_id,
        event_type=event_type,
        state=SimpleNamespace(value=state),
        status=SimpleNamespace(value="running"),
        rollback_reason=None,
        created_at=now,
        completed_at=None,
    )


def _mock_artifact(run_id: uuid.UUID, *, artifact_ref: str | None) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        run_id=run_id,
        artifact_type="transition_evidence",
        state=SimpleNamespace(value="migration"),
        status=SimpleNamespace(value="ready"),
        artifact_ref=artifact_ref,
        artifact_sha256=uuid.uuid4().hex,
        redaction_applied=True,
        created_at=now,
        completed_at=now,
    )


def _enable_root_key_settings() -> MagicMock:
    settings = MagicMock()
    settings.ROOT_KEY_SAFE_REMEDIATION_ENABLED = True
    settings.ROOT_KEY_SAFE_REMEDIATION_API_ENABLED = True
    settings.ROOT_KEY_SAFE_REMEDIATION_STRICT_TRANSITIONS = True
    settings.ROOT_KEY_SAFE_REMEDIATION_AUTO_ENABLED = True
    settings.ROOT_KEY_SAFE_REMEDIATION_EXECUTOR_ENABLED = False
    return settings


def _enable_root_key_executor_settings() -> MagicMock:
    settings = _enable_root_key_settings()
    settings.ROOT_KEY_SAFE_REMEDIATION_EXECUTOR_ENABLED = True
    return settings


def test_create_root_key_run_no_auth_returns_401(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    action = _mock_action(tenant_id)
    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(action))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return None

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        response = client.post(
            "/api/root-key-remediation-runs",
            json={"action_id": str(action.id)},
            headers={"Idempotency-Key": "rk-create-401"},
        )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "not_authenticated"
    assert isinstance(body.get("correlation_id"), str)


def test_get_root_key_run_wrong_tenant_returns_404(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        response = client.get(f"/api/root-key-remediation-runs/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


def test_get_root_key_run_includes_timeline_dependencies_and_artifacts(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
    )
    run.external_tasks = [_mock_task(run.id, status=RootKeyExternalTaskStatus.open)]
    run.dependency_fingerprints = [
        _mock_dependency(run.id, unknown_dependency=False),
        _mock_dependency(run.id, unknown_dependency=True),
    ]
    run.events = [
        _mock_event(run.id, event_type="create_run", state="discovery"),
        _mock_event(run.id, event_type="mark_needs_attention", state="needs_attention"),
    ]
    run.artifacts = [_mock_artifact(run.id, artifact_ref="s3://evidence-bucket/run-artifact.json")]

    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(run))

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        response = client.get(f"/api/root-key-remediation-runs/{run.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["id"] == str(run.id)
    assert body["dependency_count"] == 2
    assert body["event_count"] == 2
    assert body["artifact_count"] == 1
    assert len(body["dependencies"]) == 2
    assert len(body["events"]) == 2
    assert len(body["artifacts"]) == 1
    assert body["dependencies"][1]["unknown_dependency"] is True
    assert body["events"][0]["event_type"] == "create_run"
    assert body["artifacts"][0]["artifact_ref"] == "s3://evidence-bucket/run-artifact.json"


def test_create_root_key_run_happy_path_returns_201(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id)
    created_run = _mock_run(
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    migrated_run = _mock_run(
        state=RootKeyRemediationState.migration,
        status=RootKeyRemediationRunStatus.running,
    )
    migrated_run.id = created_run.id
    migrated_run.action_id = created_run.action_id

    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(action))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    service = MagicMock()
    service.create_run = AsyncMock(
        return_value=SimpleNamespace(
            run=created_run,
            state_changed=True,
            event_created=True,
            evidence_created=True,
            attempts=1,
        )
    )
    service.advance_to_migration = AsyncMock(
        return_value=SimpleNamespace(
            run=migrated_run,
            state_changed=True,
            event_created=True,
            evidence_created=True,
            attempts=1,
        )
    )

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            response = client.post(
                "/api/root-key-remediation-runs",
                json={
                    "action_id": str(action.id),
                    "mode": "manual",
                    "strategy_id": "iam_root_key_disable",
                },
                headers={
                    "Idempotency-Key": "rk-create-happy",
                    "X-Correlation-Id": "corr-create-happy",
                },
            )

    assert response.status_code == 201
    body = response.json()
    assert body["correlation_id"] == "corr-create-happy"
    assert body["run"]["state"] == "migration"
    assert body["idempotency_replayed"] is False


def test_create_root_key_run_idempotent_replay_returns_200(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id)
    first_run = _mock_run(
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    replay_run = _mock_run(
        state=RootKeyRemediationState.migration,
        status=RootKeyRemediationRunStatus.running,
    )
    replay_run.id = first_run.id

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_result(action), _scalar_result(action)]
    )
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    service = MagicMock()
    service.create_run = AsyncMock(
        side_effect=[
            SimpleNamespace(
                run=first_run,
                state_changed=True,
                event_created=True,
                evidence_created=True,
                attempts=1,
            ),
            SimpleNamespace(
                run=replay_run,
                state_changed=False,
                event_created=False,
                evidence_created=False,
                attempts=1,
            ),
        ]
    )
    service.advance_to_migration = AsyncMock(
        return_value=SimpleNamespace(
            run=replay_run,
            state_changed=True,
            event_created=True,
            evidence_created=True,
            attempts=1,
        )
    )

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            first = client.post(
                "/api/root-key-remediation-runs",
                json={"action_id": str(action.id)},
                headers={"Idempotency-Key": "rk-create-replay"},
            )
            second = client.post(
                "/api/root-key-remediation-runs",
                json={"action_id": str(action.id)},
                headers={"Idempotency-Key": "rk-create-replay"},
            )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["idempotency_replayed"] is True


def test_validate_invalid_transition_returns_409(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()

    classification = RootKeyErrorClassification(
        code="illegal_transition",
        message="Illegal transition from discovery to validation.",
        disposition=RootKeyErrorDisposition.terminal,
    )
    service = MagicMock()
    service.advance_to_validation = AsyncMock(
        side_effect=RootKeyStateMachineError(classification)
    )

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            response = client.post(
                f"/api/root-key-remediation-runs/{uuid.uuid4()}/validate",
                headers={"Idempotency-Key": "rk-validate-invalid"},
            )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "illegal_transition"
    assert isinstance(body["correlation_id"], str)


def test_disable_rollback_delete_happy_paths(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_result(run), _scalar_result(run), _scalar_result(run)]
    )

    service = MagicMock()
    transition_result = SimpleNamespace(
        run=run,
        state_changed=True,
        event_created=True,
        evidence_created=True,
        attempts=1,
    )
    service.start_disable_window = AsyncMock(return_value=transition_result)
    service.rollback = AsyncMock(return_value=transition_result)
    service.finalize_delete = AsyncMock(return_value=transition_result)

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            disable = client.post(
                f"/api/root-key-remediation-runs/{run.id}/disable",
                headers={"Idempotency-Key": "rk-disable"},
            )
            rollback = client.post(
                f"/api/root-key-remediation-runs/{run.id}/rollback",
                json={"reason": "manual_rollback"},
                headers={"Idempotency-Key": "rk-rollback"},
            )
            delete = client.post(
                f"/api/root-key-remediation-runs/{run.id}/delete",
                headers={"Idempotency-Key": "rk-delete"},
            )

    assert disable.status_code == 200
    assert rollback.status_code == 200
    assert delete.status_code == 200
    assert disable.json()["run"]["id"] == str(run.id)
    assert rollback.json()["run"]["id"] == str(run.id)
    assert delete.json()["run"]["id"] == str(run.id)


def test_disable_uses_executor_worker_when_enabled(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(run))

    transition_result = SimpleNamespace(
        run=run,
        state_changed=True,
        event_created=True,
        evidence_created=True,
        attempts=1,
    )
    worker = MagicMock()
    worker.execute_disable = AsyncMock(return_value=transition_result)
    service = MagicMock()
    service.start_disable_window = AsyncMock(return_value=transition_result)

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_executor_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationExecutorWorker",
            return_value=worker,
        ):
            with patch(
                "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
                return_value=service,
            ):
                response = client.post(
                    f"/api/root-key-remediation-runs/{run.id}/disable",
                    headers={"Idempotency-Key": "rk-disable-worker"},
                )

    assert response.status_code == 200
    assert worker.execute_disable.await_count == 1
    assert service.start_disable_window.await_count == 0


def test_complete_external_task_happy_path(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
    )
    task = _mock_task(run.id, status=RootKeyExternalTaskStatus.open)
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_result(run), _scalar_result(task), _scalar_result(run)]
    )
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.create_root_key_remediation_event_idempotent",
            new=AsyncMock(return_value=(MagicMock(), True)),
        ):
            response = client.post(
                f"/api/root-key-remediation-runs/{run.id}/external-tasks/{task.id}/complete",
                json={"result": {"check_id": "ok"}},
                headers={"Idempotency-Key": "rk-task-complete"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["task"]["status"] == "completed"
    assert body["idempotency_replayed"] is False


def test_complete_external_task_idempotent_replay_returns_true(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
    )
    task = _mock_task(run.id, status=RootKeyExternalTaskStatus.completed)
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_result(run), _scalar_result(task), _scalar_result(run)]
    )
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.create_root_key_remediation_event_idempotent",
            new=AsyncMock(return_value=(MagicMock(), False)),
        ):
            response = client.post(
                f"/api/root-key-remediation-runs/{run.id}/external-tasks/{task.id}/complete",
                json={"result": {"check_id": "ok"}},
                headers={"Idempotency-Key": "rk-task-complete-replay"},
            )

    assert response.status_code == 200
    assert response.json()["idempotency_replayed"] is True
