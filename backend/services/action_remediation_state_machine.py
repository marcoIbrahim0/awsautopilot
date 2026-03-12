"""Canonical action remediation state machine and external status mappings."""
from __future__ import annotations

from typing import Any

from backend.models.enums import ActionStatus

STATE_OPEN = ActionStatus.open.value
STATE_IN_PROGRESS = ActionStatus.in_progress.value
STATE_RESOLVED = ActionStatus.resolved.value
STATE_SUPPRESSED = ActionStatus.suppressed.value

SYNC_STATUS_IN_SYNC = "in_sync"
SYNC_STATUS_DRIFTED = "drifted"

SOURCE_INTERNAL = "internal"
SOURCE_EXTERNAL = "external"
SOURCE_RECONCILIATION = "reconciliation"

EVENT_INTERNAL_TRANSITION = "internal_transition"
EVENT_EXTERNAL_OBSERVED = "external_status_observed"
EVENT_RECONCILIATION_QUEUED = "reconciliation_queued"
EVENT_RECONCILIATION_APPLIED = "reconciliation_applied"

DECISION_CANONICAL_APPLIED = "canonical_update_applied"
DECISION_EXTERNAL_MATCHES = "external_matches_internal"
DECISION_PRESERVE_INTERNAL = "preserve_internal_canonical"
DECISION_RECONCILED = "reconciled_to_internal_canonical"

CANONICAL_ACTION_TRANSITIONS = {
    STATE_OPEN: {STATE_IN_PROGRESS, STATE_RESOLVED, STATE_SUPPRESSED},
    STATE_IN_PROGRESS: {STATE_OPEN, STATE_RESOLVED, STATE_SUPPRESSED},
    STATE_RESOLVED: {STATE_OPEN, STATE_IN_PROGRESS, STATE_SUPPRESSED},
    STATE_SUPPRESSED: {STATE_OPEN, STATE_IN_PROGRESS, STATE_RESOLVED},
}

_GENERIC_STATUS_MAP = {
    "open": STATE_OPEN,
    "todo": STATE_OPEN,
    "to do": STATE_OPEN,
    "backlog": STATE_OPEN,
    "new": STATE_OPEN,
    "queued": STATE_OPEN,
    "in_progress": STATE_IN_PROGRESS,
    "in progress": STATE_IN_PROGRESS,
    "doing": STATE_IN_PROGRESS,
    "blocked": STATE_IN_PROGRESS,
    "on hold": STATE_IN_PROGRESS,
    "resolved": STATE_RESOLVED,
    "done": STATE_RESOLVED,
    "closed": STATE_RESOLVED,
    "complete": STATE_RESOLVED,
    "completed": STATE_RESOLVED,
    "suppressed": STATE_SUPPRESSED,
    "cancelled": STATE_SUPPRESSED,
    "canceled": STATE_SUPPRESSED,
    "wont do": STATE_SUPPRESSED,
    "won't do": STATE_SUPPRESSED,
    "closed skipped": STATE_SUPPRESSED,
}

EXTERNAL_STATUS_MAPPING_TABLE = {
    "generic": dict(_GENERIC_STATUS_MAP),
    "slack": dict(_GENERIC_STATUS_MAP),
    "jira": {
        **dict(_GENERIC_STATUS_MAP),
        "selected for development": STATE_OPEN,
    },
    "servicenow": {
        **dict(_GENERIC_STATUS_MAP),
        "work in progress": STATE_IN_PROGRESS,
        "implement": STATE_IN_PROGRESS,
        "closed complete": STATE_RESOLVED,
    },
}

PREFERRED_EXTERNAL_STATUS_TABLE = {
    "generic": {
        STATE_OPEN: "open",
        STATE_IN_PROGRESS: "in_progress",
        STATE_RESOLVED: "resolved",
        STATE_SUPPRESSED: "suppressed",
    },
    "slack": {
        STATE_OPEN: "open",
        STATE_IN_PROGRESS: "in_progress",
        STATE_RESOLVED: "resolved",
        STATE_SUPPRESSED: "suppressed",
    },
    "jira": {
        STATE_OPEN: "To Do",
        STATE_IN_PROGRESS: "In Progress",
        STATE_RESOLVED: "Done",
        STATE_SUPPRESSED: "Won't Do",
    },
    "servicenow": {
        STATE_OPEN: "New",
        STATE_IN_PROGRESS: "Work in Progress",
        STATE_RESOLVED: "Resolved",
        STATE_SUPPRESSED: "Cancelled",
    },
}


def normalize_canonical_action_status(value: Any) -> str:
    raw = getattr(value, "value", value)
    normalized = str(raw or "").strip().lower()
    if normalized not in CANONICAL_ACTION_TRANSITIONS:
        raise ValueError(f"unsupported_canonical_action_status:{value}")
    return normalized


def normalize_provider(value: Any) -> str:
    normalized = str(value or "generic").strip().lower()
    return normalized or "generic"


def normalize_external_status(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def map_external_status(provider: str, external_status: Any) -> str | None:
    normalized = normalize_external_status(external_status)
    if not normalized:
        return None
    mapping = EXTERNAL_STATUS_MAPPING_TABLE.get(normalize_provider(provider), EXTERNAL_STATUS_MAPPING_TABLE["generic"])
    return mapping.get(normalized)


def preferred_external_status(provider: str, canonical_status: Any) -> str | None:
    normalized = normalize_canonical_action_status(canonical_status)
    mapping = PREFERRED_EXTERNAL_STATUS_TABLE.get(normalize_provider(provider), PREFERRED_EXTERNAL_STATUS_TABLE["generic"])
    return mapping.get(normalized)


def ensure_transition_allowed(current_status: Any, target_status: Any) -> str:
    current = normalize_canonical_action_status(current_status)
    target = normalize_canonical_action_status(target_status)
    if current != target and target not in CANONICAL_ACTION_TRANSITIONS[current]:
        raise ValueError(f"illegal_action_status_transition:{current}->{target}")
    return target


def resolve_external_status_conflict(
    canonical_status: Any,
    provider: str,
    external_status: Any,
) -> dict[str, str | None]:
    canonical = normalize_canonical_action_status(canonical_status)
    mapped = map_external_status(provider, external_status)
    preferred = preferred_external_status(provider, canonical)
    if mapped == canonical:
        detail = f"External status matches canonical state {canonical}."
        return _resolution(SYNC_STATUS_IN_SYNC, DECISION_EXTERNAL_MATCHES, detail, mapped, preferred)
    detail = _preserve_internal_detail(canonical, external_status, mapped)
    return _resolution(SYNC_STATUS_DRIFTED, DECISION_PRESERVE_INTERNAL, detail, mapped, preferred)


def _resolution(
    sync_status: str,
    decision: str,
    detail: str,
    mapped_status: str | None,
    preferred_status: str | None,
) -> dict[str, str | None]:
    return {
        "sync_status": sync_status,
        "resolution_decision": decision,
        "conflict_reason": detail,
        "mapped_internal_status": mapped_status,
        "preferred_external_status": preferred_status,
    }


def _preserve_internal_detail(
    canonical_status: str,
    external_status: Any,
    mapped_status: str | None,
) -> str:
    raw_status = str(external_status or "").strip() or "<empty>"
    if mapped_status is None:
        return f"Unknown external status '{raw_status}' preserved internal canonical state {canonical_status}."
    return (
        f"External status '{raw_status}' mapped to {mapped_status}; "
        f"internal canonical state {canonical_status} remains authoritative."
    )
