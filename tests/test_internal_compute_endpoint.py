"""Tests for POST /api/internal/compute (Wave 8 scheduler contract)."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app


def test_internal_compute_403_without_secret() -> None:
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.RECONCILIATION_SCHEDULER_SECRET = "scheduler-secret"
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "fallback-secret"
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        client = TestClient(app)
        response = client.post("/api/internal/compute", json={})
    assert response.status_code == 403


def test_internal_compute_200_enqueues_jobs() -> None:
    tenant_id = uuid.uuid4()

    async def mock_execute(statement):
        result = MagicMock()
        result.all.return_value = [(tenant_id,)]
        return result

    mock_db = AsyncMock()
    mock_db.execute = mock_execute

    async def override_get_db():
        yield mock_db

    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.RECONCILIATION_SCHEDULER_SECRET = "scheduler-secret"
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "fallback-secret"
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_sqs.send_message.return_value = {"MessageId": "msg-1"}
            mock_boto3.client.return_value = mock_sqs
            from backend.database import get_db

            app.dependency_overrides[get_db] = override_get_db
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/internal/compute",
                    json={},
                    headers={"X-Reconciliation-Scheduler-Secret": "scheduler-secret"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["enqueued"] == 1
    assert body["tenant_ids"] == [str(tenant_id)]
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["job_type"] == "compute_actions"
    assert payload["tenant_id"] == str(tenant_id)
