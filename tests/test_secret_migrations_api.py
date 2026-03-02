from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app


def _mock_user(*, role: str = "admin", tenant_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        role=role,
    )


def _mock_tx(source_ref: str, target_ref: str, status: str = "success") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_ref=source_ref,
        target_ref=target_ref,
        status=status,
        attempt_count=1,
        rollback_supported=True,
        rollback_token={"target_ref": target_ref},
        target_version="v1",
        message="applied",
        error_code=None,
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )


def _mock_run(tenant_id: uuid.UUID) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_connector="aws_secrets_manager",
        target_connector="aws_ssm_parameter_store",
        dry_run=False,
        rollback_on_failure=True,
        status="success",
        total_targets=1,
        succeeded_targets=1,
        failed_targets=0,
        rolled_back_targets=0,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
        completed_at=now,
        transactions=[_mock_tx("source/a", "target/a")],
    )


def _settings_enabled() -> SimpleNamespace:
    return SimpleNamespace(
        SECRET_MIGRATION_CONNECTORS_ENABLED=True,
        SECRET_MIGRATION_MAX_TARGETS=200,
        SECRET_MIGRATION_APPROVED_CI_BACKENDS="github_actions",
        SECRET_MIGRATION_GITHUB_CLI_BIN="gh",
    )


def _settings_disabled() -> SimpleNamespace:
    return SimpleNamespace(
        SECRET_MIGRATION_CONNECTORS_ENABLED=False,
        SECRET_MIGRATION_MAX_TARGETS=200,
        SECRET_MIGRATION_APPROVED_CI_BACKENDS="github_actions",
        SECRET_MIGRATION_GITHUB_CLI_BIN="gh",
    )


def test_create_secret_migration_run_no_auth_returns_401(client: TestClient) -> None:
    async def mock_get_current_user():
        raise HTTPException(status_code=401, detail="Not authenticated")

    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.secret_migrations.settings", _settings_enabled()):
        response = client.post(
            "/api/secret-migrations/runs",
            json={
                "source": {"connector": "aws_secrets_manager", "account_id": "029037611564"},
                "target": {"connector": "aws_ssm_parameter_store", "account_id": "029037611564"},
                "targets": [{"source_ref": "source/a", "target_ref": "target/a"}],
            },
            headers={"Idempotency-Key": "secmig-auth-401"},
        )
    assert response.status_code == 401


def test_create_secret_migration_run_member_forbidden_returns_403(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(role="member", tenant_id=tenant_id)
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_current_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.secret_migrations.settings", _settings_enabled()):
        response = client.post(
            "/api/secret-migrations/runs",
            json={
                "source": {"connector": "aws_secrets_manager", "account_id": "029037611564"},
                "target": {"connector": "aws_ssm_parameter_store", "account_id": "029037611564"},
                "targets": [{"source_ref": "source/a", "target_ref": "target/a"}],
            },
            headers={"Idempotency-Key": "secmig-member-403"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_required"


def test_create_secret_migration_run_happy_path_returns_201(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(role="admin", tenant_id=tenant_id)
    run = _mock_run(tenant_id)
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_current_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.secret_migrations.settings", _settings_enabled()):
        with patch(
            "backend.routers.secret_migrations.create_secret_migration_run_idempotent",
            AsyncMock(return_value=(run, True)),
        ):
            with patch(
                "backend.routers.secret_migrations.execute_secret_migration_run",
                AsyncMock(return_value=run),
            ):
                with patch(
                    "backend.routers.secret_migrations.get_secret_migration_run",
                    AsyncMock(return_value=run),
                ):
                    response = client.post(
                        "/api/secret-migrations/runs",
                        json={
                            "source": {"connector": "aws_secrets_manager", "account_id": "029037611564"},
                            "target": {"connector": "aws_ssm_parameter_store", "account_id": "029037611564"},
                            "targets": [{"source_ref": "source/a", "target_ref": "target/a"}],
                            "dry_run": False,
                            "rollback_on_failure": True,
                        },
                        headers={
                            "Idempotency-Key": "secmig-create-201",
                            "X-Correlation-Id": "corr-secmig-create",
                        },
                    )
    assert response.status_code == 201
    body = response.json()
    assert body["idempotency_replayed"] is False
    assert body["correlation_id"] == "corr-secmig-create"
    assert body["run"]["id"] == str(run.id)


def test_create_secret_migration_run_idempotent_replay_returns_200(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(role="admin", tenant_id=tenant_id)
    run = _mock_run(tenant_id)
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_current_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.secret_migrations.settings", _settings_enabled()):
        with patch(
            "backend.routers.secret_migrations.create_secret_migration_run_idempotent",
            AsyncMock(return_value=(run, False)),
        ):
            with patch(
                "backend.routers.secret_migrations.get_secret_migration_run",
                AsyncMock(return_value=run),
            ):
                response = client.post(
                    "/api/secret-migrations/runs",
                    json={
                        "source": {"connector": "aws_secrets_manager", "account_id": "029037611564"},
                        "target": {"connector": "aws_ssm_parameter_store", "account_id": "029037611564"},
                        "targets": [{"source_ref": "source/a", "target_ref": "target/a"}],
                    },
                    headers={"Idempotency-Key": "secmig-replay-200"},
                )
    assert response.status_code == 200
    assert response.json()["idempotency_replayed"] is True


def test_get_secret_migration_run_wrong_tenant_returns_404(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(role="admin", tenant_id=tenant_id)
    session = MagicMock()

    async def mock_get_db():
        yield session

    async def mock_get_current_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.secret_migrations.settings", _settings_enabled()):
        with patch(
            "backend.routers.secret_migrations.get_secret_migration_run",
            AsyncMock(return_value=None),
        ):
            response = client.get(f"/api/secret-migrations/runs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


def test_retry_secret_migration_run_happy_path_returns_200(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(role="admin", tenant_id=tenant_id)
    run = _mock_run(tenant_id)
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_get_db():
        yield session

    async def mock_get_current_user():
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.secret_migrations.settings", _settings_enabled()):
        with patch(
            "backend.routers.secret_migrations.get_secret_migration_run",
            AsyncMock(side_effect=[run, run]),
        ):
            with patch(
                "backend.routers.secret_migrations.retry_secret_migration_run",
                AsyncMock(return_value=run),
            ):
                response = client.post(f"/api/secret-migrations/runs/{run.id}/retry")
    assert response.status_code == 200
    assert response.json()["run"]["id"] == str(run.id)


def test_feature_flag_disabled_returns_404(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(role="admin", tenant_id=tenant_id)

    async def mock_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.secret_migrations.settings", _settings_disabled()):
        response = client.post(
            "/api/secret-migrations/runs",
            json={
                "source": {"connector": "aws_secrets_manager", "account_id": "029037611564"},
                "target": {"connector": "aws_ssm_parameter_store", "account_id": "029037611564"},
                "targets": [{"source_ref": "source/a", "target_ref": "target/a"}],
            },
            headers={"Idempotency-Key": "secmig-flag-off"},
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "feature_disabled"
