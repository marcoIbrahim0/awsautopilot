from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.models.enums import (
    ActionGroupConfirmationSource,
    ActionGroupStatusBucket,
)
from backend.services.action_run_confirmation import evaluate_confirmation_for_action


def _mock_membership(action_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        action_id=action_id,
    )


def _mock_state() -> SimpleNamespace:
    return SimpleNamespace(
        latest_run_status_bucket=ActionGroupStatusBucket.not_run_yet,
        last_attempt_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        last_confirmed_at=None,
        last_confirmation_source=None,
    )


def _mock_query_with_findings(findings: list[SimpleNamespace]) -> MagicMock:
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = findings
    return query


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
    session.query.return_value = _mock_query_with_findings([finding])

    with patch("backend.services.action_run_confirmation._get_membership", return_value=membership):
        with patch("backend.services.action_run_confirmation._get_or_create_state", return_value=state):
            result = evaluate_confirmation_for_action(session, action_id=action_id, since_run_started=state.last_attempt_at)

    assert result["confirmed"] is False
    assert state.latest_run_status_bucket == ActionGroupStatusBucket.run_not_successful


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
    session.query.return_value = _mock_query_with_findings([finding])

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
