from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from backend.workers.jobs.attack_path_materialization import execute_attack_path_materialization_job


class _SessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return None


def test_execute_attack_path_materialization_job_uses_isolated_engine() -> None:
    tenant_id = uuid.uuid4()
    session = AsyncMock()
    engine = AsyncMock()
    session_factory = lambda: _SessionContext(session)

    with patch(
        "backend.workers.jobs.attack_path_materialization.build_async_session_factory",
        return_value=(engine, session_factory),
    ) as build_factory:
        with patch(
            "backend.workers.jobs.attack_path_materialization.materialize_attack_paths",
            new=AsyncMock(return_value={"paths_materialized": 1, "actions_scanned": 2, "latency_ms": 3}),
        ) as refresh:
            execute_attack_path_materialization_job({"tenant_id": str(tenant_id), "account_id": "123", "region": "us-east-1"})

    build_factory.assert_called_once_with(isolated=True)
    refresh.assert_awaited_once_with(session, tenant_id=tenant_id, account_id="123", region="us-east-1")
    session.commit.assert_awaited_once()
    engine.dispose.assert_awaited_once()
