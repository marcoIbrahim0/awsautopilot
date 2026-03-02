from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine
from datetime import datetime, timezone
from typing import Any, TypeVar
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models.enums import (
    RootKeyArtifactStatus,
    RootKeyDependencyStatus,
    RootKeyExternalTaskStatus,
    RootKeyRemediationMode,
    RootKeyRemediationRunStatus,
    RootKeyRemediationState,
)
from backend.services.root_key_remediation_store import (
    create_root_key_remediation_artifact_idempotent,
    create_root_key_remediation_event_idempotent,
    create_root_key_remediation_run_idempotent,
    create_root_key_external_task_idempotent,
    transition_root_key_remediation_run_state,
    upsert_root_key_dependency_fingerprint,
)


_T = TypeVar("_T")


class _AsyncBeginNested:
    async def __aenter__(self) -> _AsyncBeginNested:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def _run(coro: Coroutine[Any, Any, _T]) -> _T:
    return asyncio.run(coro)



def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result



def _session_with_execute_side_effect(*results: object) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(side_effect=list(results))
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.begin_nested = MagicMock(return_value=_AsyncBeginNested())
    return session



def test_create_run_idempotent_returns_existing_without_insert() -> None:
    tenant_id = uuid.uuid4()
    existing_run = MagicMock()

    session = _session_with_execute_side_effect(_scalar_result(existing_run))
    run, created = _run(
        create_root_key_remediation_run_idempotent(
            session,
            tenant_id=tenant_id,
            account_id="029037611564",
            region="eu-north-1",
            control_id="IAM.4",
            action_id=uuid.uuid4(),
            finding_id=uuid.uuid4(),
            strategy_id="iam_root_key_disable",
            mode=RootKeyRemediationMode.auto,
            correlation_id="corr-1",
            idempotency_key="rk-1",
        )
    )

    assert created is False
    assert run is existing_run
    session.add.assert_not_called()
    session.flush.assert_not_awaited()



def test_create_run_integrity_retry_returns_existing() -> None:
    tenant_id = uuid.uuid4()
    existing_run = MagicMock()

    session = _session_with_execute_side_effect(
        _scalar_result(None),
        _scalar_result(MagicMock()),
        _scalar_result(existing_run),
    )
    session.flush = AsyncMock(side_effect=IntegrityError("insert", {}, Exception("duplicate")))

    run, created = _run(
        create_root_key_remediation_run_idempotent(
            session,
            tenant_id=tenant_id,
            account_id="029037611564",
            region=None,
            control_id="IAM.4",
            action_id=uuid.uuid4(),
            finding_id=None,
            strategy_id="iam_root_key_disable",
            mode=RootKeyRemediationMode.manual,
            correlation_id="corr-2",
            idempotency_key="rk-2",
        )
    )

    assert created is False
    assert run is existing_run
    session.add.assert_called_once()
    session.flush.assert_awaited_once()



def test_create_run_redacts_secret_like_actor_metadata() -> None:
    tenant_id = uuid.uuid4()
    session = _session_with_execute_side_effect(
        _scalar_result(None),
        _scalar_result(MagicMock()),
        _scalar_result(MagicMock()),
    )

    run, created = _run(
        create_root_key_remediation_run_idempotent(
            session,
            tenant_id=tenant_id,
            account_id="029037611564",
            region="eu-north-1",
            control_id="IAM.4",
            action_id=uuid.uuid4(),
            finding_id=uuid.uuid4(),
            strategy_id="iam_root_key_delete",
            mode=RootKeyRemediationMode.auto,
            correlation_id="corr-3",
            idempotency_key="rk-3",
            actor_metadata={
                "operator": "system",
                "session_token": "plain-token-should-not-persist",
                "nested": {"access_key": "AKIAEXAMPLE"},
            },
        )
    )

    assert created is True
    assert run.actor_metadata["operator"] == "system"
    assert run.actor_metadata["session_token"] == "<REDACTED>"
    assert run.actor_metadata["nested"]["access_key"] == "<REDACTED>"



def test_create_run_fails_closed_when_action_not_scoped_to_tenant() -> None:
    tenant_id = uuid.uuid4()
    session = _session_with_execute_side_effect(
        _scalar_result(None),
        _scalar_result(None),
    )

    with pytest.raises(ValueError, match="action not found for tenant"):
        _run(
            create_root_key_remediation_run_idempotent(
                session,
                tenant_id=tenant_id,
                account_id="029037611564",
                region="eu-north-1",
                control_id="IAM.4",
                action_id=uuid.uuid4(),
                finding_id=None,
                strategy_id="iam_root_key_disable",
                mode=RootKeyRemediationMode.auto,
                correlation_id="corr-action-scope",
                idempotency_key="rk-action-scope",
            )
        )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_create_run_fails_closed_when_finding_not_scoped_to_tenant() -> None:
    tenant_id = uuid.uuid4()
    session = _session_with_execute_side_effect(
        _scalar_result(None),
        _scalar_result(MagicMock()),
        _scalar_result(None),
    )

    with pytest.raises(ValueError, match="finding not found for tenant"):
        _run(
            create_root_key_remediation_run_idempotent(
                session,
                tenant_id=tenant_id,
                account_id="029037611564",
                region="eu-north-1",
                control_id="IAM.4",
                action_id=uuid.uuid4(),
                finding_id=uuid.uuid4(),
                strategy_id="iam_root_key_disable",
                mode=RootKeyRemediationMode.auto,
                correlation_id="corr-finding-scope",
                idempotency_key="rk-finding-scope",
            )
        )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_transition_state_returns_none_on_lock_conflict() -> None:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    update_result = MagicMock()
    update_result.rowcount = 0

    session = _session_with_execute_side_effect(update_result)
    transitioned = _run(
        transition_root_key_remediation_run_state(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            expected_lock_version=7,
            new_state=RootKeyRemediationState.validation,
            new_status=RootKeyRemediationRunStatus.running,
        )
    )

    assert transitioned is None
    statement = session.execute.call_args_list[0].args[0]
    params = statement.compile().params
    assert tenant_id in params.values()
    assert run_id in params.values()
    assert 7 in params.values()



