from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.enums import (
    RootKeyExternalTaskStatus,
    RootKeyRemediationMode,
    RootKeyRemediationRunStatus,
    RootKeyRemediationState,
)
from backend.models.root_key_remediation_run import RootKeyRemediationRun
from backend.services.root_key_remediation_closure import (
    RootKeyClosureSnapshot,
    RootKeyRemediationClosureService,
)
from backend.services.root_key_remediation_executor_worker import (
    RootKeyRemediationExecutorWorker,
)
from backend.services.root_key_remediation_state_machine import (
    RootKeyRemediationStateMachineService,
    RootKeyStateMachineError,
)

_FIXTURE_DIR = Path("/Users/marcomaher/AWS Security Autopilot/tests/fixtures")
_SCENARIOS_FIXTURE = _FIXTURE_DIR / "root_key_safe_remediation_plan_scenarios.json"
_EXPECTED_MATRIX_FIXTURE = _FIXTURE_DIR / "root_key_safe_remediation_plan_expected_matrix.json"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _now() -> datetime:
    return datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)


def _build_run(
    *,
    tenant_id: uuid.UUID,
    state: RootKeyRemediationState,
    status: RootKeyRemediationRunStatus,
) -> RootKeyRemediationRun:
    run = RootKeyRemediationRun(
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
        correlation_id=f"corr-{tenant_id.hex[:12]}",
        idempotency_key=f"idem-{tenant_id.hex[:12]}",
        lock_version=1,
        retry_count=0,
        started_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )
    return run


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
        return {"AccessKeyMetadata": [dict(item) for item in self._keys]}

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


