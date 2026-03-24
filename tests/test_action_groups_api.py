from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import ActionGroupExecutionStatus, ActionGroupRunStatus


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "user@example.com"
    return user


def _mock_scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = value
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars_result(values: list[object]) -> MagicMock:
    scalars = MagicMock()
    scalars.all.return_value = values
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


def _make_group_run_result(
    *,
    action_id: uuid.UUID,
    execution_status: ActionGroupExecutionStatus,
    raw_result: dict | None = None,
) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        action_id=action_id,
        execution_status=execution_status,
        execution_error_code=None,
        execution_error_message=None,
        execution_started_at=now,
        execution_finished_at=now,
        raw_result=raw_result,
    )


def _make_group_run(*, group_id: uuid.UUID, results: list[SimpleNamespace]) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        remediation_run_id=uuid.uuid4(),
        initiated_by_user_id=uuid.uuid4(),
        mode="download_bundle",
        status=ActionGroupRunStatus.finished,
        started_at=now,
        finished_at=now,
        reporting_source="bundle_callback",
        created_at=now,
        updated_at=now,
        group_id=group_id,
        results=results,
    )


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
                            "metadata_only": 1,
                            "not_run_yet": 3,
                            "total_actions": 7,
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
    assert payload["items"][0]["counters"]["metadata_only"] == 1
    assert payload["items"][0]["counters"]["not_run_yet"] == 3
    assert payload["items"][0]["counters"]["total_actions"] == 7


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


def test_get_action_group_detail_includes_pending_confirmation_fields(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    db = MagicMock()
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=12)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.action_groups.get_tenant", AsyncMock(return_value=MagicMock())):
        with patch(
            "backend.routers.action_groups.get_group_detail",
            AsyncMock(
                return_value={
                    "group": {
                        "id": str(uuid.uuid4()),
                        "tenant_id": str(tenant_id),
                        "group_key": "tenant|type|account|global",
                        "action_type": "aws_config_enabled",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "created_at": now,
                        "updated_at": now,
                        "metadata": {},
                    },
                    "counters": {
                        "run_successful": 1,
                        "run_not_successful": 0,
                        "metadata_only": 1,
                        "not_run_yet": 0,
                        "total_actions": 2,
                    },
                    "members": [
                        {
                            "action_id": str(uuid.uuid4()),
                            "title": "Enable AWS Config",
                            "control_id": "Config.1",
                            "resource_id": "resource-1",
                            "action_status": "open",
                            "priority": 10,
                            "assigned_at": None,
                            "status_bucket": "run_successful_pending_confirmation",
                            "last_attempt_at": now,
                            "last_confirmed_at": None,
                            "last_confirmation_source": None,
                            "latest_run_id": str(uuid.uuid4()),
                            "latest_run_status": "finished",
                            "latest_run_started_at": now,
                            "latest_run_finished_at": now,
                            "pending_confirmation": True,
                            "pending_confirmation_started_at": now.isoformat(),
                            "pending_confirmation_deadline_at": deadline.isoformat(),
                            "pending_confirmation_message": "Waiting for AWS confirmation.",
                            "pending_confirmation_severity": "info",
                        },
                        {
                            "action_id": str(uuid.uuid4()),
                            "title": "S3 review-only fix",
                            "control_id": "S3.5",
                            "resource_id": "resource-2",
                            "action_status": "open",
                            "priority": 8,
                            "assigned_at": None,
                            "status_bucket": "run_finished_metadata_only",
                            "last_attempt_at": now,
                            "last_confirmed_at": None,
                            "last_confirmation_source": None,
                            "latest_run_id": str(uuid.uuid4()),
                            "latest_run_status": "finished",
                            "latest_run_started_at": now,
                            "latest_run_finished_at": now,
                            "pending_confirmation": False,
                            "pending_confirmation_started_at": None,
                            "pending_confirmation_deadline_at": None,
                            "pending_confirmation_message": None,
                            "pending_confirmation_severity": None,
                        }
                    ],
                }
            ),
        ), patch(
            "backend.routers.action_groups._load_action_group_or_404",
            AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), account_id="123456789012", action_type="aws_config_enabled")),
        ), patch(
            "backend.routers.action_groups._load_group_actions_or_404",
            AsyncMock(return_value=[]),
        ), patch(
            "backend.routers.action_groups._load_group_account",
            AsyncMock(return_value=None),
        ), patch(
            "backend.routers.action_groups._group_bundle_generation_state",
            AsyncMock(return_value=(False, "grouped_bundle_already_created_no_changes", "No changes since the previous bundle.", "run-1")),
        ):
            response = client.get(f"/api/action-groups/{uuid.uuid4()}")

    assert response.status_code == 200
    payload = response.json()
    member = payload["members"][0]
    assert member["pending_confirmation"] is True
    assert member["pending_confirmation_message"] == "Waiting for AWS confirmation."
    assert member["pending_confirmation_severity"] == "info"
    assert payload["counters"]["metadata_only"] == 1
    assert payload["members"][1]["status_bucket"] == "run_finished_metadata_only"
    assert payload["can_generate_bundle"] is False
    assert payload["blocked_reason"] == "grouped_bundle_already_created_no_changes"
    assert payload["blocked_detail"] == "No changes since the previous bundle."
    assert payload["blocked_by_run_id"] == "run-1"


