"""
Baseline report content and format specification (Step 13.1).

Defines the data schema and constants for the 48h baseline report:
summary, top risks, decision-ready next actions, trend deltas, confidence
gaps, closure proof, and recommendations. Single source of truth for the
report structure so the generator and templates produce a consistent
deliverable. See docs/baseline-report-spec.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants (align with docs/baseline-report-spec.md)
# ---------------------------------------------------------------------------

TOP_RISKS_MAX = 20
RECOMMENDATIONS_MAX = 10
APPENDIX_FINDINGS_MAX = 100
NEXT_ACTIONS_MAX = 3
CONFIDENCE_GAPS_MAX = 8
CLOSURE_PROOF_MAX = 10

# Severity order for sorting: Critical first, then High, Medium, Low, Informational
SEVERITY_ORDER: tuple[str, ...] = (
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
    "INFORMATIONAL",
)

# Field names for top_risks (for templates and CSV/JSON export)
TOP_RISKS_FIELDS: tuple[str, ...] = (
    "title",
    "resource_id",
    "control_id",
    "severity",
    "account_id",
    "region",
    "status",
    "recommendation_text",
    "business_impact",
    "action_id",
    "action_status",
    "action_type",
    "recommended_mode",
    "remediation_readiness",
    "why_now",
    "link_to_app",
)

SeverityLiteral = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]
RecommendedModeLiteral = Literal["pr_only", "exception_review"]
ConfidenceGapCategoryLiteral = Literal["access_denied", "partial_data", "api_error", "telemetry_gap"]

# ---------------------------------------------------------------------------
# Pydantic models (data contract for generator and templates)
# ---------------------------------------------------------------------------


class BaselineSummary(BaseModel):
    """Executive summary: counts, narrative, report date. Section 1."""

    total_finding_count: int = Field(..., ge=0, description="Total findings in scope")
    critical_count: int = Field(..., ge=0)
    high_count: int = Field(..., ge=0)
    medium_count: int = Field(..., ge=0)
    low_count: int = Field(..., ge=0)
    informational_count: int = Field(..., ge=0)
    open_count: int = Field(..., ge=0, description="Open/workflow findings or actions")
    resolved_count: int = Field(..., ge=0, description="Resolved/suppressed")
    narrative: str = Field(..., min_length=1, description="One-paragraph executive summary")
    report_date: date = Field(..., description="Date the report was generated")
    generated_at: datetime = Field(..., description="Timestamp when report was built")
    account_count: int | None = Field(None, ge=0, description="Number of accounts in scope")
    region_count: int | None = Field(None, ge=0, description="Number of regions in scope")
    soc2_impacted_cc_ids: list[str] | None = Field(
        None,
        description="Optional SOC 2 Common Criteria IDs mapped from top risks",
    )
    soc2_impacted_finding_count: int | None = Field(
        None,
        ge=0,
        description="Optional count of top-risk findings mapped to SOC 2 controls",
    )


class TopRiskItem(BaseModel):
    """One item in Top risks. Section 2. Fields match spec Section 4.2."""

    title: str = Field(..., min_length=1)
    severity: SeverityLiteral = Field(...)
    account_id: str = Field(..., min_length=1, max_length=12)
    status: str = Field(..., min_length=1)
    resource_id: str | None = Field(None)
    control_id: str | None = Field(None)
    region: str | None = Field(None)
    recommendation_text: str | None = Field(None)
    business_impact: str | None = Field(None)
    action_id: str | None = Field(None)
    action_status: str | None = Field(None)
    action_type: str | None = Field(None)
    recommended_mode: RecommendedModeLiteral | None = Field(None)
    remediation_readiness: str | None = Field(None)
    why_now: str | None = Field(None)
    soc2_cc_ids: list[str] | None = Field(None)
    link_to_app: str | None = Field(None, description="View in app URL (post-sign-up)")


class RecommendationItem(BaseModel):
    """One recommendation bullet. Section 3. Fields match spec Section 5.2."""

    text: str = Field(..., min_length=1)
    control_id: str | None = Field(None)
    soc2_cc_ids: list[str] | None = Field(None)


class NextActionItem(BaseModel):
    """Top 1-3 next actions prioritized for immediate execution."""

    action_id: str | None = Field(None)
    title: str = Field(..., min_length=1)
    control_id: str | None = Field(None)
    severity: SeverityLiteral = Field(...)
    account_id: str | None = Field(None)
    region: str | None = Field(None)
    action_status: str | None = Field(None)
    why_now: str = Field(..., min_length=1)
    recommended_mode: RecommendedModeLiteral = Field(...)
    blast_radius: str = Field(..., min_length=1)
    fix_path: str = Field(..., min_length=1)
    owner: str | None = Field(None)
    due_by: date | None = Field(None)
    readiness: str = Field(..., min_length=1)
    cta_label: str = Field(..., min_length=1)
    cta_href: str | None = Field(None)


class ChangeDelta(BaseModel):
    """Change counts between the current report and the previous successful report."""

    compared_to_report_at: datetime | None = Field(None)
    new_open_count: int = Field(..., ge=0)
    regressed_count: int = Field(..., ge=0)
    stale_open_count: int = Field(..., ge=0)
    closed_count: int = Field(..., ge=0)
    summary: str = Field(..., min_length=1)


class ConfidenceGapItem(BaseModel):
    """Where certainty is limited due to telemetry/access/runtime signal gaps."""

    category: ConfidenceGapCategoryLiteral = Field(...)
    count: int = Field(..., ge=1)
    detail: str = Field(..., min_length=1)
    affected_control_ids: list[str] | None = Field(None)


class ClosureProofItem(BaseModel):
    """Evidence-oriented entries showing recently closed findings."""

    finding_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    control_id: str | None = Field(None)
    account_id: str | None = Field(None)
    region: str | None = Field(None)
    resolved_at: datetime | None = Field(None)
    action_id: str | None = Field(None)
    remediation_run_id: str | None = Field(None)
    evidence_note: str = Field(..., min_length=1)


class BaselineReportData(BaseModel):
    """
    Full baseline report payload for templates and JSON export.
    Generator (Step 13.2) builds this; PDF/HTML/JSON consume it.
    """

    summary: BaselineSummary = Field(...)
    top_risks: list[TopRiskItem] = Field(
        ...,
        max_length=TOP_RISKS_MAX,
        description=f"Top 10–{TOP_RISKS_MAX} risks by severity then priority",
    )
    recommendations: list[RecommendationItem] = Field(
        ...,
        max_length=RECOMMENDATIONS_MAX,
        description=f"5–{RECOMMENDATIONS_MAX} recommendation bullets",
    )
    next_actions: list[NextActionItem] = Field(
        default_factory=list,
        max_length=NEXT_ACTIONS_MAX,
        description=f"Top {NEXT_ACTIONS_MAX} decision-ready actions to execute now",
    )
    change_delta: ChangeDelta | None = Field(
        None,
        description="Change snapshot versus the previous successful baseline report",
    )
    confidence_gaps: list[ConfidenceGapItem] = Field(
        default_factory=list,
        max_length=CONFIDENCE_GAPS_MAX,
        description="Known signal/telemetry gaps that lower confidence",
    )
    closure_proof: list[ClosureProofItem] = Field(
        default_factory=list,
        max_length=CLOSURE_PROOF_MAX,
        description="Recently closed findings and proof references",
    )
    tenant_name: str | None = Field(None, description="Tenant/organization name for cover")
    appendix_findings: list[TopRiskItem] | None = Field(
        None,
        max_length=APPENDIX_FINDINGS_MAX,
        description="Optional appendix: first N findings (max 100)",
    )


# ---------------------------------------------------------------------------
# Helpers for generator (Step 13.2)
# ---------------------------------------------------------------------------


def severity_sort_key(severity_label: str) -> int:
    """
    Return an integer for sorting by severity (lower = higher priority).
    CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3, INFORMATIONAL=4.
    Unknown labels sort after INFORMATIONAL (5).
    """
    order = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    return order.get((severity_label or "").upper(), len(SEVERITY_ORDER))


def build_narrative(
    total: int,
    critical: int,
    high: int,
    report_date: date,
) -> str:
    """
    Build the one-paragraph executive summary narrative.
    Uses actual counts; no hardcoded values.
    """
    parts = [
        f"This baseline reflects your AWS security posture as of {report_date.isoformat()}.",
        f"Total findings: {total}.",
        f"Top priorities: {critical} critical, {high} high.",
        "Recommended next steps are listed below.",
    ]
    return " ".join(parts)