@dataclass
class _InMemoryStore:
    run: RootKeyRemediationRun

    def __post_init__(self) -> None:
        self.event_by_idem: dict[str, Any] = {}
        self.artifact_by_idem: dict[str, Any] = {}
        self.task_by_idem: dict[str, Any] = {}
        self.events: list[Any] = []
        self.artifacts: list[Any] = []
        self.tasks: list[Any] = []

    async def get_run(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> RootKeyRemediationRun | None:
        if tenant_id != self.run.tenant_id:
            return None
        if run_id != self.run.id:
            return None
        return self.run

    async def transition(
        self,
        _db: Any,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        expected_lock_version: int,
        new_state: RootKeyRemediationState,
        new_status: RootKeyRemediationRunStatus,
        retry_increment: int = 0,
        rollback_reason: str | None = None,
        completed_at: datetime | None = None,
        exception_expiry: datetime | None = None,
    ) -> RootKeyRemediationRun | None:
        del exception_expiry
        if tenant_id != self.run.tenant_id or run_id != self.run.id:
            return None
        if expected_lock_version != self.run.lock_version:
            return None
        self.run.state = new_state
        self.run.status = new_status
        self.run.retry_count = int(self.run.retry_count) + int(retry_increment)
        self.run.rollback_reason = rollback_reason
        self.run.completed_at = completed_at
        self.run.lock_version = int(self.run.lock_version) + 1
        self.run.updated_at = _now()
        return self.run

    async def create_event(self, _db: Any, **kwargs: Any) -> tuple[Any, bool]:
        key = str(kwargs.get("idempotency_key") or uuid.uuid4())
        existing = self.event_by_idem.get(key)
        if existing is not None:
            return existing, False
        event = SimpleNamespace(
            id=uuid.uuid4(),
            run_id=kwargs["run_id"],
            event_type=kwargs["event_type"],
            state=kwargs["state"],
            status=kwargs["status"],
            payload=kwargs.get("payload"),
            rollback_reason=kwargs.get("rollback_reason"),
            created_at=_now(),
            completed_at=None,
        )
        self.event_by_idem[key] = event
        self.events.append(event)
        return event, True

    async def create_artifact(self, _db: Any, **kwargs: Any) -> tuple[Any, bool]:
        key = str(kwargs.get("idempotency_key") or uuid.uuid4())
        existing = self.artifact_by_idem.get(key)
        if existing is not None:
            return existing, False
        artifact = SimpleNamespace(
            id=uuid.uuid4(),
            run_id=kwargs["run_id"],
            artifact_type=kwargs["artifact_type"],
            metadata_json=kwargs.get("metadata_json"),
            state=kwargs["state"],
            status=kwargs["status"],
            artifact_ref=kwargs.get("artifact_ref"),
            artifact_sha256=kwargs.get("artifact_sha256"),
            redaction_applied=True,
            created_at=_now(),
            completed_at=_now(),
        )
        self.artifact_by_idem[key] = artifact
        self.artifacts.append(artifact)
        return artifact, True

    async def create_external_task(self, _db: Any, **kwargs: Any) -> tuple[Any, bool]:
        key = str(kwargs.get("idempotency_key") or uuid.uuid4())
        existing = self.task_by_idem.get(key)
        if existing is not None:
            return existing, False
        task = SimpleNamespace(
            id=uuid.uuid4(),
            run_id=kwargs["run_id"],
            task_type=kwargs["task_type"],
            task_payload=kwargs.get("task_payload"),
            status=kwargs["status"],
            task_result=None,
            completed_at=None,
            actor_metadata=kwargs.get("actor_metadata"),
            created_at=_now(),
            updated_at=_now(),
        )
        self.task_by_idem[key] = task
        self.tasks.append(task)
        return task, True


def _install_store(monkeypatch: pytest.MonkeyPatch, store: _InMemoryStore) -> None:
    sm_module = "backend.services.root_key_remediation_state_machine"
    worker_module = "backend.services.root_key_remediation_executor_worker"
    closure_module = "backend.services.root_key_remediation_closure"
    monkeypatch.setattr(f"{sm_module}.get_root_key_remediation_run", store.get_run)
    monkeypatch.setattr(f"{sm_module}.transition_root_key_remediation_run_state", store.transition)
    monkeypatch.setattr(f"{sm_module}.create_root_key_remediation_event_idempotent", store.create_event)
    monkeypatch.setattr(
        f"{sm_module}.create_root_key_remediation_artifact_idempotent",
        store.create_artifact,
    )
    monkeypatch.setattr(f"{worker_module}.get_root_key_remediation_run", store.get_run)
    monkeypatch.setattr(
        f"{worker_module}.create_root_key_remediation_artifact_idempotent",
        store.create_artifact,
    )
    monkeypatch.setattr(
        f"{worker_module}.create_root_key_external_task_idempotent",
        store.create_external_task,
    )
    monkeypatch.setattr(f"{closure_module}.get_root_key_remediation_run", store.get_run)
    monkeypatch.setattr(
        f"{closure_module}.create_root_key_remediation_artifact_idempotent",
        store.create_artifact,
    )


def _state_machine() -> RootKeyRemediationStateMachineService:
    return RootKeyRemediationStateMachineService(
        enabled=True,
        strict_transitions_enabled=True,
        delete_enabled=True,
        sleep_fn=AsyncMock(),
    )


def _worker(
    *,
    mutation_access_key_id: str | None,
    observer_access_key_id: str | None,
    iam_client: _FakeIamClient,
    usage_result: Any,
    closure_service_factory: Any | None = None,
) -> RootKeyRemediationExecutorWorker:
    usage_service = _FakeUsageDiscoveryService(usage_result)
    mutation = _FakeSession(mutation_access_key_id, iam_client)
    observer = _FakeSession(observer_access_key_id, iam_client)
    return RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: mutation,
        observer_session_factory=lambda *_: observer,
        usage_discovery_factory=lambda: usage_service,
        closure_service_factory=closure_service_factory,
    )


def _scenario_managed_zero_interaction(mp: pytest.MonkeyPatch) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    _install_store(mp, store)
    mp.setattr(
        "backend.services.root_key_remediation_executor_worker.settings.ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED",
        True,
    )
    state_machine = _state_machine()
    iam = _FakeIamClient([("AKIATARGET0000001", "Active")])
    worker = _worker(
        mutation_access_key_id="AKIAMUTATE000001",
        observer_access_key_id="AKIAOBSERVER0001",
        iam_client=iam,
        usage_result=SimpleNamespace(managed_count=1, unknown_count=0, partial_data=False, retries_used=0),
    )
    mp.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    mp.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-001:disable",
            state_machine=state_machine,
        )
    )
    _run(
        worker.execute_delete(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-001:delete",
            state_machine=state_machine,
        )
    )
    assert iam.update_calls == [("AKIATARGET0000001", "Inactive")]
    assert iam.delete_calls == ["AKIATARGET0000001"]
    return {"final_state": run.state.value, "final_status": run.status.value}


