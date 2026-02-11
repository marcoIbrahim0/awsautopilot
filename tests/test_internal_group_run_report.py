from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models.enums import ActionGroupRunStatus


def _mock_scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_rows_result(rows: list[tuple[uuid.UUID]]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


def test_group_runs_report_started_updates_run_and_states(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    group_run_id = uuid.uuid4()
    action_id = uuid.uuid4()
    token_jti = str(uuid.uuid4())

    run = MagicMock()
    run.id = group_run_id
    run.tenant_id = tenant_id
    run.group_id = group_id
    run.report_token_jti = token_jti
    run.status = ActionGroupRunStatus.queued
    run.started_at = None
    run.reporting_source = "system"

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_result(run),
            _mock_rows_result([(action_id,)]),
        ]
    )
    session.commit = AsyncMock()
    session.add = MagicMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    with patch(
        "backend.routers.internal.verify_group_run_reporting_token",
        return_value={
            "tenant_id": str(tenant_id),
            "group_id": str(group_id),
            "group_run_id": str(group_run_id),
            "jti": token_jti,
            "allowed_action_ids": [str(action_id)],
            "exp": 9999999999,
        },
    ):
        with patch("backend.routers.internal.record_execution_result_async", AsyncMock()) as mock_record:
            response = client.post(
                "/api/internal/group-runs/report",
                json={
                    "token": "signed-token",
                    "event": "started",
                    "started_at": "2026-02-11T12:00:00Z",
                },
            )

    assert response.status_code == 200
    assert run.status == ActionGroupRunStatus.started
    assert run.started_at is not None
    assert mock_record.await_count == 1


def test_group_runs_report_finished_persists_results(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    group_run_id = uuid.uuid4()
    action_id = uuid.uuid4()
    token_jti = str(uuid.uuid4())

    run = MagicMock()
    run.id = group_run_id
    run.tenant_id = tenant_id
    run.group_id = group_id
    run.report_token_jti = token_jti
    run.status = ActionGroupRunStatus.started
    run.started_at = datetime.now(timezone.utc)
    run.reporting_source = "system"

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_result(run),   # group run lookup
            _mock_rows_result([(action_id,)]),  # membership verification
            _mock_scalar_result(None),  # existing run_result lookup
        ]
    )
    session.commit = AsyncMock()
    session.add = MagicMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = mock_get_db
    with patch(
        "backend.routers.internal.verify_group_run_reporting_token",
        return_value={
            "tenant_id": str(tenant_id),
            "group_id": str(group_id),
            "group_run_id": str(group_run_id),
            "jti": token_jti,
            "allowed_action_ids": [str(action_id)],
            "exp": 9999999999,
        },
    ):
        with patch("backend.routers.internal.record_execution_result_async", AsyncMock()) as mock_record:
            with patch("backend.routers.internal.evaluate_confirmation_for_action_async", AsyncMock()) as mock_eval:
                response = client.post(
                    "/api/internal/group-runs/report",
                    json={
                        "token": "signed-token",
                        "event": "finished",
                        "finished_at": "2026-02-11T12:05:00Z",
                        "action_results": [
                            {
                                "action_id": str(action_id),
                                "execution_status": "success",
                            }
                        ],
                    },
                )

    assert response.status_code == 200
    assert run.status == ActionGroupRunStatus.finished
    assert mock_record.await_count == 1
    assert mock_eval.await_count == 1
