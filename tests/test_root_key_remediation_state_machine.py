from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any, TypeVar, cast

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import IntegrityError

from backend.models.enums import (
    RootKeyRemediationMode,
    RootKeyRemediationRunStatus,
    RootKeyRemediationState,
)
from backend.models.root_key_remediation_run import RootKeyRemediationRun
from backend.services.root_key_remediation_state_machine import (
    RootKeyRemediationStateMachineService,
    RootKeyTransitionRetryPolicy,
)


_T = TypeVar("_T")


def _run(coro: Coroutine[Any, Any, _T]) -> _T:
    return asyncio.run(coro)


def _build_run(
    *,
    tenant_id: uuid.UUID,
    state: RootKeyRemediationState,
    status: RootKeyRemediationRunStatus,
    lock_version: int = 1,
) -> RootKeyRemediationRun:
    return RootKeyRemediationRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        control_id="IAM.4",
        action_id=uuid.uuid4(),
        finding_id=uuid.uuid4(),
        state=state,
        status=status,
        strategy_id="iam_root_key_disable",
        mode=RootKeyRemediationMode.auto,
        correlation_id="corr-state-machine",
        idempotency_key="create-run-1",
        lock_version=lock_version,
    )


def _install_transition_store_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    run: RootKeyRemediationRun,
    conflict_steps: list[str] | None = None,
) -> dict[str, Any]:
    module = "backend.services.root_key_remediation_state_machine"
    steps = list(conflict_steps or [])
    state: dict[str, Any] = {
        "event_calls": [],
        "artifact_calls": [],
        "transition_targets": [],
        "sleep_calls": [],
    }
    event_cache: dict[str, Any] = {}
    artifact_cache: dict[str, Any] = {}

    async def fake_get(*_: object, tenant_id: uuid.UUID, run_id: uuid.UUID, **__: object) -> RootKeyRemediationRun | None:
        if tenant_id != run.tenant_id or run_id != run.id:
            return None
        return run

    async def fake_transition(*_: object, **kwargs: object) -> RootKeyRemediationRun | None:
        new_state = cast(RootKeyRemediationState, kwargs["new_state"])
        new_status = cast(RootKeyRemediationRunStatus, kwargs["new_status"])
        state["transition_targets"].append(new_state)
        marker = steps.pop(0) if steps else "success"
        if marker == "lock_conflict":
            return None
        if marker == "converged_conflict":
            run.state = new_state
            run.status = new_status
            run.lock_version += 1
            return None
        run.state = new_state
        run.status = new_status
        run.lock_version += 1
        run.rollback_reason = cast(str | None, kwargs.get("rollback_reason"))
        if kwargs.get("completed_at") is not None:
            run.completed_at = kwargs["completed_at"]
        return run

    async def fake_event(*_: object, **kwargs: object) -> tuple[Any, bool]:
        key = str(kwargs["idempotency_key"])
        state["event_calls"].append(kwargs)
        existing = event_cache.get(key)
        if existing is not None:
            return existing, False
        created = SimpleNamespace(id=uuid.uuid4())
        event_cache[key] = created
        return created, True

    async def fake_artifact(*_: object, **kwargs: object) -> tuple[Any, bool]:
        key = str(kwargs["idempotency_key"])
        state["artifact_calls"].append(kwargs)
        existing = artifact_cache.get(key)
        if existing is not None:
            return existing, False
        created = SimpleNamespace(id=uuid.uuid4())
        artifact_cache[key] = created
        return created, True

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get)
    monkeypatch.setattr(f"{module}.transition_root_key_remediation_run_state", fake_transition)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_event_idempotent", fake_event)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", fake_artifact)
    return state


def _enabled_service(*, sleep_fn: Any | None = None, max_attempts: int = 3) -> RootKeyRemediationStateMachineService:
    return RootKeyRemediationStateMachineService(
        enabled=True,
        strict_transitions_enabled=True,
        delete_enabled=True,
        retry_policy=RootKeyTransitionRetryPolicy(
            max_attempts=max_attempts,
            base_backoff_seconds=0.5,
            max_backoff_seconds=0.6,
        ),
        sleep_fn=sleep_fn or AsyncMock(),
    )