def _scenario_unknown_dependency_needs_attention(mp: pytest.MonkeyPatch) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    _install_store(mp, store)
    mp.setattr(
        "backend.services.root_key_remediation_executor_worker.settings.ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED",
        True,
    )
    state_machine = _state_machine()
    iam = _FakeIamClient([("AKIAUNKNOWN000001", "Inactive")])
    worker = _worker(
        mutation_access_key_id="AKIAMUTATE000002",
        observer_access_key_id="AKIAOBSERVER0002",
        iam_client=iam,
        usage_result=SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0),
    )
    mp.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    mp.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=True))
    _run(
        worker.execute_delete(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-002:delete",
            state_machine=state_machine,
        )
    )
    return {"final_state": run.state.value, "final_status": run.status.value}


def _scenario_external_task_to_delete(mp: pytest.MonkeyPatch) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.needs_attention,
        status=RootKeyRemediationRunStatus.waiting_for_user,
    )
    store = _InMemoryStore(run)
    _install_store(mp, store)
    mp.setattr(
        "backend.services.root_key_remediation_executor_worker.settings.ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED",
        True,
    )
    task, _ = _run(
        store.create_external_task(
            MagicMock(),
            run_id=run.id,
            task_type="await_manual_validation",
            status=RootKeyExternalTaskStatus.open,
            idempotency_key="rk-e2e-003:task-open",
        )
    )
    task.status = RootKeyExternalTaskStatus.completed
    task.task_result = {"check_id": "verified"}
    task.completed_at = _now()
    state_machine = _state_machine()
    _run(
        state_machine.advance_to_migration(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-003:migrate",
        )
    )
    _run(
        state_machine.advance_to_validation(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-003:validate",
        )
    )
    iam = _FakeIamClient([("AKIAEXTTASK000001", "Active")])
    worker = _worker(
        mutation_access_key_id="AKIAMUTATE000003",
        observer_access_key_id="AKIAOBSERVER0003",
        iam_client=iam,
        usage_result=SimpleNamespace(managed_count=1, unknown_count=0, partial_data=False, retries_used=0),
    )
    mp.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
    mp.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
    _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-003:disable",
            state_machine=state_machine,
        )
    )
    _run(
        worker.execute_delete(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-003:delete",
            state_machine=state_machine,
        )
    )
    assert task.status == RootKeyExternalTaskStatus.completed
    return {"final_state": run.state.value, "final_status": run.status.value}


def _scenario_breakage_rollback(mp: pytest.MonkeyPatch) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    _install_store(mp, store)
    state_machine = _state_machine()
    iam = _FakeIamClient([("AKIABREAK0000001", "Active")])
    worker = _worker(
        mutation_access_key_id="AKIAMUTATE000004",
        observer_access_key_id="AKIAOBSERVER0004",
        iam_client=iam,
        usage_result=SimpleNamespace(managed_count=0, unknown_count=1, partial_data=False, retries_used=1),
    )
    _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-004:disable",
            state_machine=state_machine,
        )
    )
    rollback_tasks = [task for task in store.tasks if task.task_type == "rollback_alert"]
    assert rollback_tasks
    return {"final_state": run.state.value, "final_status": run.status.value}


def _scenario_closure_path(mp: pytest.MonkeyPatch) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.delete_window,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    _install_store(mp, store)
    state_machine = _state_machine()
    trigger_calls: list[str] = []

    async def trigger_stage(*, idempotency_key: str, **_: Any) -> dict[str, Any]:
        stage = idempotency_key.split(":")[-1]
        trigger_calls.append(stage)
        return {"accepted": True, "status_code": 202}

    async def poller(*, poll_attempt: int, **_: Any) -> RootKeyClosureSnapshot:
        if poll_attempt == 1:
            return RootKeyClosureSnapshot(
                action_resolved=False,
                finding_resolved=False,
                policy_preservation_passed=True,
                unresolved_external_tasks=0,
                payload={"phase": "warming"},
            )
        return RootKeyClosureSnapshot(
            action_resolved=True,
            finding_resolved=True,
            policy_preservation_passed=True,
            unresolved_external_tasks=0,
            payload={"phase": "complete"},
        )

    closure = RootKeyRemediationClosureService(
        enabled=True,
        max_polls=3,
        poll_interval_seconds=0,
        ingest_trigger=trigger_stage,
        compute_trigger=trigger_stage,
        reconcile_trigger=trigger_stage,
        poller=poller,
    )
    result = _run(
        closure.execute_closure_cycle(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-005:closure",
            state_machine=state_machine,
        )
    )
    assert result.closure_completed is True
    assert result.polls_used == 2
    assert trigger_calls == ["ingest", "compute", "reconcile"]
    return {"final_state": run.state.value, "final_status": run.status.value}


