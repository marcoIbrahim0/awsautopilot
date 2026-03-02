"""Wave 8 contracts for ingest-sync availability and account freshness field."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import backend.routers.aws_accounts as aws_accounts_router
from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus


def _mock_exec_scalar(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _validated_account(tenant_id: uuid.UUID, account_id: str = "123456789012") -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=tenant_id,
        account_id=account_id,
        role_read_arn=f"arn:aws:iam::{account_id}:role/ReadRole",
        role_write_arn=f"arn:aws:iam::{account_id}:role/WriteRole",
        regions=["us-east-1"],
        status=AwsAccountStatus.validated,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_validated_at=datetime.now(timezone.utc),
        id=uuid.uuid4(),
    )


def _override_db_and_user(session: MagicMock, user: SimpleNamespace | None) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    if user is not None:
        async def mock_get_optional_user() -> SimpleNamespace:
            return user

        app.dependency_overrides[get_optional_user] = mock_get_optional_user


def test_list_accounts_includes_last_synced_at(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(tenant_id=tenant_id, role="admin")
    account = _validated_account(tenant_id)
    last_synced_at = datetime.now(timezone.utc).replace(microsecond=0)

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [account]
    freshness_result = MagicMock()
    freshness_result.all.return_value = [(account.account_id, last_synced_at)]
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, accounts_result, freshness_result])

    _override_db_and_user(session, user)
    try:
        response = client.get("/api/aws/accounts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["last_synced_at"] is not None


def test_ingest_sync_non_local_admin_returns_200_and_queues(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    account = _validated_account(tenant_id)
    user = SimpleNamespace(tenant_id=tenant_id, role="admin")

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    account_result = _mock_exec_scalar(account)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, account_result])

    _override_db_and_user(session, user)
    with (
        patch.object(aws_accounts_router.settings, "ENV", "prod"),
        patch.object(aws_accounts_router.settings, "SQS_INGEST_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue"),
        patch("backend.routers.aws_accounts._enqueue_ingest_jobs", return_value=["msg-1"]),
    ):
        try:
            response = client.post(f"/api/aws/accounts/{account.account_id}/ingest-sync", json={})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "queued" in response.json()["message"].lower()


def test_ingest_sync_local_env_with_queue_prefers_async_enqueue(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    account = _validated_account(tenant_id)
    user = SimpleNamespace(tenant_id=tenant_id, role="admin")

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    account_result = _mock_exec_scalar(account)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, account_result])

    _override_db_and_user(session, user)
    with (
        patch.object(aws_accounts_router.settings, "ENV", "local"),
        patch.object(aws_accounts_router.settings, "SQS_INGEST_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue"),
        patch("backend.routers.aws_accounts._enqueue_ingest_jobs", return_value=["msg-1"]),
    ):
        try:
            response = client.post(f"/api/aws/accounts/{account.account_id}/ingest-sync", json={})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "queued" in response.json()["message"].lower()


def test_ingest_sync_enqueue_failure_returns_controlled_503_not_500(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    account = _validated_account(tenant_id)
    user = SimpleNamespace(tenant_id=tenant_id, role="admin")

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    account_result = _mock_exec_scalar(account)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, account_result])

    _override_db_and_user(session, user)
    with (
        patch.object(aws_accounts_router.settings, "ENV", "prod"),
        patch.object(aws_accounts_router.settings, "SQS_INGEST_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue"),
        patch("backend.routers.aws_accounts._enqueue_ingest_jobs", side_effect=RuntimeError("send failed")),
    ):
        try:
            response = client.post(f"/api/aws/accounts/{account.account_id}/ingest-sync", json={})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "Ingestion service unavailable"


def test_ingest_sync_invalid_account_returns_404(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(tenant_id=tenant_id, role="admin")

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    missing_account_result = _mock_exec_scalar(None)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, missing_account_result])

    _override_db_and_user(session, user)
    with patch.object(aws_accounts_router.settings, "ENV", "prod"):
        try:
            response = client.post("/api/aws/accounts/000000000000/ingest-sync", json={})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Account not found"


def test_ingest_sync_no_token_returns_401(client: TestClient) -> None:
    with patch.object(aws_accounts_router.settings, "ENV", "prod"):
        response = client.post("/api/aws/accounts/123456789012/ingest-sync", json={})
    assert response.status_code == 401


def test_ingest_sync_wrong_tenant_token_returns_404(client: TestClient) -> None:
    requester_tenant = uuid.uuid4()
    user = SimpleNamespace(tenant_id=requester_tenant, role="admin")

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=requester_tenant))
    missing_account_result = _mock_exec_scalar(None)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, missing_account_result])

    _override_db_and_user(session, user)
    with patch.object(aws_accounts_router.settings, "ENV", "prod"):
        try:
            response = client.post("/api/aws/accounts/123456789012/ingest-sync", json={})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Account not found"


def test_ingest_sync_member_token_is_deterministically_allowed(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    account = _validated_account(tenant_id)
    user = SimpleNamespace(tenant_id=tenant_id, role="member")

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    account_result = _mock_exec_scalar(account)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, account_result])

    _override_db_and_user(session, user)
    with (
        patch.object(aws_accounts_router.settings, "ENV", "prod"),
        patch.object(aws_accounts_router.settings, "SQS_INGEST_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue"),
        patch("backend.routers.aws_accounts._enqueue_ingest_jobs", return_value=["msg-1"]),
    ):
        try:
            response = client.post(f"/api/aws/accounts/{account.account_id}/ingest-sync", json={})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "queued" in response.json()["message"].lower()
