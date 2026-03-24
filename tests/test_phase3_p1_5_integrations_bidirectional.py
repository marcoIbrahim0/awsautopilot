"""Phase 3 P1.5 regression coverage for bi-directional Jira/ServiceNow/Slack integrations."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models.action import Action
from backend.models.action_external_link import ActionExternalLink
from backend.models.integration_event_receipt import IntegrationEventReceipt
from backend.models.integration_sync_task import IntegrationSyncTask
from backend.models.tenant_integration_setting import TenantIntegrationSetting
from backend.services.integration_adapters import (
    IntegrationAdapterUnavailableError,
    IntegrationAdapterValidationError,
    ProviderSyncResult,
)
from backend.services.integration_sync import (
    ACTION_STATUS_OPEN,
    ACTION_STATUS_RESOLVED,
    SYNC_OPERATION_CREATE,
    SYNC_OPERATION_REOPEN,
    SYNC_OPERATION_UPDATE,
    _build_sync_payload,
    process_inbound_event,
    plan_action_sync_tasks,
)
from backend.workers.jobs.compute_actions import execute_compute_actions_job
from backend.workers.jobs.integration_sync import execute_integration_sync_job


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_result(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _session_with_identity_flush() -> MagicMock:
    session = MagicMock()
    added: list[object] = []

    def _add(instance: object) -> None:
        added.append(instance)

    def _flush() -> None:
        for instance in added:
            if getattr(instance, "id", None) is None:
                setattr(instance, "id", uuid.uuid4())

    session.add.side_effect = _add
    session.flush.side_effect = _flush
    return session


def _action(
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    status: str,
    owner_key: str,
    owner_label: str,
) -> Action:
    return Action(
        id=action_id,
        tenant_id=tenant_id,
        action_type="sg_restrict_public_ports",
        target_id=f"target-{action_id}",
        account_id="123456789012",
        region="us-east-1",
        score=95,
        score_components={"severity": 90},
        priority=95,
        status=status,
        title=f"Action {action_id}",
        description="Restrict public access",
        control_id="EC2.53",
        resource_id="sg-0123456789abcdef0",
        resource_type="AwsEc2SecurityGroup",
        owner_type="user",
        owner_key=owner_key,
        owner_label=owner_label,
    )


def _setting(*, tenant_id: uuid.UUID, provider: str = "jira") -> TenantIntegrationSetting:
    return TenantIntegrationSetting(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        provider=provider,
        enabled=True,
        outbound_enabled=True,
        inbound_enabled=True,
        auto_create=True,
        reopen_on_regression=True,
        config_json={},
        secret_json={"webhook_token": "secret-token", "api_token": "token"},
    )


def _link(
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    provider: str,
    external_id: str,
    external_key: str | None = None,
    external_status: str | None = None,
) -> ActionExternalLink:
    return ActionExternalLink(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_id=action_id,
        provider=provider,
        external_id=external_id,
        external_key=external_key,
        external_status=external_status,
        metadata_json={},
    )


def _task(
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    provider: str = "jira",
    operation: str = SYNC_OPERATION_UPDATE,
) -> IntegrationSyncTask:
    return IntegrationSyncTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_id=action_id,
        provider=provider,
        operation=operation,
        status="queued",
        trigger="test",
        request_signature=f"sig-{uuid.uuid4()}",
        payload_json={
            "action_id": str(action_id),
            "title": "Restrict public admin ports",
            "description": "Restrict public admin ports",
            "external_status": "To Do",
            "external_assignee_key": "user-123",
            "external_assignee_label": "Platform Team",
            "operation": operation,
            "external_id": "10001",
            "external_key": "SEC-1",
        },
        attempt_count=0,
    )


def test_plan_action_sync_tasks_create_update_and_reopen_operations() -> None:
    tenant_id = uuid.uuid4()
    create_action = _action(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        status=ACTION_STATUS_OPEN,
        owner_key="owner-create",
        owner_label="Owner Create",
    )
    update_action = _action(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        status=ACTION_STATUS_RESOLVED,
        owner_key="owner-update",
        owner_label="Owner Update",
    )
    reopen_action = _action(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        status=ACTION_STATUS_OPEN,
        owner_key="owner-reopen",
        owner_label="Owner Reopen",
    )
    update_link = _link(
        tenant_id=tenant_id,
        action_id=update_action.id,
        provider="jira",
        external_id="10002",
        external_key="SEC-2",
        external_status="Done",
    )
    reopen_link = _link(
        tenant_id=tenant_id,
        action_id=reopen_action.id,
        provider="jira",
        external_id="10003",
        external_key="SEC-3",
        external_status="Done",
    )
    session = _session_with_identity_flush()
    session.execute.side_effect = [
        _scalars_result([create_action, update_action, reopen_action]),
        _scalars_result([update_link, reopen_link]),
        _scalars_result([_setting(tenant_id=tenant_id, provider="jira")]),
        _scalar_result(None),
        _scalar_result(None),
        _scalar_result(None),
    ]

    task_ids = plan_action_sync_tasks(
        session,
        tenant_id=tenant_id,
        action_ids=[create_action.id, update_action.id, reopen_action.id],
        reopened_action_ids={reopen_action.id},
        trigger="worker.compute_actions",
    )

    assert len(task_ids) == 3
    created_tasks = [call.args[0] for call in session.add.call_args_list]
    assert [task.operation for task in created_tasks] == [
        SYNC_OPERATION_CREATE,
        SYNC_OPERATION_UPDATE,
        SYNC_OPERATION_REOPEN,
    ]
    assert created_tasks[0].payload_json["external_assignee_key"] == "owner-create"
    assert created_tasks[1].payload_json["external_id"] == "10002"
    assert created_tasks[1].payload_json["external_key"] == "SEC-2"
    assert created_tasks[2].payload_json["external_status"] == "To Do"


def test_plan_action_sync_tasks_requeues_failed_task_for_same_signature() -> None:
    tenant_id = uuid.uuid4()
    action = _action(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        status=ACTION_STATUS_OPEN,
        owner_key="unassigned",
        owner_label="Unassigned",
    )
    failed_task = IntegrationSyncTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_id=action.id,
        provider="jira",
        operation=SYNC_OPERATION_CREATE,
        status="failed",
        trigger="api.manual_sync",
        request_signature="sig-existing",
        payload_json={"operation": "create"},
        result_json={"old": "result"},
        attempt_count=1,
        last_error="boom",
        started_at=datetime(2026, 3, 21, 20, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 21, 20, 1, tzinfo=timezone.utc),
    )
    session = _session_with_identity_flush()
    session.execute.side_effect = [
        _scalars_result([action]),
        _scalars_result([]),
        _scalars_result([_setting(tenant_id=tenant_id, provider="jira")]),
        _scalar_result(failed_task),
    ]

    task_ids = plan_action_sync_tasks(
        session,
        tenant_id=tenant_id,
        action_ids=[action.id],
        reopened_action_ids=set(),
        trigger="worker.compute_actions",
    )

    assert task_ids == [failed_task.id]
    assert failed_task.status == "queued"
    assert failed_task.operation == SYNC_OPERATION_CREATE
    assert failed_task.trigger == "worker.compute_actions"
    assert failed_task.last_error is None
    assert failed_task.result_json is None
    assert failed_task.started_at is None
    assert failed_task.completed_at is None
    session.add.assert_not_called()


def test_plan_action_sync_tasks_omits_non_user_owner_from_outbound_payload() -> None:
    tenant_id = uuid.uuid4()
    action = _action(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        status=ACTION_STATUS_OPEN,
        owner_key="ebs",
        owner_label="Amazon EBS",
    )
    action.owner_type = "service"
    session = _session_with_identity_flush()
    session.execute.side_effect = [
        _scalars_result([action]),
        _scalars_result([]),
        _scalars_result([_setting(tenant_id=tenant_id, provider="jira")]),
        _scalar_result(None),
    ]

    task_ids = plan_action_sync_tasks(
        session,
        tenant_id=tenant_id,
        action_ids=[action.id],
        reopened_action_ids=set(),
        trigger="worker.compute_actions",
    )

    assert len(task_ids) == 1
    created_task = session.add.call_args.args[0]
    assert created_task.payload_json["external_assignee_key"] is None
    assert created_task.payload_json["external_assignee_label"] is None


def test_build_sync_payload_includes_drift_version_metadata_for_reconciliation() -> None:
    tenant_id = uuid.uuid4()
    action = _action(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        status=ACTION_STATUS_OPEN,
        owner_key="owner-open",
        owner_label="Owner Open",
    )
    link = _link(
        tenant_id=tenant_id,
        action_id=action.id,
        provider="jira",
        external_id="10049",
        external_key="KAN-7",
        external_status="Done",
    )
    link.last_inbound_event_at = datetime(2026, 3, 24, 2, 10, tzinfo=timezone.utc)

    payload = _build_sync_payload(
        action=action,
        setting=_setting(tenant_id=tenant_id, provider="jira"),
        link=link,
        operation=SYNC_OPERATION_UPDATE,
    )

    assert payload["external_status"] == "To Do"
    assert payload["observed_external_status"] == "Done"
    assert payload["observed_external_event_at"] == "2026-03-24T02:10:00+00:00"


def test_process_inbound_event_preserves_canonical_platform_state_from_jira_webhook() -> None:
    tenant_id = uuid.uuid4()
    action = _action(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        status=ACTION_STATUS_RESOLVED,
        owner_key="owner-before",
        owner_label="Owner Before",
    )
    link = _link(
        tenant_id=tenant_id,
        action_id=action.id,
        provider="jira",
        external_id="10001",
        external_key="SEC-1",
        external_status="Done",
    )
    session = _session_with_identity_flush()
    session.execute.side_effect = [
        _scalar_result(_setting(tenant_id=tenant_id, provider="jira")),
        _scalar_result(None),
        _scalar_result(link),
        _scalar_result(action),
    ]

    with patch("backend.services.integration_sync.record_reconciled_external_status") as mock_reconcile:
        with patch(
            "backend.services.integration_sync.record_external_status_observation",
            return_value=SimpleNamespace(sync_status="drifted", mapped_internal_status="in_progress"),
        ) as mock_observe:
            result = process_inbound_event(
                session,
                provider="jira",
                webhook_token="secret-token",
                event={
                    "webhookEvent": "jira:issue_updated",
                    "issue": {
                        "key": "SEC-1",
                        "fields": {
                            "status": {"name": "In Progress"},
                            "assignee": {"accountId": "acct-42", "displayName": "On Call"},
                            "updated": "2026-03-12T10:15:00Z",
                        },
                    },
                },
                event_id="jira-evt-1",
            )

    assert result.replayed is False
    assert result.applied is True
    assert result.action_id == action.id
    assert result.action_status == "resolved"
    assert result.owner_key == "acct-42"
    assert action.status == "resolved"
    assert action.owner_key == "acct-42"
    assert action.owner_label == "On Call"
    assert link.external_status == "In Progress"
    assert link.external_assignee_key == "acct-42"
    assert link.external_assignee_label == "On Call"
    assert link.last_inbound_event_at == datetime(2026, 3, 12, 10, 15, tzinfo=timezone.utc)
    receipt = session.add.call_args.args[0]
    assert isinstance(receipt, IntegrationEventReceipt)
    assert receipt.status == "processed"
    assert receipt.action_id == action.id
    assert receipt.result_json["result"]["action_status"] == "resolved"
    assert receipt.result_json["result"]["sync_status"] == "drifted"
    mock_reconcile.assert_not_called()
    mock_observe.assert_called_once()


def test_process_inbound_event_replays_duplicate_receipt_after_integrity_error() -> None:
    tenant_id = uuid.uuid4()
    existing_receipt = IntegrationEventReceipt(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        provider="jira",
        receipt_key="jira-evt-2",
        external_id="SEC-9",
        action_id=uuid.uuid4(),
        payload_hash="hash-1",
        status="processed",
        result_json={"result": {"action_status": "resolved", "owner_key": "acct-7"}},
    )
    session = _session_with_identity_flush()
    session.execute.side_effect = [
        _scalar_result(_setting(tenant_id=tenant_id, provider="jira")),
        _scalar_result(None),
        _scalar_result(existing_receipt),
    ]
    session.flush.side_effect = [
        IntegrityError("insert", {}, Exception("duplicate receipt")),
    ]

    result = process_inbound_event(
        session,
        provider="jira",
        webhook_token="secret-token",
        event={"issue": {"key": "SEC-9", "fields": {"status": {"name": "Done"}}}},
        event_id="jira-evt-2",
    )

    assert result.replayed is True
    assert result.applied is False
    assert result.action_id == existing_receipt.action_id
    assert result.action_status == "resolved"
    assert result.owner_key == "acct-7"
    session.rollback.assert_called_once()


def test_execute_integration_sync_job_successfully_syncs_reopen_task() -> None:
    tenant_id = uuid.uuid4()
    task = _task(
        tenant_id=tenant_id,
        action_id=uuid.uuid4(),
        provider="jira",
        operation=SYNC_OPERATION_REOPEN,
    )
    session = MagicMock()
    setting = _setting(tenant_id=tenant_id, provider="jira")
    link = _link(
        tenant_id=tenant_id,
        action_id=task.action_id,
        provider="jira",
        external_id="10001",
        external_key="SEC-1",
    )

    with patch("backend.workers.jobs.integration_sync.get_session", return_value=session):
        with patch("backend.workers.jobs.integration_sync.get_sync_task", side_effect=[task, task]) as mock_get_task:
            with patch(
                "backend.workers.jobs.integration_sync.get_sync_runtime",
                return_value=(setting, None),
            ) as mock_runtime:
                with patch("backend.workers.jobs.integration_sync.mark_sync_task_running") as mock_mark_running:
                    with patch(
                        "backend.workers.jobs.integration_sync.sync_provider_item",
                        return_value=ProviderSyncResult(
                            external_id="10001",
                            external_key="SEC-1",
                            external_url="https://jira.example/browse/SEC-1",
                            external_status="To Do",
                            external_assignee_key="user-123",
                            external_assignee_label="Platform Team",
                            metadata={},
                        ),
                    ) as mock_sync:
                        with patch(
                            "backend.workers.jobs.integration_sync.complete_sync_task",
                            return_value=link,
                        ) as mock_complete:
                            execute_integration_sync_job(
                                {
                                    "job_type": "integration_sync",
                                    "task_id": str(task.id),
                                    "tenant_id": str(tenant_id),
                                    "created_at": "2026-03-12T11:00:00Z",
                                }
                            )

    assert mock_get_task.call_count == 2
    mock_runtime.assert_called_once_with(session, task=task)
    mock_mark_running.assert_called_once_with(session, task)
    assert mock_sync.call_args.kwargs["payload"]["operation"] == SYNC_OPERATION_REOPEN
    mock_complete.assert_called_once()
    assert session.commit.call_count == 2
    session.close.assert_called_once()


def test_execute_integration_sync_job_retryable_failure_marks_task_failed_and_reraises() -> None:
    tenant_id = uuid.uuid4()
    task = _task(tenant_id=tenant_id, action_id=uuid.uuid4(), provider="slack", operation=SYNC_OPERATION_UPDATE)
    task.status = "queued"
    session = MagicMock()

    with patch("backend.workers.jobs.integration_sync.get_session", return_value=session):
        with patch("backend.workers.jobs.integration_sync.get_sync_task", side_effect=[task, task]):
            with patch(
                "backend.workers.jobs.integration_sync.get_sync_runtime",
                return_value=(_setting(tenant_id=tenant_id, provider="slack"), None),
            ):
                with patch("backend.workers.jobs.integration_sync.sync_provider_item") as mock_sync:
                    mock_sync.side_effect = IntegrationAdapterUnavailableError("ratelimited", "ratelimited")
                    with pytest.raises(RuntimeError):
                        execute_integration_sync_job(
                            {
                                "job_type": "integration_sync",
                                "task_id": str(task.id),
                                "tenant_id": str(tenant_id),
                                "created_at": "2026-03-12T11:30:00Z",
                            }
                        )

    assert task.status == "failed"
    assert task.last_error == "ratelimited"
    session.rollback.assert_called_once()
    assert session.commit.call_count == 2
    session.close.assert_called_once()


def test_execute_integration_sync_job_validation_failure_is_not_retried() -> None:
    tenant_id = uuid.uuid4()
    task = _task(tenant_id=tenant_id, action_id=uuid.uuid4(), provider="servicenow", operation=SYNC_OPERATION_UPDATE)
    session = MagicMock()

    with patch("backend.workers.jobs.integration_sync.get_session", return_value=session):
        with patch("backend.workers.jobs.integration_sync.get_sync_task", side_effect=[task, task]):
            with patch(
                "backend.workers.jobs.integration_sync.get_sync_runtime",
                return_value=(_setting(tenant_id=tenant_id, provider="servicenow"), None),
            ):
                with patch("backend.workers.jobs.integration_sync.sync_provider_item") as mock_sync:
                    mock_sync.side_effect = IntegrationAdapterValidationError("bad_request", "bad_request")
                    execute_integration_sync_job(
                        {
                            "job_type": "integration_sync",
                            "task_id": str(task.id),
                            "tenant_id": str(tenant_id),
                            "created_at": "2026-03-12T11:45:00Z",
                        }
                    )

    assert task.status == "failed"
    assert task.last_error == "bad_request"
    session.rollback.assert_called_once()
    assert session.commit.call_count == 2
    session.close.assert_called_once()


def test_execute_compute_actions_job_enqueues_sync_for_resolved_and_reopened_actions() -> None:
    tenant_id = uuid.uuid4()
    created_id = uuid.uuid4()
    updated_id = uuid.uuid4()
    resolved_id = uuid.uuid4()
    reopened_id = uuid.uuid4()
    call_order: list[str] = []
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = False

    with patch("backend.workers.jobs.compute_actions.session_scope", return_value=ctx):
        with patch(
            "backend.workers.jobs.compute_actions.compute_actions_for_tenant",
            side_effect=lambda *args, **kwargs: call_order.append("compute") or {
                "actions_created": 1,
                "actions_updated": 1,
                "actions_resolved": 1,
                "action_findings_linked": 4,
                "created_action_ids": [created_id],
                "updated_action_ids": [updated_id],
                "resolved_action_ids": [resolved_id],
                "reopened_action_ids": [reopened_id],
            },
        ):
            with patch(
                "backend.workers.jobs.compute_actions.plan_action_sync_tasks",
                side_effect=lambda *args, **kwargs: call_order.append("plan") or [uuid.uuid4()],
            ) as mock_plan:
                with patch(
                    "backend.workers.jobs.compute_actions.dispatch_sync_tasks",
                    side_effect=lambda *args, **kwargs: call_order.append("dispatch") or {"enqueued": 1, "failed": 0},
                ) as mock_dispatch:
                    with patch(
                        "backend.workers.jobs.compute_actions.maybe_schedule_attack_path_refresh",
                        side_effect=lambda *args, **kwargs: call_order.append("attack_path") or True,
                    ) as mock_attack_path:
                        execute_compute_actions_job(
                            {
                                "job_type": "compute_actions",
                                "tenant_id": str(tenant_id),
                                "created_at": "2026-03-12T12:00:00Z",
                            }
                        )

    assert set(mock_plan.call_args.kwargs["action_ids"]) == {
        created_id,
        updated_id,
        resolved_id,
        reopened_id,
    }
    assert mock_plan.call_args.kwargs["reopened_action_ids"] == {reopened_id}
    mock_dispatch.assert_called_once()
    mock_attack_path.assert_called_once()
    assert call_order == ["compute", "plan", "dispatch", "attack_path"]
