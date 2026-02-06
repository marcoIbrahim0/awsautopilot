"""
Unit tests for baseline report HTML renderer (Step 13.2).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from backend.services.baseline_report_spec import (
    BaselineReportData,
    BaselineSummary,
    RecommendationItem,
    TopRiskItem,
)
from backend.services.baseline_report_renderer import render_baseline_report_html


def test_render_baseline_report_html_contains_sections() -> None:
    """render_baseline_report_html produces HTML with summary, top risks, recommendations."""
    now = datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc)
    report_date = date(2026, 2, 3)
    summary = BaselineSummary(
        total_finding_count=5,
        critical_count=1,
        high_count=2,
        medium_count=1,
        low_count=1,
        informational_count=0,
        open_count=4,
        resolved_count=1,
        narrative="This baseline reflects your AWS security posture.",
        report_date=report_date,
        generated_at=now,
        account_count=2,
        region_count=3,
    )
    top_risks = [
        TopRiskItem(
            title="S3 bucket public",
            severity="CRITICAL",
            account_id="123456789012",
            status="open",
            resource_id="arn:aws:s3:::x",
            control_id="S3.1",
            region="us-east-1",
            recommendation_text="Enable S3 block public access.",
            link_to_app=None,
        ),
    ]
    recommendations = [
        RecommendationItem(text="Enable Security Hub in all configured regions.", control_id="SecurityHub.1"),
    ]
    data = BaselineReportData(
        summary=summary,
        top_risks=top_risks,
        recommendations=recommendations,
        tenant_name="Acme Corp",
        appendix_findings=None,
    )
    html = render_baseline_report_html(data)
    assert "Acme Corp" in html
    assert "Baseline Security Report" in html
    assert "Executive summary" in html or "1. Executive summary" in html
    assert "Total findings:" in html and " 5</p>" in html
    assert "Top risks" in html or "2. Top risks" in html
    assert "S3 bucket public" in html
    assert "Recommendations" in html or "3. Recommendations" in html
    assert "Enable Security Hub" in html
    assert "<!DOCTYPE html>" in html
    assert "2026-02-03" in html


def test_render_baseline_report_html_escapes_content() -> None:
    """render_baseline_report_html escapes HTML in content."""
    now = datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc)
    summary = BaselineSummary(
        total_finding_count=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        informational_count=0,
        open_count=0,
        resolved_count=0,
        narrative="Test <script>alert(1)</script>",
        report_date=date(2026, 2, 3),
        generated_at=now,
    )
    data = BaselineReportData(
        summary=summary,
        top_risks=[],
        recommendations=[],
        tenant_name=None,
        appendix_findings=None,
    )
    html = render_baseline_report_html(data)
    assert "&lt;script&gt;" in html
    assert "<script>" not in html or "&lt;" in html
