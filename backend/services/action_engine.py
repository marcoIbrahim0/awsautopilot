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
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import Action, ActionFinding, AwsAccount, Finding, Tenant
from backend.models.enums import ActionStatus, FindingStatus
from backend.services.action_business_impact import (
    build_business_impact_for_finding,
    build_business_impact_from_components,
)
from backend.services.action_groups import ensure_membership_for_actions
from backend.services.action_ownership import resolve_action_owner
from backend.services.action_remediation_sync import apply_canonical_action_status
from backend.services.action_scoring import score_action_group
from backend.services.aws import (
    WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)
from backend.services.control_scope import (
    action_type_from_control as _action_type_from_control_impl,
    canonical_control_id_for_action_type,
)
from backend.services.security_graph import sync_security_graph_for_scope
from backend.services.sg_account_scope_resolver import (
    SGAccountScopeResolution,
    is_account_scoped_sg_control,
    resolve_account_scoped_sg_ids_from_finding,
)
from backend.services.toxic_combinations import apply_toxic_combination_overlays

logger = logging.getLogger(__name__)

# Closed finding statuses; every other status is treated as open for action computation.
# Resolved matching is intentionally strict: only RESOLVED (driven by Security Hub PASSED).
_CLOSED_STATUSES = (FindingStatus.RESOLVED.value,)
_SHADOW_CLOSED_STATUSES = frozenset({"RESOLVED", "SOFT_RESOLVED"})
_SHADOW_OPEN_STATUSES = frozenset({"OPEN"})
_SG_ACTION_TYPE = "sg_restrict_public_ports"


def _sync_existing_action_status(session: Session, action: Action, target_status: str, detail: str) -> None:
    if not callable(getattr(session, "execute", None)):
        action.status = target_status
        return
    apply_canonical_action_status(
        session,
        action=action,
        target_status=target_status,
        source="action_engine.recompute",
        detail=detail,
    )


@dataclass(frozen=True)
class ExpandedFindingTarget:
    finding: Finding
    resource_id: str | None
    resource_type: str | None
    allow_multi_action_links: bool = False


class _ActionExpansionContext:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._tenant_external_id: str | None = None
        self._account_by_id: dict[str, AwsAccount | None] = {}
        self._boto_session_by_account: dict[str, Any | None] = {}
        self._session_error_by_account: dict[str, str] = {}
        self._resolution_cache: dict[tuple[str, str, str], SGAccountScopeResolution] = {}

    def expand_finding(self, finding: Finding) -> list[ExpandedFindingTarget]:
        if not is_account_scoped_sg_control(finding.control_id, finding.resource_type):
            return [ExpandedFindingTarget(finding, finding.resource_id, finding.resource_type)]
        resolution = self._resolve_account_scoped_sg_ids(finding)
        if not resolution.security_group_ids:
            logger.warning(
                "Skipping account-scoped SG finding expansion tenant_id=%s account_id=%s region=%s finding_id=%s control_id=%s reason=%s config_rule=%s",
                finding.tenant_id,
                finding.account_id,
                finding.region,
                finding.finding_id,
                finding.control_id,
                resolution.reason,
                resolution.config_rule_name,
            )
            return []
        return [
            ExpandedFindingTarget(finding, sg_id, "AwsEc2SecurityGroup", allow_multi_action_links=True)
            for sg_id in resolution.security_group_ids
        ]

    def _resolve_account_scoped_sg_ids(self, finding: Finding) -> SGAccountScopeResolution:
        cache_key = (finding.account_id or "", finding.region or "", finding.finding_id or "")
        cached = self._resolution_cache.get(cache_key)
        if cached is not None:
            return cached

        aws_session = self._assumed_role_session(finding.account_id)
        if aws_session is None:
            reason = self._session_error_by_account.get(finding.account_id or "", "assume_role_unavailable")
            resolution = SGAccountScopeResolution([], None, reason)
            self._resolution_cache[cache_key] = resolution
            return resolution

        try:
            config_client = aws_session.client("config", region_name=finding.region)
            payload = finding.raw_json if isinstance(finding.raw_json, dict) else {}
            resolution = resolve_account_scoped_sg_ids_from_finding(config_client, payload)
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            resolution = SGAccountScopeResolution([], None, f"config_client_error:{type(exc).__name__}")
        self._resolution_cache[cache_key] = resolution
        return resolution

    def _assumed_role_session(self, account_id: str) -> Any | None:
        cached = self._boto_session_by_account.get(account_id)
        if account_id in self._boto_session_by_account:
            return cached

        account = self._load_account(account_id)
        external_id = self._load_tenant_external_id()
        if account is None or not external_id:
            self._session_error_by_account[account_id] = "missing_account_or_external_id"
            self._boto_session_by_account[account_id] = None
            return None

        try:
            aws_session = assume_role(
                role_arn=account.role_read_arn,
                external_id=external_id,
                source_identity=WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
                tags=build_assume_role_tags(service_component="worker", tenant_id=self._tenant_id),
            )
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            self._session_error_by_account[account_id] = f"assume_role_failed:{type(exc).__name__}"
            self._boto_session_by_account[account_id] = None
            return None

        self._boto_session_by_account[account_id] = aws_session
        return aws_session

    def _load_account(self, account_id: str) -> AwsAccount | None:
        if account_id in self._account_by_id:
            return self._account_by_id[account_id]
        account = (
            self._session.query(AwsAccount)
            .filter(AwsAccount.tenant_id == self._tenant_id, AwsAccount.account_id == account_id)
            .first()
        )
        self._account_by_id[account_id] = account
        return account

    def _load_tenant_external_id(self) -> str | None:
        if self._tenant_external_id is not None:
            return self._tenant_external_id
        tenant = self._session.query(Tenant).filter(Tenant.id == self._tenant_id).first()
        external_id = str((tenant.external_id if tenant else "") or "").strip()
        self._tenant_external_id = external_id or ""
        return self._tenant_external_id or None


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
    return _grouping_key_for_target(finding, finding.resource_id)


