from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app


def _valid_event(event_name: str = "AuthorizeSecurityGroupIngress") -> dict:
    return {
        "id": "evt-1",
        "time": "2026-02-10T10:00:00Z",
        "account": "123456789012",
        "region": "us-east-1",
        "source": "aws.ec2",
        "detail-type": "AWS API Call via CloudTrail",
        "detail": {
            "eventName": event_name,
            "eventCategory": "Management",
            "requestParameters": {"groupId": "sg-123"},
        },
    }


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_public_intake_403_missing_token(client: TestClient) -> None:
    resp = client.post("/api/control-plane/events", json=_valid_event())
    assert resp.status_code == 403


def test_public_intake_403_invalid_token(client: TestClient) -> None:
    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        yield session

    app.dependency_overrides[get_db] = override_get_db
    resp = client.post(
        "/api/control-plane/events",
        headers={"X-Control-Plane-Token": "bad"},
        json=_valid_event(),
    )
    assert resp.status_code == 403


def test_public_intake_200_enqueues_and_updates_status(client: TestClient) -> None:
    tenant = MagicMock()
    tenant.id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    account = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        # 1) tenant lookup 2) account lookup 3) upsert
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = tenant
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = account
        session = MagicMock()
        session.execute = AsyncMock(side_effect=[r1, r2, MagicMock()])
        session.commit = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = override_get_db

    with patch("backend.routers.control_plane.settings") as mock_settings:
        mock_settings.SQS_EVENTS_FAST_LANE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/events"
        with patch("backend.routers.control_plane.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs

            resp = client.post(
                "/api/control-plane/events",
                headers={"X-Control-Plane-Token": "cptok-test"},
                json=_valid_event(),
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["enqueued"] == 1
    assert body["dropped"] == 0
    assert mock_sqs.send_message.call_count == 1


def test_public_intake_drops_unsupported_event(client: TestClient) -> None:
    tenant = MagicMock()
    tenant.id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    account = MagicMock()

    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = tenant
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = account
        session = MagicMock()
        session.execute = AsyncMock(side_effect=[r1, r2])
        session.commit = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = override_get_db

    with patch("backend.routers.control_plane.settings") as mock_settings:
        mock_settings.SQS_EVENTS_FAST_LANE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/events"
        resp = client.post(
            "/api/control-plane/events",
            headers={"X-Control-Plane-Token": "cptok-test"},
            json=_valid_event(event_name="PutObject"),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["enqueued"] == 0
    assert body["dropped"] == 1

