"""
Action engine: groups findings into actionable remediation units, dedupes,
computes priority, upserts actions and action_findings. Idempotent per run.

Control_id -> action_type mapping and canonical control normalization live in
backend.services.control_scope so equivalent controls can safely merge into one
action when remediation is the same.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from backend.models import Action, ActionFinding, Finding
from backend.models.enums import ActionStatus, FindingStatus
from backend.config import settings
from backend.services.control_scope import (
    action_type_from_control as _action_type_from_control_impl,
    canonical_control_id_for_action_type,
)
from backend.services.action_groups import ensure_membership_for_actions

logger = logging.getLogger(__name__)

# Closed finding statuses; every other status is treated as open for action computation.
# Resolved matching is intentionally strict: only RESOLVED (driven by Security Hub PASSED).
_CLOSED_STATUSES = (FindingStatus.RESOLVED.value,)
_SHADOW_CLOSED_STATUSES = frozenset({"RESOLVED", "SOFT_RESOLVED"})
_SHADOW_OPEN_STATUSES = frozenset({"OPEN"})


def _is_open_finding_status(status: str | None) -> bool:
    """True for any non-closed finding status."""
    if status is None:
        return True
    return status not in _CLOSED_STATUSES


def _is_effectively_open_finding(finding: Finding) -> bool:
    """
    Resolve effective open/closed state using shadow overlays when present.

    In CONTROL_PLANE_SHADOW_MODE deployments, canonical finding.status may lag while
    shadow status reflects the latest control-plane truth.
    """
    shadow_normalized = str(getattr(finding, "shadow_status_normalized", "") or "").strip().upper()
    if shadow_normalized in _SHADOW_CLOSED_STATUSES:
        return False
    if shadow_normalized in _SHADOW_OPEN_STATUSES:
        return True
    return _is_open_finding_status(getattr(finding, "status", None))


def _grouping_key(finding: Finding) -> tuple[Any, ...]:
    """
    Hashable key for grouping findings.

    Equivalent controls are merged when they map to the same action_type and
    canonical control_id (for example S3.2/S3.8 -> s3_bucket_block_public_access).
    """
    action_type = _action_type_from_control(finding.control_id)
    canonical_control_id = canonical_control_id_for_action_type(action_type, finding.control_id) or ""
    return (
        finding.tenant_id,
        finding.account_id,
        finding.region or "",
        (finding.resource_id or "")[:512],
        action_type,
        canonical_control_id[:64],
    )


def _build_target_id(account_id: str, region: str | None, resource_id: str | None, control_id: str | None) -> str:
    """Normalized target identifier for dedupe; used in unique constraint."""
    r = (resource_id or "")[:512]
    c = (control_id or "")[:64]
    reg = (region or "")
    return f"{account_id}|{reg}|{r}|{c}"


def _action_type_from_control(control_id: str | None) -> str:
    """Derive action_type from control_id; default pr_only (Step 9.8, control_scope)."""
    return _action_type_from_control_impl(control_id)


def _priority_for_finding(finding: Finding) -> int:
    """
    Priority 0–100: severity_normalized + exploitability (0–10) + exposure (0–10), capped at 100.
    Exploitability: +5 if title/description mention 'public' or 'unrestricted'.
    """
    base = finding.severity_normalized
    text = f"{(finding.title or '')} {(finding.description or '')}".lower()
    exploit = 5 if ("public" in text or "unrestricted" in text) else 0
    exposure = 0  # MVP: optional later from raw_json
    return min(100, base + exploit + exposure)


def _priority_for_group(findings: list[Finding]) -> int:
    """Max priority across findings in the group."""
    if not findings:
        return 0
    return max(_priority_for_finding(f) for f in findings)


def _action_status_from_findings(findings: list[Finding]) -> str:
    """Resolved if all findings are RESOLVED or SUPPRESSED; else open."""
    if not findings:
        return ActionStatus.resolved.value
    for f in findings:
        if _is_effectively_open_finding(f):
            return ActionStatus.open.value
    return ActionStatus.resolved.value


def _title_and_description_for_group(findings: list[Finding]) -> tuple[str, str | None]:
    """Human-readable title (max 500) and description from first finding in group."""
    if not findings:
        return "Action", None
    first = findings[0]
    title = (first.title or "Security finding")[:500]
    desc = first.description
    if len(findings) > 1:
        desc = (desc or "") + f" (+{len(findings) - 1} related finding(s))"
    return title, (desc[:65535] if desc else None)


def _upsert_action_and_sync_links(
    session: Session,
    tenant_id: uuid.UUID,
    findings: list[Finding],
) -> tuple[Action, bool]:
    """
    Upsert one action for the group of findings; sync action_findings to current group.
    Returns (action, created).
    """
    if not findings:
        raise ValueError("findings must be non-empty")
    first = findings[0]
    account_id = first.account_id
    region = first.region
    resource_id = first.resource_id
    action_type = _action_type_from_control(first.control_id)
    control_id = canonical_control_id_for_action_type(action_type, first.control_id)
    target_id = _build_target_id(account_id, region, resource_id, control_id)
    priority = _priority_for_group(findings)
    status = _action_status_from_findings(findings)
    title, description = _title_and_description_for_group(findings)
    resource_type = first.resource_type
    if resource_type and len(resource_type) > 128:
        resource_type = resource_type[:128]

    # Look up existing action (unique on tenant_id, action_type, target_id, account_id, region)
    q = session.query(Action).filter(
        Action.tenant_id == tenant_id,
        Action.action_type == action_type,
        Action.target_id == target_id,
        Action.account_id == account_id,
    )
    if region is None:
        q = q.filter(Action.region.is_(None))
    else:
        q = q.filter(Action.region == region)
    action = q.first()

    if action:
        action.priority = priority
        action.status = status
        action.title = title
        action.description = description
        action.resource_id = resource_id
        action.resource_type = resource_type
        action.control_id = control_id
        action.action_finding_links = [ActionFinding(finding=f) for f in findings]
        return action, False

    action = Action(
        tenant_id=tenant_id,
        action_type=action_type,
        target_id=target_id,
        account_id=account_id,
        region=region,
        priority=priority,
        status=status,
        title=title,
        description=description,
        control_id=control_id,
        resource_id=resource_id,
        resource_type=resource_type,
    )
    action.action_finding_links = [ActionFinding(finding=f) for f in findings]
    session.add(action)
    return action, True


def _remove_conflicting_links_for_findings(
    session: Session,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    finding_ids: list[uuid.UUID],
) -> int:
    """
    Ensure each finding maps to a single action by removing links to other actions.

    This prevents duplicate open actions from persisting after merge-key changes.
    """
    if not finding_ids:
        return 0

    stale_links = (
        session.query(ActionFinding)
        .join(Action, Action.id == ActionFinding.action_id)
        .filter(
            Action.tenant_id == tenant_id,
            ActionFinding.finding_id.in_(finding_ids),
            ActionFinding.action_id != action_id,
        )
        .all()
    )
    for link in stale_links:
        session.delete(link)
    return len(stale_links)


def _mark_resolved_actions_with_no_open_findings(
    session: Session,
    tenant_id: uuid.UUID,
    account_id: str | None,
    region: str | None,
) -> int:
    """
    Mark actions as resolved when all their linked findings are RESOLVED.
    Returns number of actions updated.
    """
    q = session.query(Action).filter(Action.tenant_id == tenant_id, Action.status == ActionStatus.open.value)
    if account_id is not None:
        q = q.filter(Action.account_id == account_id)
    if region is not None:
        q = q.filter(Action.region == region)
    open_actions = q.all()
    resolved_count = 0
    for action in open_actions:
        unresolved_count = _linked_unresolved_finding_count(action)
        if unresolved_count == 0:
            action.status = ActionStatus.resolved.value
            resolved_count += 1
    return resolved_count


def _linked_unresolved_finding_count(action: Action) -> int:
    """
    Count unresolved findings linked to an action.

    A missing linked finding object is treated as unresolved to fail safe.
    """
    unresolved = 0
    links = action.action_finding_links or []
    for link in links:
        finding = getattr(link, "finding", None)
        if finding is None:
            unresolved += 1
            continue
        if _is_effectively_open_finding(finding):
            unresolved += 1
    return unresolved


def _reopen_resolved_orphan_actions(
    session: Session,
    tenant_id: uuid.UUID,
    account_id: str | None,
    region: str | None,
) -> int:
    """
    Reopen actions marked resolved when linked unresolved findings still exist.
    """
    q = session.query(Action).filter(
        Action.tenant_id == tenant_id,
        Action.status == ActionStatus.resolved.value,
    )
    if account_id is not None:
        q = q.filter(Action.account_id == account_id)
    if region is not None:
        q = q.filter(Action.region == region)

    resolved_actions = q.all()
    reopened = 0
    for action in resolved_actions:
        if _linked_unresolved_finding_count(action) > 0:
            action.status = ActionStatus.open.value
            reopened += 1
    return reopened


def compute_actions_for_tenant(
    session: Session,
    tenant_id: uuid.UUID,
    account_id: str | None = None,
    region: str | None = None,
) -> dict[str, int]:
    """
    Compute actions from findings for a tenant (optionally scoped to account/region).
    Groups by (tenant, account, region, resource_id, action_type, canonical_control_id),
    dedupes, scores, upserts actions and syncs action_findings. Idempotent.

    Caller must provide a session (e.g. from worker session_scope()).

    Returns:
        dict with keys: actions_created, actions_updated, actions_resolved, action_findings_linked.
    """
    q = (
        session.query(Finding)
        .filter(Finding.tenant_id == tenant_id, ~Finding.status.in_(_CLOSED_STATUSES))
    )
    if account_id is not None:
        q = q.filter(Finding.account_id == account_id)
    if region is not None:
        q = q.filter(Finding.region == region)

    if settings.ONLY_IN_SCOPE_CONTROLS:
        q = q.filter(Finding.in_scope.is_(True))
    findings = [finding for finding in q.all() if _is_effectively_open_finding(finding)]

    groups: defaultdict[tuple[Any, ...], list[Finding]] = defaultdict(list)
    for f in findings:
        groups[_grouping_key(f)].append(f)

    created = 0
    updated = 0
    links_count = 0
    removed_conflicting_links = 0
    actions_touched: list[Action] = []
    for _key, group in groups.items():
        action, is_new = _upsert_action_and_sync_links(session, tenant_id, group)
        if action.id is None:
            session.flush()
        actions_touched.append(action)

        finding_ids = [f.id for f in group]
        removed_conflicting_links += _remove_conflicting_links_for_findings(
            session=session,
            tenant_id=tenant_id,
            action_id=action.id,
            finding_ids=finding_ids,
        )

        if is_new:
            created += 1
        else:
            updated += 1
        links_count += len(group)

    # Immutable append-only membership assignment for newly created actions.
    if actions_touched:
        ensure_membership_for_actions(session, actions_touched, source="recompute")

    resolved = _mark_resolved_actions_with_no_open_findings(session, tenant_id, account_id, region)
    reopened_with_open_findings = _reopen_resolved_orphan_actions(session, tenant_id, account_id, region)

    logger.info(
        "compute_actions_for_tenant tenant_id=%s scope=(account=%s region=%s) groups=%d created=%d updated=%d resolved=%d reopened_with_open_findings=%d links=%d removed_links=%d",
        tenant_id,
        account_id,
        region,
        len(groups),
        created,
        updated,
        resolved,
        reopened_with_open_findings,
        links_count,
        removed_conflicting_links,
    )
    return {
        "actions_created": created,
        "actions_updated": updated,
        "actions_resolved": resolved,
        "actions_reopened_orphaned": reopened_with_open_findings,
        "actions_reopened_with_open_findings": reopened_with_open_findings,
        "action_findings_linked": links_count,
    }