def test_get_action_group_runs_includes_mixed_per_action_results(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    executable_action_id = uuid.uuid4()
    review_action_id = uuid.uuid4()
    run = _make_group_run(
        group_id=group_id,
        results=[
            _make_group_run_result(
                action_id=executable_action_id,
                execution_status=ActionGroupExecutionStatus.success,
            ),
            _make_group_run_result(
                action_id=review_action_id,
                execution_status=ActionGroupExecutionStatus.unknown,
                raw_result={
                    "result_type": "non_executable",
                    "support_tier": "review_required_bundle",
                    "reason": "review_required_metadata_only",
                    "blocked_reasons": ["needs approval"],
                },
            ),
        ],
    )
    db = MagicMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db

    async def mock_get_optional_user() -> MagicMock:
        return user

    db.execute = AsyncMock(
        side_effect=[
            _mock_scalar_result(1),
            _mock_scalars_result([run]),
        ]
    )
    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    with patch("backend.routers.action_groups.get_tenant", AsyncMock(return_value=MagicMock())):
        try:
            response = client.get(f"/api/action-groups/{group_id}/runs")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    results = payload["items"][0]["results"]
    assert len(results) == 2

    executable = next(item for item in results if item["action_id"] == str(executable_action_id))
    assert executable["execution_status"] == ActionGroupExecutionStatus.success.value
    assert executable["result_type"] == "executable"
    assert executable["support_tier"] is None
    assert executable["reason"] is None
    assert executable["blocked_reasons"] == []
    assert executable["execution_started_at"] == run.results[0].execution_started_at.isoformat()
    assert executable["execution_finished_at"] == run.results[0].execution_finished_at.isoformat()

    review = next(item for item in results if item["action_id"] == str(review_action_id))
    assert review["execution_status"] == ActionGroupExecutionStatus.unknown.value
    assert review["result_type"] == "non_executable"
    assert review["support_tier"] == "review_required_bundle"
    assert review["reason"] == "review_required_metadata_only"
    assert review["blocked_reasons"] == ["needs approval"]
    assert review["execution_started_at"] == run.results[1].execution_started_at.isoformat()
    assert review["execution_finished_at"] == run.results[1].execution_finished_at.isoformat()
    assert payload["items"][0]["started_at"] == run.started_at.isoformat()
    assert payload["items"][0]["finished_at"] == run.finished_at.isoformat()


def test_get_action_group_run_returns_results_for_specific_run(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action_id = uuid.uuid4()
    run = _make_group_run(
        group_id=group_id,
        results=[
            _make_group_run_result(
                action_id=action_id,
                execution_status=ActionGroupExecutionStatus.failed,
                raw_result={"blocked_reasons": ["ignored for executable row"]},
            )
        ],
    )
    db = MagicMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db

    async def mock_get_optional_user() -> MagicMock:
        return user

    db.execute = AsyncMock(return_value=_mock_scalar_result(run))
    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    with patch("backend.routers.action_groups.get_tenant", AsyncMock(return_value=MagicMock())):
        try:
            response = client.get(f"/api/action-groups/{group_id}/runs/{run.id}")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(run.id)
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert result["action_id"] == str(action_id)
    assert result["execution_status"] == ActionGroupExecutionStatus.failed.value
    assert result["result_type"] == "executable"
    assert result["blocked_reasons"] == []
    assert result["execution_started_at"] == run.results[0].execution_started_at.isoformat()
    assert result["execution_finished_at"] == run.results[0].execution_finished_at.isoformat()
    assert payload["started_at"] == run.started_at.isoformat()
    assert payload["finished_at"] == run.finished_at.isoformat()
