"""Persistence helpers for action remediation system-of-record sync state."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.action import Action
from backend.models.action_external_link import ActionExternalLink
from backend.models.action_remediation_sync_event import ActionRemediationSyncEvent
from backend.models.action_remediation_sync_state import ActionRemediationSyncState
from backend.services.action_remediation_state_machine import (
    DECISION_CANONICAL_APPLIED,
    DECISION_PRESERVE_INTERNAL,
    DECISION_RECONCILED,
    EVENT_EXTERNAL_OBSERVED,
    EVENT_INTERNAL_TRANSITION,
    EVENT_RECONCILIATION_QUEUED,
    EVENT_RECONCILIATION_APPLIED,
    SOURCE_EXTERNAL,
    SOURCE_INTERNAL,
    SOURCE_RECONCILIATION,
    SYNC_STATUS_DRIFTED,
    SYNC_STATUS_IN_SYNC,
    ensure_transition_allowed,
    normalize_canonical_action_status,
    normalize_provider,
    preferred_external_status,
    resolve_external_status_conflict,
)
@dataclass(frozen=True)
class CanonicalActionStatusUpdateResult:
    status_before: str
    status_after: str
    changed: bool
    impacted_sync_states: int


@dataclass(frozen=True)
class ExternalObservationResult:
    provider: str
    sync_status: str
    mapped_internal_status: str | None
    preferred_external_status: str | None


@dataclass(frozen=True)
class ReconciliationRunResult:
    scanned: int
    planned_tasks: int
    skipped: int
    task_ids_by_tenant: dict[uuid.UUID, list[uuid.UUID]] = field(default_factory=dict)


def apply_canonical_action_status(
    session: Session,
    *,
    action: Action,
    target_status: str,
    source: str,
    actor_user_id: uuid.UUID | None = None,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> CanonicalActionStatusUpdateResult:
    if _find_existing_event(session, action.tenant_id, action.id, idempotency_key) is not None:
        current = normalize_canonical_action_status(action.status)
        return CanonicalActionStatusUpdateResult(current, current, False, 0)
    current = normalize_canonical_action_status(action.status)
    target = ensure_transition_allowed(current, target_status)
    states = _ensure_sync_states_for_action(session, action)
    changed = current != target
    if changed:
        action.status = target
    updates = [_apply_canonical_to_state(state, target) for state in states]
    if changed or updates:
        _record_event(
            session,
            tenant_id=action.tenant_id,
            action_id=action.id,
            sync_state_id=None,
            source=source or SOURCE_INTERNAL,
            event_type=EVENT_INTERNAL_TRANSITION,
            provider=None,
            external_ref=None,
            idempotency_key=idempotency_key,
            internal_status_before=current,
            internal_status_after=target,
            external_status=None,
            mapped_internal_status=None,
            preferred_external_status=None,
            resolution_decision=DECISION_CANONICAL_APPLIED,
            decision_detail=detail or f"Canonical action state updated from {current} to {target}.",
            event_payload=_canonical_event_payload(target, updates, payload),
            actor_user_id=actor_user_id,
        )
    return CanonicalActionStatusUpdateResult(current, target, changed, len(updates))


def record_external_status_observation(
    session: Session,
    *,
    action: Action,
    provider: str,
    external_status: str,
    external_ref: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> ExternalObservationResult:
    provider_name = normalize_provider(provider)
    if _find_existing_event(session, action.tenant_id, action.id, idempotency_key) is not None:
        state = _load_sync_state(session, action.tenant_id, action.id, provider_name)
        return _observation_from_state(provider_name, state, action.status)
    state = _get_or_create_sync_state(session, action, provider_name, external_ref)
    resolution = resolve_external_status_conflict(action.status, provider_name, external_status)
    _update_state_from_resolution(state, external_status, external_ref, resolution, SOURCE_EXTERNAL, payload)
    _record_event(
        session,
        tenant_id=action.tenant_id,
        action_id=action.id,
        sync_state_id=state.id,
        source=SOURCE_EXTERNAL,
        event_type=EVENT_EXTERNAL_OBSERVED,
        provider=provider_name,
        external_ref=external_ref,
        idempotency_key=idempotency_key,
        internal_status_before=normalize_canonical_action_status(action.status),
        internal_status_after=normalize_canonical_action_status(action.status),
        external_status=external_status,
        mapped_internal_status=resolution["mapped_internal_status"],
        preferred_external_status=resolution["preferred_external_status"],
        resolution_decision=resolution["resolution_decision"],
        decision_detail=detail or resolution["conflict_reason"],
        event_payload=payload,
        actor_user_id=actor_user_id,
    )
    return ExternalObservationResult(
        provider_name,
        str(resolution["sync_status"]),
        _string_or_none(resolution["mapped_internal_status"]),
        _string_or_none(resolution["preferred_external_status"]),
    )


def reconcile_drifted_sync_states(
    session: Session,
    *,
    tenant_id: uuid.UUID | None = None,
    provider: str | None = None,
    action_ids: Iterable[uuid.UUID] | None = None,
    limit: int = 100,
) -> ReconciliationRunResult:
    states = _load_drifted_states(session, tenant_id=tenant_id, provider=provider, action_ids=action_ids, limit=limit)
    planned_tasks = 0
    skipped = 0
    task_ids_by_tenant: dict[uuid.UUID, list[uuid.UUID]] = {}
    for state in states:
        task_ids = _plan_reconciliation(session, state)
        if task_ids:
            planned_tasks += len(task_ids)
            task_ids_by_tenant.setdefault(state.tenant_id, []).extend(task_ids)
        else:
            skipped += 1
    return ReconciliationRunResult(len(states), planned_tasks, skipped, task_ids_by_tenant)


def record_reconciled_external_status(
    session: Session,
    *,
    action: Action,
    provider: str,
    external_status: str | None,
    external_ref: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> ExternalObservationResult:
    provider_name = normalize_provider(provider)
    if _find_existing_event(session, action.tenant_id, action.id, idempotency_key) is not None:
        state = _load_sync_state(session, action.tenant_id, action.id, provider_name)
        return _observation_from_state(provider_name, state, action.status)
    state = _get_or_create_sync_state(session, action, provider_name, external_ref)
    preferred = preferred_external_status(provider_name, action.status)
    state.external_ref = external_ref or state.external_ref
    state.external_status = _string_or_none(external_status) or preferred
    state.mapped_internal_status = normalize_canonical_action_status(action.status)
    state.canonical_internal_status = normalize_canonical_action_status(action.status)
    state.preferred_external_status = preferred
    state.sync_status = SYNC_STATUS_IN_SYNC
    state.last_source = SOURCE_RECONCILIATION
    state.resolution_decision = DECISION_RECONCILED
    state.conflict_reason = None
    state.sync_metadata = payload or state.sync_metadata
    state.last_event_at = _utcnow()
    state.last_reconciled_at = state.last_event_at
    _record_event(
        session,
        tenant_id=action.tenant_id,
        action_id=action.id,
        sync_state_id=state.id,
        source=SOURCE_RECONCILIATION,
        event_type=EVENT_RECONCILIATION_APPLIED,
        provider=provider_name,
        external_ref=external_ref,
        idempotency_key=idempotency_key,
        internal_status_before=normalize_canonical_action_status(action.status),
        internal_status_after=normalize_canonical_action_status(action.status),
        external_status=state.external_status,
        mapped_internal_status=state.mapped_internal_status,
        preferred_external_status=preferred,
        resolution_decision=DECISION_RECONCILED,
        decision_detail=detail or f"External {provider_name} status reconciled to canonical state {action.status}.",
        event_payload=payload,
        actor_user_id=actor_user_id,
    )
    return ExternalObservationResult(provider_name, state.sync_status, state.mapped_internal_status, preferred)


def _apply_canonical_to_state(
    state: ActionRemediationSyncState,
    target_status: str,
) -> dict[str, str | None]:
    resolution = resolve_external_status_conflict(target_status, state.provider, state.external_status)
    state.canonical_internal_status = target_status
    state.preferred_external_status = resolution["preferred_external_status"]
    state.sync_status = str(resolution["sync_status"])
    state.last_source = SOURCE_INTERNAL
    state.resolution_decision = resolution["resolution_decision"]
    state.conflict_reason = resolution["conflict_reason"]
    state.mapped_internal_status = resolution["mapped_internal_status"]
    state.last_event_at = _utcnow()
    return _state_snapshot(state)


def _canonical_event_payload(
    target_status: str,
    updates: list[dict[str, str | None]],
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(payload or {})
    merged["canonical_status"] = target_status
    merged["impacted_providers"] = updates
    return merged


def _get_or_create_sync_state(
    session: Session,
    action: Action,
    provider: str,
    external_ref: str | None,
) -> ActionRemediationSyncState:
    state = _load_sync_state(session, action.tenant_id, action.id, provider)
    if state is not None:
        return state
    state = ActionRemediationSyncState(
        tenant_id=action.tenant_id,
        action_id=action.id,
        provider=provider,
        external_ref=external_ref,
        canonical_internal_status=normalize_canonical_action_status(action.status),
        preferred_external_status=preferred_external_status(provider, action.status),
        sync_status=SYNC_STATUS_IN_SYNC,
        last_source=SOURCE_INTERNAL,
    )
    session.add(state)
    session.flush()
    return state


def _update_state_from_resolution(
    state: ActionRemediationSyncState,
    external_status: str,
    external_ref: str | None,
    resolution: dict[str, str | None],
    source: str,
    payload: dict[str, Any] | None,
) -> None:
    state.external_ref = external_ref or state.external_ref
    state.external_status = str(external_status or "").strip() or None
    state.sync_status = str(resolution["sync_status"])
    state.last_source = source
    state.resolution_decision = resolution["resolution_decision"]
    state.conflict_reason = resolution["conflict_reason"]
    state.mapped_internal_status = resolution["mapped_internal_status"]
    state.preferred_external_status = resolution["preferred_external_status"]
    state.sync_metadata = payload or state.sync_metadata
    state.last_event_at = _utcnow()


def _load_sync_state(
    session: Session,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    provider: str,
) -> ActionRemediationSyncState | None:
    stmt = select(ActionRemediationSyncState).where(
        ActionRemediationSyncState.tenant_id == tenant_id,
        ActionRemediationSyncState.action_id == action_id,
        ActionRemediationSyncState.provider == provider,
    )
    return session.execute(stmt).scalar_one_or_none()


def _list_sync_states(
    session: Session,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
) -> list[ActionRemediationSyncState]:
    stmt = select(ActionRemediationSyncState).where(
        ActionRemediationSyncState.tenant_id == tenant_id,
        ActionRemediationSyncState.action_id == action_id,
    )
    return list(session.execute(stmt).scalars().all())


def _ensure_sync_states_for_action(session: Session, action: Action) -> list[ActionRemediationSyncState]:
    states = {state.provider: state for state in _list_sync_states(session, action.tenant_id, action.id)}
    for link in _list_external_links(session, action.tenant_id, action.id):
        if link.provider in states:
            continue
        states[link.provider] = _create_state_from_link(session, action, link)
    return list(states.values())


def _list_external_links(
    session: Session,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
) -> list[ActionExternalLink]:
    stmt = select(ActionExternalLink).where(
        ActionExternalLink.tenant_id == tenant_id,
        ActionExternalLink.action_id == action_id,
    )
    return list(session.execute(stmt).scalars().all())


def _create_state_from_link(
    session: Session,
    action: Action,
    link: ActionExternalLink,
) -> ActionRemediationSyncState:
    resolution = resolve_external_status_conflict(action.status, link.provider, link.external_status)
    state = ActionRemediationSyncState(
        tenant_id=action.tenant_id,
        action_id=action.id,
        provider=link.provider,
        external_ref=link.external_id,
        external_status=link.external_status,
        mapped_internal_status=resolution["mapped_internal_status"],
        canonical_internal_status=normalize_canonical_action_status(action.status),
        preferred_external_status=resolution["preferred_external_status"],
        sync_status=str(resolution["sync_status"]),
        last_source=SOURCE_INTERNAL,
        resolution_decision=resolution["resolution_decision"],
        conflict_reason=resolution["conflict_reason"],
    )
    session.add(state)
    session.flush()
    return state


def _load_drifted_states(
    session: Session,
    *,
    tenant_id: uuid.UUID | None,
    provider: str | None,
    action_ids: Iterable[uuid.UUID] | None,
    limit: int,
) -> list[ActionRemediationSyncState]:
    stmt = select(ActionRemediationSyncState).where(ActionRemediationSyncState.sync_status == SYNC_STATUS_DRIFTED)
    if tenant_id is not None:
        stmt = stmt.where(ActionRemediationSyncState.tenant_id == tenant_id)
    if provider:
        stmt = stmt.where(ActionRemediationSyncState.provider == normalize_provider(provider))
    if action_ids:
        stmt = stmt.where(ActionRemediationSyncState.action_id.in_(list(action_ids)))
    stmt = stmt.order_by(ActionRemediationSyncState.updated_at.asc()).limit(max(1, int(limit)))
    return list(session.execute(stmt).scalars().all())


def _plan_reconciliation(session: Session, state: ActionRemediationSyncState) -> list[uuid.UUID]:
    from backend.services.integration_sync import plan_manual_action_sync

    if state.sync_status != SYNC_STATUS_DRIFTED:
        return []
    task_ids = plan_manual_action_sync(
        session,
        tenant_id=state.tenant_id,
        action_id=state.action_id,
        provider=state.provider,
    )
    if not task_ids:
        return []
    state.last_source = SOURCE_RECONCILIATION
    state.last_event_at = _utcnow()
    _record_event(
        session,
        tenant_id=state.tenant_id,
        action_id=state.action_id,
        sync_state_id=state.id,
        source=SOURCE_RECONCILIATION,
        event_type=EVENT_RECONCILIATION_QUEUED,
        provider=state.provider,
        external_ref=state.external_ref,
        idempotency_key=_queued_reconciliation_key(state, task_ids),
        internal_status_before=state.canonical_internal_status,
        internal_status_after=state.canonical_internal_status,
        external_status=state.external_status,
        mapped_internal_status=state.mapped_internal_status,
        preferred_external_status=state.preferred_external_status,
        resolution_decision=DECISION_PRESERVE_INTERNAL,
        decision_detail=f"Queued outbound reconciliation for drifted {state.provider} status.",
        event_payload={"task_ids": [str(task_id) for task_id in task_ids], "state": _state_snapshot(state)},
        actor_user_id=None,
    )
    return task_ids


def _queued_reconciliation_key(
    state: ActionRemediationSyncState,
    task_ids: list[uuid.UUID],
) -> str:
    joined = ",".join(sorted(str(task_id) for task_id in task_ids))
    return f"reconcile:{state.provider}:{state.action_id}:{joined}"


def _record_event(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    sync_state_id: uuid.UUID | None,
    source: str,
    event_type: str,
    provider: str | None,
    external_ref: str | None,
    idempotency_key: str | None,
    internal_status_before: str | None,
    internal_status_after: str | None,
    external_status: str | None,
    mapped_internal_status: str | None,
    preferred_external_status: str | None,
    resolution_decision: str | None,
    decision_detail: str | None,
    event_payload: dict[str, Any] | None,
    actor_user_id: uuid.UUID | None,
) -> ActionRemediationSyncEvent:
    existing = _find_existing_event(session, tenant_id, action_id, idempotency_key)
    if existing is not None:
        return existing
    event = ActionRemediationSyncEvent(
        tenant_id=tenant_id,
        action_id=action_id,
        sync_state_id=sync_state_id,
        source=source,
        event_type=event_type,
        provider=provider,
        external_ref=external_ref,
        idempotency_key=idempotency_key,
        internal_status_before=internal_status_before,
        internal_status_after=internal_status_after,
        external_status=external_status,
        mapped_internal_status=mapped_internal_status,
        preferred_external_status=preferred_external_status,
        resolution_decision=resolution_decision,
        decision_detail=decision_detail,
        event_payload=event_payload,
        actor_user_id=actor_user_id,
    )
    session.add(event)
    return event


def _find_existing_event(
    session: Session,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    idempotency_key: str | None,
) -> ActionRemediationSyncEvent | None:
    if not idempotency_key:
        return None
    stmt = select(ActionRemediationSyncEvent).where(
        ActionRemediationSyncEvent.tenant_id == tenant_id,
        ActionRemediationSyncEvent.action_id == action_id,
        ActionRemediationSyncEvent.idempotency_key == idempotency_key,
    )
    return session.execute(stmt).scalar_one_or_none()


def _state_snapshot(state: ActionRemediationSyncState) -> dict[str, str | None]:
    return {
        "provider": state.provider,
        "external_status": state.external_status,
        "mapped_internal_status": state.mapped_internal_status,
        "canonical_internal_status": state.canonical_internal_status,
        "preferred_external_status": state.preferred_external_status,
        "sync_status": state.sync_status,
        "resolution_decision": state.resolution_decision,
    }


def _observation_from_state(
    provider_name: str,
    state: ActionRemediationSyncState | None,
    action_status: str,
) -> ExternalObservationResult:
    preferred = preferred_external_status(provider_name, action_status)
    if state is None:
        return ExternalObservationResult(provider_name, SYNC_STATUS_IN_SYNC, None, preferred)
    return ExternalObservationResult(provider_name, state.sync_status, state.mapped_internal_status, preferred)


def _string_or_none(value: str | None) -> str | None:
    return str(value) if value is not None else None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
