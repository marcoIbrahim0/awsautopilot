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
    tenant_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
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
    settings.ROOT_KEY_SAFE_REMEDIATION_DISCOVERY_ENABLED = False
    settings.ROOT_KEY_SAFE_REMEDIATION_EXECUTOR_ENABLED = False
    settings.ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED = False
    settings.ROOT_KEY_SAFE_REMEDIATION_CANARY_ENABLED = False
    settings.root_key_canary_percent = 100
    settings.root_key_canary_tenant_allowlist = set()
    settings.root_key_canary_account_allowlist = set()
    settings.ROOT_KEY_SAFE_REMEDIATION_KILL_SWITCH_ENABLED = False
    settings.ROOT_KEY_SAFE_REMEDIATION_OPS_METRICS_ENABLED = False
    settings.ROOT_KEY_SAFE_REMEDIATION_MONITOR_LOOKBACK_MINUTES = 15
    settings.ROOT_KEY_SAFE_REMEDIATION_OBSERVER_AWS_PROFILE = ""
    settings.ROOT_KEY_SAFE_REMEDIATION_OBSERVER_AWS_ACCESS_KEY_ID = ""
    settings.ROOT_KEY_SAFE_REMEDIATION_OBSERVER_AWS_SECRET_ACCESS_KEY = ""
    settings.ROOT_KEY_SAFE_REMEDIATION_OBSERVER_AWS_SESSION_TOKEN = ""
    settings.AWS_REGION = "eu-north-1"
    settings.ROLE_SESSION_NAME = "security-autopilot-session"
    return settings


def _enable_root_key_executor_settings() -> MagicMock:
    settings = _enable_root_key_settings()
    settings.ROOT_KEY_SAFE_REMEDIATION_EXECUTOR_ENABLED = True
    return settings


def _enable_root_key_discovery_settings() -> MagicMock:
    settings = _enable_root_key_settings()
    settings.ROOT_KEY_SAFE_REMEDIATION_DISCOVERY_ENABLED = True
    return settings


def _enable_root_key_canary_zero_settings() -> MagicMock:
    settings = _enable_root_key_settings()
    settings.ROOT_KEY_SAFE_REMEDIATION_CANARY_ENABLED = True
    settings.root_key_canary_percent = 0
    return settings


def _enable_root_key_kill_switch_settings() -> MagicMock:
    settings = _enable_root_key_settings()
    settings.ROOT_KEY_SAFE_REMEDIATION_KILL_SWITCH_ENABLED = True
    return settings


def _discovery_result(
    *,
    run_id: uuid.UUID,
    managed_count: int,
    unknown_count: int,
    partial_data: bool,
    eligible_for_auto_flow: bool,
    retries_used: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_id,
        fingerprints=[],
        managed_count=managed_count,
        unknown_count=unknown_count,
        eligible_for_auto_flow=eligible_for_auto_flow,
        partial_data=partial_data,
        retries_used=retries_used,
    )


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
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_executor_settings()):
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


