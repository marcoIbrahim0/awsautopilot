"""
Tests for POST /api/internal/weekly-digest (Step 11.1).

Covers: 403 without/invalid secret, 403 deny-closed when DIGEST_CRON_SECRET is unset,
503 when queue is unset,
200 with valid secret and mocked DB/SQS.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app


def test_weekly_digest_403_without_header() -> None:
    """Without X-Digest-Cron-Secret header returns 403."""
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.DIGEST_CRON_SECRET = "secret123"
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_settings.AWS_REGION = "us-east-1"
        client = TestClient(app)
        resp = client.post("/api/internal/weekly-digest")
    assert resp.status_code == 403
    assert "X-Digest-Cron-Secret" in resp.json().get("detail", "")


def test_weekly_digest_403_wrong_secret() -> None:
    """Wrong X-Digest-Cron-Secret returns 403."""
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.DIGEST_CRON_SECRET = "secret123"
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_settings.AWS_REGION = "us-east-1"
        client = TestClient(app)
        resp = client.post(
            "/api/internal/weekly-digest",
            headers={"X-Digest-Cron-Secret": "wrong"},
        )
    assert resp.status_code == 403


def test_weekly_digest_403_secret_unset() -> None:
    """When DIGEST_CRON_SECRET is unset endpoint remains deny-closed with 403."""
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.DIGEST_CRON_SECRET = ""
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        client = TestClient(app)
        resp = client.post(
            "/api/internal/weekly-digest",
            headers={"X-Digest-Cron-Secret": "any"},
        )
    assert resp.status_code == 403
    assert "X-Digest-Cron-Secret" in resp.json().get("detail", "")


def test_weekly_digest_503_queue_unset() -> None:
    """When SQS_INGEST_QUEUE_URL is unset returns 503 after secret check."""
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.DIGEST_CRON_SECRET = "secret123"
        mock_settings.SQS_INGEST_QUEUE_URL = ""
        mock_settings.AWS_REGION = "us-east-1"
        client = TestClient(app)
        resp = client.post(
            "/api/internal/weekly-digest",
            headers={"X-Digest-Cron-Secret": "secret123"},
        )
    assert resp.status_code == 503
    assert "SQS_INGEST_QUEUE_URL" in resp.json().get("detail", "")


def test_weekly_digest_200_enqueues_per_tenant() -> None:
    """With valid secret and queue, lists tenants and enqueues one job per tenant."""
    tenant_id = uuid.uuid4()
    mock_tenant = MagicMock()
    mock_tenant.id = tenant_id

    async def mock_execute(statement):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_tenant]
        return result

    mock_db = AsyncMock()
    mock_db.execute = mock_execute

    async def override_get_db():
        yield mock_db

    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.DIGEST_CRON_SECRET = "secret123"
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_settings.AWS_REGION = "us-east-1"
        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs
            from backend.database import get_db
            app.dependency_overrides[get_db] = override_get_db
            try:
                client = TestClient(app)
                resp = client.post(
                    "/api/internal/weekly-digest",
                    headers={"X-Digest-Cron-Secret": "secret123"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["enqueued"] == 1
                assert data["tenants"] == 1
                mock_sqs.send_message.assert_called_once()
                body = __import__("json").loads(mock_sqs.send_message.call_args[1]["MessageBody"])
                assert body["job_type"] == "weekly_digest"
                assert body["tenant_id"] == str(tenant_id)
                assert "created_at" in body
            finally:
                app.dependency_overrides.pop(get_db, None)
