from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.finding import Finding
from backend.models.finding_shadow_state import FindingShadowState
from backend.workers.services.control_plane_events import build_fingerprint
from backend.services.canonicalization import build_resource_key, canonicalize_control_id
from backend.workers.config import settings

logger = logging.getLogger("worker.services.shadow_state")


def _normalize_shadow_status(status_raw: str | None) -> str:
    s = (status_raw or "").strip().upper()
    if s == "OPEN":
        return "OPEN"
    if s in {"RESOLVED", "SOFT_RESOLVED"}:
        return "RESOLVED"
    return "UNKNOWN"


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _state_confidence_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pending_shadow_state(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    source: str,
    fingerprint: str,
) -> FindingShadowState | None:
    for candidate in getattr(session, "new", ()):
        if not isinstance(candidate, FindingShadowState):
            continue
        if (
            candidate.tenant_id == tenant_id
            and candidate.source == source
            and candidate.fingerprint == fingerprint
        ):
            return candidate
    return None


def _promotion_block_reasons(
    *,
    tenant_id: uuid.UUID,
    canonical_control_id: str,
    raw_status: str | None,
    state_confidence: int,
) -> list[str]:
    reasons: list[str] = []
    control_id = canonical_control_id.upper()
    high_confidence_controls = settings.control_plane_high_confidence_controls_set
    medium_low_controls = settings.control_plane_medium_low_confidence_controls_set
    is_high_confidence_control = control_id in high_confidence_controls
    is_medium_low_control = control_id in medium_low_controls
    if settings.CONTROL_PLANE_SHADOW_MODE:
        reasons.append("shadow_mode_enabled")
    if not settings.CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED:
        reasons.append("promotion_disabled")
    if not is_high_confidence_control and not is_medium_low_control:
        reasons.append("control_not_high_confidence")
    if state_confidence < settings.control_plane_promotion_min_confidence:
        reasons.append("confidence_below_threshold")
    if (raw_status or "").strip().upper() == "SOFT_RESOLVED" and not settings.CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED:
        reasons.append("soft_resolved_not_allowed")
    pilot_tenants = settings.control_plane_promotion_pilot_tenants_set
    if pilot_tenants and str(tenant_id).lower() not in pilot_tenants:
        reasons.append("tenant_not_in_pilot")
    if is_medium_low_control:
        if settings.control_plane_medium_low_promotion_observed_coverage < settings.control_plane_medium_low_promotion_min_coverage:
            reasons.append("medium_low_coverage_below_threshold")
        if settings.control_plane_medium_low_promotion_observed_precision < settings.control_plane_medium_low_promotion_min_precision:
            reasons.append("medium_low_precision_below_threshold")
        if settings.CONTROL_PLANE_MEDIUM_LOW_PROMOTION_ROLLBACK_TRIGGERED:
            reasons.append("medium_low_rollback_triggered")
    return reasons


