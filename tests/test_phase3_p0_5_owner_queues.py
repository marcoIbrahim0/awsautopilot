"""Phase 3 P0.5 tests for ownership-based action queues."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.routers import actions as actions_router
from backend.services.action_ownership import (
    UNASSIGNED_OWNER_KEY,
    UNASSIGNED_OWNER_TYPE,
    resolve_action_owner,
)


def _finding(raw_json: dict) -> SimpleNamespace:
    return SimpleNamespace(raw_json=raw_json)


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.tenant_id = tenant_id
    user.id = uuid.uuid4()
    return user


def _mock_action(
    *,
    tenant_id: uuid.UUID,
    owner_type: str,
    owner_key: str,
    owner_label: str,
    score: int = 88,
    status: str = "open",
    suffix: str = "1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(f"00000000-0000-0000-0000-00000000000{suffix}"),
        tenant_id=tenant_id,
        action_type="s3_bucket_block_public_access",
        target_id="target-1",
        account_id="029037611564",
        region="eu-north-1",
        score=score,
        score_components={"severity": {"normalized": 0.75, "points": 26}, "score": score},
        priority=score,
        status=status,
        title="S3 bucket should block public access",
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-data",
        resource_type="AwsS3Bucket",
        owner_type=owner_type,
        owner_key=owner_key,
        owner_label=owner_label,
        created_at=datetime(2026, 3, 9, 8, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
        action_finding_links=[],
    )


def test_owner_resolver_prefers_explicit_user_over_team_and_service() -> None:
    finding = _finding(
        {
            "ProductFields": {
                "owner_email": "Security.Owner@example.com",
                "team": "Platform Team",
                "service": "Payments API",
            }
        }
    )

    owner = resolve_action_owner([finding], action_type="s3_bucket_encryption", resource_type="AwsS3Bucket")

    assert owner.owner_type == "user"
    assert owner.owner_key == "security.owner@example.com"
    assert owner.owner_label == "Security.Owner@example.com"


def test_owner_resolver_falls_back_to_service_from_action_type() -> None:
    owner = resolve_action_owner([], action_type="sg_restrict_public_ports", resource_type="AwsEc2SecurityGroup")

    assert owner.owner_type == "service"
    assert owner.owner_key == "ec2"
    assert owner.owner_label == "Amazon EC2"


def test_owner_resolver_keeps_unknown_actions_unassigned() -> None:
    owner = resolve_action_owner([], action_type="pr_only", resource_type=None)

    assert owner.owner_type == UNASSIGNED_OWNER_TYPE
    assert owner.owner_key == UNASSIGNED_OWNER_KEY


def test_actions_list_filters_by_owner_scope(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(
        tenant_id=tenant_id,
        owner_type="service",
        owner_key="payments-api",
        owner_label="Payments API",
    )
    executed_sql: list[str] = []

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001
        executed_sql.append(str(statement))
        result = MagicMock()
        if len(executed_sql) == 1:
            result.scalar.return_value = 1
            return result
        result.all.return_value = [(action, 1)]
        return result

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", False):
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            with patch("backend.routers.actions.get_exception_states_for_entities", new=AsyncMock(return_value={})):
                response = client.get(
                    "/api/actions",
                    params={"owner_type": "service", "owner_key": "payments-api"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["owner_type"] == "service"
    assert body["items"][0]["owner_key"] == "payments-api"
    assert all("actions.tenant_id" in sql for sql in executed_sql)
    assert any("actions.owner_type" in sql for sql in executed_sql)
    assert any("actions.owner_key" in sql for sql in executed_sql)


def test_actions_list_supports_unassigned_queue_visibility(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(
        tenant_id=tenant_id,
        owner_type=UNASSIGNED_OWNER_TYPE,
        owner_key=UNASSIGNED_OWNER_KEY,
        owner_label="Unassigned",
        suffix="2",
    )

    execute_count = {"value": 0}

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001
        execute_count["value"] += 1
        result = MagicMock()
        if execute_count["value"] == 1:
            result.scalar.return_value = 1
            return result
        result.all.return_value = [(action, 1)]
        return result

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", False):
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            with patch("backend.routers.actions.get_exception_states_for_entities", new=AsyncMock(return_value={})):
                response = client.get(
                    "/api/actions",
                    params={"owner_type": "unassigned", "owner_key": "unassigned"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["owner_type"] == "unassigned"
    assert body["items"][0]["owner_label"] == "Unassigned"


def test_actions_list_expiring_exception_queue_uses_exception_window(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(
        tenant_id=tenant_id,
        owner_type="team",
        owner_key="platform-team",
        owner_label="Platform Team",
        suffix="3",
    )
    executed_sql: list[str] = []

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001
        executed_sql.append(str(statement))
        result = MagicMock()
        if len(executed_sql) == 1:
            result.one.return_value = SimpleNamespace(
                open=0,
                expiring=0,
                overdue=0,
                blocked_fixes=0,
                expiring_exceptions=1,
            )
            return result
        if len(executed_sql) == 2:
            result.scalar.return_value = 1
            return result
        result.all.return_value = [(action, 1)]
        return result

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", False):
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            with patch("backend.routers.actions.get_exception_states_for_entities", new=AsyncMock(return_value={})):
                response = client.get(
                    "/api/actions",
                    params={
                        "owner_type": "team",
                        "owner_key": "platform-team",
                        "owner_queue": "expiring_exceptions",
                    },
                )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["owner_queue_counters"]["expiring_exceptions"] == 1
    assert body["items"][0]["owner_key"] == "platform-team"
    assert any("exception_expires_at" in sql for sql in executed_sql)
    assert all("actions.tenant_id" in sql for sql in executed_sql)
