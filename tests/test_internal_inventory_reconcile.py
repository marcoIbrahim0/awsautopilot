from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.internal import router as internal_router
from backend.utils.sqs import BACKFILL_FINDING_KEYS_JOB_TYPE


app = FastAPI()
app.include_router(internal_router, prefix="/api")


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
    mock_db = AsyncMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = SimpleNamespace(id=tenant_id, external_id="ext-1")
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [enabled_account, disabled_account]
    mock_db.execute = AsyncMock(side_effect=[tenant_result, accounts_result])

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
            with patch(
                "backend.routers.internal.collect_reconciliation_queue_snapshot",
                return_value={
                    "inventory_queue_depth": 0,
                    "inventory_queue_depth_threshold": 100,
                    "inventory_dlq_depth": 0,
                    "inventory_dlq_depth_threshold": 0,
                },
            ):
                with patch(
                    "backend.routers.internal.evaluate_reconciliation_prereqs_async",
                    new=AsyncMock(return_value={"ok": True, "reasons": [], "snapshot": {}}),
                ):
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
    assert data["skipped_prereq"] == 0
    assert data["prereq_reasons"] == []
    assert data["services"] == ["ec2", "s3"]
    assert mock_sqs.send_message.call_count == 4

    payload = json.loads(mock_sqs.send_message.call_args_list[0][1]["MessageBody"])
    assert payload["sweep_mode"] == "global"
    assert payload["max_resources"] == 300


def test_reconcile_inventory_global_prereq_failure_skips_enqueue() -> None:
    tenant_id = uuid.uuid4()
    enabled_account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id="123456789012",
        regions=["us-east-1"],
        status="validated",
    )

    mock_db = AsyncMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = SimpleNamespace(id=tenant_id, external_id="ext-1")
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [enabled_account]
    mock_db.execute = AsyncMock(side_effect=[tenant_result, accounts_result])

    async def override_get_db():
        yield mock_db

    prereq_result = {
        "ok": False,
        "reasons": ["control_plane_stale", "missing_resource_keys"],
        "snapshot": {"control_plane_age_minutes": 91.2, "missing_resource_keys": 4},
    }

    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/inventory"
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.control_plane_inventory_services_list = ["ec2", "s3"]

        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs
            with patch(
                "backend.routers.internal.collect_reconciliation_queue_snapshot",
                return_value={
                    "inventory_queue_depth": 0,
                    "inventory_queue_depth_threshold": 100,
                    "inventory_dlq_depth": 0,
                    "inventory_dlq_depth_threshold": 0,
                },
            ):
                with patch(
                    "backend.routers.internal.evaluate_reconciliation_prereqs_async",
                    new=AsyncMock(return_value=prereq_result),
                ):
                    from backend.database import get_db

                    app.dependency_overrides[get_db] = override_get_db
                    try:
                        client = TestClient(app)
                        resp = client.post(
                            "/api/internal/reconcile-inventory-global",
                            headers={"X-Control-Plane-Secret": "secret123"},
                            json={"tenant_id": str(tenant_id), "services": ["ec2", "s3"]},
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["enqueued"] == 0
    assert data["skipped_prereq"] == 1
    assert data["prereq_reasons"] == ["control_plane_stale", "missing_resource_keys"]
    assert len(data["prereq_failures"]) == 1
    assert data["prereq_failures"][0]["tenant_id"] == str(tenant_id)
    assert data["prereq_failures"][0]["account_id"] == "123456789012"
    assert data["prereq_failures"][0]["region"] == "us-east-1"
    assert mock_sqs.send_message.call_count == 0


def test_reconcile_inventory_global_all_tenants_enqueues_orchestration_jobs() -> None:
    tenant_id = uuid.uuid4()
    tenant_row = SimpleNamespace(id=tenant_id, external_id="ext-1")
    tenants_result = MagicMock()
    tenants_result.scalars.return_value.all.return_value = [tenant_row]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[tenants_result])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def override_get_db():
        yield mock_db

    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/inventory"
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.control_plane_inventory_services_list = ["ec2", "s3"]
        mock_settings.CONTROL_PLANE_SHADOW_MODE = True

        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs
            from backend.database import get_db

            app.dependency_overrides[get_db] = override_get_db
            try:
                client = TestClient(app)
                resp = client.post(
                    "/api/internal/reconcile-inventory-global-all-tenants",
                    headers={"X-Control-Plane-Secret": "secret123"},
                    json={"tenant_ids": [str(tenant_id)]},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["enqueued"] == 1
    assert data["orchestration_jobs_enqueued"] == 1
    assert data["orchestration_jobs_failed"] == 0
    assert data["tenants_considered"] == 1
    assert mock_sqs.send_message.call_count == 1
    payload = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
    assert payload["job_type"] == "reconcile_inventory_global_orchestration"
    assert payload["tenant_id"] == str(tenant_id)


def test_backfill_finding_keys_enqueues_chunked_job() -> None:
    async def override_get_db():
        yield AsyncMock()

    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/inventory"
        mock_settings.AWS_REGION = "us-east-1"
        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs

            from backend.database import get_db

            app.dependency_overrides[get_db] = override_get_db
            try:
                client = TestClient(app)
                resp = client.post(
                    "/api/internal/backfill-finding-keys",
                    headers={"X-Control-Plane-Secret": "secret123"},
                    json={
                        "enqueue_per_tenant": False,
                        "chunk_size": 250,
                        "max_chunks": 4,
                        "include_stale": True,
                        "auto_continue": True,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["enqueued"] == 1
    body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
    assert body["job_type"] == BACKFILL_FINDING_KEYS_JOB_TYPE
    assert body["chunk_size"] == 250
    assert body["max_chunks"] == 4
    assert body["include_stale"] is True


def test_reconciliation_schedule_tick_enqueues_due_account() -> None:
    tenant_id = uuid.uuid4()
    account_id = "123456789012"

    settings_row = SimpleNamespace(
        tenant_id=tenant_id,
        account_id=account_id,
        enabled=True,
        interval_minutes=60,
        services=["ec2", "s3"],
        regions=["us-east-1"],
        max_resources=250,
        sweep_mode="global",
        cooldown_minutes=10,
        last_enqueued_at=None,
        last_run_id=None,
    )
    account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id=account_id,
        regions=["us-east-1"],
        status="validated",
    )
    tenant = SimpleNamespace(id=tenant_id, external_id="ext-1")

    mock_db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(settings_row, account, tenant)]
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    async def override_get_db():
        yield mock_db

    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.RECONCILIATION_SCHEDULER_SECRET = "sched-secret"
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = ""
        mock_settings.TENANT_RECONCILIATION_SCHEDULE_MIN_INTERVAL_MINUTES = 30
        mock_settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD = 500
        mock_settings.control_plane_inventory_services_list = ["ec2", "s3", "rds"]
        with patch("backend.routers.internal.ensure_tenant_reconciliation_enabled", return_value=None):
            with patch("backend.routers.internal.create_reconciliation_run") as mock_create_run:
                mock_create_run.return_value = SimpleNamespace(id=uuid.uuid4())
                from backend.database import get_db

                app.dependency_overrides[get_db] = override_get_db
                try:
                    client = TestClient(app)
                    resp = client.post(
                        "/api/internal/reconciliation/schedule-tick",
                        headers={"X-Reconciliation-Scheduler-Secret": "sched-secret"},
                        json={},
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["evaluated"] == 1
    assert payload["enqueued"] == 1
    assert payload["failed"] == 0
    assert mock_create_run.call_count == 1
