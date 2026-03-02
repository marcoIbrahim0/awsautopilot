# Baseline Security Report — Content and Format Specification

**Version:** 1.1  
**Step:** Implementation Plan 13.1 — Report content and format  
**Purpose:** Single source of truth for the 48h baseline report structure so the generator (Step 13.2) and templates produce a consistent, professional deliverable. This report is the Alpha lead magnet: prospects connect read-only → ingest → request report → receive within 48 hours → propose onboarding.

---

## 1. Audience and use

- **Primary audience:** Prospects who have connected a read-only AWS account and requested a one-off baseline report (no WriteRole or remediation required).
- **Use:** Informational only. Summarizes findings and top risks; supports the GTM motion from “connect” to “propose onboarding.”
- **Outputs:** PDF (primary, for sharing and “report” feel), HTML (optional, in-app preview or email snippet), JSON (optional, for API or power users).

---

## 2. Report sections

The report has four sections. Sections 1–3 are mandatory; Section 4 (Appendix) is optional.

| Section | Title | Content | Placement |
|--------|--------|--------|------------|
| 1 | Executive summary | Totals, severity breakdown, open vs resolved, optional account/region breakdown, one-paragraph narrative | Page 1 (or first screen) |
| 2 | Top risks | Top 10–20 findings or aggregated actions, ordered by severity then priority | Section 2 |
| 3 | Recommendations | 5–10 bullet recommendations derived from the scan | Section 3 |
| 4 | Appendix (optional) | Full finding list (truncated, e.g. first 100) or “Available in app after sign-up” | End of report |

### 2.1 Decision-oriented extensions (v1.1)

To make the report operational (not just informational), the in-app payload and HTML renderer also include:

- **Next actions (top 3):** concrete “what to do now” items with severity, readiness, recommended mode (`direct_fix` / `pr_only`), blast radius, and fix path.
- **Change delta:** counts vs the previous successful baseline (`new_open`, `regressed`, `stale_open`, `closed`) plus narrative summary.
- **Confidence gaps:** explicit signal-quality caveats (`access_denied`, `partial_data`, `api_error`, `telemetry_gap`) and affected controls.
- **Closure proof:** recently resolved findings with timestamps and evidence notes (including remediation-run linkage when available).

---

## 3. Section 1 — Executive summary

### 3.1 Content

- **Total finding count:** Integer (all findings in scope).
- **Counts by severity:** For each of: Critical, High, Medium, Low, Informational. Use same severity labels as Security Hub / `Finding.severity_label` (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL).
- **Open vs resolved:** Count of findings (or actions) in open/workflow status vs resolved/suppressed. Definition of “open”: status in `NEW`, `NOTIFIED` for findings; `open`, `in_progress` for actions. “Resolved”: `RESOLVED`, `SUPPRESSED` for findings; `resolved`, `suppressed` for actions.
- **Optional breakdown:** By account (e.g. “3 accounts”) and/or by region (e.g. “5 regions”). Useful for multi-account/region prospects.
- **One-paragraph narrative:** Single paragraph, e.g.  
  *“This baseline reflects your AWS security posture as of [report date]. Total findings: [N]. Top priorities: [N] critical, [N] high. Recommended next steps are listed below.”*  
  Narrative must be generated from the summary data (no hardcoded counts).

### 3.2 Field list (data contract)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `total_finding_count` | integer | Yes | Total findings in scope |
| `critical_count` | integer | Yes | Findings with severity CRITICAL |
| `high_count` | integer | Yes | Findings with severity HIGH |
| `medium_count` | integer | Yes | Findings with severity MEDIUM |
| `low_count` | integer | Yes | Findings with severity LOW |
| `informational_count` | integer | Yes | Findings with severity INFORMATIONAL |
| `open_count` | integer | Yes | Open/workflow findings (or actions) |
| `resolved_count` | integer | Yes | Resolved/suppressed findings (or actions) |
| `account_count` | integer | No | Number of accounts in scope |
| `region_count` | integer | No | Number of regions in scope |
| `narrative` | string | Yes | One-paragraph executive summary text |
| `report_date` | string (ISO 8601 date) | Yes | Date the report was generated |
| `generated_at` | string (ISO 8601 datetime) | Yes | Timestamp when report was built |

---

## 4. Section 2 — Top risks

### 4.1 Content

- **Source:** Findings and/or aggregated actions. Prefer actions when available (deduplicated); otherwise findings.
- **Ordering:** By severity (Critical first, then High, Medium, Low, Informational), then by priority/exploitability (e.g. `Action.priority` or finding `severity_normalized`).
- **Count:** Top 10–20 items. Upper bound configurable (default 20) to keep the report scannable.
- **Per item:** Title, resource identifier, control ID, severity, account ID, region, status. Optional: short recommendation line (e.g. “Enable GuardDuty in us-east-1”); optional “View in app” link (URL to app with tenant/finding context for post-sign-up use).

### 4.2 Field list (per top-risk item)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Finding or action title |
| `resource_id` | string | No | AWS resource identifier (e.g. ARN or ID) |
| `control_id` | string | No | Security Hub / CIS control ID (e.g. S3.1, GuardDuty.1) |
| `severity` | string | Yes | CRITICAL \| HIGH \| MEDIUM \| LOW \| INFORMATIONAL |
| `account_id` | string | Yes | AWS account ID (12 digits) |
| `region` | string | No | AWS region (e.g. us-east-1); null for account-level |
| `status` | string | Yes | open \| resolved \| in_progress \| suppressed (or finding workflow status) |
| `recommendation_text` | string | No | Short recommendation (e.g. “Enable GuardDuty in us-east-1”) |
| `link_to_app` | string (URL) | No | “View in app” link (for post-sign-up) |

