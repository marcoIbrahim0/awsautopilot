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


def test_list_accounts_includes_last_synced_at(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(tenant_id=tenant_id, role="admin")
    account = SimpleNamespace(
        id=uuid.uuid4(),
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        role_write_arn="arn:aws:iam::123456789012:role/WriteRole",
        regions=["us-east-1"],
        status=AwsAccountStatus.validated,
        last_validated_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    last_synced_at = datetime.now(timezone.utc).replace(microsecond=0)

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [account]
    freshness_result = MagicMock()
    freshness_result.all.return_value = [(account.account_id, last_synced_at)]

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, accounts_result, freshness_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> SimpleNamespace:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.get("/api/aws/accounts")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["last_synced_at"] is not None


def test_ingest_sync_non_local_queues_async_instead_of_404(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(tenant_id=tenant_id, role="admin")
    account_id = "123456789012"
    account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id=account_id,
        regions=["us-east-1"],
        status=AwsAccountStatus.validated,
    )

    tenant_result = _mock_exec_scalar(SimpleNamespace(id=tenant_id))
    account_result = _mock_exec_scalar(account)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[tenant_result, account_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> SimpleNamespace:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with (
        patch.object(aws_accounts_router.settings, "ENV", "prod"),
        patch.object(aws_accounts_router.settings, "SQS_INGEST_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue"),
        patch("backend.routers.aws_accounts._enqueue_ingest_jobs", return_value=["msg-1"]),
    ):
        try:
            response = client.post(f"/api/aws/accounts/{account_id}/ingest-sync", json={})
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    assert "queued" in response.json()["message"].lower()
