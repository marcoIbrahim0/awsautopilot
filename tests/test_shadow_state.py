from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.models import Finding
from backend.workers.services import shadow_state


def _build_session_for_overlay_rowcount(rowcount: int) -> MagicMock:
    session = MagicMock()

    shadow_query = MagicMock()
    shadow_query.filter.return_value.first.return_value = None

    finding_query = MagicMock()
    finding_query.filter.return_value.update.return_value = rowcount

    session.query.side_effect = [shadow_query, finding_query]
    return session


def _build_evaluation() -> SimpleNamespace:
    return SimpleNamespace(
        resource_id="AWS::::Account:029037611564",
        resource_type="AwsAccount",
        control_id="EC2.7",
        status="RESOLVED",
        status_reason="inventory_confirmed_compliant",
        evidence_ref={"source": "inventory"},
        state_confidence=95,
    )


def _build_session_for_overlay_and_promotion_rowcount(
    overlay_rowcount: int,
    promotion_rowcount: int,
) -> tuple[MagicMock, MagicMock]:
    session = MagicMock()

    shadow_query = MagicMock()
    shadow_query.filter.return_value.first.return_value = None

    overlay_query = MagicMock()
    overlay_query.filter.return_value.update.return_value = overlay_rowcount

    promotion_query = MagicMock()
    promotion_query.filter.return_value.update.return_value = promotion_rowcount

    session.query.side_effect = [shadow_query, overlay_query, promotion_query]
    return session, promotion_query


def test_upsert_shadow_state_warns_when_overlay_update_matches_zero_rows(monkeypatch) -> None:
    monkeypatch.setattr(shadow_state.settings, "CONTROL_PLANE_SHADOW_MODE", True, raising=False)
    warning = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "warning", warning)

    session = _build_session_for_overlay_rowcount(0)
    applied, changed = shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(),
    )

    assert applied is True
    assert changed is True
    warning.assert_called_once()
    assert "matched zero rows" in str(warning.call_args[0][0])


def test_upsert_shadow_state_does_not_warn_when_overlay_update_matches_rows(monkeypatch) -> None:
    monkeypatch.setattr(shadow_state.settings, "CONTROL_PLANE_SHADOW_MODE", True, raising=False)
    warning = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "warning", warning)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(),
    )

    warning.assert_not_called()


def test_upsert_shadow_state_warns_when_promotion_update_matches_zero_rows(monkeypatch) -> None:
    monkeypatch.setattr(shadow_state.settings, "CONTROL_PLANE_SHADOW_MODE", False, raising=False)
    monkeypatch.setattr(shadow_state.settings, "CONTROL_PLANE_AUTHORITATIVE_CONTROLS", "EC2.7", raising=False)
    warning = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "warning", warning)

    session, promotion_query = _build_session_for_overlay_and_promotion_rowcount(overlay_rowcount=1, promotion_rowcount=0)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(),
    )

    warning.assert_called_once()
    assert "shadow promotion matched zero rows" in str(warning.call_args[0][0])

    update_payload = promotion_query.filter.return_value.update.call_args.args[0]
    assert update_payload[Finding.status] == "RESOLVED"
    assert Finding.resolved_at in update_payload