def test_create_root_key_run_rejects_keep_exception_strategy(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id)
    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(action))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_settings()):
        response = client.post(
            "/api/root-key-remediation-runs",
            json={
                "action_id": str(action.id),
                "strategy_id": "iam_root_key_keep_exception",
            },
            headers={"Idempotency-Key": "rk-create-invalid-strategy"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_strategy_id"


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
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_executor_settings()):
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


def test_disable_rollback_happy_paths(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()

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
            with patch(
                "backend.routers.root_key_remediation_runs._latest_pause_control_event",
                new=AsyncMock(return_value=None),
            ):
                with patch(
                    "backend.routers.root_key_remediation_runs._load_tenant_run_with_children",
                    new=AsyncMock(return_value=run),
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

    assert disable.status_code == 200
    assert rollback.status_code == 200
    assert disable.json()["run"]["id"] == str(run.id)
    assert rollback.json()["run"]["id"] == str(run.id)


def test_delete_fails_closed_when_executor_disabled(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    run = _mock_run(
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()

    service = MagicMock()
    service.finalize_delete = AsyncMock()

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
                f"/api/root-key-remediation-runs/{run.id}/delete",
                headers={"Idempotency-Key": "rk-delete-disabled-executor"},
            )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "executor_unavailable"
    assert service.finalize_delete.await_count == 0


def test_create_root_key_run_routes_to_needs_attention_on_unknown_or_partial_discovery(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id)
    created_run = _mock_run(
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
        tenant_id=tenant_id,
    )
    attention_run = _mock_run(
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
        tenant_id=tenant_id,
    )
    attention_run.id = created_run.id
    attention_run.action_id = created_run.action_id
    attention_run.finding_id = created_run.finding_id

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
    service.mark_needs_attention = AsyncMock(
        return_value=SimpleNamespace(
            run=attention_run,
            state_changed=True,
            event_created=True,
            evidence_created=True,
            attempts=1,
        )
    )
    service.advance_to_migration = AsyncMock()

    discovery = MagicMock()
    discovery.discover_and_classify = AsyncMock(
        return_value=_discovery_result(
            run_id=created_run.id,
            managed_count=1,
            unknown_count=1,
            partial_data=True,
            eligible_for_auto_flow=False,
            retries_used=2,
        )
    )

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_discovery_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            with patch(
                "backend.routers.root_key_remediation_runs.RootKeyUsageDiscoveryService",
                return_value=discovery,
            ):
                response = client.post(
                    "/api/root-key-remediation-runs",
                    json={"action_id": str(action.id)},
                    headers={"Idempotency-Key": "rk-create-needs-attention-discovery"},
                )

    assert response.status_code == 201
    body = response.json()
    assert body["run"]["state"] == "needs_attention"
    assert service.mark_needs_attention.await_count == 1
    assert service.advance_to_migration.await_count == 0


def test_create_root_key_run_routes_to_migration_on_safe_discovery(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id)
    created_run = _mock_run(
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
        tenant_id=tenant_id,
    )
    migrated_run = _mock_run(
        state=RootKeyRemediationState.migration,
        status=RootKeyRemediationRunStatus.running,
        tenant_id=tenant_id,
    )
    migrated_run.id = created_run.id
    migrated_run.action_id = created_run.action_id
    migrated_run.finding_id = created_run.finding_id

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
    service.mark_needs_attention = AsyncMock()

    discovery = MagicMock()
    discovery.discover_and_classify = AsyncMock(
        return_value=_discovery_result(
            run_id=created_run.id,
            managed_count=2,
            unknown_count=0,
            partial_data=False,
            eligible_for_auto_flow=True,
            retries_used=0,
        )
    )

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_discovery_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            with patch(
                "backend.routers.root_key_remediation_runs.RootKeyUsageDiscoveryService",
                return_value=discovery,
            ):
                response = client.post(
                    "/api/root-key-remediation-runs",
                    json={"action_id": str(action.id)},
                    headers={"Idempotency-Key": "rk-create-safe-discovery"},
                )

    assert response.status_code == 201
    body = response.json()
    assert body["run"]["state"] == "migration"
    assert service.advance_to_migration.await_count == 1
    assert service.mark_needs_attention.await_count == 0


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
    settings_obj = _enable_root_key_executor_settings()
    settings_obj.ROOT_KEY_SAFE_REMEDIATION_OBSERVER_AWS_PROFILE = "observer-profile"
    account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id=run.account_id,
        role_read_arn=f"arn:aws:iam::{run.account_id}:role/ReadRole",
        external_id="ext-observer",
    )
    session.execute = AsyncMock(return_value=_scalar_result(account))
    base_session = MagicMock()
    base_sts = MagicMock()
    base_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIATEMP00000001",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
        }
    }
    base_session.client.return_value = base_sts
    observer_session = MagicMock()
    with patch("backend.routers.root_key_remediation_runs.settings", settings_obj):
        with patch(
            "backend.routers.root_key_remediation_runs._latest_pause_control_event",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "backend.routers.root_key_remediation_runs._load_tenant_run_with_children",
                new=AsyncMock(return_value=run),
            ):
                with patch(
                    "backend.routers.root_key_remediation_runs.boto3.Session",
                    side_effect=[base_session, observer_session],
                ):
                    with patch(
                        "backend.routers.root_key_remediation_runs.RootKeyRemediationExecutorWorker",
                        return_value=worker,
                    ) as worker_ctor:
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
    observer_factory = worker_ctor.call_args.kwargs["observer_session_factory"]
    assert observer_factory(run.account_id, run.region) is observer_session
    base_sts.assume_role.assert_called_once()


def test_disable_fails_closed_when_observer_context_is_unavailable(client: TestClient) -> None:
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
        return_value=_scalar_result(
            SimpleNamespace(
                tenant_id=tenant_id,
                account_id=run.account_id,
                role_read_arn=f"arn:aws:iam::{run.account_id}:role/ReadRole",
                external_id="ext-observer",
            )
        )
    )

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_executor_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs._load_tenant_run_with_children",
            new=AsyncMock(return_value=run),
        ):
            with patch(
                "backend.routers.root_key_remediation_runs.RootKeyRemediationExecutorWorker",
            ) as worker_ctor:
                response = client.post(
                    f"/api/root-key-remediation-runs/{run.id}/disable",
                    headers={"Idempotency-Key": "rk-disable-no-observer"},
                )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "observer_context_unavailable"
    worker_ctor.assert_not_called()