def upsert_shadow_state(
    session: Session,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str,
    event_time: datetime,
    source: str,
    evaluation: Any,
) -> tuple[bool, bool]:
    """
    Upsert deterministic shadow state with out-of-order guard.

    Returns:
        (applied, changed_status)
    """
    fingerprint = build_fingerprint(
        account_id=account_id,
        region=region,
        resource_id=evaluation.resource_id,
        control_id=evaluation.control_id,
    )
    existing = _pending_shadow_state(
        session,
        tenant_id=tenant_id,
        source=source,
        fingerprint=fingerprint,
    )
    if existing is None:
        existing = (
            session.query(FindingShadowState)
            .filter(
                FindingShadowState.tenant_id == tenant_id,
                FindingShadowState.source == source,
                FindingShadowState.fingerprint == fingerprint,
            )
            .first()
        )

    canonical_control_id = canonicalize_control_id(getattr(evaluation, "control_id", None))
    resource_key = build_resource_key(
        account_id=account_id,
        region=region,
        resource_id=getattr(evaluation, "resource_id", None),
        resource_type=getattr(evaluation, "resource_type", None),
    )

    now = datetime.now(timezone.utc)
    shadow_norm = _normalize_shadow_status(getattr(evaluation, "status", None))

    def _apply_overlay() -> None:
        # Only update findings when we have stable join keys.
        if not canonical_control_id or not resource_key:
            return
        overlay_matched = session.query(Finding).filter(
            Finding.tenant_id == tenant_id,
            Finding.account_id == account_id,
            Finding.region == region,
            Finding.canonical_control_id == canonical_control_id,
            Finding.resource_key == resource_key,
        ).update(
            {
                Finding.shadow_status_raw: getattr(evaluation, "status", None),
                Finding.shadow_status_normalized: shadow_norm,
                Finding.shadow_status_reason: getattr(evaluation, "status_reason", None),
                Finding.shadow_last_observed_event_time: event_time,
                Finding.shadow_last_evaluated_at: now,
                Finding.shadow_fingerprint: fingerprint,
                Finding.shadow_source: source,
            },
            synchronize_session=False,
        )
        if overlay_matched == 0:
            logger.warning(
                "shadow overlay update matched zero rows tenant_id=%s account_id=%s region=%s "
                "canonical_control_id=%s resource_key=%s fingerprint=%s source=%s status=%s",
                tenant_id,
                account_id,
                region,
                canonical_control_id,
                resource_key,
                fingerprint,
                source,
                getattr(evaluation, "status", None),
            )

        raw_status = getattr(evaluation, "status", None)
        state_confidence = _state_confidence_or_zero(getattr(evaluation, "state_confidence", None))
        block_reasons = _promotion_block_reasons(
            tenant_id=tenant_id,
            canonical_control_id=canonical_control_id,
            raw_status=raw_status,
            state_confidence=state_confidence,
        )
        if block_reasons:
            if shadow_norm in {"OPEN", "RESOLVED"}:
                logger.info(
                    "shadow promotion blocked tenant_id=%s account_id=%s region=%s canonical_control_id=%s "
                    "resource_key=%s shadow_status=%s raw_status=%s state_confidence=%s min_confidence=%s "
                    "reason_codes=%s",
                    tenant_id,
                    account_id,
                    region,
                    canonical_control_id,
                    resource_key,
                    shadow_norm,
                    raw_status,
                    state_confidence,
                    settings.control_plane_promotion_min_confidence,
                    ",".join(block_reasons),
                )
            return

        if shadow_norm == "RESOLVED":
            promoted = session.query(Finding).filter(
                Finding.tenant_id == tenant_id,
                Finding.account_id == account_id,
                Finding.region == region,
                Finding.source == "security_hub",
                Finding.canonical_control_id == canonical_control_id,
                Finding.resource_key == resource_key,
            ).update(
                {
                    Finding.status: "RESOLVED",
                    Finding.resolved_at: now,
                },
                synchronize_session=False,
            )
            if promoted == 0:
                logger.warning(
                    "shadow promotion matched zero rows tenant_id=%s account_id=%s region=%s "
                    "canonical_control_id=%s resource_key=%s",
                    tenant_id,
                    account_id,
                    region,
                    canonical_control_id,
                    resource_key,
                )
        elif shadow_norm == "OPEN":
            # Reopen previously-resolved findings when drift is detected.
            session.query(Finding).filter(
                Finding.tenant_id == tenant_id,
                Finding.account_id == account_id,
                Finding.region == region,
                Finding.source == "security_hub",
                Finding.status == "RESOLVED",
                Finding.canonical_control_id == canonical_control_id,
                Finding.resource_key == resource_key,
            ).update(
                {
                    Finding.status: "NEW",
                    Finding.resolved_at: None,
                },
                synchronize_session=False,
            )

    if existing:
        last_event = _to_utc(existing.last_observed_event_time)
        incoming = _to_utc(event_time)
        if last_event and incoming and incoming < last_event:
            return False, False

        changed_status = existing.status != evaluation.status
        existing.status = evaluation.status
        existing.status_reason = evaluation.status_reason
        existing.evidence_ref = evaluation.evidence_ref
        existing.state_confidence = evaluation.state_confidence
        existing.resource_type = evaluation.resource_type
        existing.canonical_control_id = canonical_control_id
        existing.resource_key = resource_key
        existing.last_observed_event_time = event_time
        existing.last_evaluated_at = now
        _apply_overlay()
        return True, changed_status

    shadow = FindingShadowState(
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
        source=source,
        fingerprint=fingerprint,
        resource_id=evaluation.resource_id,
        resource_type=evaluation.resource_type,
        control_id=evaluation.control_id,
        canonical_control_id=canonical_control_id,
        resource_key=resource_key,
        status=evaluation.status,
        status_reason=evaluation.status_reason,
        evidence_ref=evaluation.evidence_ref,
        state_confidence=evaluation.state_confidence,
        first_observed_event_time=event_time,
        last_observed_event_time=event_time,
        last_evaluated_at=now,
    )
    session.add(shadow)
    _apply_overlay()
    return True, True
