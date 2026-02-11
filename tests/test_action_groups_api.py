from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "user@example.com"
    return user


def test_list_action_groups_returns_counters(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    db = MagicMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.action_groups.get_tenant", AsyncMock(return_value=MagicMock())):
        with patch(
            "backend.routers.action_groups.list_groups_with_counters",
            AsyncMock(
                return_value={
                    "items": [
                        {
                            "id": str(uuid.uuid4()),
                            "group_key": "tenant|type|account|global",
                            "action_type": "s3_bucket_block_public_access",
                            "account_id": "123456789012",
                            "region": None,
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                            "metadata": {},
                            "run_successful": 1,
                            "run_not_successful": 2,
                            "not_run_yet": 3,
                            "total_actions": 6,
                        }
                    ],
                    "total": 1,
                }
            ),
        ):
            response = client.get("/api/action-groups")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["counters"]["run_successful"] == 1
    assert payload["items"][0]["counters"]["run_not_successful"] == 2
    assert payload["items"][0]["counters"]["not_run_yet"] == 3
    assert payload["items"][0]["counters"]["total_actions"] == 6


def test_get_action_group_detail_not_found(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    db = MagicMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.action_groups.get_tenant", AsyncMock(return_value=MagicMock())):
        with patch("backend.routers.action_groups.get_group_detail", AsyncMock(return_value=None)):
            response = client.get(f"/api/action-groups/{uuid.uuid4()}")

    assert response.status_code == 404
