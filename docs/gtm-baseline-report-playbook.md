# GTM Playbook: 48h Baseline Report (Lead Magnet)

This playbook documents the end-to-end lead-magnet flow for the **48h baseline report** so sales and marketing can use it consistently in Alpha (and beyond). It aligns with **Step 13** of the implementation plan and the **Alpha → Beta → GA** motion: *connect read-only → ingest → report → propose onboarding*.

---

## 1. Lead-magnet flow (numbered steps)

1. **Prospect signs up (or is invited)** and lands in the app.
2. **Prospect connects a read-only AWS account**  
   - CloudFormation ReadRole + ExternalId.  
   - **No WriteRole required** for the baseline report.
3. **Ingestion runs**  
   - App (or manual trigger) runs ingestion for the connected account(s). Findings (and optionally actions) are stored.
4. **Prospect requests the report**  
   - In the app: **Settings → Baseline report** → “Request baseline report.”  
   - Report job is enqueued; prospect sees “Queued” / “Generating…” and can leave.  
   - Rate limit: one report per tenant per 24 hours (API returns 429 if exceeded).
5. **Within 48 hours: report ready**  
   - Report is generated and stored (HTML; PDF can be added later).  
   - Prospect receives email (if enabled): “Your baseline report is ready” with a download link.  
   - They can also open **Settings → Baseline report** and use “Download report” or the “Recent reports” list.
6. **Prospect reviews the report**  
   - Summary, top risks, and recommendations.  
   - Use this as the conversation starter for value and next steps.
7. **Sales/CS follow-up**  
   - “Here’s your baseline; we recommend an onboarding sprint to address the top risks, then monthly autopilot.”  
   - Propose paid onboarding or subscription (Beta/GA).

---

## 2. Copy suggestions

Use these in landing pages, emails, and in-app:

- **Headline:** “Get your free 48h security baseline”
- **Subhead:** “Connect read-only, we analyze your AWS security posture and send a one-off report within 48 hours.”
- **CTA:** “Request baseline report” / “Get my baseline report”
- **Post-request (in-app):** “Your report will be ready within 48 hours. We’ll email you when it’s ready.”
- **Rate limit (429):** “You can request one report per 24 hours. Try again later or use the download link from your last report.”

---

## 3. Qualification criteria (for CRM / lead scoring)

Consider a prospect **qualified for follow-up** when:

- They have **at least one connected AWS account** (read-only).
- They have **requested at least one baseline report** (shows intent).
- Optional: They have **downloaded** the report (opens the presigned link).

Use these signals in your CRM or marketing automation to prioritize “report requested” or “report downloaded” leads for sales outreach.

---

## 4. Where this is documented

- **Implementation plan:** Step 13 (48h Baseline Report), including 13.4 (Frontend) and 13.5 (GTM playbook).
- **Alpha motion:** Section “Implementation starter” / “Alpha → Beta → GA”: use 48h baseline report as lead magnet: *connect → ingest → report → propose onboarding*.
- **This doc:** `docs/gtm-baseline-report-playbook.md` — one-pager for sales/marketing with flow, copy, and qualification criteria.

---

## 5. Technical reference (for support/ops)

| Item | Detail |
|------|--------|
| **SLA** | Report ready within 48 hours under normal load; worker processes queue continuously. |
| **Rate limit** | One report per tenant per 24 hours (429 + `Retry-After`). |
| **Delivery** | HTML report in S3; presigned download URL (e.g. 1 hour expiry). Optional email when ready. |
| **UI** | **Settings → Baseline report**: request, status, download, recent reports list. |
| **API** | `POST /api/baseline-report`, `GET /api/baseline-report`, `GET /api/baseline-report/{id}`. |

---

*Last updated: 2026-02-03 (Step 13.4 UI and GTM playbook).*