### 4.3 Severity order (for sorting)

Use this order for “Top risks” and narrative: **CRITICAL** → **HIGH** → **MEDIUM** → **LOW** → **INFORMATIONAL**.

---

## 5. Section 3 — Recommendations

### 5.1 Content

- **Source:** Derived from the scan: control IDs, action types, or finding patterns. Examples:
  - “Enable Security Hub in all configured regions.”
  - “Review S3 public access (N buckets with public read).”
  - “Enable GuardDuty in N regions.”
  - “Restrict SSH/RDP (N security groups).”
- **Count:** 5–10 bullets. Upper bound configurable (default 10).
- **Tie to controls:** Where useful, recommendations can reference control_id or action type for auditor/engineer clarity.

### 5.2 Field list (per recommendation)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Recommendation text (one bullet) |
| `control_id` | string | No | Related control ID (e.g. S3.1, GuardDuty.1) |

---

## 6. Section 4 — Appendix (optional)

- **Option A:** Full finding list with same fields as Top risks (Section 2), truncated to first 100 rows, with note “First 100 findings. Full list available in app after sign-up.”
- **Option B:** No appendix; single line: “Full finding list and ongoing monitoring available in app after sign-up.”

Implementations may choose Option A or B; the schema supports an optional `appendix_findings` list (same shape as top_risks, max 100).

---

## 7. Format and layout

### 7.1 PDF (primary)

- **Purpose:** Preferred for “report” feel and sharing with stakeholders.
- **Structure:**  
  - Cover page: logo (optional), title “Baseline Security Report,” tenant name, report date.  
  - Table of contents: optional.  
  - Section 1: Executive summary (totals, narrative).  
  - Section 2: Top risks (table or list with columns per field list).  
  - Section 3: Recommendations (bulleted list).  
  - Section 4 (if present): Appendix table or note.
- **Style:** Font and spacing consistent with product brand; professional, readable. Use a template engine (e.g. WeasyPrint, ReportLab, or headless Chrome/Puppeteer) fed by the same structured data as below.

### 7.2 HTML (optional)

- Same sections as PDF; useful for in-app preview or email “View report” link.
- Semantic structure: `<section>` per report section; tables/lists for top risks and recommendations. Styling can mirror PDF or use a minimal CSS set.

### 7.3 JSON (optional)

- For API or power users. Single JSON object with keys:
  - `summary`: object matching Section 3 field list.
  - `top_risks`: array of objects matching Section 4.2 field list.
  - `recommendations`: array of objects matching Section 5.2 field list.
  - `report_date`, `generated_at`, `tenant_name` (optional).
  - `appendix_findings` (optional): array, same shape as top_risks, max 100.

No layout; consumers render as needed.

---

## 8. Data schema (code contract)

The generator (Step 13.2) must produce a **BaselineReportData** structure that matches this contract so templates (PDF/HTML) and JSON export stay consistent.

- **Summary:** Object with fields from Section 3.2 (counts, narrative, report_date, generated_at).
- **Top risks:** Array of objects with fields from Section 4.2; length ≤ 20 (configurable).
- **Recommendations:** Array of objects with fields from Section 5.2; length ≤ 10 (configurable).
- **Next actions:** Array of up to 3 decision-ready actions (`next_actions`).
- **Change delta:** Optional object (`change_delta`) comparing the current report to the previous successful report.
- **Confidence gaps:** Array (`confidence_gaps`) describing certainty limits and impacted controls.
- **Closure proof:** Array (`closure_proof`) for recently closed findings and evidence notes.
- **Metadata:** `report_date`, `generated_at`, `tenant_name` (optional).

See `backend/services/baseline_report_spec.py` for Pydantic models and constants (TOP_RISKS_MAX, RECOMMENDATIONS_MAX, severity order, field names).

---

## 9. Sample layout (outline)

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo]   Baseline Security Report                          │
│           Tenant: Acme Corp   Report date: 2026-02-03        │
└─────────────────────────────────────────────────────────────┘

1. Executive summary
   • Total findings: 142
   • By severity: Critical 2, High 8, Medium 45, Low 62, Informational 25
   • Open: 120   Resolved: 22
   • Scope: 3 accounts, 5 regions

   This baseline reflects your AWS security posture as of 2026-02-03.
   Total findings: 142. Top priorities: 2 critical, 8 high. Recommended
   next steps are listed below.

2. Top risks
   | # | Title                    | Resource     | Control   | Severity | Account     | Region    | Status |
   |---|--------------------------|--------------|-----------|----------|-------------|-----------|--------|
   | 1 | S3 bucket public access | arn:aws:...  | S3.1      | CRITICAL | 123456789012| us-east-1 | open   |
   ...

3. Recommendations
   • Enable Security Hub in all configured regions.
   • Review S3 public access (12 buckets with public read).
   • Enable GuardDuty in 3 regions.
   ...

4. Appendix (optional)
   Full finding list (first 100) — or: “Full list available in app after sign-up.”
```

---

## 10. Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.1 | 2026-03-02 | Added decision-oriented sections: next_actions, change_delta, confidence_gaps, closure_proof; updated data contract for actionable baseline reports. |
| 1.0 | 2026-02-03 | Initial spec: sections 1–4, field lists, format/layout, sample outline, code contract reference. |
