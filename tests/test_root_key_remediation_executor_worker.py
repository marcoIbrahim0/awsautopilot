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
from backend.services.root_key_remediation_closure import (
    RootKeyClosureSnapshot,
    RootKeyRemediationClosureService,
)
from backend.services.root_key_remediation_executor_worker import (
    FINAL_ROOT_KEY_MANUAL_DELETE_TASK_TYPE,
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
    def __init__(
        self,
        keys: list[tuple[str, str]],
        *,
        account_mfa_enabled: int = 1,
        get_account_summary_error: Exception | None = None,
    ) -> None:
        self._keys = [{"AccessKeyId": key_id, "Status": status} for key_id, status in keys]
        self._account_mfa_enabled = account_mfa_enabled
        self._get_account_summary_error = get_account_summary_error
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
        if self._get_account_summary_error is not None:
            raise self._get_account_summary_error
        return {
            "SummaryMap": {
                "AccountAccessKeysPresent": len(self._keys),
                "AccountMFAEnabled": self._account_mfa_enabled,
            }
        }


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

    async def _fail_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        run.state = RootKeyRemediationState.failed
        run.status = RootKeyRemediationRunStatus.failed
        return _result(run)

    sm.start_disable_window = AsyncMock(side_effect=_start_disable_window)
    sm.rollback = AsyncMock(side_effect=_rollback)
    sm.mark_needs_attention = AsyncMock(side_effect=_mark_needs_attention)
    sm.finalize_delete = AsyncMock(side_effect=_finalize_delete)
    sm.fail_run = AsyncMock(side_effect=_fail_run)
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
    task_mock = AsyncMock(return_value=(MagicMock(), True))
    monkeypatch.setattr(f"{module}.create_root_key_external_task_idempotent", task_mock)

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


def test_disable_preserved_caller_key_requires_operator_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIAPRESERVE0001", "Active")])
    mutation_session = _FakeSession("AKIAPRESERVE0001", iam_client)
    observer_session = _FakeSession("AKIAOBSERVER9001", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
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
    task_mock = AsyncMock(return_value=(MagicMock(), True))
    monkeypatch.setattr(f"{module}.create_root_key_external_task_idempotent", task_mock)

    result = _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-disable-preserved-caller",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.needs_attention
    assert service.start_disable_window.await_count == 1
    assert service.mark_needs_attention.await_count == 1
    assert service.rollback.await_count == 0
    assert iam_client.update_calls == []
    disable_artifacts = [
        call for call in artifact_mock.await_args_list if call.kwargs.get("artifact_type") == "disable_window_evidence"
    ]
    assert len(disable_artifacts) == 1
    metadata = disable_artifacts[0].kwargs.get("metadata_json")
    assert isinstance(metadata, dict)
    assert metadata.get("window_clean") is False
    assert metadata.get("operator_attention_reason") == "mutation_key_preserved_requires_new_credential_context"
    assert metadata.get("disabled_summary", {}).get("caller_key_preserved") == "AKIA...0001"
    assert task_mock.await_count == 1
    assert task_mock.await_args.kwargs["task_type"] == FINAL_ROOT_KEY_MANUAL_DELETE_TASK_TYPE


def test_rollback_reactivates_root_key(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIAROLLBACK00001", "Inactive")])
    mutation_session = _FakeSession("AKIAMUTATE000015", iam_client)
    observer_session = _FakeSession("AKIAOBSERVER00015", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
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
        worker.execute_rollback(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-rollback-success",
            rollback_reason="manual_validation_failed",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.rolled_back
    assert service.rollback.await_count == 1
    assert iam_client.update_calls == [("AKIAROLLBACK00001", "Active")]
    rollback_artifacts = [
        call for call in artifact_mock.await_args_list if call.kwargs.get("artifact_type") == "rollback_evidence"
    ]
    assert len(rollback_artifacts) == 1
    metadata = rollback_artifacts[0].kwargs.get("metadata_json")
    assert isinstance(metadata, dict)
    assert metadata.get("rollback_summary", {}).get("reactivated_count") == 1
    assert task_mock.await_count == 1


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
    assert iam_client.update_calls == [
        ("AKIATARGET0000002", "Inactive"),
        ("AKIATARGET0000002", "Active"),
    ]
    rollback_artifacts = [
        call for call in artifact_mock.await_args_list if call.kwargs.get("artifact_type") == "rollback_evidence"
    ]
    assert len(rollback_artifacts) == 1
    metadata = rollback_artifacts[0].kwargs.get("metadata_json")
    assert isinstance(metadata, dict)
    summary = metadata.get("rollback_summary")
    assert isinstance(summary, dict)
    assert summary.get("reactivated_count") == 1
    assert summary.get("disable_summary", {}).get("disabled_count") == 1
    assert summary.get("signals", {}).get("unknown_usage_count") == 1


def test_disable_signal_collection_falls_back_to_preserved_mutation_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    mutation_iam_client = _FakeIamClient([("AKIATARGET0000003", "Active")])
    observer_iam_client = _FakeIamClient(
        [],
        get_account_summary_error=RuntimeError("observer health access denied"),
    )
    mutation_session = _FakeSession("AKIAMUTATE000003", mutation_iam_client)
    observer_session = _FakeSession("AKIAOBSERVER0003", observer_iam_client)
    observer_usage = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=True, retries_used=0)
    )
    mutation_usage = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )
    usage_services = [observer_usage, mutation_usage]
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_services.pop(0),
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
            transition_id="tx-disable-mutation-fallback",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.disable_window
    assert service.rollback.await_count == 0
    assert task_mock.await_count == 0
    assert mutation_iam_client.update_calls == [("AKIATARGET0000003", "Inactive")]
    assert observer_usage.calls[0]["session_boto"] is observer_session
    assert mutation_usage.calls[0]["session_boto"] is mutation_session
    disable_artifacts = [
        call for call in artifact_mock.await_args_list if call.kwargs.get("artifact_type") == "disable_window_evidence"
    ]
    assert len(disable_artifacts) == 1
    metadata = disable_artifacts[0].kwargs.get("metadata_json")
    assert isinstance(metadata, dict)
    assert metadata.get("window_clean") is True
    assert metadata.get("root_keys_present") == 1


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


def test_delete_root_mfa_not_enrolled_marks_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000013", "Inactive")], account_mfa_enabled=0)
    mutation_session = _FakeSession("AKIAMUTATE000013", iam_client)
    observer_session = _FakeSession("AKIAOBSERVE000013", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
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

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=False,
            AWS_REGION="eu-north-1",
        ),
    )
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
            transition_id="tx-delete-mfa-gate",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.needs_attention
    assert service.mark_needs_attention.await_count == 1
    assert service.finalize_delete.await_count == 0
    reason = service.mark_needs_attention.await_args.kwargs["evidence_metadata"]["reason"]
    assert reason == "root_mfa_not_enrolled"
    assert iam_client.delete_calls == []


def test_is_disable_window_clean_allows_completed_manual_final_key_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
    )
    worker = RootKeyRemediationExecutorWorker()
    metadata_result = MagicMock()
    metadata_result.scalar_one_or_none.return_value = {
        "window_clean": False,
        "partial_data": False,
        "unknown_usage_count": 0,
        "breakage_signals": [],
        "operator_attention_reason": "mutation_key_preserved_requires_new_credential_context",
    }
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[metadata_result, task_result])

    assert _run(worker._is_disable_window_clean(db=db, run=run)) is True


