"""
Baseline report data builder (Step 13.2).

Builds BaselineReportData from tenant findings: summary (counts, narrative),
top_risks (sorted by severity), recommendations (derived from control IDs).
Used by generate_baseline_report service before rendering and upload.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.finding import Finding
from backend.services.baseline_report_spec import (
    RECOMMENDATIONS_MAX,
    SEVERITY_ORDER,
    TOP_RISKS_MAX,
    BaselineReportData,
    BaselineSummary,
    RecommendationItem,
    TopRiskItem,
    build_narrative,
    severity_sort_key,
)

# Finding status: open = NEW, NOTIFIED; resolved = RESOLVED, SUPPRESSED
_OPEN_STATUSES = {"NEW", "NOTIFIED"}
_RESOLVED_STATUSES = {"RESOLVED", "SUPPRESSED"}

# Control ID → recommendation text (one bullet per control family)
_CONTROL_RECOMMENDATIONS: dict[str, str] = {
    "SecurityHub.1": "Enable Security Hub in all configured regions.",
    "GuardDuty.1": "Enable GuardDuty in all regions.",
    "S3.1": "Review S3 public access (block public access at account and bucket level).",
    "CloudTrail.1": "Ensure CloudTrail is enabled in all regions.",
}


def _severity_for_display(label: str) -> Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]:
    """Normalize severity label to spec Literal (UNTRIAGED → MEDIUM)."""
    u = (label or "").upper()
    if u in SEVERITY_ORDER:
        return u  # type: ignore[return-value]
    return "MEDIUM"


def _recommendation_text_for_control(control_id: str | None, region: str | None) -> str | None:
    """Short recommendation line for a finding (e.g. 'Enable GuardDuty in us-east-1')."""
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
    return None


def build_baseline_report_data(
    session: Session,
    tenant_id: str,
    account_ids: list[str] | None = None,
    tenant_name: str | None = None,
) -> BaselineReportData:
    """
    Build BaselineReportData from tenant findings (Step 13.2).

    Loads findings for tenant_id, optionally filtered by account_ids.
    Computes summary (counts by severity, open/resolved, narrative), top_risks
    (sorted by severity then priority, max TOP_RISKS_MAX), and recommendations
    (from control IDs, deduped, max RECOMMENDATIONS_MAX).

    Args:
        session: DB session.
        tenant_id: Tenant UUID (as string for query).
        account_ids: Optional list of account IDs to include; if None, all accounts.
        tenant_name: Optional tenant name for report cover.

    Returns:
        BaselineReportData ready for render and upload.
    """
    tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    q = select(Finding).where(Finding.tenant_id == tid).order_by(Finding.severity_normalized.desc())
    if account_ids:
        q = q.where(Finding.account_id.in_(account_ids))
    findings = list(session.execute(q).scalars().all())

    now = datetime.now(timezone.utc)
    report_date = date(now.year, now.month, now.day)

    total = len(findings)
    by_severity: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        k = _severity_for_display(f.severity_label)
        by_severity[k] = by_severity.get(k, 0) + 1
    open_count = sum(1 for f in findings if (f.status or "").upper() in _OPEN_STATUSES)
    resolved_count = sum(1 for f in findings if (f.status or "").upper() in _RESOLVED_STATUSES)

    account_count: int | None = None
    region_count: int | None = None
    if findings:
        account_count = len({f.account_id for f in findings})
        region_count = len({f.region for f in findings})

    narrative = build_narrative(
        total=total,
        critical=by_severity.get("CRITICAL", 0),
        high=by_severity.get("HIGH", 0),
        report_date=report_date,
    )

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
    )

    # Top risks: sort by severity then severity_normalized desc, take first TOP_RISKS_MAX
    sorted_findings = sorted(
        findings,
        key=lambda f: (severity_sort_key(f.severity_label), -(f.severity_normalized or 0)),
    )
    top_findings = sorted_findings[:TOP_RISKS_MAX]
    top_risks = [
        TopRiskItem(
            title=f.title or "Finding",
            severity=_severity_for_display(f.severity_label),
            account_id=f.account_id,
            status=f.status or "open",
            resource_id=f.resource_id,
            control_id=f.control_id,
            region=f.region,
            recommendation_text=_recommendation_text_for_control(f.control_id, f.region),
            link_to_app=None,
        )
        for f in top_findings
    ]

    # Recommendations: from control IDs in findings, dedupe, take first RECOMMENDATIONS_MAX
    seen_controls: set[str] = set()
    rec_texts: list[tuple[str, str | None]] = []
    for f in findings:
        c = (f.control_id or "").strip()
        if not c or c in seen_controls:
            continue
        text = _CONTROL_RECOMMENDATIONS.get(c)
        if text:
            seen_controls.add(c)
            rec_texts.append((text, c))
    rec_texts = rec_texts[:RECOMMENDATIONS_MAX]
    recommendations = [RecommendationItem(text=t, control_id=c) for t, c in rec_texts]

    return BaselineReportData(
        summary=summary,
        top_risks=top_risks,
        recommendations=recommendations,
        tenant_name=tenant_name,
        appendix_findings=None,
    )
