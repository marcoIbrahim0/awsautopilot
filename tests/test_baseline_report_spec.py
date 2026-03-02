"""
Unit tests for baseline report content and format specification (Step 13.1).

Covers: constants, Pydantic models (Summary, TopRiskItem, RecommendationItem,
BaselineReportData), severity_sort_key, build_narrative, JSON serialization.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from backend.services.baseline_report_spec import (
    APPENDIX_FINDINGS_MAX,
    CLOSURE_PROOF_MAX,
    CONFIDENCE_GAPS_MAX,
    NEXT_ACTIONS_MAX,
    RECOMMENDATIONS_MAX,
    SEVERITY_ORDER,
    TOP_RISKS_FIELDS,
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


def test_constants() -> None:
    """Constants match spec: top risks max 20, recommendations max 10, severity order."""
    assert TOP_RISKS_MAX == 20
    assert RECOMMENDATIONS_MAX == 10
    assert APPENDIX_FINDINGS_MAX == 100
    assert NEXT_ACTIONS_MAX == 3
    assert CONFIDENCE_GAPS_MAX == 8
    assert CLOSURE_PROOF_MAX == 10
    assert SEVERITY_ORDER == (
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "INFORMATIONAL",
    )
    assert "title" in TOP_RISKS_FIELDS
    assert "severity" in TOP_RISKS_FIELDS
    assert "business_impact" in TOP_RISKS_FIELDS
    assert "recommended_mode" in TOP_RISKS_FIELDS
    assert "link_to_app" in TOP_RISKS_FIELDS


def test_top_risks_fields_order() -> None:
    """TOP_RISKS_FIELDS matches spec Section 4.2 field list."""
    assert TOP_RISKS_FIELDS == (
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


def test_severity_sort_key() -> None:
    """severity_sort_key: CRITICAL=0, HIGH=1, ... INFORMATIONAL=4; unknown=5."""
    assert severity_sort_key("CRITICAL") == 0
    assert severity_sort_key("HIGH") == 1
    assert severity_sort_key("MEDIUM") == 2
    assert severity_sort_key("LOW") == 3
    assert severity_sort_key("INFORMATIONAL") == 4
    assert severity_sort_key("unknown") == 5
    assert severity_sort_key("") == 5
    assert severity_sort_key("critical") == 0  # case normalized


def test_build_narrative() -> None:
    """build_narrative uses provided counts and report_date."""
    d = date(2026, 2, 3)
    out = build_narrative(total=142, critical=2, high=8, report_date=d)
    assert "2026-02-03" in out
    assert "142" in out
    assert "2 critical" in out
    assert "8 high" in out
    assert "Recommended next steps" in out


def test_baseline_summary_valid() -> None:
    """BaselineSummary accepts valid counts and narrative."""
    s = BaselineSummary(
        total_finding_count=100,
        critical_count=2,
        high_count=8,
        medium_count=40,
        low_count=35,
        informational_count=15,
        open_count=90,
        resolved_count=10,
        narrative="This baseline reflects your AWS security posture.",
        report_date=date(2026, 2, 3),
        generated_at=datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc),
        account_count=3,
        region_count=5,
    )
    assert s.total_finding_count == 100
    assert s.critical_count == 2
    assert s.narrative == "This baseline reflects your AWS security posture."
    assert s.account_count == 3
    assert s.region_count == 5


def test_baseline_summary_negative_count_rejected() -> None:
    """BaselineSummary rejects negative counts."""
    with pytest.raises(ValidationError) as exc_info:
        BaselineSummary(
            total_finding_count=-1,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            informational_count=0,
            open_count=0,
            resolved_count=0,
            narrative="x",
            report_date=date(2026, 2, 3),
            generated_at=datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc),
        )
    assert "total_finding_count" in str(exc_info.value) or "greater_than_equal" in str(exc_info.value)


def test_top_risk_item_valid() -> None:
    """TopRiskItem accepts required fields and optional recommendation_text, link_to_app."""
    item = TopRiskItem(
        title="S3 bucket public access",
        severity="CRITICAL",
        account_id="123456789012",
        status="open",
        resource_id="arn:aws:s3:::my-bucket",
        control_id="S3.1",
        region="us-east-1",
        recommendation_text="Enable S3 block public access.",
        link_to_app="https://app.example.com/actions/abc",
    )
    assert item.title == "S3 bucket public access"
    assert item.severity == "CRITICAL"
    assert item.recommendation_text == "Enable S3 block public access."
    assert item.link_to_app == "https://app.example.com/actions/abc"


def test_top_risk_item_invalid_severity_rejected() -> None:
    """TopRiskItem rejects severity not in CRITICAL/HIGH/MEDIUM/LOW/INFORMATIONAL."""
    with pytest.raises(ValidationError):
        TopRiskItem(
            title="x",
            severity="UNKNOWN",
            account_id="123456789012",
            status="open",
        )


def test_recommendation_item_valid() -> None:
    """RecommendationItem accepts text and optional control_id."""
    r = RecommendationItem(text="Enable Security Hub in all regions.", control_id="SecurityHub.1")
    assert r.text == "Enable Security Hub in all regions."
    assert r.control_id == "SecurityHub.1"


def test_recommendation_item_empty_text_rejected() -> None:
    """RecommendationItem rejects empty text."""
    with pytest.raises(ValidationError):
        RecommendationItem(text="", control_id=None)


def test_next_action_item_valid() -> None:
    item = NextActionItem(
        action_id="5d4b7904-1b14-4fd1-b538-f3dfc2d10210",
        title="Restrict SG public ports",
        control_id="EC2.53",
        severity="HIGH",
        account_id="123456789012",
        region="us-east-1",
        action_status="open",
        why_now="High risk remains open.",
        recommended_mode="pr_only",
        blast_radius="Affects 2 linked findings.",
        fix_path="Generate PR bundle and merge.",
        owner=None,
        due_by=date(2026, 2, 10),
        readiness="ready",
        cta_label="Open PR bundle",
        cta_href="/actions/5d4b7904-1b14-4fd1-b538-f3dfc2d10210",
    )
    assert item.severity == "HIGH"
    assert item.recommended_mode == "pr_only"


def test_change_delta_valid() -> None:
    delta = ChangeDelta(
        compared_to_report_at=datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc),
        new_open_count=4,
        regressed_count=1,
        stale_open_count=6,
        closed_count=3,
        summary="Since 2026-02-02: 4 new open.",
    )
    assert delta.new_open_count == 4
    assert delta.closed_count == 3


def test_confidence_gap_item_valid() -> None:
    gap = ConfidenceGapItem(
        category="access_denied",
        count=5,
        detail="ReadRole scope is incomplete.",
        affected_control_ids=["S3.1", "CloudTrail.1"],
    )
    assert gap.category == "access_denied"
    assert gap.count == 5


def test_closure_proof_item_valid() -> None:
    item = ClosureProofItem(
        finding_id="arn:aws:securityhub:...",
        title="GuardDuty disabled",
        control_id="GuardDuty.1",
        account_id="123456789012",
        region="us-east-1",
        resolved_at=datetime(2026, 2, 3, 13, 0, 0, tzinfo=timezone.utc),
        action_id="a6202c7b-31f5-4f68-8e38-1ecf9f373cb7",
        remediation_run_id="1618eca4-e845-4bcf-9d4a-a958fceda2c0",
        evidence_note="Remediation run succeeded.",
    )
    assert item.finding_id
    assert item.evidence_note


def test_baseline_report_data_valid() -> None:
    """BaselineReportData accepts summary, top_risks, recommendations; optional tenant_name, appendix."""
    summary = BaselineSummary(
        total_finding_count=10,
        critical_count=0,
        high_count=1,
        medium_count=5,
        low_count=3,
        informational_count=1,
        open_count=9,
        resolved_count=1,
        narrative="Test narrative.",
        report_date=date(2026, 2, 3),
        generated_at=datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc),
    )
    top_risks = [
        TopRiskItem(
            title="GuardDuty not enabled",
            severity="HIGH",
            account_id="123456789012",
            status="open",
        ),
    ]
    recommendations = [
        RecommendationItem(text="Enable GuardDuty in us-east-1.", control_id="GuardDuty.1"),
    ]
    data = BaselineReportData(
        summary=summary,
        top_risks=top_risks,
        recommendations=recommendations,
        next_actions=[],
        confidence_gaps=[],
        closure_proof=[],
        tenant_name="Acme Corp",
        appendix_findings=None,
    )
    assert data.summary.total_finding_count == 10
    assert len(data.top_risks) == 1
    assert data.top_risks[0].title == "GuardDuty not enabled"
    assert len(data.recommendations) == 1
    assert data.tenant_name == "Acme Corp"
    assert data.appendix_findings is None


def test_baseline_report_data_json_serialization() -> None:
    """BaselineReportData is JSON-serializable via model_dump for templates/API."""
    summary = BaselineSummary(
        total_finding_count=5,
        critical_count=0,
        high_count=0,
        medium_count=3,
        low_count=2,
        informational_count=0,
        open_count=5,
        resolved_count=0,
        narrative="Short narrative.",
        report_date=date(2026, 2, 3),
        generated_at=datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc),
    )
    data = BaselineReportData(
        summary=summary,
        top_risks=[],
        recommendations=[],
        next_actions=[],
        confidence_gaps=[],
        closure_proof=[],
    )
    dumped = data.model_dump()
    assert "summary" in dumped
    assert dumped["summary"]["total_finding_count"] == 5
    assert dumped["summary"]["narrative"] == "Short narrative."
    assert dumped["top_risks"] == []
    assert dumped["recommendations"] == []
    # For JSON/API use model_dump(mode='json') to get ISO date/datetime strings
    json_dumped = data.model_dump(mode="json")
    assert json_dumped["summary"]["report_date"] == "2026-02-03"
    assert "T" in str(json_dumped["summary"]["generated_at"])  # ISO datetime


def test_baseline_report_data_top_risks_max_length_enforced() -> None:
    """BaselineReportData rejects more than TOP_RISKS_MAX top_risks."""
    summary = BaselineSummary(
        total_finding_count=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        informational_count=0,
        open_count=0,
        resolved_count=0,
        narrative="x",
        report_date=date(2026, 2, 3),
        generated_at=datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc),
    )
    item = TopRiskItem(
        title="x",
        severity="LOW",
        account_id="123456789012",
        status="open",
    )
    with pytest.raises(ValidationError):
        BaselineReportData(
            summary=summary,
            top_risks=[item] * (TOP_RISKS_MAX + 1),
            recommendations=[],
            next_actions=[],
            confidence_gaps=[],
            closure_proof=[],
        )


def test_baseline_report_data_next_actions_max_length_enforced() -> None:
    summary = BaselineSummary(
        total_finding_count=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        informational_count=0,
        open_count=0,
        resolved_count=0,
        narrative="x",
        report_date=date(2026, 2, 3),
        generated_at=datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc),
    )
    action = NextActionItem(
        action_id=None,
        title="x",
        control_id=None,
        severity="LOW",
        account_id=None,
        region=None,
        action_status=None,
        why_now="x",
        recommended_mode="pr_only",
        blast_radius="x",
        fix_path="x",
        owner=None,
        due_by=None,
        readiness="ready",
        cta_label="x",
        cta_href=None,
    )
    with pytest.raises(ValidationError):
        BaselineReportData(
            summary=summary,
            top_risks=[],
            recommendations=[],
            next_actions=[action] * (NEXT_ACTIONS_MAX + 1),
            confidence_gaps=[],
            closure_proof=[],
        )