def _scenario_policy_preservation_fail_closed(mp: pytest.MonkeyPatch) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.delete_window,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    _install_store(mp, store)
    state_machine = _state_machine()

    async def trigger_stage(**_: Any) -> dict[str, Any]:
        return {"accepted": True, "status_code": 202}

    async def poller(**_: Any) -> RootKeyClosureSnapshot:
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
        ingest_trigger=trigger_stage,
        compute_trigger=trigger_stage,
        reconcile_trigger=trigger_stage,
        poller=poller,
    )
    result = _run(
        closure.execute_closure_cycle(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-006:closure",
            state_machine=state_machine,
        )
    )
    assert result.closure_completed is False
    assert run.state == RootKeyRemediationState.needs_attention
    return {"final_state": run.state.value, "final_status": run.status.value}


def _scenario_self_cutoff_prevention(mp: pytest.MonkeyPatch) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.validation,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    _install_store(mp, store)
    state_machine = _state_machine()
    iam = _FakeIamClient([("AKIASELF00000001", "Active")])
    shared_session = _FakeSession("AKIASELF00000001", iam)
    usage_service = _FakeUsageDiscoveryService(
        SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0)
    )
    worker = RootKeyRemediationExecutorWorker(
        mutation_session_factory=lambda *_: shared_session,
        observer_session_factory=lambda *_: shared_session,
        usage_discovery_factory=lambda: usage_service,
    )
    _run(
        worker.execute_disable(
            MagicMock(),
            tenant_id=tenant_id,
            run_id=run.id,
            transition_id="rk-e2e-007:disable",
            state_machine=state_machine,
        )
    )
    assert iam.update_calls == []
    return {"final_state": run.state.value, "final_status": run.status.value}


