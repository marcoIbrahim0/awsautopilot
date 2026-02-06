"""
Baseline report content and format specification (Step 13.1).

Defines the data schema and constants for the 48h baseline report:
executive summary, top risks, recommendations. Single source of truth
for the report structure so the generator (Step 13.2) and templates
produce a consistent deliverable. See docs/baseline-report-spec.md.
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
    "link_to_app",
)

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


class TopRiskItem(BaseModel):
    """One item in Top risks. Section 2. Fields match spec Section 4.2."""

    title: str = Field(..., min_length=1)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"] = Field(...)
    account_id: str = Field(..., min_length=1, max_length=12)
    status: str = Field(..., min_length=1)
    resource_id: str | None = Field(None)
    control_id: str | None = Field(None)
    region: str | None = Field(None)
    recommendation_text: str | None = Field(None)
    link_to_app: str | None = Field(None, description="View in app URL (post-sign-up)")


class RecommendationItem(BaseModel):
    """One recommendation bullet. Section 3. Fields match spec Section 5.2."""

    text: str = Field(..., min_length=1)
    control_id: str | None = Field(None)


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