def test_is_disable_window_clean_rejects_manual_final_key_handoff_with_breakage_signals() -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
    )
    worker = RootKeyRemediationExecutorWorker()
    metadata_result = MagicMock()
    metadata_result.scalar_one_or_none.return_value = {
        "window_clean": False,
        "partial_data": False,
        "unknown_usage_count": 0,
        "breakage_signals": ["usage_signal_collection_failed"],
        "operator_attention_reason": "mutation_key_preserved_requires_new_credential_context",
    }
    db = MagicMock()
    db.execute = AsyncMock(return_value=metadata_result)

    assert _run(worker._is_disable_window_clean(db=db, run=run)) is False


def test_delete_manual_final_key_handoff_finalizes_without_mutation_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([], account_mfa_enabled=1)
    observer_session = _FakeSession("AKIAOBSERVE000020", iam_client)
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: observer_session,
        observer_session_factory=lambda *_: observer_session,
        observer_only_delete_finalize=True,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=False,
            AWS_REGION="eu-north-1",
        ),
    )
    monkeypatch.setattr(
        f"{module}.create_root_key_remediation_artifact_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )

    result = _run(
        worker.execute_delete(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-delete-manual-handoff",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.completed
    assert service.finalize_delete.await_count == 1
    assert service.mark_needs_attention.await_count == 0
    assert iam_client.delete_calls == []


def test_delete_manual_final_key_handoff_blocks_when_root_key_still_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000021", "Active")], account_mfa_enabled=1)
    observer_session = _FakeSession("AKIAOBSERVE000021", iam_client)
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: observer_session,
        observer_session_factory=lambda *_: observer_session,
        observer_only_delete_finalize=True,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=False,
            AWS_REGION="eu-north-1",
        ),
    )
    monkeypatch.setattr(
        f"{module}.create_root_key_remediation_artifact_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )

    result = _run(
        worker.execute_delete(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="tx-delete-manual-handoff-active",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.needs_attention
    assert service.finalize_delete.await_count == 0
    assert service.mark_needs_attention.await_count == 1
    reason = service.mark_needs_attention.await_args.kwargs["evidence_metadata"]["reason"]
    assert reason == "delete_active_keys_present:1"


def test_delete_root_mfa_enrolled_allows_normal_delete_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000014", "Inactive")], account_mfa_enabled=1)
    mutation_session = _FakeSession("AKIAMUTATE000014", iam_client)
    observer_session = _FakeSession("AKIAOBSERVE000014", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
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

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=False,
            AWS_REGION="eu-north-1",
        ),
    )
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
            transition_id="tx-delete-mfa-pass",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.completed
    assert service.finalize_delete.await_count == 1
    assert service.mark_needs_attention.await_count == 0
    assert iam_client.delete_calls == ["AKIADELETE0000014"]


def test_delete_uses_closure_runtime_path_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000009", "Inactive")])
    mutation_session = _FakeSession("AKIAMUTATE000009", iam_client)
    observer_session = _FakeSession("AKIAOBSERVE000009", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )
    trigger_calls: list[str] = []

    async def trigger_stage(*, idempotency_key: str, **_: Any) -> dict[str, Any]:
        trigger_calls.append(idempotency_key.split(":")[-1])
        return {"accepted": True, "status_code": 202}

    async def poller(**_: Any) -> RootKeyClosureSnapshot:
        return RootKeyClosureSnapshot(
            action_resolved=True,
            finding_resolved=True,
            policy_preservation_passed=True,
            unresolved_external_tasks=0,
            payload={"phase": "complete"},
        )

    closure = RootKeyRemediationClosureService(
        enabled=True,
        max_polls=1,
        poll_interval_seconds=0,
        ingest_trigger=trigger_stage,
        compute_trigger=trigger_stage,
        reconcile_trigger=trigger_stage,
        poller=poller,
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_service,
        closure_service_factory=lambda: closure,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    artifact_mock = AsyncMock(return_value=(MagicMock(), True))
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.get_root_key_remediation_run",
        fake_get_run,
    )
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=True,
            AWS_REGION="eu-north-1",
        ),
    )
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", artifact_mock)
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.create_root_key_remediation_artifact_idempotent",
        artifact_mock,
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
            transition_id="tx-delete-closure",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.completed
    assert trigger_calls == ["ingest", "compute", "reconcile"]
    artifact_types = [call.kwargs["artifact_type"] for call in artifact_mock.await_args_list]
    assert "delete_window_evidence" in artifact_types
    assert "closure_cycle_summary" in artifact_types


def test_delete_closure_trigger_rejection_marks_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000010", "Inactive")])
    mutation_session = _FakeSession("AKIAMUTATE000010", iam_client)
    observer_session = _FakeSession("AKIAOBSERVE000010", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )
    poller = AsyncMock()

    async def reject_ingest(**_: Any) -> dict[str, Any]:
        return {"accepted": False, "status_code": 503}

    async def accepted_stage(**_: Any) -> dict[str, Any]:
        return {"accepted": True, "status_code": 202}

    closure = RootKeyRemediationClosureService(
        enabled=True,
        max_polls=1,
        poll_interval_seconds=0,
        ingest_trigger=reject_ingest,
        compute_trigger=accepted_stage,
        reconcile_trigger=accepted_stage,
        poller=poller,
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_service,
        closure_service_factory=lambda: closure,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    artifact_mock = AsyncMock(return_value=(MagicMock(), True))
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.get_root_key_remediation_run",
        fake_get_run,
    )
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=True,
            AWS_REGION="eu-north-1",
        ),
    )
    monkeypatch.setattr(f"{module}.create_root_key_remediation_artifact_idempotent", artifact_mock)
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.create_root_key_remediation_artifact_idempotent",
        artifact_mock,
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
            transition_id="tx-delete-closure-reject",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.needs_attention
    assert service.mark_needs_attention.await_count == 1
    assert service.finalize_delete.await_count == 0
    assert service.fail_run.await_count == 0
    poller.assert_not_awaited()


