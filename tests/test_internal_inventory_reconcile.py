from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app


def test_reconcile_inventory_shard_enqueues_with_sweep_options() -> None:
    tenant_id = uuid.uuid4()
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/inventory"
        mock_settings.AWS_REGION = "us-east-1"
        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs

            client = TestClient(app)
            resp = client.post(
                "/api/internal/reconcile-inventory-shard",
                headers={"X-Control-Plane-Secret": "secret123"},
                json={
                    "shards": [
                        {
                            "tenant_id": str(tenant_id),
                            "account_id": "123456789012",
                            "region": "eu-north-1",
                            "service": "ec2",
                            "resource_ids": ["sg-123"],
                            "sweep_mode": "global",
                            "max_resources": 120,
                        }
                    ]
                },
            )

    assert resp.status_code == 200
    assert resp.json()["enqueued"] == 1
    body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
    assert body["sweep_mode"] == "global"
    assert body["max_resources"] == 120


def test_reconcile_recently_touched_enqueues_with_service_filters() -> None:
    tenant_id = uuid.uuid4()
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/inventory"
        mock_settings.AWS_REGION = "us-east-1"
        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs

            client = TestClient(app)
            resp = client.post(
                "/api/internal/reconcile-recently-touched",
                headers={"X-Control-Plane-Secret": "secret123"},
                json={
                    "tenant_id": str(tenant_id),
                    "lookback_minutes": 45,
                    "services": ["ec2", "s3"],
                    "max_resources": 150,
                },
            )

    assert resp.status_code == 200
    assert resp.json()["enqueued"] == 1
    body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
    assert body["services"] == ["ec2", "s3"]
    assert body["max_resources"] == 150


def test_reconcile_inventory_global_enqueues_per_account_region_service() -> None:
    tenant_id = uuid.uuid4()
    enabled_account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id="123456789012",
        regions=["eu-north-1", "us-east-1"],
        status="validated",
    )
    disabled_account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id="999999999999",
        regions=["eu-west-1"],
        status="disabled",
    )

    async def mock_execute(_statement):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [enabled_account, disabled_account]
        return result

    mock_db = AsyncMock()
    mock_db.execute = mock_execute

    async def override_get_db():
        yield mock_db

    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/inventory"
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.control_plane_inventory_services_list = ["ec2", "s3"]

        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs

            from backend.database import get_db

            app.dependency_overrides[get_db] = override_get_db
            try:
                client = TestClient(app)
                resp = client.post(
                    "/api/internal/reconcile-inventory-global",
                    headers={"X-Control-Plane-Secret": "secret123"},
                    json={
                        "tenant_id": str(tenant_id),
                        "services": ["ec2", "s3"],
                        "max_resources": 300,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["enqueued"] == 4
    assert data["accounts_considered"] == 1
    assert data["accounts_skipped_disabled"] == 1
    assert data["services"] == ["ec2", "s3"]
    assert mock_sqs.send_message.call_count == 4

    payload = json.loads(mock_sqs.send_message.call_args_list[0][1]["MessageBody"])
    assert payload["sweep_mode"] == "global"
    assert payload["max_resources"] == 300
