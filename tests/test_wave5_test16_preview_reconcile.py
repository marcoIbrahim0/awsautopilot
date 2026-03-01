"""
Wave 5 Test 16 regressions: remediation preview mode compatibility and reconcile write path.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.tenant_id = tenant_id
    return user


def _mock_action(*, tenant_id: uuid.UUID, action_type: str = "sg_restrict_public_ports") -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.tenant_id = tenant_id
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = "eu-north-1"
    return action


def _mock_account() -> MagicMock:
    account = MagicMock()
    account.regions = ["eu-north-1"]
    return account


def test_remediation_preview_accepts_pr_only_mode_from_options(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id=tenant_id, action_type="sg_restrict_public_ports")

    db_session = MagicMock()
    action_result = MagicMock()
    action_result.scalar_one_or_none.return_value = action
    db_session.execute = AsyncMock(return_value=action_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
        response = client.get(
            f"/api/actions/{action.id}/remediation-preview",
            params={"mode": "pr_only"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["compliant"] is False
    assert body["will_apply"] is False
    assert "pr_only" in body["message"]


def test_actions_compute_retry_stays_idempotent(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    account = _mock_account()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "compute-msg-1"}

    with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
        with patch("backend.routers.actions.get_account_for_tenant", new=AsyncMock(return_value=account)):
            with patch("backend.routers.actions.settings") as mock_settings:
                mock_settings.has_ingest_queue = True
                mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/ingest"
                with patch("backend.routers.actions.boto3.client", return_value=mock_sqs):
                    first = client.post(
                        "/api/actions/compute",
                        json={"account_id": "123456789012", "region": "eu-north-1"},
                    )
                    retry = client.post(
                        "/api/actions/compute",
                        json={"account_id": "123456789012", "region": "eu-north-1"},
                    )

    assert first.status_code == 202
    assert retry.status_code == 202
    assert first.json() == retry.json()
    assert mock_sqs.send_message.call_count == 2


def test_actions_reconcile_post_contract_and_retry_stable(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    account = _mock_account()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "reconcile-msg-1"}

    with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
        with patch("backend.routers.actions.get_account_for_tenant", new=AsyncMock(return_value=account)):
            with patch("backend.routers.actions.settings") as mock_settings:
                mock_settings.has_inventory_reconcile_queue = True
                mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/reconcile"
                mock_settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD = 500
                mock_settings.control_plane_inventory_services_list = ["ec2", "s3"]
                mock_settings.AWS_REGION = "us-east-1"
                with patch("backend.routers.actions.boto3.client", return_value=mock_sqs):
                    first = client.post(
                        "/api/actions/reconcile",
                        json={"account_id": "123456789012", "region": "eu-north-1"},
                    )
                    retry = client.post(
                        "/api/actions/reconcile",
                        json={"account_id": "123456789012", "region": "eu-north-1"},
                    )

    assert first.status_code == 202
    assert retry.status_code == 202
    assert first.json() == retry.json()
    assert first.json()["enqueued_jobs"] == 2
    assert mock_sqs.send_message.call_count == 4
    first_payload = json.loads(mock_sqs.send_message.call_args_list[0].kwargs["MessageBody"])
    assert first_payload["tenant_id"] == str(tenant_id)
    assert first_payload["account_id"] == "123456789012"
    assert first_payload["region"] == "eu-north-1"
    assert first_payload["job_type"] == "reconcile_inventory_shard"


def test_actions_reconcile_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/actions/reconcile",
        json={"account_id": "123456789012", "region": "eu-north-1"},
    )
    assert response.status_code == 401


def test_actions_reconcile_enforces_tenant_account_boundary(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
        with patch("backend.routers.actions.get_account_for_tenant", new=AsyncMock(return_value=None)):
            with patch("backend.routers.actions.settings") as mock_settings:
                mock_settings.has_inventory_reconcile_queue = True
                mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/reconcile"
                response = client.post(
                    "/api/actions/reconcile",
                    json={"account_id": "123456789012", "region": "eu-north-1"},
                )

    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "Account not found"