def test_create_run_idempotent_emits_event_and_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    module = "backend.services.root_key_remediation_state_machine"
    created_first = True
    event_cache: dict[str, Any] = {}
    artifact_cache: dict[str, Any] = {}

    async def fake_create_run(*_: object, **__: object) -> tuple[RootKeyRemediationRun, bool]:
        nonlocal created_first
        if created_first:
            created_first = False
            return run, True
        return run, False

    async def fake_event(*_: object, **kwargs: object) -> tuple[Any, bool]:
        key = str(kwargs["idempotency_key"])
        existing = event_cache.get(key)
        if existing is not None:
            return existing, False
        event = SimpleNamespace(id=uuid.uuid4())
        event_cache[key] = event
        return event, True

    async def fake_artifact(*_: object, **kwargs: object) -> tuple[Any, bool]:
        key = str(kwargs["idempotency_key"])
        existing = artifact_cache.get(key)
        if existing is not None:
            return existing, False
        artifact = SimpleNamespace(id=uuid.uuid4())
        artifact_cache[key] = artifact
        return artifact, True

    monkeypatch.setattr(f"{module}.create_root_key_remediation_run_idempotent", fake_create_run)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_event_idempotent", fake_event)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", fake_artifact)
    service = _enabled_service()
    db = MagicMock()

    first = _run(
        service.create_run(
            db,
            tenant_id=tenant_id,
            account_id=run.account_id,
            region=run.region,
            control_id=run.control_id,
            action_id=run.action_id,
            finding_id=run.finding_id,
            strategy_id=run.strategy_id,
            mode=run.mode,
            correlation_id=run.correlation_id,
            idempotency_key="create-1",
        )
    )
    second = _run(
        service.create_run(
            db,
            tenant_id=tenant_id,
            account_id=run.account_id,
            region=run.region,
            control_id=run.control_id,
            action_id=run.action_id,
            finding_id=run.finding_id,
            strategy_id=run.strategy_id,
            mode=run.mode,
            correlation_id=run.correlation_id,
            idempotency_key="create-1",
        )
    )

    assert first.state_changed is True
    assert first.event_created is True
    assert first.evidence_created is True
    assert second.state_changed is False
    assert second.event_created is False
    assert second.evidence_created is False


def test_create_run_auth_scope_violation_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    module = "backend.services.root_key_remediation_state_machine"
    event_mock = AsyncMock()
    artifact_mock = AsyncMock()

    async def fake_create_run(*_: object, **__: object) -> tuple[RootKeyRemediationRun, bool]:
        raise ValueError("root-key remediation action not found for tenant")

    monkeypatch.setattr(f"{module}.create_root_key_remediation_run_idempotent", fake_create_run)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_event_idempotent", event_mock)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", artifact_mock)

    service = _enabled_service()
    with pytest.raises(Exception) as exc_info:
        _run(
            service.create_run(
                MagicMock(),
                tenant_id=tenant_id,
                account_id=run.account_id,
                region=run.region,
                control_id=run.control_id,
                action_id=run.action_id,
                finding_id=run.finding_id,
                strategy_id=run.strategy_id,
                mode=run.mode,
                correlation_id=run.correlation_id,
                idempotency_key="create-auth-scope",
            )
        )

    err = exc_info.value
    assert hasattr(err, "classification")
    assert err.classification.code == "tenant_scope_violation"
    assert err.classification.is_retryable is False
    event_mock.assert_not_awaited()
    artifact_mock.assert_not_awaited()


def test_create_run_retries_on_integrity_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    module = "backend.services.root_key_remediation_state_machine"
    event_cache: dict[str, Any] = {}
    artifact_cache: dict[str, Any] = {}
    sleep_mock = AsyncMock()
    attempts = {"count": 0}

    async def fake_create_run(*_: object, **__: object) -> tuple[RootKeyRemediationRun, bool]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise IntegrityError("insert", {}, Exception("duplicate"))
        return run, True

    async def fake_event(*_: object, **kwargs: object) -> tuple[Any, bool]:
        key = str(kwargs["idempotency_key"])
        existing = event_cache.get(key)
        if existing is not None:
            return existing, False
        created = SimpleNamespace(id=uuid.uuid4())
        event_cache[key] = created
        return created, True

    async def fake_artifact(*_: object, **kwargs: object) -> tuple[Any, bool]:
        key = str(kwargs["idempotency_key"])
        existing = artifact_cache.get(key)
        if existing is not None:
            return existing, False
        created = SimpleNamespace(id=uuid.uuid4())
        artifact_cache[key] = created
        return created, True

    monkeypatch.setattr(f"{module}.create_root_key_remediation_run_idempotent", fake_create_run)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_event_idempotent", fake_event)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", fake_artifact)
    service = _enabled_service(sleep_fn=sleep_mock, max_attempts=4)

    result = _run(
        service.create_run(
            MagicMock(),
            tenant_id=tenant_id,
            account_id=run.account_id,
            region=run.region,
            control_id=run.control_id,
            action_id=run.action_id,
            finding_id=run.finding_id,
            strategy_id=run.strategy_id,
            mode=run.mode,
            correlation_id=run.correlation_id,
            idempotency_key="create-retry",
        )
    )

    assert result.run.id == run.id
    assert result.attempts == 2
    assert sleep_mock.await_count == 1
    assert sleep_mock.await_args_list[0].args[0] == 0.5


