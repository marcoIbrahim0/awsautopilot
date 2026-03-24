from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.models.enums import (
    ActionGroupConfirmationSource,
    ActionGroupExecutionStatus,
    ActionGroupStatusBucket,
)
from backend.services.action_run_confirmation import (
    evaluate_confirmation_for_action,
    record_execution_result,
    record_non_executable_result,
    SUCCESS_NEEDS_FOLLOWUP_KIND,
)


def _mock_membership(action_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        action_id=action_id,
    )


def _mock_state() -> SimpleNamespace:
    return SimpleNamespace(
        latest_run_status_bucket=ActionGroupStatusBucket.not_run_yet,
        latest_run_id=None,
        last_attempt_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        last_confirmed_at=None,
        last_confirmation_source=None,
    )


def _mock_execute_with_findings(findings: list[SimpleNamespace]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = findings
    return result


def _mock_execute_with_rows(*rows: object) -> MagicMock:
    result = MagicMock()
    result.one_or_none.return_value = rows[0] if rows else None
    result.all.return_value = rows[1] if len(rows) > 1 else []
    return result


def test_apply_success_without_aws_confirmation_stays_not_successful() -> None:
    action_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    finding = SimpleNamespace(
        status="NEW",
        last_observed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        shadow_status_normalized=None,
        shadow_last_observed_event_time=None,
        shadow_last_evaluated_at=None,
    )
    session = MagicMock()
    session.execute.return_value = _mock_execute_with_findings([finding])

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            result = evaluate_confirmation_for_action(
                session,
                action_id=action_id,
                since_run_started=state.last_attempt_at,
                execution_status=ActionGroupExecutionStatus.failed,
            )

    assert result["confirmed"] is False
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_not_successful


def test_record_execution_result_success_sets_pending_confirmation_bucket() -> None:
    action_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    session = MagicMock()

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            with patch(
                "backend.services.action_run_confirmation._load_latest_run_context",
                return_value=(None, None, None, None, None),
            ):
                result = record_execution_result(
                    session,
                    action_id=action_id,
                    latest_run_id=uuid.uuid4(),
                    execution_status=ActionGroupExecutionStatus.success,
                    finished_at=datetime.now(timezone.utc),
                )

    assert result is state
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_pending_confirmation


def test_record_execution_result_success_sets_needs_followup_bucket_for_additive_run() -> None:
    action_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    session = MagicMock()

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            with patch(
                "backend.services.action_run_confirmation._load_latest_run_context",
                return_value=(
                    None,
                    None,
                    None,
                    None,
                    {
                        "selected_strategy": "sg_restrict_public_ports_guided",
                        "strategy_inputs": {"access_mode": "close_public"},
                    },
                ),
            ):
                result = record_execution_result(
                    session,
                    action_id=action_id,
                    latest_run_id=uuid.uuid4(),
                    execution_status=ActionGroupExecutionStatus.success,
                    finished_at=datetime.now(timezone.utc),
                )

    assert result is state
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_needs_followup


def test_apply_success_without_aws_confirmation_stays_pending_confirmation() -> None:
    action_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    state.latest_run_status_bucket = ActionGroupStatusBucket.run_successful_pending_confirmation
    finding = SimpleNamespace(
        status="NEW",
        last_observed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        shadow_status_normalized=None,
        shadow_last_observed_event_time=None,
        shadow_last_evaluated_at=None,
    )
    session = MagicMock()
    session.execute.return_value = _mock_execute_with_findings([finding])

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            with patch(
                "backend.services.action_run_confirmation._load_latest_run_context",
                return_value=(None, "finished", None, state.last_attempt_at, None),
            ):
                result = evaluate_confirmation_for_action(
                    session,
                    action_id=action_id,
                    since_run_started=state.last_attempt_at,
                    execution_status=ActionGroupExecutionStatus.success,
                )

    assert result["confirmed"] is False
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_pending_confirmation


def test_apply_success_without_aws_confirmation_moves_additive_run_to_needs_followup() -> None:
    action_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    state.latest_run_status_bucket = ActionGroupStatusBucket.run_successful_pending_confirmation
    finding = SimpleNamespace(
        status="NEW",
        last_observed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        shadow_status_normalized=None,
        shadow_last_observed_event_time=None,
        shadow_last_evaluated_at=None,
    )
    session = MagicMock()
    session.execute.return_value = _mock_execute_with_findings([finding])

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            with patch(
                "backend.services.action_run_confirmation._load_latest_run_context",
                return_value=(
                    ActionGroupExecutionStatus.success,
                    "finished",
                    None,
                    state.last_attempt_at,
                    {
                        "selected_strategy": "sg_restrict_public_ports_guided",
                        "strategy_inputs": {"access_mode": "close_public"},
                    },
                ),
            ):
                result = evaluate_confirmation_for_action(
                    session,
                    action_id=action_id,
                    since_run_started=state.last_attempt_at,
                    execution_status=ActionGroupExecutionStatus.success,
                )

    assert result["confirmed"] is False
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_needs_followup


def test_additive_run_followup_kind_is_detected() -> None:
    action_id = uuid.uuid4()
    latest_run_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    state.latest_run_id = latest_run_id
    state.latest_run_status_bucket = ActionGroupStatusBucket.run_not_successful
    started_at = datetime.now(timezone.utc) - timedelta(minutes=4)
    finding = SimpleNamespace(
        status="NEW",
        last_observed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        shadow_status_normalized="OPEN",
        shadow_last_observed_event_time=datetime.now(timezone.utc),
        shadow_last_evaluated_at=datetime.now(timezone.utc),
    )
    session = MagicMock()
    session.execute.return_value = _mock_execute_with_findings([finding])

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            with patch(
                "backend.services.action_run_confirmation._load_latest_run_context",
                return_value=(
                    ActionGroupExecutionStatus.success,
                    "finished",
                    {"result_type": "applied"},
                    started_at,
                    {
                        "selected_strategy": "sg_restrict_public_ports_guided",
                        "strategy_inputs": {"access_mode": "close_public"},
                    },
                ),
            ):
                result = record_execution_result(
                    session,
                    action_id=action_id,
                    latest_run_id=latest_run_id,
                    execution_status=ActionGroupExecutionStatus.success,
                    finished_at=datetime.now(timezone.utc),
                )

    assert result is state
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_needs_followup
    assert SUCCESS_NEEDS_FOLLOWUP_KIND == "unrestricted_public_access_retained"


def test_record_non_executable_result_sets_metadata_only_bucket() -> None:
    action_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    session = MagicMock()

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            result = record_non_executable_result(
                session,
                action_id=action_id,
                latest_run_id=uuid.uuid4(),
                finished_at=datetime.now(timezone.utc),
            )

    assert result is state
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_finished_metadata_only


def test_evaluate_confirmation_uses_persisted_latest_run_success_context() -> None:
    action_id = uuid.uuid4()
    latest_run_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    state.latest_run_id = latest_run_id
    state.latest_run_status_bucket = ActionGroupStatusBucket.run_not_successful
    started_at = datetime.now(timezone.utc) - timedelta(minutes=4)
    finding = SimpleNamespace(
        status="NEW",
        last_observed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        shadow_status_normalized="OPEN",
        shadow_last_observed_event_time=datetime.now(timezone.utc),
        shadow_last_evaluated_at=datetime.now(timezone.utc),
    )
    run_row = SimpleNamespace(
        execution_status=ActionGroupExecutionStatus.success,
        run_status="finished",
        raw_result={"result_type": "applied"},
        run_started_at=started_at,
        remediation_artifacts=None,
    )
    session = MagicMock()
    session.execute.return_value = _mock_execute_with_findings([finding])

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            with patch(
                "backend.services.action_run_confirmation._load_latest_run_context",
                return_value=(
                    run_row.execution_status,
                    run_row.run_status,
                    run_row.raw_result,
                    run_row.run_started_at,
                    run_row.remediation_artifacts,
                ),
            ):
                result = evaluate_confirmation_for_action(session, action_id=action_id)

    assert result["confirmed"] is False
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_pending_confirmation


def test_security_hub_confirmation_flips_to_successful_confirmed() -> None:
    action_id = uuid.uuid4()
    membership = _mock_membership(action_id)
    state = _mock_state()
    confirmed_at = datetime.now(timezone.utc)
    finding = SimpleNamespace(
        status="RESOLVED",
        last_observed_at=confirmed_at,
        updated_at=confirmed_at,
        shadow_status_normalized=None,
        shadow_last_observed_event_time=None,
        shadow_last_evaluated_at=None,
    )
    session = MagicMock()
    session.execute.return_value = _mock_execute_with_findings([finding])

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            result = evaluate_confirmation_for_action(
                session,
                action_id=action_id,
                since_run_started=state.last_attempt_at,
            )

    assert result["confirmed"] is True
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_successful_confirmed
    assert state.last_confirmation_source == ActionGroupConfirmationSource.security_hub
