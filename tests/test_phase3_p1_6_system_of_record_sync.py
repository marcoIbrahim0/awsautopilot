"""Phase 3 P1.6 regression coverage for remediation state system-of-record sync."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid
from unittest.mock import MagicMock, patch

from backend.models.action import Action
from backend.models.action_external_link import ActionExternalLink
from backend.models.action_remediation_sync_event import ActionRemediationSyncEvent
from backend.models.action_remediation_sync_state import ActionRemediationSyncState
from backend.models.integration_event_receipt import IntegrationEventReceipt
from backend.models.tenant_integration_setting import TenantIntegrationSetting
from backend.services.action_remediation_state_machine import (
    DECISION_CANONICAL_APPLIED,
    DECISION_PRESERVE_INTERNAL,
    DECISION_RECONCILED,
    EVENT_EXTERNAL_OBSERVED,
    EVENT_INTERNAL_TRANSITION,
    EVENT_RECONCILIATION_APPLIED,
    EVENT_RECONCILIATION_QUEUED,
    SOURCE_EXTERNAL,
    SOURCE_RECONCILIATION,
    SYNC_STATUS_DRIFTED,
    SYNC_STATUS_IN_SYNC,
)
from backend.services.action_remediation_sync import (
    ExternalObservationResult,
    apply_canonical_action_status,
    reconcile_drifted_sync_states,
    record_external_status_observation,
    record_reconciled_external_status,
)
from backend.services.integration_sync import process_inbound_event
from backend.workers.jobs.reconcile_action_remediation_sync import (
    execute_reconcile_action_remediation_sync_job,
)


def _action(*, status: str) -> Action:
    tenant_id = uuid.uuid4()
    return Action(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_type="sg_restrict_public_ports",
        target_id="sg-0123456789abcdef0",
        account_id="123456789012",
        region="us-east-1",
        score=0,
        score_components={},
        priority=10,
        status=status,
        title="Restrict public security group ingress",
        description="Close public ingress on the affected security group.",
        control_id="EC2.53",
        resource_id="sg-0123456789abcdef0",
        resource_type="AwsEc2SecurityGroup",
        owner_type="unassigned",
        owner_key="unassigned",
        owner_label="Unassigned",
    )


def _sync_state(
    action: Action,
    *,
    provider: str = "jira",
    external_status: str | None,
    sync_status: str = SYNC_STATUS_IN_SYNC,
) -> ActionRemediationSyncState:
    return ActionRemediationSyncState(
        id=uuid.uuid4(),
        tenant_id=action.tenant_id,
        action_id=action.id,
        provider=provider,
        external_ref="JIRA-42",
        external_status=external_status,
        mapped_internal_status=None,
        canonical_internal_status=action.status,
        preferred_external_status="To Do",
        sync_status=sync_status,
        last_source="internal",
        resolution_decision=None,
        conflict_reason=None,
        sync_metadata={},
    )


def test_apply_canonical_action_status_marks_external_state_drift_and_records_internal_event() -> None:
    action = _action(status="open")
    state = _sync_state(action, external_status="To Do")
    session = MagicMock()

    with patch("backend.services.action_remediation_sync._find_existing_event", return_value=None):
        with patch("backend.services.action_remediation_sync._ensure_sync_states_for_action", return_value=[state]):
            with patch("backend.services.action_remediation_sync._record_event") as record_event:
                result = apply_canonical_action_status(
                    session,
                    action=action,
                    target_status="resolved",
                    source="api.actions.patch",
                    idempotency_key="patch-1",
                )

    assert result.changed is True
    assert result.impacted_sync_states == 1
    assert action.status == "resolved"
    assert state.canonical_internal_status == "resolved"
    assert state.sync_status == SYNC_STATUS_DRIFTED
    assert state.mapped_internal_status == "open"
    assert state.preferred_external_status == "Done"
    assert state.resolution_decision == DECISION_PRESERVE_INTERNAL
    kwargs = record_event.call_args.kwargs
    assert kwargs["event_type"] == EVENT_INTERNAL_TRANSITION
    assert kwargs["source"] == "api.actions.patch"
    assert kwargs["internal_status_before"] == "open"
    assert kwargs["internal_status_after"] == "resolved"
    assert kwargs["resolution_decision"] == DECISION_CANONICAL_APPLIED


def test_record_external_status_observation_preserves_canonical_state_and_audits_conflict() -> None:
    action = _action(status="resolved")
    state = _sync_state(action, external_status="Done")
    session = MagicMock()

    with patch("backend.services.action_remediation_sync._find_existing_event", return_value=None):
        with patch("backend.services.action_remediation_sync._get_or_create_sync_state", return_value=state):
            with patch("backend.services.action_remediation_sync._record_event") as record_event:
                result = record_external_status_observation(
                    session,
                    action=action,
                    provider="jira",
                    external_status="To Do",
                    external_ref="JIRA-42",
                    idempotency_key="webhook-1",
                )

    assert action.status == "resolved"
    assert result.sync_status == SYNC_STATUS_DRIFTED
    assert result.mapped_internal_status == "open"
    assert result.preferred_external_status == "Done"
    assert state.external_status == "To Do"
    assert state.sync_status == SYNC_STATUS_DRIFTED
    assert state.last_source == SOURCE_EXTERNAL
    assert state.resolution_decision == DECISION_PRESERVE_INTERNAL
    assert "remains authoritative" in str(state.conflict_reason)
    kwargs = record_event.call_args.kwargs
    assert kwargs["event_type"] == EVENT_EXTERNAL_OBSERVED
    assert kwargs["source"] == SOURCE_EXTERNAL
    assert kwargs["internal_status_before"] == "resolved"
    assert kwargs["internal_status_after"] == "resolved"
    assert kwargs["external_status"] == "To Do"
    assert kwargs["resolution_decision"] == DECISION_PRESERVE_INTERNAL


def test_record_external_status_observation_is_idempotent_on_replay() -> None:
    action = _action(status="resolved")
    state = _sync_state(action, external_status="Done")
    sentinel = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
    state.last_event_at = sentinel
    session = MagicMock()
    existing_event = ActionRemediationSyncEvent(
        id=uuid.uuid4(),
        tenant_id=action.tenant_id,
        action_id=action.id,
        source=SOURCE_EXTERNAL,
        event_type=EVENT_EXTERNAL_OBSERVED,
        provider="jira",
        idempotency_key="webhook-2",
    )

    with patch("backend.services.action_remediation_sync._find_existing_event", return_value=existing_event):
        with patch("backend.services.action_remediation_sync._load_sync_state", return_value=state):
            with patch("backend.services.action_remediation_sync._get_or_create_sync_state") as get_state:
                with patch("backend.services.action_remediation_sync._record_event") as record_event:
                    result = record_external_status_observation(
                        session,
                        action=action,
                        provider="jira",
                        external_status="To Do",
                        external_ref="JIRA-42",
                        idempotency_key="webhook-2",
                    )

    assert result.sync_status == SYNC_STATUS_IN_SYNC
    assert result.preferred_external_status == "Done"
    assert state.external_status == "Done"
    assert state.last_event_at == sentinel
    get_state.assert_not_called()
    record_event.assert_not_called()


def test_process_inbound_event_keeps_internal_canonical_state_under_conflict() -> None:
    action = _action(status="resolved")
    receipt = IntegrationEventReceipt(
        id=uuid.uuid4(),
        tenant_id=action.tenant_id,
        provider="jira",
        receipt_key="jira-webhook-1",
        external_id="JIRA-42",
        payload_hash="hash",
        status="processing",
        result_json={"payload": {}},
    )
    setting = TenantIntegrationSetting(
        id=uuid.uuid4(),
        tenant_id=action.tenant_id,
        provider="jira",
        enabled=True,
        outbound_enabled=True,
        inbound_enabled=True,
        auto_create=True,
        reopen_on_regression=True,
        config_json={},
    )
    link = ActionExternalLink(
        id=uuid.uuid4(),
        tenant_id=action.tenant_id,
        action_id=action.id,
        provider="jira",
        external_id="JIRA-42",
        external_status="Done",
        metadata_json={},
    )
    normalized = {
        "receipt_key": "jira-webhook-1",
        "external_id": "JIRA-42",
        "external_status": "To Do",
        "external_assignee_key": None,
        "external_assignee_label": None,
        "occurred_at": datetime(2026, 3, 12, 11, 0, tzinfo=timezone.utc),
        "payload_hash": "hash",
        "result_payload": {"issue": {"id": "JIRA-42"}},
    }
    sync_result = ExternalObservationResult(
        provider="jira",
        sync_status=SYNC_STATUS_DRIFTED,
        mapped_internal_status="open",
        preferred_external_status="Done",
    )

    with patch("backend.services.integration_sync.resolve_setting_for_webhook", return_value=setting):
        with patch("backend.services.integration_sync._normalize_inbound_event", return_value=normalized):
            with patch("backend.services.integration_sync._receipt_by_key", return_value=None):
                with patch("backend.services.integration_sync._create_receipt", return_value=receipt):
                        with patch("backend.services.integration_sync._find_link_for_inbound", return_value=link):
                            with patch("backend.services.integration_sync._is_stale_inbound", return_value=False):
                                with patch("backend.services.integration_sync._require_action", return_value=action):
                                    with patch(
                                        "backend.services.integration_sync._record_inbound_status",
                                        return_value=sync_result,
                                    ) as record_inbound_status:
                                        result = process_inbound_event(
                                            MagicMock(),
                                            provider="jira",
                                            webhook_token="token",
                                        event={"issue": {"id": "JIRA-42"}},
                                    )

    assert result.applied is True
    assert result.action_status == "resolved"
    assert action.status == "resolved"
    assert link.external_status == "To Do"
    assert receipt.status == "processed"
    assert receipt.result_json["result"]["action_status"] == "resolved"
    assert receipt.result_json["result"]["sync_status"] == SYNC_STATUS_DRIFTED
    record_inbound_status.assert_called_once()


def test_record_reconciled_external_status_marks_provider_back_in_sync() -> None:
    action = _action(status="resolved")
    state = _sync_state(action, external_status="To Do", sync_status=SYNC_STATUS_DRIFTED)
    state.mapped_internal_status = "open"
    state.preferred_external_status = "Done"
    state.last_source = SOURCE_EXTERNAL
    session = MagicMock()

    with patch("backend.services.action_remediation_sync._find_existing_event", return_value=None):
        with patch("backend.services.action_remediation_sync._get_or_create_sync_state", return_value=state):
            with patch("backend.services.action_remediation_sync._record_event") as record_event:
                result = record_reconciled_external_status(
                    session,
                    action=action,
                    provider="jira",
                    external_status="Done",
                    external_ref="JIRA-42",
                    idempotency_key="sync-task-1",
                )

    assert result.sync_status == SYNC_STATUS_IN_SYNC
    assert state.external_status == "Done"
    assert state.sync_status == SYNC_STATUS_IN_SYNC
    assert state.mapped_internal_status == "resolved"
    assert state.canonical_internal_status == "resolved"
    assert state.last_source == SOURCE_RECONCILIATION
    assert state.last_reconciled_at is not None
    kwargs = record_event.call_args.kwargs
    assert kwargs["event_type"] == EVENT_RECONCILIATION_APPLIED
    assert kwargs["source"] == SOURCE_RECONCILIATION
    assert kwargs["resolution_decision"] == DECISION_RECONCILED


def test_record_reconciled_external_status_is_idempotent_on_replay() -> None:
    action = _action(status="resolved")
    state = _sync_state(action, external_status="Done")
    state.last_source = SOURCE_RECONCILIATION
    sentinel = datetime(2026, 3, 12, 12, 30, tzinfo=timezone.utc)
    state.last_reconciled_at = sentinel
    session = MagicMock()
    existing_event = ActionRemediationSyncEvent(
        id=uuid.uuid4(),
        tenant_id=action.tenant_id,
        action_id=action.id,
        source=SOURCE_RECONCILIATION,
        event_type=EVENT_RECONCILIATION_APPLIED,
        provider="jira",
        idempotency_key="sync-task-2",
    )

    with patch("backend.services.action_remediation_sync._find_existing_event", return_value=existing_event):
        with patch("backend.services.action_remediation_sync._load_sync_state", return_value=state):
            with patch("backend.services.action_remediation_sync._get_or_create_sync_state") as get_state:
                with patch("backend.services.action_remediation_sync._record_event") as record_event:
                    result = record_reconciled_external_status(
                        session,
                        action=action,
                        provider="jira",
                        external_status="Reopened",
                        external_ref="JIRA-42",
                        idempotency_key="sync-task-2",
                    )

    assert result.sync_status == SYNC_STATUS_IN_SYNC
    assert state.external_status == "Done"
    assert state.last_reconciled_at == sentinel
    get_state.assert_not_called()
    record_event.assert_not_called()


def test_reconcile_drifted_sync_states_queues_manual_sync_and_audits_decision() -> None:
    action = _action(status="resolved")
    state = _sync_state(action, external_status="To Do", sync_status=SYNC_STATUS_DRIFTED)
    state.mapped_internal_status = "open"
    task_id = uuid.uuid4()
    session = MagicMock()

    with patch("backend.services.action_remediation_sync._load_drifted_states", return_value=[state]):
        with patch("backend.services.integration_sync.plan_manual_action_sync", return_value=[task_id]):
            with patch("backend.services.action_remediation_sync._record_event") as record_event:
                result = reconcile_drifted_sync_states(session, tenant_id=action.tenant_id)

    assert result.scanned == 1
    assert result.planned_tasks == 1
    assert result.skipped == 0
    assert result.task_ids_by_tenant == {action.tenant_id: [task_id]}
    assert state.last_source == SOURCE_RECONCILIATION
    kwargs = record_event.call_args.kwargs
    assert kwargs["event_type"] == EVENT_RECONCILIATION_QUEUED
    assert kwargs["source"] == SOURCE_RECONCILIATION
    assert kwargs["resolution_decision"] == DECISION_PRESERVE_INTERNAL


def test_reconcile_worker_dispatches_planned_sync_tasks() -> None:
    tenant_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = MagicMock()
    job = {
        "job_type": "reconcile_action_remediation_sync",
        "tenant_id": str(tenant_id),
        "provider": "jira",
        "created_at": datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc).isoformat(),
    }

    @contextmanager
    def _scope():
        yield session

    result = SimpleNamespace(
        scanned=1,
        planned_tasks=1,
        skipped=0,
        task_ids_by_tenant={tenant_id: [task_id]},
    )

    with patch("backend.workers.jobs.reconcile_action_remediation_sync.session_scope", return_value=_scope()):
        with patch("backend.workers.jobs.reconcile_action_remediation_sync.reconcile_drifted_sync_states", return_value=result) as reconcile:
            with patch(
                "backend.workers.jobs.reconcile_action_remediation_sync.dispatch_sync_tasks",
                return_value={"enqueued": 1},
            ) as dispatch:
                execute_reconcile_action_remediation_sync_job(job)

    reconcile.assert_called_once_with(
        session,
        tenant_id=tenant_id,
        provider="jira",
        action_ids=[],
        limit=100,
    )
    dispatch.assert_called_once_with([task_id], tenant_id=tenant_id)
