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


def _build_session_for_overlay_and_canonical_rowcount(
    overlay_rowcount: int,
    canonical_rowcount: int,
) -> tuple[MagicMock, MagicMock]:
    session = MagicMock()

    shadow_query = MagicMock()
    shadow_query.filter.return_value.first.return_value = None

    overlay_query = MagicMock()
    overlay_query.filter.return_value.update.return_value = overlay_rowcount

    canonical_query = MagicMock()
    canonical_query.filter.return_value.update.return_value = canonical_rowcount

    session.query.side_effect = [shadow_query, overlay_query, canonical_query]
    return session, canonical_query


def _build_evaluation(
    *,
    control_id: str = "EC2.7",
    status: str = "RESOLVED",
    state_confidence: int = 95,
) -> SimpleNamespace:
    return SimpleNamespace(
        resource_id="AWS::::Account:029037611564",
        resource_type="AwsAccount",
        control_id=control_id,
        status=status,
        status_reason="inventory_confirmed_compliant",
        evidence_ref={"source": "inventory"},
        state_confidence=state_confidence,
    )


def _configure_promotion_guardrails(
    monkeypatch,
    *,
    shadow_mode: bool,
    promotion_enabled: bool,
    high_confidence_controls: str,
    min_confidence: int,
    pilot_tenants: str = "",
    allow_soft_resolved: bool = False,
    medium_low_controls: str = "",
    medium_low_min_coverage: int = 95,
    medium_low_min_precision: int = 95,
    medium_low_observed_coverage: int = 0,
    medium_low_observed_precision: int = 0,
    medium_low_rollback_triggered: bool = False,
) -> None:
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_SHADOW_MODE",
        shadow_mode,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED",
        promotion_enabled,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_HIGH_CONFIDENCE_CONTROLS",
        high_confidence_controls,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_PROMOTION_MIN_CONFIDENCE",
        min_confidence,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_PROMOTION_PILOT_TENANTS",
        pilot_tenants,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED",
        allow_soft_resolved,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_MEDIUM_LOW_CONFIDENCE_CONTROLS",
        medium_low_controls,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_COVERAGE",
        medium_low_min_coverage,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_PRECISION",
        medium_low_min_precision,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_COVERAGE",
        medium_low_observed_coverage,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_PRECISION",
        medium_low_observed_precision,
        raising=False,
    )
    monkeypatch.setattr(
        shadow_state.settings,
        "CONTROL_PLANE_MEDIUM_LOW_PROMOTION_ROLLBACK_TRIGGERED",
        medium_low_rollback_triggered,
        raising=False,
    )


def test_upsert_shadow_state_warns_when_overlay_update_matches_zero_rows(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=True,
        promotion_enabled=False,
        high_confidence_controls="EC2.7",
        min_confidence=95,
    )
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
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=True,
        promotion_enabled=False,
        high_confidence_controls="EC2.7",
        min_confidence=95,
    )
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


def test_upsert_shadow_state_promotes_for_qualified_high_confidence_control(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="EC2.7",
        min_confidence=90,
    )
    warning = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "warning", warning)

    session, promotion_query = _build_session_for_overlay_and_canonical_rowcount(
        overlay_rowcount=1,
        canonical_rowcount=1,
    )
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

    update_payload = promotion_query.filter.return_value.update.call_args.args[0]
    assert update_payload[Finding.status] == "RESOLVED"
    assert Finding.resolved_at in update_payload