_CASE_EXECUTORS: dict[str, Any] = {
    "RK-E2E-001": _scenario_managed_zero_interaction,
    "RK-E2E-002": _scenario_unknown_dependency_needs_attention,
    "RK-E2E-003": _scenario_external_task_to_delete,
    "RK-E2E-004": _scenario_breakage_rollback,
    "RK-E2E-005": _scenario_closure_path,
    "RK-E2E-006": _scenario_policy_preservation_fail_closed,
    "RK-E2E-007": _scenario_self_cutoff_prevention,
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_key_plan_matrix_matches_expected_artifact() -> None:
    scenarios = _load_json(_SCENARIOS_FIXTURE)
    expected = _load_json(_EXPECTED_MATRIX_FIXTURE)
    generated_results: list[dict[str, Any]] = []

    for case in scenarios["scenarios"]:
        case_id = case["case_id"]
        with pytest.MonkeyPatch.context() as mp:
            outcome = _CASE_EXECUTORS[case_id](mp)
        final_state = outcome["final_state"]
        final_status = outcome["final_status"]
        passed = (
            final_state == case["expected_final_state"]
            and final_status == case["expected_final_status"]
        )
        generated_results.append(
            {
                "case_id": case_id,
                "path": case["path"],
                "acceptance_case_ids": case["acceptance_case_ids"],
                "status": "pass" if passed else "fail",
                "final_state": final_state,
                "final_status": final_status,
            }
        )

    generated = {
        "spec_acceptance_doc": scenarios["spec_acceptance_doc"],
        "source_fixture": str(_SCENARIOS_FIXTURE),
        "results": generated_results,
    }
    assert generated == expected


def test_worker_delete_runtime_wires_closure_and_summary_artifacts() -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.disable_window,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
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

    with pytest.MonkeyPatch.context() as mp:
        _install_store(mp, store)
        mp.setattr(
            "backend.services.root_key_remediation_executor_worker.settings",
            SimpleNamespace(
                ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED=True,
                ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED=True,
                AWS_REGION="eu-north-1",
            ),
        )
        iam = _FakeIamClient([("AKIARUNTIME000001", "Inactive")])
        closure = RootKeyRemediationClosureService(
            enabled=True,
            max_polls=1,
            poll_interval_seconds=0,
            ingest_trigger=trigger_stage,
            compute_trigger=trigger_stage,
            reconcile_trigger=trigger_stage,
            poller=poller,
        )
        worker = _worker(
            mutation_access_key_id="AKIAMUTATERUNTIME1",
            observer_access_key_id="AKIAOBSERVERUNTIME1",
            iam_client=iam,
            usage_result=SimpleNamespace(managed_count=0, unknown_count=0, partial_data=False, retries_used=0),
            closure_service_factory=lambda: closure,
        )
        mp.setattr(worker, "_is_disable_window_clean", AsyncMock(return_value=True))
        mp.setattr(worker, "_has_unknown_active_dependencies", AsyncMock(return_value=False))
        _run(
            worker.execute_delete(
                MagicMock(),
                tenant_id=tenant_id,
                run_id=run.id,
                transition_id="rk-runtime-closure:delete",
                state_machine=_state_machine(),
            )
        )

    artifact_types = [artifact.artifact_type for artifact in store.artifacts]
    assert run.state == RootKeyRemediationState.completed
    assert run.status == RootKeyRemediationRunStatus.completed
    assert trigger_calls == ["ingest", "compute", "reconcile"]
    assert "delete_window_evidence" in artifact_types
    assert "closure_cycle_summary" in artifact_types


def test_root_key_plan_auth_scope_fail_closed() -> None:
    tenant_id = uuid.uuid4()
    wrong_tenant = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.delete_window,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    with pytest.MonkeyPatch.context() as mp:
        _install_store(mp, store)
        closure = RootKeyRemediationClosureService(enabled=True)
        with pytest.raises(RootKeyStateMachineError) as exc_info:
            _run(
                closure.execute_closure_cycle(
                    MagicMock(),
                    tenant_id=wrong_tenant,
                    run_id=run.id,
                    transition_id="rk-e2e-auth:closure",
                    state_machine=_state_machine(),
                )
            )

    assert exc_info.value.classification.code == "tenant_scope_violation"


def test_root_key_plan_retry_path_is_idempotent() -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(
        tenant_id=tenant_id,
        state=RootKeyRemediationState.delete_window,
        status=RootKeyRemediationRunStatus.running,
    )
    store = _InMemoryStore(run)
    trigger_calls: list[str] = []

    async def trigger_stage(*, idempotency_key: str, **_: Any) -> dict[str, Any]:
        trigger_calls.append(idempotency_key)
        return {"accepted": True, "status_code": 202}

    async def poller(**_: Any) -> RootKeyClosureSnapshot:
        return RootKeyClosureSnapshot(
            action_resolved=True,
            finding_resolved=True,
            policy_preservation_passed=True,
            unresolved_external_tasks=0,
            payload={"attempt": "complete"},
        )

    with pytest.MonkeyPatch.context() as mp:
        _install_store(mp, store)
        closure = RootKeyRemediationClosureService(
            enabled=True,
            max_polls=1,
            poll_interval_seconds=0,
            ingest_trigger=trigger_stage,
            compute_trigger=trigger_stage,
            reconcile_trigger=trigger_stage,
            poller=poller,
        )
        first = _run(
            closure.execute_closure_cycle(
                MagicMock(),
                tenant_id=tenant_id,
                run_id=run.id,
                transition_id="rk-e2e-retry:closure",
                state_machine=_state_machine(),
            )
        )
        first_call_count = len(trigger_calls)
        second = _run(
            closure.execute_closure_cycle(
                MagicMock(),
                tenant_id=tenant_id,
                run_id=run.id,
                transition_id="rk-e2e-retry:closure",
                state_machine=_state_machine(),
            )
        )

    assert first.closure_completed is True
    assert second.idempotency_replayed is True
    assert len(trigger_calls) == first_call_count