def test_disable_fails_closed_when_observer_profile_cannot_load(client: TestClient) -> None:
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
        return_value=_scalar_result(
            SimpleNamespace(
                tenant_id=tenant_id,
                account_id=run.account_id,
                role_read_arn=f"arn:aws:iam::{run.account_id}:role/ReadRole",
                external_id="ext-observer",
            )
        )
    )

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    settings_obj = _enable_root_key_executor_settings()
    settings_obj.ROOT_KEY_SAFE_REMEDIATION_OBSERVER_AWS_PROFILE = "missing-profile"
    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", settings_obj):
        with patch(
            "backend.routers.root_key_remediation_runs._load_tenant_run_with_children",
            new=AsyncMock(return_value=run),
        ):
            with patch(
                "backend.routers.root_key_remediation_runs.boto3.Session",
                side_effect=RuntimeError("profile not found"),
            ):
                with patch(
                    "backend.routers.root_key_remediation_runs.RootKeyRemediationExecutorWorker",
                ) as worker_ctor:
                    response = client.post(
                        f"/api/root-key-remediation-runs/{run.id}/disable",
                        headers={"Idempotency-Key": "rk-disable-bad-observer-profile"},
                    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "observer_context_unavailable"
    assert payload["error"]["details"]["reason"] == "observer_profile_unavailable:RuntimeError"
    worker_ctor.assert_not_called()


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
            with patch(
                "backend.routers.root_key_remediation_runs._latest_pause_control_event",
                new=AsyncMock(return_value=None),
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
            with patch(
                "backend.routers.root_key_remediation_runs._latest_pause_control_event",
                new=AsyncMock(return_value=None),
            ):
                response = client.post(
                    f"/api/root-key-remediation-runs/{run.id}/external-tasks/{task.id}/complete",
                    json={"result": {"check_id": "ok"}},
                    headers={"Idempotency-Key": "rk-task-complete-replay"},
                )

    assert response.status_code == 200
    assert response.json()["idempotency_replayed"] is True


def test_create_root_key_run_canary_not_selected_returns_409(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id)
    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(action))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_canary_zero_settings()):
        response = client.post(
            "/api/root-key-remediation-runs",
            json={"action_id": str(action.id)},
            headers={"Idempotency-Key": "rk-create-canary-blocked"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "canary_not_selected"


def test_create_root_key_run_canary_override_logs_reason(client: TestClient) -> None:
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
    override_event_mock = AsyncMock(return_value=(MagicMock(), True))

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_canary_zero_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            with patch(
                "backend.routers.root_key_remediation_runs.create_root_key_remediation_event_idempotent",
                override_event_mock,
            ):
                response = client.post(
                    "/api/root-key-remediation-runs",
                    json={"action_id": str(action.id)},
                    headers={
                        "Idempotency-Key": "rk-create-canary-override",
                        "X-Operator-Override-Reason": "manual canary approval",
                    },
                )

    assert response.status_code == 201
    assert override_event_mock.await_count >= 1
    payload = override_event_mock.await_args_list[-1].kwargs["payload"]
    assert payload["operation"] == "create_run"
    assert payload["reason"] == "manual canary approval"


def test_kill_switch_blocks_mutating_endpoint(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    session = MagicMock()

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_kill_switch_settings()):
        response = client.post(
            f"/api/root-key-remediation-runs/{uuid.uuid4()}/validate",
            headers={"Idempotency-Key": "rk-kill-switch"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "kill_switch_enabled"


def test_pause_resume_correctness_blocks_transition_until_resumed(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    active_run = _mock_run(
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    paused_run = _mock_run(
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
    )
    paused_run.id = active_run.id
    resumed_run = _mock_run(
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    resumed_run.id = active_run.id
    pause_event = SimpleNamespace(
        event_type="pause_run",
        payload={"from_state": "validation"},
        created_at=datetime.now(timezone.utc),
        id=uuid.uuid4(),
    )

    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    service = MagicMock()
    service.pause_run = AsyncMock(
        return_value=SimpleNamespace(
            run=paused_run,
            state_changed=True,
            event_created=True,
            evidence_created=True,
            attempts=1,
        )
    )
    service.resume_run = AsyncMock(
        return_value=SimpleNamespace(
            run=resumed_run,
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
    with patch("backend.routers.root_key_remediation_runs.settings", _enable_root_key_executor_settings()):
        with patch(
            "backend.routers.root_key_remediation_runs.RootKeyRemediationStateMachineService",
            return_value=service,
        ):
            with patch(
                "backend.routers.root_key_remediation_runs._latest_pause_control_event",
                new=AsyncMock(side_effect=[None, None, pause_event, pause_event, pause_event]),
            ):
                with patch(
                    "backend.routers.root_key_remediation_runs._load_tenant_run_with_children",
                    new=AsyncMock(side_effect=[active_run, paused_run, resumed_run]),
                ):
                    pause = client.post(
                        f"/api/root-key-remediation-runs/{active_run.id}/pause",
                        json={"reason": "maintenance window"},
                        headers={"Idempotency-Key": "rk-pause"},
                    )
                    blocked = client.post(
                        f"/api/root-key-remediation-runs/{active_run.id}/delete",
                        headers={"Idempotency-Key": "rk-delete-while-paused"},
                    )
                    resume = client.post(
                        f"/api/root-key-remediation-runs/{active_run.id}/resume",
                        json={"reason": "maintenance complete"},
                        headers={"Idempotency-Key": "rk-resume"},
                    )

    assert pause.status_code == 200
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "run_paused"
    assert resume.status_code == 200
    assert resume.json()["run"]["state"] == "validation"


def test_get_root_key_ops_metrics_happy_path(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    session = MagicMock()

    async def mock_get_db():
        yield session

    async def mock_get_optional_user():
        return user

    settings_obj = _enable_root_key_settings()
    settings_obj.ROOT_KEY_SAFE_REMEDIATION_OPS_METRICS_ENABLED = True
    snapshot = SimpleNamespace(
        auto_success_rate=SimpleNamespace(numerator=3, denominator=4, rate=0.75),
        rollback_rate=SimpleNamespace(numerator=1, denominator=5, rate=0.2),
        needs_attention_rate=SimpleNamespace(numerator=2, denominator=5, rate=0.4),
        closure_pass_rate=SimpleNamespace(numerator=4, denominator=5, rate=0.8),
        mean_time_to_detect_unknown_dependency_seconds=12.5,
        unknown_dependency_sample_size=2,
    )

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.root_key_remediation_runs.settings", settings_obj):
        with patch(
            "backend.routers.root_key_remediation_runs.compute_root_key_ops_metrics",
            new=AsyncMock(return_value=snapshot),
        ):
            response = client.get("/api/root-key-remediation-runs/ops/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["auto_success_rate"]["rate"] == 0.75
    assert body["closure_pass_rate"]["numerator"] == 4
    assert body["unknown_dependency_sample_size"] == 2