def test_create_event_fail_closed_when_run_not_scoped_to_tenant() -> None:
    session = _session_with_execute_side_effect(_scalar_result(None))

    with pytest.raises(ValueError, match="run not found"):
        _run(
            create_root_key_remediation_event_idempotent(
                session,
                run_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                account_id="029037611564",
                region="eu-north-1",
                control_id="IAM.4",
                action_id=None,
                finding_id=None,
                state=RootKeyRemediationState.discovery,
                status=RootKeyRemediationRunStatus.queued,
                strategy_id="iam_root_key_disable",
                mode=RootKeyRemediationMode.manual,
                correlation_id="corr-4",
                event_type="state_entered",
                idempotency_key="evt-1",
            )
        )

    assert session.execute.await_count == 1
    session.add.assert_not_called()



def test_create_event_idempotent_query_is_tenant_scoped() -> None:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    run = MagicMock()
    existing_event = MagicMock()
    session = _session_with_execute_side_effect(
        _scalar_result(run),
        _scalar_result(existing_event),
    )

    event, created = _run(
        create_root_key_remediation_event_idempotent(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            account_id="029037611564",
            region="eu-north-1",
            control_id="IAM.4",
            action_id=uuid.uuid4(),
            finding_id=uuid.uuid4(),
            state=RootKeyRemediationState.discovery,
            status=RootKeyRemediationRunStatus.queued,
            strategy_id="iam_root_key_disable",
            mode=RootKeyRemediationMode.auto,
            correlation_id="corr-5",
            event_type="state_entered",
            idempotency_key="evt-idem-1",
        )
    )

    assert created is False
    assert event is existing_event
    idempotency_query = session.execute.call_args_list[1].args[0]
    assert tenant_id in idempotency_query.compile().params.values()
    assert run_id in idempotency_query.compile().params.values()
    assert "evt-idem-1" in idempotency_query.compile().params.values()



def test_upsert_dependency_fingerprint_handles_integrity_race() -> None:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    run = MagicMock()
    existing = MagicMock()

    session = _session_with_execute_side_effect(
        _scalar_result(run),
        _scalar_result(None),
        _scalar_result(existing),
    )
    session.flush = AsyncMock(side_effect=IntegrityError("insert", {}, Exception("duplicate")))

    fingerprint, created = _run(
        upsert_root_key_dependency_fingerprint(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            account_id="029037611564",
            region="eu-north-1",
            control_id="IAM.4",
            action_id=None,
            finding_id=None,
            state=RootKeyRemediationState.migration,
            status=RootKeyDependencyStatus.unknown,
            strategy_id="iam_root_key_delete",
            mode=RootKeyRemediationMode.auto,
            correlation_id="corr-6",
            fingerprint_type="iam_policy",
            fingerprint_hash="hash-1",
            fingerprint_payload={"authorization": "abc"},
            unknown_dependency=True,
            unknown_reason="unmapped principal",
            actor_metadata={"secret": "hidden"},
        )
    )

    assert created is False
    assert fingerprint is existing
    assert existing.state == RootKeyRemediationState.migration
    assert existing.status == RootKeyDependencyStatus.unknown
    assert existing.unknown_dependency is True
    assert existing.fingerprint_payload["authorization"] == "<REDACTED>"
    assert existing.actor_metadata["secret"] == "<REDACTED>"



def test_artifact_and_external_task_fail_closed_on_tenant_scope_violation() -> None:
    artifact_session = _session_with_execute_side_effect(_scalar_result(None))
    task_session = _session_with_execute_side_effect(_scalar_result(None))
    common_kwargs = dict(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        control_id="IAM.4",
        action_id=None,
        finding_id=None,
        state=RootKeyRemediationState.discovery,
        strategy_id="iam_root_key_disable",
        mode=RootKeyRemediationMode.manual,
        correlation_id="corr-7",
        actor_metadata={"token": "dont-store"},
    )

    with pytest.raises(ValueError, match="run not found"):
        _run(
            create_root_key_remediation_artifact_idempotent(
                artifact_session,
                status=RootKeyArtifactStatus.pending,
                artifact_type="plan_output",
                idempotency_key="art-1",
                **common_kwargs,
            )
        )

    with pytest.raises(ValueError, match="run not found"):
        _run(
            create_root_key_external_task_idempotent(
                task_session,
                status=RootKeyExternalTaskStatus.open,
                task_type="await_manual_validation",
                idempotency_key="task-1",
                due_at=datetime.now(timezone.utc),
                **common_kwargs,
            )
        )

    assert artifact_session.execute.await_count == 1
    assert task_session.execute.await_count == 1