def test_upsert_shadow_state_blocks_promotion_for_low_confidence(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="EC2.7",
        min_confidence=95,
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(state_confidence=40),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    assert "confidence_below_threshold" in str(info.call_args.args[-1])


def test_upsert_shadow_state_blocks_non_high_confidence_control(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="S3.1",
        min_confidence=90,
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(control_id="EC2.7", state_confidence=99),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    assert "control_not_high_confidence" in str(info.call_args.args[-1])


def test_upsert_shadow_state_blocks_soft_resolved_when_not_allowed(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="EC2.7",
        min_confidence=90,
        allow_soft_resolved=False,
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(status="SOFT_RESOLVED", state_confidence=99),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    assert "soft_resolved_not_allowed" in str(info.call_args.args[-1])


def test_upsert_shadow_state_blocks_non_pilot_tenant(monkeypatch) -> None:
    pilot_tenant_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="EC2.7",
        min_confidence=90,
        pilot_tenants=str(pilot_tenant_id),
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(state_confidence=99),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    assert "tenant_not_in_pilot" in str(info.call_args.args[-1])


def test_upsert_shadow_state_blocks_medium_low_by_default_until_quality_thresholds_met(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="",
        min_confidence=90,
        medium_low_controls="S3.2",
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(control_id="S3.2", state_confidence=99),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    blocked_reasons = str(info.call_args.args[-1])
    assert "medium_low_coverage_below_threshold" in blocked_reasons
    assert "medium_low_precision_below_threshold" in blocked_reasons


def test_upsert_shadow_state_blocks_medium_low_when_coverage_threshold_unmet(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="",
        min_confidence=90,
        medium_low_controls="S3.2",
        medium_low_min_coverage=95,
        medium_low_min_precision=95,
        medium_low_observed_coverage=90,
        medium_low_observed_precision=99,
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(control_id="S3.2", state_confidence=99),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    assert "medium_low_coverage_below_threshold" in str(info.call_args.args[-1])


def test_upsert_shadow_state_blocks_medium_low_when_precision_threshold_unmet(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="",
        min_confidence=90,
        medium_low_controls="S3.2",
        medium_low_min_coverage=95,
        medium_low_min_precision=95,
        medium_low_observed_coverage=99,
        medium_low_observed_precision=90,
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(control_id="S3.2", state_confidence=99),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    assert "medium_low_precision_below_threshold" in str(info.call_args.args[-1])


def test_upsert_shadow_state_blocks_medium_low_when_rollback_triggered(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="",
        min_confidence=90,
        medium_low_controls="S3.2",
        medium_low_min_coverage=95,
        medium_low_min_precision=95,
        medium_low_observed_coverage=99,
        medium_low_observed_precision=99,
        medium_low_rollback_triggered=True,
    )
    info = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "info", info)

    session = _build_session_for_overlay_rowcount(1)
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(control_id="S3.2", state_confidence=99),
    )

    assert session.query.call_count == 2
    info.assert_called_once()
    assert "medium_low_rollback_triggered" in str(info.call_args.args[-1])


def test_upsert_shadow_state_promotes_medium_low_when_quality_thresholds_met(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="",
        min_confidence=90,
        medium_low_controls="S3.2",
        medium_low_min_coverage=95,
        medium_low_min_precision=95,
        medium_low_observed_coverage=99,
        medium_low_observed_precision=99,
        medium_low_rollback_triggered=False,
    )
    warning = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "warning", warning)

    session, promotion_query = _build_session_for_overlay_and_canonical_rowcount(
        overlay_rowcount=1,
        canonical_rowcount=1,
    )
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(control_id="S3.2", state_confidence=99),
    )

    warning.assert_not_called()
    update_payload = promotion_query.filter.return_value.update.call_args.args[0]
    assert update_payload[Finding.status] == "RESOLVED"
    assert Finding.resolved_at in update_payload


def test_upsert_shadow_state_reopens_for_qualified_open_status(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="EC2.7",
        min_confidence=90,
    )
    warning = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "warning", warning)

    session, reopen_query = _build_session_for_overlay_and_canonical_rowcount(
        overlay_rowcount=1,
        canonical_rowcount=1,
    )
    shadow_state.upsert_shadow_state(
        session=session,
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        region="eu-north-1",
        event_time=datetime.now(timezone.utc),
        source="event_monitor_shadow",
        evaluation=_build_evaluation(status="OPEN", state_confidence=99),
    )

    warning.assert_not_called()
    update_payload = reopen_query.filter.return_value.update.call_args.args[0]
    assert update_payload[Finding.status] == "NEW"
    assert update_payload[Finding.resolved_at] is None


def test_upsert_shadow_state_warns_when_promotion_update_matches_zero_rows(monkeypatch) -> None:
    _configure_promotion_guardrails(
        monkeypatch,
        shadow_mode=False,
        promotion_enabled=True,
        high_confidence_controls="EC2.7",
        min_confidence=90,
    )
    warning = MagicMock()
    monkeypatch.setattr(shadow_state.logger, "warning", warning)

    session, promotion_query = _build_session_for_overlay_and_canonical_rowcount(
        overlay_rowcount=1,
        canonical_rowcount=0,
    )
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
