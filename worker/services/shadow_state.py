from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.finding import Finding
from backend.models.finding_shadow_state import FindingShadowState
from worker.services.control_plane_events import build_fingerprint
from backend.services.canonicalization import build_resource_key, canonicalize_control_id
from worker.config import settings


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
    authoritative_controls = settings.control_plane_authoritative_controls_set

    def _apply_overlay() -> None:
        # Only update findings when we have stable join keys.
        if not canonical_control_id or not resource_key:
            return
        session.query(Finding).filter(
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

        # Promotion path: when shadow is authoritative, drive canonical finding.status.
        if (
            not settings.CONTROL_PLANE_SHADOW_MODE
            and canonical_control_id.upper() in authoritative_controls
        ):
            if shadow_norm == "RESOLVED":
                session.query(Finding).filter(
                    Finding.tenant_id == tenant_id,
                    Finding.account_id == account_id,
                    Finding.region == region,
                    Finding.source == "security_hub",
                    Finding.canonical_control_id == canonical_control_id,
                    Finding.resource_key == resource_key,
                ).update({Finding.status: "RESOLVED"}, synchronize_session=False)
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
                ).update({Finding.status: "NEW"}, synchronize_session=False)

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
