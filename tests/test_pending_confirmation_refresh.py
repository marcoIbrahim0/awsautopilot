from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.routers.internal import router as internal_router
from backend.services.pending_confirmation_refresh import enqueue_due_pending_confirmation_refreshes


def _state(*, tenant_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=tenant_id or uuid.uuid4(),
        latest_run_status_bucket="run_successful_pending_confirmation",
        last_confirmed_at=None,
        last_attempt_at=datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc),
        confirmation_refresh_last_enqueued_at=None,
        confirmation_refresh_next_due_at=datetime(2026, 3, 26, 12, 15, tzinfo=timezone.utc),
        confirmation_refresh_attempt_count=0,
    )


def _action(*, account_id: str, region: str) -> SimpleNamespace:
    return SimpleNamespace(account_id=account_id, region=region)


@pytest.mark.asyncio
async def test_enqueue_due_pending_confirmation_refreshes_dedupes_scopes() -> None:
    tenant_id = uuid.uuid4()
    state_one = _state(tenant_id=tenant_id)
    state_two = _state(tenant_id=tenant_id)
    state_three = _state(tenant_id=tenant_id)
    rows = [
        (state_one, _action(account_id="696505809372", region="eu-north-1")),
        (state_two, _action(account_id="696505809372", region="eu-north-1")),
        (state_three, _action(account_id="696505809372", region="us-east-1")),
    ]
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = rows
    db.execute = AsyncMock(return_value=execute_result)

    with patch("backend.services.pending_confirmation_refresh.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.eu-north-1.amazonaws.com/123/ingest"
        mock_settings.AWS_REGION = "eu-north-1"
        with patch("backend.services.pending_confirmation_refresh.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_sqs.send_message.side_effect = [
                {"MessageId": "msg-1"},
                {"MessageId": "msg-2"},
            ]
            mock_boto3.client.return_value = mock_sqs

            result = await enqueue_due_pending_confirmation_refreshes(
                db,
                tenant_ids=[tenant_id],
                limit=10,
                now=datetime(2026, 3, 26, 12, 15, tzinfo=timezone.utc),
            )

    assert result["due_states"] == 3
    assert result["enqueued_scopes"] == 2
    assert result["invalid_scope_states"] == 0
    assert mock_sqs.send_message.call_count == 2
    assert state_one.confirmation_refresh_attempt_count == 1
    assert state_two.confirmation_refresh_attempt_count == 1
    assert state_three.confirmation_refresh_attempt_count == 1
    assert state_one.confirmation_refresh_next_due_at == datetime(2026, 3, 26, 13, 15, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_enqueue_due_pending_confirmation_refreshes_stops_invalid_scope() -> None:
    tenant_id = uuid.uuid4()
    invalid_state = _state(tenant_id=tenant_id)
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [
        (invalid_state, _action(account_id="696505809372", region="")),
    ]
    db.execute = AsyncMock(return_value=execute_result)

    with patch("backend.services.pending_confirmation_refresh.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.eu-north-1.amazonaws.com/123/ingest"
        mock_settings.AWS_REGION = "eu-north-1"
        with patch("backend.services.pending_confirmation_refresh.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs

            result = await enqueue_due_pending_confirmation_refreshes(
                db,
                tenant_ids=[tenant_id],
                limit=10,
                now=datetime(2026, 3, 26, 12, 15, tzinfo=timezone.utc),
            )

    assert result["due_states"] == 1
    assert result["enqueued_scopes"] == 0
    assert result["invalid_scope_states"] == 1
    assert invalid_state.confirmation_refresh_next_due_at is None
    mock_sqs.send_message.assert_not_called()


def test_pending_confirmation_sweep_endpoint_requires_scheduler_secret() -> None:
    app = FastAPI()
    app.include_router(internal_router, prefix="/api")
    mock_db = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        with patch("backend.routers.internal.settings") as mock_settings:
            mock_settings.RECONCILIATION_SCHEDULER_SECRET = "sched-secret"
            mock_settings.CONTROL_PLANE_EVENTS_SECRET = ""
            response = client.post("/api/internal/pending-confirmation/sweep", json={})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403


def test_pending_confirmation_sweep_endpoint_returns_enqueued_summary() -> None:
    app = FastAPI()
    app.include_router(internal_router, prefix="/api")
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("backend.routers.internal.settings") as mock_settings:
            mock_settings.RECONCILIATION_SCHEDULER_SECRET = "sched-secret"
            mock_settings.CONTROL_PLANE_EVENTS_SECRET = ""
            with patch(
                "backend.routers.internal.enqueue_due_pending_confirmation_refreshes",
                new=AsyncMock(
                    return_value={
                        "evaluated_states": 1,
                        "due_states": 1,
                        "enqueued_scopes": 1,
                        "invalid_scope_states": 0,
                        "message_ids": ["msg-1"],
                        "scopes": [
                            {
                                "tenant_id": str(uuid.uuid4()),
                                "account_id": "696505809372",
                                "region": "eu-north-1",
                                "state_count": 1,
                            }
                        ],
                    }
                ),
            ) as sweep_mock:
                client = TestClient(app)
                response = client.post(
                    "/api/internal/pending-confirmation/sweep",
                    headers={"X-Reconciliation-Scheduler-Secret": "sched-secret"},
                    json={"account_ids": ["696505809372"], "regions": ["eu-north-1"]},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["enqueued_scopes"] == 1
    mock_db.commit.assert_awaited_once()
    sweep_mock.assert_awaited_once()