@pytest.mark.parametrize(
    ("method_name", "source_state", "source_status", "target_state", "target_status"),
    [
        (
            "advance_to_migration",
            RootKeyRemediationState.discovery,
            RootKeyRemediationRunStatus.queued,
            RootKeyRemediationState.migration,
            RootKeyRemediationRunStatus.running,
        ),
        (
            "advance_to_migration",
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
            RootKeyRemediationState.migration,
            RootKeyRemediationRunStatus.running,
        ),
        (
            "advance_to_validation",
            RootKeyRemediationState.migration,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.validation,
            RootKeyRemediationRunStatus.running,
        ),
        (
            "start_disable_window",
            RootKeyRemediationState.validation,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.disable_window,
            RootKeyRemediationRunStatus.running,
        ),
        (
            "start_disable_window",
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
            RootKeyRemediationState.disable_window,
            RootKeyRemediationRunStatus.running,
        ),
        (
            "mark_needs_attention",
            RootKeyRemediationState.discovery,
            RootKeyRemediationRunStatus.queued,
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
        ),
        (
            "mark_needs_attention",
            RootKeyRemediationState.migration,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
        ),
        (
            "mark_needs_attention",
            RootKeyRemediationState.validation,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
        ),
        (
            "mark_needs_attention",
            RootKeyRemediationState.disable_window,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
        ),
        (
            "mark_needs_attention",
            RootKeyRemediationState.delete_window,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
        ),
        (
            "rollback",
            RootKeyRemediationState.migration,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.rolled_back,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "rollback",
            RootKeyRemediationState.validation,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.rolled_back,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "rollback",
            RootKeyRemediationState.disable_window,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.rolled_back,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "rollback",
            RootKeyRemediationState.delete_window,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.rolled_back,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "rollback",
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
            RootKeyRemediationState.rolled_back,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "fail_run",
            RootKeyRemediationState.migration,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.failed,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "fail_run",
            RootKeyRemediationState.validation,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.failed,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "fail_run",
            RootKeyRemediationState.disable_window,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.failed,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "fail_run",
            RootKeyRemediationState.discovery,
            RootKeyRemediationRunStatus.queued,
            RootKeyRemediationState.failed,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "fail_run",
            RootKeyRemediationState.delete_window,
            RootKeyRemediationRunStatus.running,
            RootKeyRemediationState.failed,
            RootKeyRemediationRunStatus.failed,
        ),
        (
            "fail_run",
            RootKeyRemediationState.needs_attention,
            RootKeyRemediationRunStatus.waiting_for_user,
            RootKeyRemediationState.failed,
            RootKeyRemediationRunStatus.failed,
        ),
    ],
)
def test_transition_matrix_legal_paths(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    source_state: RootKeyRemediationState,
    source_status: RootKeyRemediationRunStatus,
    target_state: RootKeyRemediationState,
    target_status: RootKeyRemediationRunStatus,
) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(tenant_id=tenant_id, state=source_state, status=source_status)
    trace = _install_transition_store_fakes(monkeypatch, run=run)
    service = _enabled_service()
    db = MagicMock()

    method = getattr(service, method_name)
    kwargs: dict[str, Any] = dict(tenant_id=tenant_id, run_id=run.id, transition_id="tx-1")
    if method_name == "rollback":
        kwargs["rollback_reason"] = "policy_guard"
    if method_name == "fail_run":
        kwargs["failure_reason"] = "terminal_error"
        kwargs["retry_increment"] = 1
    result = _run(method(db, **kwargs))

    assert result.run.state == target_state
    assert result.run.status == target_status
    assert result.event_created is True
    assert result.evidence_created is True
    assert len(trace["event_calls"]) == 1
    assert len(trace["artifact_calls"]) == 1