def test_delete_closure_policy_failure_marks_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000011", "Inactive")])
    mutation_session = _FakeSession("AKIAMUTATE000011", iam_client)
    observer_session = _FakeSession("AKIAOBSERVE000011", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )

    async def accepted_stage(**_: Any) -> dict[str, Any]:
        return {"accepted": True, "status_code": 202}

    async def policy_failed_poller(**_: Any) -> RootKeyClosureSnapshot:
        return RootKeyClosureSnapshot(
            action_resolved=False,
            finding_resolved=False,
            policy_preservation_passed=False,
            unresolved_external_tasks=0,
            payload={"required_safe_permissions_unchanged": False},
        )

    closure = RootKeyRemediationClosureService(
        enabled=True,
        max_polls=1,
        poll_interval_seconds=0,
        ingest_trigger=accepted_stage,
        compute_trigger=accepted_stage,
        reconcile_trigger=accepted_stage,
        poller=policy_failed_poller,
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_service,
        closure_service_factory=lambda: closure,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.get_root_key_remediation_run",
        fake_get_run,
    )
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=True,
            AWS_REGION="eu-north-1",
        ),
    )
    monkeypatch.setattr(
        f"{module}.create_root_key_remediation_artifact_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.create_root_key_remediation_artifact_idempotent",
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
            transition_id="tx-delete-closure-policy",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.needs_attention
    assert service.mark_needs_attention.await_count == 1
    assert service.finalize_delete.await_count == 0
    assert service.fail_run.await_count == 0


def test_delete_closure_timeout_fails_run(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    iam_client = _FakeIamClient([("AKIADELETE0000012", "Inactive")])
    mutation_session = _FakeSession("AKIAMUTATE000012", iam_client)
    observer_session = _FakeSession("AKIAOBSERVE000012", iam_client)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )

    async def accepted_stage(**_: Any) -> dict[str, Any]:
        return {"accepted": True, "status_code": 202}

    async def timeout_poller(**_: Any) -> RootKeyClosureSnapshot:
        return RootKeyClosureSnapshot(
            action_resolved=False,
            finding_resolved=False,
            policy_preservation_passed=True,
            unresolved_external_tasks=0,
            payload={"phase": "pending"},
        )

    closure = RootKeyRemediationClosureService(
        enabled=True,
        max_polls=1,
        poll_interval_seconds=0,
        ingest_trigger=accepted_stage,
        compute_trigger=accepted_stage,
        reconcile_trigger=accepted_stage,
        poller=timeout_poller,
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation_session,
        observer_session_factory=lambda *_: observer_session,
        usage_discovery_factory=lambda: usage_service,
        closure_service_factory=lambda: closure,
    )
    service = _state_machine(run)
    module = "backend.services.root_key_remediation_executor_worker"

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return run

    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.get_root_key_remediation_run",
        fake_get_run,
    )
    monkeypatch.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    monkeypatch.setattr(
        module + ".settings",
        SimpleNamespace(
            ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
            ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=True,
            AWS_REGION="eu-north-1",
        ),
    )
    monkeypatch.setattr(
        f"{module}.create_root_key_remediation_artifact_idempotent",
        AsyncMock(return_value=(MagicMock(), True)),
    )
    monkeypatch.setattr(
        "backend.services.root_key_remediation_closure.create_root_key_remediation_artifact_idempotent",
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
            transition_id="tx-delete-closure-timeout",
            state_machine=service,
        )
    )

    assert result.run.state == RootKeyRemediationState.failed
    assert service.fail_run.await_count == 1
    assert service.finalize_delete.await_count == 0
    assert service.mark_needs_attention.await_count == 0


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
