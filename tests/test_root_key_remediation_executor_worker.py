from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.enums import (
    RootKeyRemediationMode,
    RootKeyRemediationRunStatus,
    RootKeyRemediationState,
)
from backend.services.root_key_remediation_executor_worker import (
    RootKeyRemediationExecutorWorker,
)
from backend.services.root_key_remediation_state_machine import RootKeyStateMachineError


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _build_run(
    *,
    tenant_id: uuid.UUID,
    state: RootKeyRemediationState,
    status: RootKeyRemediationRunStatus,
) -> Any:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
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
        mode=RootKeyRemediationMode.manual,
        correlation_id="corr-root-key-worker",
        created_at=now,
        updated_at=now,
    )


def _result(run: Any, *, state_changed: bool = True) -> Any:
    return SimpleNamespace(
        run=run,
        state_changed=state_changed,
        event_created=True,
        evidence_created=True,
        attempts=1,
    )


class _FakeCredentials:
    def __init__(self, access_key: str | None) -> None:
        self.access_key = access_key

    def get_frozen_credentials(self) -> "_FakeCredentials":
        return self


class _FakeIamClient:
    def __init__(self, keys: list[tuple[str, str]]) -> None:
        self._keys = [{"AccessKeyId": key_id, "Status": status} for key_id, status in keys]
        self.update_calls: list[tuple[str, str]] = []
        self.delete_calls: list[str] = []

    def list_access_keys(self) -> dict[str, Any]:
        snapshot = [dict(item) for item in self._keys]
        return {"AccessKeyMetadata": snapshot}

    def update_access_key(self, *, AccessKeyId: str, Status: str) -> None:
        self.update_calls.append((AccessKeyId, Status))
        for item in self._keys:
            if item["AccessKeyId"] == AccessKeyId:
                item["Status"] = Status

    def delete_access_key(self, *, AccessKeyId: str) -> None:
        self.delete_calls.append(AccessKeyId)
        self._keys = [item for item in self._keys if item["AccessKeyId"] != AccessKeyId]

    def get_account_summary(self) -> dict[str, Any]:
        return {"SummaryMap": {"AccountAccessKeysPresent": len(self._keys)}}


class _FakeSession:
    def __init__(self, access_key_id: str | None, iam_client: _FakeIamClient) -> None:
        self._access_key_id = access_key_id
        self._iam_client = iam_client

    def get_credentials(self) -> _FakeCredentials | None:
        if self._access_key_id is None:
            return None
        return _FakeCredentials(self._access_key_id)

    def client(self, service_name: str, *, region_name: str | None = None) -> _FakeIamClient:
        del region_name
        assert service_name == "iam"
        return self._iam_client