@pytest.mark.parametrize(
    ("source_state", "transition_calls"),
    [
        (RootKeyRemediationState.disable_window, [RootKeyRemediationState.delete_window, RootKeyRemediationState.completed]),
        (RootKeyRemediationState.delete_window, [RootKeyRemediationState.completed]),
    ],
)
def test_finalize_delete_covers_required_path(
    monkeypatch: pytest.MonkeyPatch,
    source_state: RootKeyRemediationState,
    transition_calls: list[RootKeyRemediationState],
) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(tenant_id=tenant_id, state=source_state, status=RootKeyRemediationRunStatus.running)
    trace = _install_transition_store_fakes(monkeypatch, run=run)
    service = _enabled_service()

    result = _run(
        service.finalize_delete(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-finalize",
        )
    )

    assert result.run.state == RootKeyRemediationState.completed
    assert result.run.status == RootKeyRemediationRunStatus.completed
    assert trace["transition_targets"] == transition_calls
    assert len(trace["event_calls"]) == len(transition_calls)
    assert len(trace["artifact_calls"]) == len(transition_calls)


def test_illegal_transition_is_rejected_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    trace = _install_transition_store_fakes(monkeypatch, run=run)
    service = _enabled_service()

    with pytest.raises(Exception) as exc_info:
        _run(
            service.advance_to_validation(
                MagicMock(),
                tenant_id=tenant_id,
                run_id=run.id,
                transition_id="tx-illegal",
            )
        )

    err = exc_info.value
    assert hasattr(err, "classification")
    assert err.classification.code == "illegal_transition"
    assert err.classification.is_retryable is False
    assert trace["transition_targets"] == []
    assert trace["event_calls"] == []
    assert trace["artifact_calls"] == []


def test_auth_scope_violation_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = "backend.services.root_key_remediation_state_machine"
    service = _enabled_service()

    async def fake_get(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get)
    with pytest.raises(Exception) as exc_info:
        _run(
            service.mark_needs_attention(
                MagicMock(),
                tenant_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                transition_id="tx-auth",
            )
        )

    err = exc_info.value
    assert hasattr(err, "classification")
    assert err.classification.code == "tenant_scope_violation"
    assert err.classification.is_retryable is False


def test_retry_idempotency_on_converged_lock_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.migration,
        status=RootKeyRemediationRunStatus.running,
    )
    trace = _install_transition_store_fakes(monkeypatch, run=run, conflict_steps=["converged_conflict"])
    service = _enabled_service()

    result = _run(
        service.advance_to_validation(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-retry-idem",
        )
    )

    assert result.run.state == RootKeyRemediationState.validation
    assert result.run.status == RootKeyRemediationRunStatus.running
    assert result.attempts == 1
    assert len(trace["event_calls"]) == 1
    assert len(trace["artifact_calls"]) == 1


def test_retry_policy_uses_capped_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    _install_transition_store_fakes(
        monkeypatch,
        run=run,
        conflict_steps=["lock_conflict", "lock_conflict", "success"],
    )
    sleep_mock = AsyncMock()
    service = _enabled_service(sleep_fn=sleep_mock, max_attempts=4)

    result = _run(
        service.advance_to_migration(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-backoff",
        )
    )

    assert result.run.state == RootKeyRemediationState.migration
    assert result.attempts == 3
    assert sleep_mock.await_count == 2
    first = sleep_mock.await_args_list[0].args[0]
    second = sleep_mock.await_args_list[1].args[0]
    assert first == 0.5
    assert second == 0.6


def test_cancellation_hook_prevents_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.discovery,
        status=RootKeyRemediationRunStatus.queued,
    )
    trace = _install_transition_store_fakes(monkeypatch, run=run)
    service = _enabled_service()

    with pytest.raises(Exception) as exc_info:
        _run(
            service.advance_to_migration(
                MagicMock(),
                tenant_id=tenant_id,
                run_id=run.id,
                transition_id="tx-cancel",
                cancellation_hook=lambda *_: True,
            )
        )

    err = exc_info.value
    assert hasattr(err, "classification")
    assert err.classification.code == "transition_cancelled"
    assert trace["transition_targets"] == []
    assert trace["event_calls"] == []
    assert trace["artifact_calls"] == []
