"""
Baseline report HTML renderer.

Renders BaselineReportData to downloadable HTML with decision-oriented
sections: summary, next actions, top risks, change delta, confidence gaps,
closure proof, and recommendations.
"""
from __future__ import annotations

import html
from datetime import date, datetime

from backend.services.baseline_report_spec import (
    BaselineReportData,
    BaselineSummary,
    ChangeDelta,
    ClosureProofItem,
    ConfidenceGapItem,
    NextActionItem,
    RecommendationItem,
    TopRiskItem,
)


def _escape(s: str | None) -> str:
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def _format_datetime(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _format_date(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%Y-%m-%d")


def _render_summary(s: BaselineSummary) -> str:
    return f"""
<section class="baseline-summary">
  <h2>1. Executive summary</h2>
  <p><strong>Total findings:</strong> {s.total_finding_count}</p>
  <p><strong>By severity:</strong> Critical {s.critical_count}, High {s.high_count}, Medium {s.medium_count}, Low {s.low_count}, Informational {s.informational_count}</p>
  <p><strong>Open:</strong> {s.open_count} &nbsp; <strong>Resolved:</strong> {s.resolved_count}</p>
  {f'<p><strong>Scope:</strong> {s.account_count} account(s), {s.region_count} region(s)</p>' if s.account_count is not None and s.region_count is not None else ''}
  <p>{_escape(s.narrative)}</p>
  <p><em>Report date: {_format_date(s.report_date)}. Generated: {_format_datetime(s.generated_at)}</em></p>
</section>
"""


def _render_next_actions(items: list[NextActionItem]) -> str:
    if not items:
        return "<section><h2>2. Next actions</h2><p>No immediate actions identified.</p></section>"
    rows = "".join(
        f"""
    <tr>
      <td>{_escape(item.title)}</td>
      <td>{_escape(item.severity)}</td>
      <td>{_escape(item.readiness)}</td>
      <td>{_escape(item.recommended_mode)}</td>
      <td>{_escape(item.why_now)}</td>
      <td>{_escape(item.fix_path)}</td>
      <td>{_escape(_format_date(item.due_by))}</td>
    </tr>"""
        for item in items
    )
    return f"""
<section class="baseline-next-actions">
  <h2>2. Next actions</h2>
  <table>
    <thead>
      <tr>
        <th>Action</th>
        <th>Severity</th>
        <th>Readiness</th>
        <th>Mode</th>
        <th>Why now</th>
        <th>Fix path</th>
        <th>Due by</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</section>
"""


def _render_top_risks(items: list[TopRiskItem]) -> str:
    if not items:
        return "<section><h2>3. Top risks</h2><p>No findings in scope.</p></section>"
    rows = "".join(
        f"""
    <tr>
      <td>{_escape(item.title)}</td>
      <td>{_escape(item.severity)}</td>
      <td>{_escape(item.account_id)}</td>
      <td>{_escape(item.region)}</td>
      <td>{_escape(item.status)}</td>
      <td>{_escape(item.business_impact)}</td>
      <td>{_escape(item.recommended_mode)}</td>
      <td>{_escape(item.remediation_readiness)}</td>
    </tr>"""
        for item in items
    )
    return f"""
<section class="baseline-top-risks">
  <h2>3. Top risks</h2>
  <table>
    <thead>
      <tr>
        <th>Title</th>
        <th>Severity</th>
        <th>Account</th>
        <th>Region</th>
        <th>Status</th>
        <th>Business impact</th>
        <th>Mode</th>
        <th>Readiness</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</section>
"""


def _render_change_delta(change: ChangeDelta | None) -> str:
    if not change:
        return "<section><h2>4. Change since last baseline</h2><p>No comparison baseline available.</p></section>"
    compared = _format_datetime(change.compared_to_report_at) if change.compared_to_report_at else "N/A"
    return f"""
<section class="baseline-delta">
  <h2>4. Change since last baseline</h2>
  <p><strong>Compared to:</strong> {compared}</p>
  <p><strong>New open:</strong> {change.new_open_count} &nbsp; <strong>Regressed:</strong> {change.regressed_count}</p>
  <p><strong>Stale open:</strong> {change.stale_open_count} &nbsp; <strong>Closed:</strong> {change.closed_count}</p>
  <p>{_escape(change.summary)}</p>
</section>
"""


def _render_confidence_gaps(items: list[ConfidenceGapItem]) -> str:
    if not items:
        return "<section><h2>5. Confidence gaps</h2><p>No confidence gaps detected in this snapshot.</p></section>"
    rows = "".join(
        f"""
    <tr>
      <td>{_escape(item.category)}</td>
      <td>{item.count}</td>
      <td>{_escape(item.detail)}</td>
      <td>{_escape(', '.join(item.affected_control_ids or []))}</td>
    </tr>"""
        for item in items
    )
    return f"""
<section class="baseline-confidence-gaps">
  <h2>5. Confidence gaps</h2>
  <table>
    <thead>
      <tr>
        <th>Category</th>
        <th>Count</th>
        <th>Detail</th>
        <th>Affected controls</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</section>
"""


def _render_closure_proof(items: list[ClosureProofItem]) -> str:
    if not items:
        return "<section><h2>6. Closure proof</h2><p>No recently closed findings.</p></section>"
    rows = "".join(
        f"""
    <tr>
      <td>{_escape(item.finding_id)}</td>
      <td>{_escape(item.title)}</td>
      <td>{_escape(item.control_id)}</td>
      <td>{_escape(item.account_id)}</td>
      <td>{_escape(item.region)}</td>
      <td>{_escape(_format_datetime(item.resolved_at))}</td>
      <td>{_escape(item.evidence_note)}</td>
    </tr>"""
        for item in items
    )
    return f"""
<section class="baseline-closure-proof">
  <h2>6. Closure proof</h2>
  <table>
    <thead>
      <tr>
        <th>Finding ID</th>
        <th>Title</th>
        <th>Control</th>
        <th>Account</th>
        <th>Region</th>
        <th>Resolved at</th>
        <th>Evidence</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</section>
"""


def _render_recommendations(items: list[RecommendationItem]) -> str:
    if not items:
        return "<section><h2>7. Recommendations</h2><p>No recommendations.</p></section>"
    bullets = "".join(f"  <li>{_escape(item.text)}</li>\n" for item in items)
    return f"""
<section class="baseline-recommendations">
  <h2>7. Recommendations</h2>
  <ul>
{bullets}
  </ul>
</section>
"""


def render_baseline_report_html(data: BaselineReportData) -> str:
    """Render BaselineReportData to a self-contained HTML document."""
    title = "Baseline Security Report"
    if data.tenant_name:
        title = f"{_escape(data.tenant_name)} - Baseline Security Report"

    head = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 980px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
    h1 {{ font-size: 1.6rem; border-bottom: 1px solid #ccc; padding-bottom: 0.5rem; }}
    h2 {{ font-size: 1.1rem; margin-top: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.88rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.4rem 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    ul {{ padding-left: 1.35rem; }}
    section {{ margin-bottom: 1.6rem; }}
    .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  </style>
</head>
<body>
  <header>
    <h1>{_escape(title)}</h1>
    <p class="meta">Report date: {_format_date(data.summary.report_date)}. Generated: {_format_datetime(data.summary.generated_at)}.</p>
  </header>
"""

    sections = "".join(
        [
            _render_summary(data.summary),
            _render_next_actions(data.next_actions),
            _render_top_risks(data.top_risks),
            _render_change_delta(data.change_delta),
            _render_confidence_gaps(data.confidence_gaps),
            _render_closure_proof(data.closure_proof),
            _render_recommendations(data.recommendations),
        ]
    )

    tail = """
  <footer style="margin-top: 2rem; font-size: 0.85rem; color: #666;">
    <p>Generated by AWS Security Autopilot. This is a point-in-time baseline; use the app for continuous monitoring and remediation workflows.</p>
  </footer>
</body>
</html>
"""
    return head + sections + tail

