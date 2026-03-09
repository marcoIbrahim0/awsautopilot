"""Regression tests for shadow/effective reopen visibility in /api/actions."""
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


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.tenant_id = tenant_id
    user.id = uuid.uuid4()
    return user


def _mock_action(*, tenant_id: uuid.UUID, status: str, score: int = 50, suffix: str = "a") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(f"00000000-0000-0000-0000-00000000000{suffix}"),
        tenant_id=tenant_id,
        action_type="s3_bucket_block_public_access",
        target_id="029037611564|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-029037611564-eu-north-1|S3.2",
        account_id="029037611564",
        region="eu-north-1",
        score=score,
        score_components={"severity": {"normalized": 0.75, "points": 26}, "score": score},
        priority=score,
        status=status,
        title="S3 general purpose buckets should block public read access",
        control_id="S3.2",
        resource_id="arn:aws:s3:::arch1-bucket-evidence-b1-029037611564-eu-north-1",
        updated_at=datetime.now(timezone.utc),
        action_finding_links=[],
    )


def test_actions_list_open_visibility_uses_effective_shadow_status_when_enabled(client: TestClient) -> None:
    """Resolved actions with effective-open findings should surface in open-list mode."""
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id=tenant_id, status="resolved")
    executed_sql: list[str] = []

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001 - SQLAlchemy statement
        executed_sql.append(str(statement))
        result = MagicMock()
        if len(executed_sql) == 1:
            result.scalar.return_value = 1
            return result
        result.all.return_value = [(action, 1, True)]
        return result

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", True):
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            with patch("backend.routers.actions.get_exception_states_for_entities", new=AsyncMock(return_value={})):
                response = client.get(
                    "/api/actions",
                    params={
                        "status": "open",
                        "action_type": "s3_bucket_block_public_access",
                        "account_id": "029037611564",
                        "region": "eu-north-1",
                    },
                )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "open"
    assert body["items"][0]["score"] == 50
    assert body["items"][0]["score_components"]["score"] == 50
    assert any("shadow_status_normalized" in sql for sql in executed_sql)


def test_actions_list_keeps_stored_status_when_effective_visibility_disabled(client: TestClient) -> None:
    """When rollout is disabled, list status stays backward-compatible with stored action.status."""
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id=tenant_id, status="resolved")
    executed_sql: list[str] = []

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001 - SQLAlchemy statement
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
                    params={
                        "status": "resolved",
                        "action_type": "s3_bucket_block_public_access",
                        "account_id": "029037611564",
                        "region": "eu-north-1",
                    },
                )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "resolved"
    assert not any("shadow_status_normalized" in sql for sql in executed_sql)


def test_actions_list_orders_by_score_with_stable_tie_breakers(client: TestClient) -> None:
    """List queries should order by score, then updated_at, then action ID."""
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    high_score = _mock_action(tenant_id=tenant_id, status="open", score=92, suffix="1")
    tied_score = _mock_action(tenant_id=tenant_id, status="open", score=92, suffix="2")
    executed_sql: list[str] = []

    high_score.updated_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
    tied_score.updated_at = datetime(2026, 3, 9, 11, 0, tzinfo=timezone.utc)

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001 - SQLAlchemy statement
        executed_sql.append(str(statement))
        result = MagicMock()
        if len(executed_sql) == 1:
            result.scalar.return_value = 2
            return result
        result.all.return_value = [(high_score, 1, True), (tied_score, 1, True)]
        return result

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", True):
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            with patch("backend.routers.actions.get_exception_states_for_entities", new=AsyncMock(return_value={})):
                response = client.get("/api/actions")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(high_score.id), str(tied_score.id)]
    assert body["items"][0]["score"] == 92
    assert any("ORDER BY actions.score DESC" in sql for sql in executed_sql)
    assert any("actions.id ASC" in sql for sql in executed_sql)
