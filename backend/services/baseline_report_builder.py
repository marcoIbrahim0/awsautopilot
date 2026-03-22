"""
Baseline report data builder.

Builds decision-oriented BaselineReportData from tenant findings and related
action/remediation state:
- summary and top risks
- next actions (top 3)
- change delta vs previous successful report
- confidence gaps
- closure proof
- recommendations
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.action import Action
from backend.models.action_finding import ActionFinding
from backend.models.enums import EntityType, RemediationRunStatus
from backend.models.exception import Exception as FindingActionException
from backend.models.finding import Finding
from backend.models.remediation_run import RemediationRun
from backend.services.baseline_report_spec import (
    CLOSURE_PROOF_MAX,
    RECOMMENDATIONS_MAX,
    SEVERITY_ORDER,
    TOP_RISKS_MAX,
    BaselineReportData,
    BaselineSummary,
    ChangeDelta,
    ClosureProofItem,
    ConfidenceGapItem,
    NextActionItem,
    RecommendationItem,
    TopRiskItem,
    build_narrative,
    severity_sort_key,
)
from backend.services.control_scope import ACTION_TYPE_DEFAULT, action_type_from_control
from backend.services.direct_fix_bridge import get_supported_direct_fix_action_types

# Finding status: open = NEW, NOTIFIED; resolved = RESOLVED, SUPPRESSED
_OPEN_STATUSES = {"NEW", "NOTIFIED"}
_RESOLVED_STATUSES = {"RESOLVED", "SUPPRESSED"}

_OPEN_ACTION_STATUSES = {"open", "in_progress"}

_ACTIVE_RUN_STATUSES = {
    RemediationRunStatus.pending,
    RemediationRunStatus.running,
    RemediationRunStatus.awaiting_approval,
}

_CONTROL_RECOMMENDATIONS: dict[str, str] = {
    "SecurityHub.1": "Enable Security Hub in all configured regions.",
    "GuardDuty.1": "Enable GuardDuty in all regions.",
    "S3.1": "Review S3 public access (block public access at account and bucket level).",
    "CloudTrail.1": "Ensure CloudTrail is enabled in all regions.",
    "Config.1": "Enable AWS Config recorder and delivery in every account and region.",
    "EC2.53": "Restrict public SSH/RDP exposure in security groups.",
    "IAM.4": "Remove root account access keys and migrate usage to least-privilege IAM roles.",
}

_CONTROL_BUSINESS_IMPACT: dict[str, str] = {
    "S3.1": "Public data exposure risk from permissive S3 access.",
    "S3.2": "Internet exposure risk on buckets intended to stay private.",
    "S3.4": "Unencrypted object storage raises breach and audit risk.",
    "S3.5": "Missing SSL-only policy allows plaintext access patterns.",
    "CloudTrail.1": "Missing trails weakens forensics and incident response.",
    "GuardDuty.1": "Threat detection blind spot for malicious activity.",
    "SecurityHub.1": "Centralized security visibility and standards tracking is degraded.",
    "Config.1": "Compliance drift cannot be reliably detected or proven.",
    "EC2.53": "Direct attack surface exists via publicly exposed administrative ports.",
    "IAM.4": "Root-key presence increases account-takeover blast radius.",
}

_SOC2_CC_BY_CONTROL: dict[str, tuple[str, ...]] = {
    "S3.1": ("CC6.1",),
    "S3.2": ("CC6.1",),
    "S3.4": ("CC6.7",),
    "S3.5": ("CC6.7",),
    "CloudTrail.1": ("CC7.2",),
    "GuardDuty.1": ("CC7.2",),
    "SecurityHub.1": ("CC7.2",),
    "Config.1": ("CC7.2",),
    "EC2.53": ("CC6.6",),
    "IAM.4": ("CC6.1",),
}

_DUE_DAYS_BY_SEVERITY: dict[str, int] = {
    "CRITICAL": 3,
    "HIGH": 7,
    "MEDIUM": 14,
    "LOW": 30,
    "INFORMATIONAL": 45,
}

_WHY_NOW_BY_SEVERITY: dict[str, str] = {
    "CRITICAL": "Critical exposure is open now; reduce exploit window immediately.",
    "HIGH": "High-severity risk is still open and should be closed in the current sprint.",
    "MEDIUM": "Medium-risk finding is unresolved and accumulating operational debt.",
    "LOW": "Low-risk hardening is still pending and should be scheduled.",
    "INFORMATIONAL": "Informational issue is open and should be triaged for closure or exception.",
}

_CONFIDENCE_DETAILS: dict[str, str] = {
    "access_denied": "Some checks returned access denied responses; ReadRole scope may be incomplete.",
    "partial_data": "Some probes returned partial/indeterminate data; status may be conservative.",
    "api_error": "Provider/API errors (for example throttling) reduced certainty of the snapshot.",
    "telemetry_gap": "Recent telemetry/evidence for some checks is missing or stale.",
}

_CONFIDENCE_CATEGORY_TOKENS: dict[str, tuple[str, ...]] = {
    "access_denied": ("access_denied", "access denied", "unauthorized", "not authorized"),
    "partial_data": ("partial_data", "partial data", "indeterminate", "status_mismatch"),
    "api_error": ("api_error", "api error", "throttling", "serviceunavailable", "internalerror"),
    "telemetry_gap": ("telemetry", "evidence_unavailable", "event_missing", "no_event"),
}

_ACCOUNT_LEVEL_ACTION_TYPES = {
    "s3_block_public_access",
    "enable_security_hub",
    "enable_guardduty",
    "cloudtrail_enabled",
    "aws_config_enabled",
    "ebs_default_encryption",
}


def _to_utc(value: object | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _severity_for_display(label: str) -> Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]:
    u = (label or "").upper()
    if u in SEVERITY_ORDER:
        return u  # type: ignore[return-value]
    return "MEDIUM"


def _severity_from_priority(priority: int | None) -> Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]:
    p = int(priority or 0)
    if p >= 90:
        return "CRITICAL"
    if p >= 70:
        return "HIGH"
    if p >= 45:
        return "MEDIUM"
    if p >= 20:
        return "LOW"
    return "INFORMATIONAL"


def _recommendation_text_for_control(control_id: str | None, region: str | None) -> str | None:
    if not control_id:
        return None
    c = control_id.strip()
    if c == "GuardDuty.1" and region:
        return f"Enable GuardDuty in {region}."
    if c == "SecurityHub.1" and region:
        return f"Enable Security Hub in {region}."
    if c == "S3.1":
        return "Enable S3 block public access."
    if c == "CloudTrail.1" and region:
        return f"Enable CloudTrail in {region}."
    return _CONTROL_RECOMMENDATIONS.get(c)


def _business_impact_for_control(
    control_id: str | None,
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"],
) -> str:
    if control_id:
        mapped = _CONTROL_BUSINESS_IMPACT.get(control_id.strip())
        if mapped:
            return mapped
    if severity == "CRITICAL":
        return "Immediate data-loss or compromise risk if left unaddressed."
    if severity == "HIGH":
        return "Material security and compliance exposure requiring near-term action."
    if severity == "MEDIUM":
        return "Moderate control weakness with potential downstream audit impact."
    if severity == "LOW":
        return "Hardening gap that increases long-term operational risk."
    return "Control hygiene issue requiring triage and disposition."


def _soc2_cc_ids(control_id: str | None) -> list[str] | None:
    if not control_id:
        return None
    ids = _SOC2_CC_BY_CONTROL.get(control_id.strip())
    if not ids:
        return None
    return list(ids)


def _recommended_mode_for_action_type(
    action_type: str | None,
    *,
    direct_fix_supported: frozenset[str],
) -> Literal["pr_only", "exception_review"]:
    _ = action_type, direct_fix_supported
    return "pr_only"


def _pick_primary_action(
    finding_id: uuid.UUID,
    *,
    finding_to_action_ids: dict[uuid.UUID, list[uuid.UUID]],
    actions_by_id: dict[uuid.UUID, Action],
) -> Action | None:
    action_ids = finding_to_action_ids.get(finding_id, [])
    if not action_ids:
        return None
    status_rank = {"open": 0, "in_progress": 1, "resolved": 2, "suppressed": 3}
    candidates = [actions_by_id[aid] for aid in action_ids if aid in actions_by_id]
    if not candidates:
        return None
    candidates.sort(
        key=lambda action: (
            status_rank.get((action.status or "").lower(), 9),
            -(action.priority or 0),
        )
    )
    return candidates[0]


def _readiness_for_action(
    *,
    latest_run: RemediationRun | None,
    action_exception: FindingActionException | None,
    now: datetime,
) -> str:
    if action_exception and _to_utc(action_exception.expires_at) and _to_utc(action_exception.expires_at) > now:
        return "blocked_by_exception"
    if not latest_run:
        return "ready"
    if latest_run.status in _ACTIVE_RUN_STATUSES:
        return "in_progress"
    if latest_run.status == RemediationRunStatus.failed:
        return "needs_attention"
    return "ready"


def _fix_path_for_action(
    *,
    mode: Literal["pr_only", "exception_review"],
    readiness: str,
    action_exception: FindingActionException | None,
) -> str:
    if readiness == "blocked_by_exception":
        expires_at = _to_utc(action_exception.expires_at) if action_exception else None
        if expires_at:
            return f"Exception is active until {expires_at.date().isoformat()}; review or expire it before remediation."
        return "Exception is active; review exception before remediation."
    if readiness == "needs_attention":
        return "Latest remediation run failed; inspect run logs and re-run with corrected permissions/inputs."
    if mode == "exception_review":
        return "Open action and complete exception-style review before remediation proceeds."
    return "Open action, generate PR bundle, and merge through your IaC change process."


def _blast_radius_for_action(action: Action, linked_findings: list[Finding]) -> str:
    finding_count = len(linked_findings)
    if action.action_type in _ACCOUNT_LEVEL_ACTION_TYPES:
        scope = action.region or "all configured regions"
        return f"Account-level control across account {action.account_id} ({scope})."
    if finding_count > 1:
        return f"Affects {finding_count} linked findings on target {action.target_id}."
    return f"Affects target {action.target_id} in account {action.account_id}."


def _change_delta_summary(change: ChangeDelta) -> str:
    if not change.compared_to_report_at:
        return "No prior successful baseline report was found for this scope."
    prior = change.compared_to_report_at.date().isoformat()
    return (
        f"Since {prior}: {change.new_open_count} new open, "
        f"{change.regressed_count} regressed, {change.stale_open_count} stale open, "
        f"{change.closed_count} newly closed."
    )


def _build_change_delta(
    findings: list[Finding],
    *,
    previous_report_requested_at: datetime | None,
) -> ChangeDelta:
    previous = _to_utc(previous_report_requested_at)

    if previous is None:
        return ChangeDelta(
            compared_to_report_at=None,
            new_open_count=0,
            regressed_count=0,
            stale_open_count=0,
            closed_count=0,
            summary="No prior successful baseline report was found for this scope.",
        )

    new_open_count = 0
    regressed_count = 0
    stale_open_count = 0
    closed_count = 0

    for finding in findings:
        status = (finding.status or "").upper()
        created_at = _to_utc(getattr(finding, "created_at", None))
        first_observed = _to_utc(getattr(finding, "first_observed_at", None)) or created_at
        resolved_at = _to_utc(getattr(finding, "resolved_at", None))
        updated_at = _to_utc(getattr(finding, "updated_at", None))

        if status in _OPEN_STATUSES:
            if created_at and created_at > previous:
                new_open_count += 1
            elif first_observed and first_observed <= previous:
                stale_open_count += 1
            if resolved_at and resolved_at <= previous:
                regressed_count += 1

        if status in _RESOLVED_STATUSES:
            if resolved_at and resolved_at > previous:
                closed_count += 1
            elif not resolved_at and updated_at and updated_at > previous:
                closed_count += 1

    change = ChangeDelta(
        compared_to_report_at=previous,
        new_open_count=new_open_count,
        regressed_count=regressed_count,
        stale_open_count=stale_open_count,
        closed_count=closed_count,
        summary="Pending summary.",
    )
    change.summary = _change_delta_summary(change)
    return change


def _signal_text_from_raw(raw_json: object) -> str:
    try:
        rendered = json.dumps(raw_json, default=str)
    except Exception:
        rendered = str(raw_json)
    return rendered[:5000].lower()


def _extract_confidence_categories(finding: Finding) -> set[str]:
    reason = (getattr(finding, "shadow_status_reason", None) or "").lower()
    status = (getattr(finding, "shadow_status_normalized", None) or "").lower()
    raw_signal = _signal_text_from_raw(getattr(finding, "raw_json", {}))
    combined = " ".join([reason, status, raw_signal])

    matched: set[str] = set()
    for category, tokens in _CONFIDENCE_CATEGORY_TOKENS.items():
        if any(token in combined for token in tokens):
            matched.add(category)
    return matched


def _build_confidence_gaps(findings: list[Finding]) -> list[ConfidenceGapItem]:
    category_count: dict[str, int] = defaultdict(int)
    category_controls: dict[str, set[str]] = defaultdict(set)

    for finding in findings:
        categories = _extract_confidence_categories(finding)
        for category in categories:
            category_count[category] += 1
            control_id = (finding.control_id or "").strip()
            if control_id:
                category_controls[category].add(control_id)

    ordered = sorted(category_count.items(), key=lambda item: (-item[1], item[0]))
    out: list[ConfidenceGapItem] = []
    for category, count in ordered:
        if count <= 0:
            continue
        controls = sorted(category_controls.get(category, set()))
        out.append(
            ConfidenceGapItem(
                category=category,  # type: ignore[arg-type]
                count=count,
                detail=_CONFIDENCE_DETAILS.get(category, "Confidence gap detected in this snapshot."),
                affected_control_ids=controls or None,
            )
        )
    return out


def _action_severity(
    action: Action,
    linked_findings: list[Finding],
) -> Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]:
    if linked_findings:
        best = min(linked_findings, key=lambda finding: severity_sort_key(finding.severity_label))
        return _severity_for_display(best.severity_label)
    return _severity_from_priority(action.priority)


def _top_recommendations(findings: list[Finding]) -> list[RecommendationItem]:
    seen_controls: set[str] = set()
    recs: list[RecommendationItem] = []
    for finding in findings:
        control_id = (finding.control_id or "").strip()
        if not control_id or control_id in seen_controls:
            continue
        text = _CONTROL_RECOMMENDATIONS.get(control_id)
        if not text:
            continue
        seen_controls.add(control_id)
        recs.append(
            RecommendationItem(
                text=text,
                control_id=control_id,
                soc2_cc_ids=_soc2_cc_ids(control_id),
            )
        )
        if len(recs) >= RECOMMENDATIONS_MAX:
            break
    return recs


def build_baseline_report_data(
    session: Session,
    tenant_id: str,
    account_ids: list[str] | None = None,
    tenant_name: str | None = None,
    current_report_requested_at: datetime | None = None,
    previous_report_requested_at: datetime | None = None,
) -> BaselineReportData:
    """Build BaselineReportData from tenant findings and related action lifecycle state."""
    tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    now = _to_utc(current_report_requested_at) or datetime.now(timezone.utc)
    report_date = date(now.year, now.month, now.day)

    findings_query = (
        select(Finding)
        .where(Finding.tenant_id == tid)
        .order_by(Finding.severity_normalized.desc(), Finding.updated_at.desc())
    )
    if account_ids:
        findings_query = findings_query.where(Finding.account_id.in_(account_ids))
    findings = list(session.execute(findings_query).scalars().all())

    total = len(findings)
    by_severity: dict[str, int] = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        display_severity = _severity_for_display(finding.severity_label)
        by_severity[display_severity] = by_severity.get(display_severity, 0) + 1

    open_count = sum(1 for finding in findings if (finding.status or "").upper() in _OPEN_STATUSES)
    resolved_count = sum(1 for finding in findings if (finding.status or "").upper() in _RESOLVED_STATUSES)

    account_count: int | None = None
    region_count: int | None = None
    if findings:
        account_count = len({finding.account_id for finding in findings})
        region_count = len({finding.region for finding in findings if finding.region})

    finding_by_id: dict[uuid.UUID, Finding] = {finding.id: finding for finding in findings}
    finding_ids = list(finding_by_id.keys())

    finding_to_action_ids: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    action_to_finding_ids: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    actions_by_id: dict[uuid.UUID, Action] = {}
    latest_run_by_action: dict[uuid.UUID, RemediationRun] = {}
    exception_by_action: dict[uuid.UUID, FindingActionException] = {}

    if finding_ids:
        link_rows = list(
            session.execute(
                select(ActionFinding.action_id, ActionFinding.finding_id)
                .join(Action, Action.id == ActionFinding.action_id)
                .where(Action.tenant_id == tid, ActionFinding.finding_id.in_(finding_ids))
            ).all()
        )
        action_ids = sorted({row[0] for row in link_rows})
        for action_id, finding_id in link_rows:
            finding_to_action_ids[finding_id].append(action_id)
            action_to_finding_ids[action_id].append(finding_id)

        if action_ids:
            actions = list(
                session.execute(
                    select(Action).where(Action.tenant_id == tid, Action.id.in_(action_ids))
                ).scalars().all()
            )
            actions_by_id = {action.id: action for action in actions}

            runs = list(
                session.execute(
                    select(RemediationRun)
                    .where(RemediationRun.tenant_id == tid, RemediationRun.action_id.in_(action_ids))
                    .order_by(RemediationRun.created_at.desc())
                ).scalars().all()
            )
            for run in runs:
                if run.action_id not in latest_run_by_action:
                    latest_run_by_action[run.action_id] = run

            exceptions = list(
                session.execute(
                    select(FindingActionException).where(
                        FindingActionException.tenant_id == tid,
                        FindingActionException.entity_type == EntityType.action,
                        FindingActionException.entity_id.in_(action_ids),
                    )
                ).scalars().all()
            )
            for exc in exceptions:
                if exc.entity_id not in exception_by_action:
                    exception_by_action[exc.entity_id] = exc

    direct_fix_supported = get_supported_direct_fix_action_types()

    sorted_findings = sorted(
        findings,
        key=lambda finding: (
            severity_sort_key(finding.severity_label),
            -(finding.severity_normalized or 0),
        ),
    )
    top_findings = sorted_findings[:TOP_RISKS_MAX]
    top_risks: list[TopRiskItem] = []
    for finding in top_findings:
        severity = _severity_for_display(finding.severity_label)
        primary_action = _pick_primary_action(
            finding.id,
            finding_to_action_ids=finding_to_action_ids,
            actions_by_id=actions_by_id,
        )
        action_type = primary_action.action_type if primary_action else action_type_from_control(finding.control_id)
        if action_type == ACTION_TYPE_DEFAULT and primary_action is None:
            action_type = None
        mode = _recommended_mode_for_action_type(action_type, direct_fix_supported=direct_fix_supported)
        latest_run = latest_run_by_action.get(primary_action.id) if primary_action else None
        action_exception = exception_by_action.get(primary_action.id) if primary_action else None
        readiness = _readiness_for_action(latest_run=latest_run, action_exception=action_exception, now=now)

        top_risks.append(
            TopRiskItem(
                title=finding.title or "Finding",
                severity=severity,
                account_id=finding.account_id,
                status=finding.status or "open",
                resource_id=finding.resource_id,
                control_id=finding.control_id,
                region=finding.region,
                recommendation_text=_recommendation_text_for_control(finding.control_id, finding.region),
                business_impact=_business_impact_for_control(finding.control_id, severity),
                action_id=str(primary_action.id) if primary_action else None,
                action_status=primary_action.status if primary_action else None,
                action_type=action_type,
                recommended_mode=mode,
                remediation_readiness=readiness,
                why_now=_WHY_NOW_BY_SEVERITY[severity],
                soc2_cc_ids=_soc2_cc_ids(finding.control_id),
                link_to_app=f"/actions/{primary_action.id}" if primary_action else None,
            )
        )

    next_actions: list[NextActionItem] = []
    action_candidates = [
        action
        for action in actions_by_id.values()
        if (action.status or "").lower() in _OPEN_ACTION_STATUSES
    ]

    scored_actions: list[
        tuple[
            tuple[int, int, int],
            NextActionItem,
        ]
    ] = []
    readiness_rank = {"needs_attention": 0, "ready": 1, "in_progress": 2, "blocked_by_exception": 3}
    for action in action_candidates:
        linked_findings = [
            finding_by_id[fid]
            for fid in action_to_finding_ids.get(action.id, [])
            if fid in finding_by_id
        ]
        severity = _action_severity(action, linked_findings)
        mode = _recommended_mode_for_action_type(
            action.action_type,
            direct_fix_supported=direct_fix_supported,
        )
        latest_run = latest_run_by_action.get(action.id)
        action_exception = exception_by_action.get(action.id)
        readiness = _readiness_for_action(
            latest_run=latest_run,
            action_exception=action_exception,
            now=now,
        )

        due_days = _DUE_DAYS_BY_SEVERITY.get(severity, 14)
        due_by = report_date + timedelta(days=due_days)
        owner = None
        if action_exception and action_exception.owner_user_id:
            owner = str(action_exception.owner_user_id)
        elif action_exception and action_exception.approved_by_user_id:
            owner = str(action_exception.approved_by_user_id)

        fix_path = _fix_path_for_action(
            mode=mode,
            readiness=readiness,
            action_exception=action_exception,
        )
        cta_label = "Review exception" if readiness == "blocked_by_exception" else (
            "Open direct fix" if mode == "direct_fix" else "Open PR bundle"
        )

        top_control_id = action.control_id
        if not top_control_id and linked_findings:
            top_control_id = linked_findings[0].control_id

        next_item = NextActionItem(
            action_id=str(action.id),
            title=action.title or (linked_findings[0].title if linked_findings else "Action"),
            control_id=top_control_id,
            severity=severity,
            account_id=action.account_id,
            region=action.region,
            action_status=action.status,
            why_now=_WHY_NOW_BY_SEVERITY[severity],
            recommended_mode=mode,
            blast_radius=_blast_radius_for_action(action, linked_findings),
            fix_path=fix_path,
            owner=owner,
            due_by=due_by,
            readiness=readiness,
            cta_label=cta_label,
            cta_href=f"/actions/{action.id}",
        )
        score = (
            readiness_rank.get(readiness, 9),
            severity_sort_key(severity),
            -(action.priority or 0),
        )
        scored_actions.append((score, next_item))

    scored_actions.sort(key=lambda pair: pair[0])
    next_actions = [item for _, item in scored_actions[:3]]

    if not next_actions:
        for risk in top_risks:
            mode = risk.recommended_mode or "pr_only"
            readiness = risk.remediation_readiness or "ready"
            next_actions.append(
                NextActionItem(
                    action_id=risk.action_id,
                    title=risk.title,
                    control_id=risk.control_id,
                    severity=risk.severity,
                    account_id=risk.account_id,
                    region=risk.region,
                    action_status=risk.action_status,
                    why_now=risk.why_now or _WHY_NOW_BY_SEVERITY[risk.severity],
                    recommended_mode=mode,
                    blast_radius=f"Affects account {risk.account_id} ({risk.region or 'global'}).",
                    fix_path=(
                        "Open action and execute approved direct fix flow."
                        if mode == "direct_fix"
                        else "Generate PR bundle and merge through IaC workflow."
                    ),
                    owner=None,
                    due_by=report_date + timedelta(days=_DUE_DAYS_BY_SEVERITY.get(risk.severity, 14)),
                    readiness=readiness,
                    cta_label="Open details",
                    cta_href=risk.link_to_app,
                )
            )
            if len(next_actions) >= 3:
                break

    change_delta = _build_change_delta(
        findings,
        previous_report_requested_at=previous_report_requested_at,
    )

    open_findings = [finding for finding in findings if (finding.status or "").upper() in _OPEN_STATUSES]
    confidence_gaps = _build_confidence_gaps(open_findings)

    resolved_findings = [finding for finding in findings if (finding.status or "").upper() in _RESOLVED_STATUSES]
    resolved_findings.sort(
        key=lambda finding: (
            _to_utc(getattr(finding, "resolved_at", None))
            or _to_utc(getattr(finding, "updated_at", None))
            or datetime(1970, 1, 1, tzinfo=timezone.utc)
        ),
        reverse=True,
    )

    closure_proof: list[ClosureProofItem] = []
    for finding in resolved_findings[:CLOSURE_PROOF_MAX]:
        primary_action = _pick_primary_action(
            finding.id,
            finding_to_action_ids=finding_to_action_ids,
            actions_by_id=actions_by_id,
        )
        latest_run = latest_run_by_action.get(primary_action.id) if primary_action else None
        resolved_at = _to_utc(getattr(finding, "resolved_at", None)) or _to_utc(getattr(finding, "updated_at", None))

        if latest_run and latest_run.status == RemediationRunStatus.success:
            completed_at = _to_utc(getattr(latest_run, "completed_at", None))
            if completed_at:
                evidence_note = f"Remediation run succeeded on {completed_at.date().isoformat()}."
            else:
                evidence_note = "Remediation run succeeded."
        elif (finding.status or "").upper() == "SUPPRESSED":
            evidence_note = "Suppressed through approved exception workflow."
        elif resolved_at:
            evidence_note = "Resolved by latest telemetry/control-plane evaluation."
        else:
            evidence_note = "Resolved in workflow state."

        closure_proof.append(
            ClosureProofItem(
                finding_id=finding.finding_id or str(finding.id),
                title=finding.title or "Finding",
                control_id=finding.control_id,
                account_id=finding.account_id,
                region=finding.region,
                resolved_at=resolved_at,
                action_id=str(primary_action.id) if primary_action else None,
                remediation_run_id=str(latest_run.id) if latest_run else None,
                evidence_note=evidence_note,
            )
        )

    recommendations = _top_recommendations(findings)
    if not recommendations and next_actions:
        for action in next_actions:
            if not action.control_id:
                continue
            text = _CONTROL_RECOMMENDATIONS.get(action.control_id)
            if not text:
                continue
            recommendations.append(
                RecommendationItem(
                    text=text,
                    control_id=action.control_id,
                    soc2_cc_ids=_soc2_cc_ids(action.control_id),
                )
            )
            if len(recommendations) >= RECOMMENDATIONS_MAX:
                break

    soc2_ids: set[str] = set()
    for risk in top_risks:
        for cc_id in risk.soc2_cc_ids or []:
            soc2_ids.add(cc_id)
    soc2_impacted_finding_count = sum(1 for risk in top_risks if risk.soc2_cc_ids)

    narrative = build_narrative(
        total=total,
        critical=by_severity.get("CRITICAL", 0),
        high=by_severity.get("HIGH", 0),
        report_date=report_date,
    )
    if change_delta.compared_to_report_at:
        narrative = f"{narrative} {change_delta.summary}"

    summary = BaselineSummary(
        total_finding_count=total,
        critical_count=by_severity.get("CRITICAL", 0),
        high_count=by_severity.get("HIGH", 0),
        medium_count=by_severity.get("MEDIUM", 0),
        low_count=by_severity.get("LOW", 0),
        informational_count=by_severity.get("INFORMATIONAL", 0),
        open_count=open_count,
        resolved_count=resolved_count,
        narrative=narrative,
        report_date=report_date,
        generated_at=now,
        account_count=account_count,
        region_count=region_count,
        soc2_impacted_cc_ids=sorted(soc2_ids) or None,
        soc2_impacted_finding_count=soc2_impacted_finding_count if soc2_impacted_finding_count else None,
    )

    return BaselineReportData(
        summary=summary,
        top_risks=top_risks,
        recommendations=recommendations,
        next_actions=next_actions,
        change_delta=change_delta,
        confidence_gaps=confidence_gaps,
        closure_proof=closure_proof,
        tenant_name=tenant_name,
        appendix_findings=None,
    )
