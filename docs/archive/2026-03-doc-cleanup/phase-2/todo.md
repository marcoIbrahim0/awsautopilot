# Phase 2 To-Do List

> **Dev environment**
> - Frontend: `npm run dev` in `frontend/` → `http://localhost:3000`
> - Public URL: **https://dev.ocypheris.com**
> - Tunnel: `cloudflared tunnel --config /Users/marcomaher/.cloudflared/config.yml run 71b14aef-c5f7-4a83-bd93-9c04b4f025f4`
> - Login: `maromaher54@gmail.com` / `Maher730`


- [x] **UI/UX: Findings Experience Redesign** — _[spec](ui-ux-design-pending.md)_

  ### Phase A — Backend (Data Layer)
  - [x] **A1** · Confirm `ONLY_IN_SCOPE_CONTROLS` flag is ON in production config (§2 — Server-Side Filtering)
  - [x] **A2** · Add `GET /findings/grouped` endpoint — groups by `(control_id, resource_type)`, returns `severity_distribution`, `finding_count`, `account_ids`, `regions`, `remediation_action_id` per group (§3.2, §8)
  - [x] **A3** · Add `is_shared_resource: bool` field to `FindingResponse` — flag findings whose `resource_id` appears across multiple scope boundaries (§6)

  ### Phase B — Core Grouped UI
  - [x] **B1** · Create `FindingGroupCard.tsx` — severity distribution pills, rule title, `N findings across M resources`, account/region context, `Generate PR` primary button (§3.2)
  - [x] **B2** · Add expand/collapse on `FindingGroupCard` to reveal individual `FindingCard` rows (ARN, detection time, granular context) (§3.3)
  - [x] **B3** · Wire `Generate PR` button to remediation action — add loading state `Generating PR...` → `Pending Change` / `Resolved` transitions (§4)
  - [x] **B4** · Add secondary actions dropdown (`⋮`) on each group: Suppress Group (30d), Acknowledge Risk, Mark as False Positive (§4)
  - [x] **B5** · Add `Shared Resource` badge to group card when `is_shared_resource=true` + confirmation dialog on any action (§6)

  ### Phase C — Grouping Control Bar
  - [x] **C1** · Implement `GroupingControlBar.tsx` — `+ Add Grouping` button with dimension picker (Rule, Severity, Region, Resource, Status) (§8.3)
  - [x] **C2** · Grouping token pills with `×` remove button; cap at 3 active dimensions (§8.2)
  - [x] **C3** · Drag-and-drop reorder of tokens → re‑renders nested grouping hierarchy (§8.3)
  - [x] **C4** · Default grouping state: `Severity → Rules` applied on page load (§8.4)

  ### Phase D — Findings Page Integration
  - [x] **D1** · Add **Grouped / Flat** view toggle to `findings/page.tsx` (Grouped = new default) (§3)
  - [x] **D2** · Grouped view calls `GET /findings/grouped`; renders collapsible `Severity` accordion with `FindingGroupCard` rows inside
  - [x] **D3** · Flat view keeps existing `FindingCard` list (no regression)
  - [x] **D4** · All existing filters (severity tabs, source, account, region, status, search) apply to grouped view too

  ### Phase E — Dashboard & Discovery
  - [x] **E1** · Global dashboard widget: **Actionable Risk Score** + severity counts (in-scope only) (§5)
  - [x] **E2** · Inline resource badges (yellow/red dots) on inventory/architecture views; clicking opens side-panel with resource findings (§5) — _[spec](remaining-features.md#e2--inline-resource-badges-inventory-view)_
  - [x] **E3** · Notification config: Slack/Email alerts fire only for in-scope Critical/High (§5) — _[spec](remaining-features.md#e3--notification-config-slack--email-alerts)_

  ### Phase G — Blocked / Future Work
  > _See full specs in [remaining-features.md](remaining-features.md)_
  - [x] **G1 (E2)** · Build `/inventory` page + `GET /resources` endpoint — prerequisite for inline resource badges
  - [x] **G2 (E3)** · `tenant_notification_config` table + migration + Slack/SES worker job + `/settings` notification form + Terraform SES
  - [x] **G3 (§6)** · Scope-change detection during ingestion + `tenant_notifications` table + `NotificationBell` in AppShell + findings page banner — _[spec](remaining-features.md#6--new-resources-in-scope-notification)_

  ### Phase F — Verification & Handover
  - [x] **F1** · Manual smoke test: grouped view, generate PR flow, expand/collapse, grouping control bar
  - [x] **F2** · Write/update backend unit test for `GET /findings/grouped`
- [ ] [QA Strategy Prompt](qa-strategy-prompt.md)
- [ ] [Pricing and Differentiation Analysis](pricing-and-differentiation.md)
- [ ] [PR Safety Instructions](pr-safety-instructions.md)
- [x] Complete 48-hour baseline report revision (incorporating insights on SOC 2 proof-of-value)
- [ ] Develop comprehensive account management features (e.g., delete account, change password, profile settings)
