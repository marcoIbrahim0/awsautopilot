from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.finding_shadow_state import FindingShadowState
from worker.services.control_plane_events import build_fingerprint


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

    now = datetime.now(timezone.utc)
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
        existing.last_observed_event_time = event_time
        existing.last_evaluated_at = now
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
        status=evaluation.status,
        status_reason=evaluation.status_reason,
        evidence_ref=evaluation.evidence_ref,
        state_confidence=evaluation.state_confidence,
        first_observed_event_time=event_time,
        last_observed_event_time=event_time,
        last_evaluated_at=now,
    )
    session.add(shadow)
    return True, True