def _grouping_key_for_target(finding: Finding, resource_id: str | None) -> tuple[Any, ...]:
    action_type = _action_type_from_control(finding.control_id)
    canonical_control_id = canonical_control_id_for_action_type(action_type, finding.control_id) or ""
    return (
        finding.tenant_id,
        finding.account_id,
        finding.region or "",
        (resource_id or "")[:512],
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


def _group_score(findings: list[Finding]) -> tuple[int, dict[str, Any], Finding | None]:
    """Return deterministic group score, persisted component payload, and representative finding."""
    group_score = score_action_group(findings)
    representative = group_score.representative_finding if isinstance(group_score.representative_finding, Finding) else None
    components = dict(group_score.components)
    components["business_impact"] = _business_impact_payload(group_score.score, representative, components)
    return group_score.score, components, representative


def _business_impact_payload(score: int, representative: Finding | None, components: dict[str, Any]) -> dict[str, Any]:
    if representative is None:
        return build_business_impact_from_components(components, stored_score=score)
    return build_business_impact_for_finding(representative, technical_score=score)


def _action_status_from_findings(findings: list[Finding]) -> str:
    """Resolved if all findings are RESOLVED or SUPPRESSED; else open."""
    if not findings:
        return ActionStatus.resolved.value
    for f in findings:
        if _is_effectively_open_finding(f):
            return ActionStatus.open.value
    return ActionStatus.resolved.value


def _title_and_description_for_group(
    findings: list[Finding],
    representative: Finding | None,
) -> tuple[str, str | None]:
    """Human-readable title (max 500) and description from the representative finding."""
    selected = representative or (findings[0] if findings else None)
    if selected is None:
        return "Action", None
    title = (selected.title or "Security finding")[:500]
    desc = selected.description
    if len(findings) > 1:
        desc = (desc or "") + f" (+{len(findings) - 1} related finding(s))"
    return title, (desc[:65535] if desc else None)


def _unique_findings(group: list[ExpandedFindingTarget]) -> list[Finding]:
    deduped: list[Finding] = []
    seen: set[uuid.UUID] = set()
    for item in group:
        finding = item.finding
        if finding.id in seen:
            continue
        seen.add(finding.id)
        deduped.append(finding)
    return deduped


def _upsert_action_and_sync_links(
    session: Session,
    tenant_id: uuid.UUID,
    group: list[ExpandedFindingTarget],
) -> tuple[Action, bool, list[uuid.UUID], bool]:
    """
    Upsert one action for the group of findings; sync action_findings to current group.
    Returns (action, created, finding_ids, allow_multi_action_links).
    """
    if not group:
        raise ValueError("group must be non-empty")

    findings = _unique_findings(group)
    first_target = group[0]
    first_finding = first_target.finding
    account_id = first_finding.account_id
    region = first_finding.region
    resource_id = first_target.resource_id
    action_type = _action_type_from_control(first_finding.control_id)
    control_id = canonical_control_id_for_action_type(action_type, first_finding.control_id)
    target_id = _build_target_id(account_id, region, resource_id, control_id)

    score, score_components, representative = _group_score(findings)
    status = _action_status_from_findings(findings)
    title, description = _title_and_description_for_group(findings, representative)
    resource_type = first_target.resource_type
    if resource_type and len(resource_type) > 128:
        resource_type = resource_type[:128]
    owner = resolve_action_owner(findings, action_type=action_type, resource_type=resource_type)

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
        action.score = score
        action.score_components = score_components
        action.priority = score
        if action.status != status:
            _sync_existing_action_status(session, action, status, "Recomputed canonical action state from linked findings.")
        action.title = title
        action.description = description
        action.resource_id = resource_id
        action.resource_type = resource_type
        action.control_id = control_id
        action.owner_type = owner.owner_type
        action.owner_key = owner.owner_key
        action.owner_label = owner.owner_label
        action.action_finding_links = [ActionFinding(finding=finding) for finding in findings]
        finding_ids = [finding.id for finding in findings]
        allow_multi = any(item.allow_multi_action_links for item in group)
        return action, False, finding_ids, allow_multi

    action = Action(
        tenant_id=tenant_id,
        action_type=action_type,
        target_id=target_id,
        account_id=account_id,
        region=region,
        score=score,
        score_components=score_components,
        priority=score,
        status=status,
        title=title,
        description=description,
        control_id=control_id,
        resource_id=resource_id,
        resource_type=resource_type,
        owner_type=owner.owner_type,
        owner_key=owner.owner_key,
        owner_label=owner.owner_label,
    )
    action.action_finding_links = [ActionFinding(finding=finding) for finding in findings]
    session.add(action)
    finding_ids = [finding.id for finding in findings]
    allow_multi = any(item.allow_multi_action_links for item in group)
    return action, True, finding_ids, allow_multi


def _remove_conflicting_links_for_findings(
    session: Session,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    finding_ids: list[uuid.UUID],
    *,
    allow_multi_action_links: bool,
) -> int:
    """
    Ensure each finding maps to a single action by removing links to other actions.

    SG account-scoped expansion intentionally allows one finding to fan out into
    multiple SG actions, so conflicting-link cleanup is skipped for those groups.
    """
    if not finding_ids or allow_multi_action_links:
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


def _prune_expanded_sg_links(
    session: Session,
    tenant_id: uuid.UUID,
    allowed_action_ids_by_finding: dict[uuid.UUID, set[uuid.UUID]],
) -> int:
    removed = 0
    for finding_id, allowed_action_ids in allowed_action_ids_by_finding.items():
        query = (
            session.query(ActionFinding)
            .join(Action, Action.id == ActionFinding.action_id)
            .filter(
                Action.tenant_id == tenant_id,
                Action.action_type == _SG_ACTION_TYPE,
                ActionFinding.finding_id == finding_id,
            )
        )
        if allowed_action_ids:
            query = query.filter(~ActionFinding.action_id.in_(list(allowed_action_ids)))
        for link in query.all():
            session.delete(link)
            removed += 1
    return removed


def _mark_resolved_actions_with_no_open_findings(
    session: Session,
    tenant_id: uuid.UUID,
    account_id: str | None,
    region: str | None,
    *,
    return_action_ids: bool = False,
) -> int | list[uuid.UUID]:
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
    resolved_ids: list[uuid.UUID] = []
    for action in open_actions:
        unresolved_count = _linked_unresolved_finding_count(action)
        if unresolved_count == 0:
            _sync_existing_action_status(session, action, ActionStatus.resolved.value, "Closed action after linked findings resolved.")
            resolved_count += 1
            if return_action_ids:
                action_id = getattr(action, "id", None)
                if action_id is not None:
                    resolved_ids.append(action_id)
    if return_action_ids:
        return resolved_ids
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
    *,
    return_action_ids: bool = False,
) -> int | list[uuid.UUID]:
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
    reopened_count = 0
    reopened_ids: list[uuid.UUID] = []
    for action in resolved_actions:
        if _linked_unresolved_finding_count(action) > 0:
            _sync_existing_action_status(session, action, ActionStatus.open.value, "Reopened action after linked findings regressed.")
            reopened_count += 1
            if return_action_ids:
                action_id = getattr(action, "id", None)
                if action_id is not None:
                    reopened_ids.append(action_id)
    if return_action_ids:
        return reopened_ids
    return reopened_count


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
    q = session.query(Finding).filter(Finding.tenant_id == tenant_id)
    if account_id is not None:
        q = q.filter(Finding.account_id == account_id)
    if region is not None:
        q = q.filter(Finding.region == region)

    if settings.ONLY_IN_SCOPE_CONTROLS:
        q = q.filter(Finding.in_scope.is_(True))
    findings = [finding for finding in q.all() if _is_effectively_open_finding(finding)]

    expansion_context = _ActionExpansionContext(session, tenant_id)
    groups: defaultdict[tuple[Any, ...], list[ExpandedFindingTarget]] = defaultdict(list)
    expanded_account_scoped_finding_ids: set[uuid.UUID] = set()
    for finding in findings:
        if is_account_scoped_sg_control(finding.control_id, finding.resource_type):
            expanded_account_scoped_finding_ids.add(finding.id)
        for target in expansion_context.expand_finding(finding):
            groups[_grouping_key_for_target(finding, target.resource_id)].append(target)

    created = 0
    updated = 0
    links_count = 0
    removed_conflicting_links = 0
    actions_touched: list[Action] = []
    created_action_ids: list[str] = []
    updated_action_ids: list[str] = []
    allowed_expanded_action_ids_by_finding: defaultdict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)

    for group in groups.values():
        action, is_new, finding_ids, allow_multi = _upsert_action_and_sync_links(session, tenant_id, group)
        if action.id is None:
            session.flush()
        actions_touched.append(action)

        removed_conflicting_links += _remove_conflicting_links_for_findings(
            session=session,
            tenant_id=tenant_id,
            action_id=action.id,
            finding_ids=finding_ids,
            allow_multi_action_links=allow_multi,
        )

        if allow_multi:
            for finding_id in finding_ids:
                allowed_expanded_action_ids_by_finding[finding_id].add(action.id)

        if is_new:
            created += 1
            created_action_ids.append(str(action.id))
        else:
            updated += 1
            updated_action_ids.append(str(action.id))
        links_count += len(finding_ids)

    for finding_id in expanded_account_scoped_finding_ids:
        allowed_expanded_action_ids_by_finding.setdefault(finding_id, set())
    if allowed_expanded_action_ids_by_finding:
        removed_conflicting_links += _prune_expanded_sg_links(
            session,
            tenant_id,
            dict(allowed_expanded_action_ids_by_finding),
        )

    toxic_combination_matches = apply_toxic_combination_overlays(actions_touched)

    if actions_touched:
        ensure_membership_for_actions(session, actions_touched, source="recompute")

    resolved_action_ids = _mark_resolved_actions_with_no_open_findings(
        session,
        tenant_id,
        account_id,
        region,
        return_action_ids=True,
    )
    reopened_action_ids = _reopen_resolved_orphan_actions(
        session,
        tenant_id,
        account_id,
        region,
        return_action_ids=True,
    )
    resolved = len(resolved_action_ids)
    reopened_with_open_findings = len(reopened_action_ids)
    graph_counts = sync_security_graph_for_scope(
        session,
        tenant_id,
        account_id=account_id,
        region=region,
    )

    logger.info(
        "compute_actions_for_tenant tenant_id=%s scope=(account=%s region=%s) groups=%d created=%d updated=%d resolved=%d reopened_with_open_findings=%d links=%d removed_links=%d toxic_combination_matches=%d graph_nodes_created=%d graph_edges_created=%d graph_nodes_deleted=%d graph_edges_deleted=%d",
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
        toxic_combination_matches,
        graph_counts["graph_nodes_created"],
        graph_counts["graph_edges_created"],
        graph_counts["graph_nodes_deleted"],
        graph_counts["graph_edges_deleted"],
    )
    return {
        "actions_created": created,
        "actions_updated": updated,
        "actions_resolved": resolved,
        "actions_reopened_orphaned": reopened_with_open_findings,
        "actions_reopened_with_open_findings": reopened_with_open_findings,
        "action_findings_linked": links_count,
        "created_action_ids": created_action_ids,
        "updated_action_ids": updated_action_ids,
        "resolved_action_ids": [str(action_id) for action_id in resolved_action_ids],
        "reopened_action_ids": [str(action_id) for action_id in reopened_action_ids],
        "toxic_combination_matches": toxic_combination_matches,
        **graph_counts,
    }