class _FakeUsageDiscoveryService:
    def __init__(self, result: Any) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def discover_and_classify(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._result


def _state_machine(run: Any) -> Any:
    sm = SimpleNamespace()

    async def _start_disable_window(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        run.state = RootKeyRemediationState.disable_window
        run.status = RootKeyRemediationRunStatus.running
        return _result(run)

    async def _rollback(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        run.state = RootKeyRemediationState.rolled_back
        run.status = RootKeyRemediationRunStatus.failed
        return _result(run)

    async def _mark_needs_attention(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        run.state = RootKeyRemediationState.needs_attention
        run.status = RootKeyRemediationRunStatus.waiting_for_user
        return _result(run)

    async def _finalize_delete(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        run.state = RootKeyRemediationState.completed
        run.status = RootKeyRemediationRunStatus.completed
        return _result(run)

    sm.start_disable_window = AsyncMock(side_effect=_start_disable_window)
    sm.rollback = AsyncMock(side_effect=_rollback)
    sm.mark_needs_attention = AsyncMock(side_effect=_mark_needs_attention)
    sm.finalize_delete = AsyncMock(side_effect=_finalize_delete)
    return sm


def test_self_cutoff_regression_marks_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIASELF00000001", "Active")])
    shared_session = _FakeSession("AKIASELF00000001", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: shared_session,
        observer_session_factory=lambda *_: shared_session,
        usage_discovery_factory=lambda: usage_service,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    artifact_mock = AsyncMock(return_value=(MagicMock(), True))
    task_mock = AsyncMock(return_value=(MagicMock(), True))
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", artifact_mock)
    monkeypatch.setattr(f"{module}.create_root_key_external_task_idempotent", task_mock)

    result = _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-disable-guard",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.needs_attention
    assert service.mark_needs_attention.await_count == 1
    assert service.start_disable_window.await_count == 0
    assert iam_client.update_calls == []
    assert artifact_mock.await_count == 0
    assert task_mock.await_count == 0


def test_disable_clean_window_success(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIATARGET0000001", "Active")])
    mutation_session = _FakeSession("AKIAMUTATE000001", iam_client)
    observer_session = _FakeSession("AKIAOBSERVER0001", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=1, unknown_count=0, partial_data=False, retries_used=0)
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_service,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    artifact_mock = AsyncMock(return_value=(MagicMock(), True))
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", artifact_mock)
    monkeypatch.setattr(
        f"{module}.create_root_key_external_task_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )

    result = _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-disable-success",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.disable_window
    assert service.start_disable_window.await_count == 1
    assert service.rollback.await_count == 0
    assert iam_client.update_calls == [("AKIATARGET0000001", "Inactive")]
    disable_artifacts = [
        call for call in artifact_mock.await_args_list if call.kwargs.get("artifact_type") == "disable_window_evidence"
    ]
    assert len(disable_artifacts) == 1
    metadata = disable_artifacts[0].kwargs.get("metadata_json")
    assert isinstance(metadata, dict)
    assert metadata.get("window_clean") is True


def test_disable_breakage_signal_triggers_rollback_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIATARGET0000002", "Active")])
    mutation_session = _FakeSession("AKIAMUTATE000002", iam_client)
    observer_session = _FakeSession("AKIAOBSERVER0002", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=1, partial_data=False, retries_used=1)
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_service,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    artifact_mock = AsyncMock(return_value=(MagicMock(), True))
    task_mock = AsyncMock(return_value=(MagicMock(), True))
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", artifact_mock)
    monkeypatch.setattr(f"{module}.create_root_key_external_task_idempotent", task_mock)

    result = _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-disable-breakage",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.rolled_back
    assert service.rollback.await_count == 1
    assert task_mock.await_count == 1
    assert iam_client.update_calls == [("AKIATARGET0000002", "Inactive")]


@pytest.mark.parametrize(
    ("run_state", "clean_window", "delete_enabled", "unknown_deps", "expected_reason"),
    [
        (
            RootKeyRemediationState.validation,
            True,
            True,
            False,
            "delete_validation_not_passed",
        ),
        (
            RootKeyRemediationState.disable_window,
            False,
            True,
            False,
            "delete_disable_window_not_clean",
        ),
        (
            RootKeyRemediationState.disable_window,
            True,
            False,
            False,
            "delete_window_disabled",
        ),
        (
            RootKeyRemediationState.disable_window,
            True,
            True,
            True,
            "delete_unknown_dependencies",
        ),
    ],
)
def test_delete_gating_failures_mark_needs_attention(
    monkeypatch: pytest.MonkeyPatch,
    run_state: RootKeyRemediationState,
    clean_window: bool,
    delete_enabled: bool,
    unknown_deps: bool,
    expected_reason: str,
) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=run_state,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000001", "Inactive")])
    session = _FakeSession("AKIAOBSERVER0003", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: session,
        observer_session_factory=lambda *_: session,
        usage_discovery_factory=lambda: usage_service,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(
        worker,
        "_is_disable_window_clean",
        AsyncMock(return_value=clean_window),
    )
    monkeypatch.setattr(
        worker,
        "_has_unknown_active_dependencies",
        AsyncMock(return_value=unknown_deps),
    )
    monkeypatch.setattr(module + ".settings", SimpleNamespace(ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=delete_enabled))
    monkeypatch.setattr(
        f"{module}.create_root_key_remediation_artifact_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )
    monkeypatch.setattr(
        f"{module}.create_root_key_external_task_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )

    result = _run(
        worker.execute_delete(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-delete-gate",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.needs_attention
    assert service.mark_needs_attention.await_count == 1
    assert service.finalize_delete.await_count == 0
    reason = service.mark_needs_attention.await_args.kwargs["evidence_metadata"]["reason"]
    assert expected_reason in reason


def test_worker_auth_scope_violation_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    iam_client = _FakeIamClient([("AKIAAUTH00000001", "Active")])
    session = _FakeSession("AKIAAUTH00000001", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: session,
        observer_session_factory=lambda *_: session,
        usage_discovery_factory=lambda: usage_service,
    )
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return None

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)

    with pytest.raises(RootKeyStateMachineError) as exc_info:
        _run(
            worker.execute_disable(
                MagicMock(),
                tenant_id=tenant_id,
                run_id=run_id,
                transition_id="tx-auth-fail",
                state_machine=_state_machine(
                    _build_run(
                        tenant_id=tenant_id,
                        state=RootKeyRemediationState.validation,
                        status=RootKeyRemediationRunStatus.running,
                    )
                ),
            )
        )

    assert exc_info.value.classification.code == "tenant_scope_violation"


def test_disable_retry_is_idempotent_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIARETRY00000001", "Active")])
    mutation_session = _FakeSession("AKIAMUTATE000004", iam_client)
    observer_session = _FakeSession("AKIAOBSERVER0004", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=1, unknown_count=0, partial_data=False, retries_used=0)
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_service,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    artifact_mock = AsyncMock(side_effect=[(MagicMock(), True), (MagicMock(), False)])
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", artifact_mock)
    monkeypatch.setattr(
        f"{module}.create_root_key_external_task_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )

    first = _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-disable-retry",
            state_machine=service,
        )
    )
    second = _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-disable-retry",
            state_machine=service,
        )
    )

    assert first.run.state == RootKeyRemediationState.disable_window
    assert second.run.state == RootKeyRemediationState.disable_window
    assert iam_client.update_calls == [("AKIARETRY00000001", "Inactive")]
    assert service.rollback.await_count == 0

