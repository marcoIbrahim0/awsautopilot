"""
Contract tests for POST /api/aws/accounts/{account_id}/control-plane-synthetic-event.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app


def _url(account_id: str = "123456789012") -> str:
    return f"/api/aws/accounts/{account_id}/control-plane-synthetic-event"


def _params(tenant_id: str = "123e4567-e89b-12d3-a456-426614174000", region: str = "eu-north-1") -> dict:
    return {"tenant_id": tenant_id, "region": region}


async def _mock_db() -> AsyncGenerator[MagicMock, None]:
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    yield session


def test_control_plane_synthetic_event_404_when_account_missing(client: TestClient) -> None:
    tenant_uuid = uuid.uuid4()

    with (
        patch("backend.routers.aws_accounts.resolve_tenant_id", return_value=tenant_uuid),
        patch("backend.routers.aws_accounts.get_account_for_tenant", new=AsyncMock(return_value=None)),
    ):
        app.dependency_overrides[get_db] = _mock_db
        try:
            response = client.post(_url(), params=_params(str(tenant_uuid)))
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_control_plane_synthetic_event_200_enqueues_and_updates_status(client: TestClient) -> None:
    tenant_uuid = uuid.uuid4()
    account = SimpleNamespace(account_id="123456789012", regions=["eu-north-1", "us-east-1"])
    upsert_mock = AsyncMock()

    with (
        patch("backend.routers.aws_accounts.resolve_tenant_id", return_value=tenant_uuid),
        patch("backend.routers.aws_accounts.get_account_for_tenant", new=AsyncMock(return_value=account)),
        patch("backend.routers.aws_accounts._enqueue_control_plane_event") as enqueue_mock,
        patch("backend.routers.aws_accounts._upsert_control_plane_status", new=upsert_mock),
        patch("backend.routers.aws_accounts.settings") as settings_mock,
    ):
        settings_mock.SQS_EVENTS_FAST_LANE_QUEUE_URL = "https://sqs.eu-north-1.amazonaws.com/123/events-fast-lane"
        settings_mock.AWS_REGION = "eu-north-1"
        app.dependency_overrides[get_db] = _mock_db
        try:
            response = client.post(_url(), params=_params(str(tenant_uuid), "eu-north-1"))
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["enqueued"] == 1
    assert body["dropped"] == 0
    assert body["drop_reasons"] == {}
    enqueue_mock.assert_called_once()
    assert upsert_mock.await_count == 1


def test_control_plane_synthetic_event_400_when_region_not_configured(client: TestClient) -> None:
    tenant_uuid = uuid.uuid4()
    account = SimpleNamespace(account_id="123456789012", regions=["eu-north-1"])

    with (
        patch("backend.routers.aws_accounts.resolve_tenant_id", return_value=tenant_uuid),
        patch("backend.routers.aws_accounts.get_account_for_tenant", new=AsyncMock(return_value=account)),
        patch("backend.routers.aws_accounts.settings") as settings_mock,
    ):
        settings_mock.SQS_EVENTS_FAST_LANE_QUEUE_URL = "https://sqs.eu-north-1.amazonaws.com/123/events-fast-lane"
        settings_mock.AWS_REGION = "eu-north-1"
        app.dependency_overrides[get_db] = _mock_db
        try:
            response = client.post(_url(), params=_params(str(tenant_uuid), "us-east-1"))
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert "configured regions" in response.json()["detail"].lower()
