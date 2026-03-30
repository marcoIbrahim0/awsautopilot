# AWS Security Autopilot
## End-to-End UI/UX Redesign Spec (Onboarding -> All Pages)

## 1) Product-Wide UI/UX Audit Summary

### 1.1 Top Issues Found
1. Onboarding had hidden dependencies and unclear prerequisites (IAM role, Security Hub, Config, Inspector, control-plane).
2. Validation/check actions were distributed across onboarding, settings, and account surfaces, causing contradictory state.
3. Async actions lacked consistent feedback; users could not tell if jobs started, were running, or failed.
4. Findings lacked direct next-step pathways from issue -> remediation workflow -> PR bundle grouping.
5. Account management mixed setup and lifecycle functions without clear information hierarchy.
6. Copy quality varied (short labels mixed with long technical text), increasing cognitive load for non-experts.
7. First login had no stable progress model for ingestion/computation, causing uncertainty and refresh loops.

### 1.2 Cross-Product Patterns To Fix
1. Single, deterministic onboarding gate for all account-read checks.
2. One async pattern everywhere: immediate top banner + durable notification-center lifecycle item.
3. Clear required/optional taxonomy on each setup screen.
4. Action-oriented findings UX with explicit button outcomes and unavailable states.
5. Consistent page anatomy (title, status, primary action zone, guidance, empty/error states).

### 1.3 Dashboard Visual System Status (Implemented 2026-03-22)
1. Dashboard surfaces now converge on one brand-led operator style instead of mixing generic bordered cards, older `nm-neu-*` treatments, and newer remediation panels.
2. Shared theme tokens are now logo-driven in both light and dark mode:
   - shell, card, inset, overlay, badge, and control surfaces use explicit token roles
   - primary actions now center on the logo azure/navy pair instead of page-local colors
3. Shared action/status primitives are now stricter:
   - buttons and badges no longer share the same visual weight
   - settings/help/workflow forms use the same input and control surface language
4. The shell and weaker product areas were refit onto the shared system:
   - sidebar and top bar
   - settings
   - help hub
   - PR bundle create flow
   - action detail entry chrome and suppress workflow
5. Findings, Accounts, and Top Risks remain the structural reference surfaces, with lighter alignment changes only where they needed to match the final shared tokens.

### 1.4 Responsiveness Follow-Up Status (Implemented 2026-03-22)
1. Action Detail no longer blocks the whole modal on non-critical follow-up work:
   - core `getAction(...)` detail renders first
   - remediation history, direct-fix capability checks, and write-role account lookups now hydrate after the shell is visible
   - short-lived in-memory caches now reuse action detail and run history across subview switches
2. Suppress now stays inside the Action Detail dialog without losing draft context on simple back/return transitions:
   - the suppress workflow stays mounted after first open
   - successful exception creation updates visible exception state immediately and then reconciles with a background action refresh
3. Remediation workflow fetches are narrower:
   - remediation options are reused per action/mode session instead of reloading on every reopen
   - preview generation is debounced and keeps the previous preview visible while refresh is in flight
   - public-IP lookup is reused as a best-effort session helper instead of repeating for every modal open
4. PR Bundle create and summary no longer crawl the entire open-action universe client-side:
   - `GET /api/actions` now supports additive `q` text search and explicit `ids` loading
   - create page filtering is server-backed with local selection persistence and explicit paging
   - summary loads only the chosen action IDs before running preflight/generation
5. Action Detail follow-up actions now stay scoped to the selected action/group instead of broad tenant recomputes:
   - `Refresh State` uses targeted action reevaluation first and falls back only to scoped account ingest when the strategy does not support immediate reevaluation
   - remediation history and implementation artifacts now include grouped PR-bundle runs for every member action in the execution group, not only the representative action that owns the stored run row

### 1.5 Action Detail Visual Consistency Follow-Up (Implemented 2026-03-22)
1. Action Detail now uses a stronger dashboard-native hero layout instead of isolated title text plus loose chips:
   - title, supporting description, badge cluster, refresh control, and action workflow now read as one system
   - badge treatment now matches the shared premium surface language in light and dark mode
2. Attack Path entry is now promoted near the top of the detail surface:
   - `Open Attack Paths` is no longer buried in the section header
   - the CTA now sits in a dedicated high-visibility danger-toned navigation card so users can identify the next triage surface quickly
3. The priority-storyboard command rail was rebuilt:
   - `Recommended check` now reads as a branded `Recommended next step` surface
   - command text is presented in a stronger inset panel aligned with the remediation/dashboard card system

### 1.6 Dark-Mode Border Hierarchy Follow-Up (Implemented 2026-03-22)
1. Dark mode no longer relies on one generic border line across shell, cards, and controls.
2. Shared border roles now distinguish:
   - shell chrome borders for the top and left navigation
   - standard card borders
   - stronger interactive control borders for buttons, tabs, and hover states
   - softer inset/group borders for nested panels
3. The new dark-mode border hierarchy was applied through the shared tokens and primitives so it propagates across the website instead of being patched per page.

### 1.7 Remediation Run Progress Surface Follow-Up (Implemented 2026-03-22)
1. The Run progress screen now uses the same dashboard-native panel/inset/control surfaces as the rest of the operator UI instead of older mixed `nm-neu-*` and `bg-bg` card treatments.
2. Light mode was cleaned up so the primary run hero, side rail, closure sections, technical details, and generated-file cards all sit on clearer branded blue-white surfaces instead of flatter washed-out boxes.
3. Dark mode no longer drops any Run progress card onto near-black fills:
   - activity log cards
   - execution workspace cards
   - generated file/code preview cards
   - apply-guide/tab content cards
   - compact-mode action/evidence/artifact cards
4. The change stays frontend-only and keeps the same run states, evidence links, and workflow actions while aligning the run detail view with the shared dashboard system in both themes.

### 1.8 Bundle Progress Terminology + Layout Cleanup (Implemented 2026-03-24)
1. The dedicated PR-bundle progress experience now presents itself as bundle generation rather than a generic "run" so the UI does not imply Autopilot is executing the downloaded bundle for the customer.
2. The dedicated full-width page now shows one primary progress bar only; the secondary duplicate percentage bar was removed from the deeper details section.
3. The modal/success path now keeps `Download bundle` in the first visible status/actions block so users do not need to scroll down to the generated-files section to retrieve the artifact.
4. The grouped bundle page now uses generation-oriented wording (`Generate bundle`, `Generation timeline`, `Generated and successful`, `Not generated yet`) while keeping backend routes and internal remediation-run contracts unchanged.
5. The grouped action detail page now adds a `Back to Findings` link, narrows the member section to only `Generated and needs follow-up` items, adds a per-member `Open action and refresh state` CTA, and collapses older generation outcomes by default so the page emphasizes the next operator step instead of raw timeline volume.

## 2) New Information Architecture + Navigation Model

### 2.1 Primary Navigation
1. Findings
2. Accounts
3. Actions
4. PR Bundles
5. Exceptions
6. Settings
7. Top Risks
8. Exports
9. Shared Files

### 2.2 IA Rules
1. `/onboarding` is a hard gate for authenticated users until `onboarding_completed_at` exists.
2. Account-read readiness checks run only in onboarding final checks.
3. Account area is reorganized as a hub with four sections:
   - Connection Health
   - Roles & Permissions
   - Integrations
   - Usage & Lifecycle
4. Root route behavior:
   - Authenticated + incomplete onboarding -> `/onboarding`
   - Authenticated + complete onboarding -> `/findings`
   - Unauthenticated -> `/landing`
5. `/settings` is the canonical admin surface plus the baseline-report deep-link surface. Deep links use `/settings?tab=<tab-id>`.
6. `/exports` is the canonical exports and compliance workspace in the primary navbar.
7. `/baseline-report` redirects to `/settings?tab=baseline-report` for compatibility.

### 2.3 Settings Information Architecture
1. `Account`
   - Uses the existing profile/security/delete-account surface.
2. `Team`
   - Keeps tenant invite/remove management.
3. `Organization`
   - Read-only tenant metadata and connected-account summary.
   - Routes users to `Accounts` and onboarding final checks instead of running validation inline.
4. `Notifications`
   - Weekly digest email plus Slack digest webhook only.
5. `Integrations`
   - Canonical provider settings surface for Jira, ServiceNow, and Slack.
   - See [Integration-first remediation operations](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/integration-first-remediation-operations.md).
6. `Governance`
   - Tenant governance notifications and webhook controls.
   - See [Communication + Governance layer](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/communication-governance-layer.md).
7. `Remediation Defaults`
   - Tenant remediation-profile defaults and approved-input policy.
   - See [Wave 1 foundation contracts](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/wave-1-foundation-contracts.md).
8. `Exports & Compliance`
   - Combines evidence/compliance export requests and control mappings.
9. `Baseline Report`
   - Reuses the shared baseline report panel from Settings.

## 3) Onboarding Redesign

### 3.1 Happy Path Flow Diagram (Text)
```text
Login
-> Onboarding: Welcome
-> Step 2: Connect Core Integration Role (required)
-> Step 3: Verify Inspector (required)
-> Step 4: Verify Security Hub + AWS Config (required)
-> Step 5: Verify Control-Plane Forwarder (required)
-> Step 6: Final Checks (required, onboarding-only account-read checks)
-> Step 7: Initial Processing (queue ingest + compute)
-> Findings page progress module:
   - Loading findings
   - Computing actions
-> Steady-state findings/actions experience
```

### 3.2 Screen-by-Screen Flow
1. Welcome
   - Purpose, expected duration, required vs optional summary.
   - CTA: `Start onboarding`.
2. Connect Core Integration Role (required)
   - Numbered deployment steps.
   - CloudFormation launch entry point.
   - Inputs:
     - Integration Role ARN (required)
     - Account ID (required)
     - Regions (required, min 1)
   - Validation rules + success criteria shown inline.
3. Inspector (required)
   - Cost-aware defaults:
     - Enable EC2 first
     - ECR/Lambda only if used
     - Lambda code scanning off by default
   - Verification action blocks progress until pass.
4. Security Hub + AWS Config (required)
   - Explicitly states Config must be enabled first.
   - Safe standards default: AWS Foundational Security Best Practices.
   - Additional standards (CIS/NIST/PCI) recommended only when required.
   - Verification action blocks progress until pass.
5. Control-Plane Forwarder (required)
   - Region-specific stack deploy.
   - Explicit test event guidance (e.g., temporary SG ingress change).
   - Verification action blocks progress until pass.
6. Final Checks (required)
   - Runs all required account-read checks in onboarding only.
   - Fails with explicit missing service/region list.
7. Initial Processing
   - Starts ingestion and action computation.
   - Stores first-run handoff state.
   - Redirects to findings with active progress module.

### 3.3 Required vs Optional Steps
1. Required:
   - Integration Role
   - Inspector
   - Security Hub + AWS Config
   - Control-plane forwarder
   - Final checks
   - Reason: required for trusted connection state and baseline remediation confidence.
2. Optional:
   - None in onboarding right now.
   - Access Analyzer guidance is intentionally deferred to post-onboarding account-management surfaces so users do not enable it during initial connection.

### 3.4 Permission/Role Setup Guidance (No Gaps)
1. Where to find role ARN:
   - AWS Console -> IAM -> Roles -> select deployed role -> copy `Role ARN`.
2. Where to paste in app:
   - Onboarding -> `Connect Core Integration Role` -> `Integration Role ARN (required)`.
3. Validation rules:
   - ARN regex format enforced.
   - Account ID must be exactly 12 digits.
   - ARN account ID must match onboarding account ID.
   - At least one monitored region required.
4. Success confirmation:
   - Success banner + notification item.
   - Step auto-advances on successful required check.
5. Common errors and handling:
   - Invalid ARN format -> inline error with example format.
   - Account mismatch -> explicit account mismatch message.
   - Missing regional services -> list missing regions per service.
   - No recent control-plane intake -> explain required test event and retry path.

### 3.5 Cost-Efficient Enablement Guidance
1. Inspector:
   - Start with EC2 scanning.
   - Enable ECR/Lambda selectively to avoid unnecessary spend.
   - Keep Lambda code scanning disabled by default.
2. Security Hub + AWS Config:
   - Enable Config recorder first in monitored regions.
   - Record global IAM resources in one home region.
   - Enable only required resource types in Config where feasible.
3. Security Hub standards:
   - Safe default: AWS Foundational Security Best Practices.
   - Add CIS/NIST/PCI only when compliance scope requires.

### 3.6 Onboarding Progress Persistence
1. Persisted state key: `localStorage:onboarding_v2_draft`.
2. Saved fields:
   - Current step
   - All form inputs
   - Completed checks/step flags
   - Last service/control-plane check timestamps
   - Connected account id
3. Persistence TTL: 30 days.
4. Stale AWS state handling:
   - >=15 minutes: quick re-validation prompt/flow.
   - >=24 hours: full re-validation required.
5. Browser close/reload behavior:
   - Resume from last saved step with inputs intact.
   - No forced restart.

## 4) Page Templates + Component System

### 4.1 Standard Page Template
1. Header zone:
   - Title
   - Optional subtitle/help text
   - Primary actions (right side)
2. Global status zone:
   - Async banner rail (top)
   - Critical inline page alerts
3. Content zone:
   - Primary module
   - Secondary guidance module
4. States:
   - Loading skeleton
   - Empty state with action CTA
   - Error state with retry and next-step guidance

### 4.2 Component Guidelines
1. Buttons
   - Primary: one per area, task completion CTA.
   - Secondary: supporting actions.
   - Disabled requires explicit reason (tooltip/inline helper).
2. Banners
   - Top-of-page, immediate for async starts.
   - Persistent for running/error/timed_out/canceled.
   - Auto-dismiss success (8 seconds).
3. Toasts
   - Avoid for long jobs; use banners + notification center instead.
4. Tables
   - Always include empty row state and retry path for failures.
   - Status columns use consistent badge language.
5. Tabs
   - Use when datasets share one decision context (e.g., account hub sections).
6. Modals
   - Use for focused edits, destructive confirmation, account details.
7. Drawers
   - Use for contextual detail when preserving page comparison context matters.

### 4.3 Copywriting Standards
1. Tone: direct, operational, confidence-building, non-alarmist.
2. Length:
   - Heading: <= 7 words
   - Helper text: <= 120 characters where possible
   - Error copy: first sentence states failure, second sentence states next action
3. Style:
   - Prefer action verbs (`Verify`, `Run checks`, `Retry`, `Open onboarding checks`)
   - Avoid internal jargon without expansion.
4. Examples:
   - Good: `Inspector is still missing in: us-east-1. Enable Inspector, then verify again.`
   - Good: `Role ARN must match arn:aws:iam::123456789012:role/RoleName`

## 5) Interaction Rules

### 5.1 Loading, Skeletons, Progress
1. Initial page fetch: skeleton if data not yet loaded.
2. User-triggered async job:
   - Immediate banner + notification item (status `running`).
3. Long-running jobs:
   - Progress bar with status text.
   - Partial state allowed when findings are ready but actions lag.
4. First login:
   - Two tracks always visible:
     - `Loading findings`
     - `Computing actions`
   - Soft timeout: 120s -> show partial-state language.
   - Hard timeout: 15m -> show retry action + keep partial results usable.

### 5.2 Notification Architecture
1. Event surfaces:
   - Banner rail (real-time, high visibility)
   - Notification center (durable timeline)
2. Status lifecycle:
   - `queued -> running -> partial -> success|error|timed_out|canceled`
3. Severity levels:
   - `info`, `success`, `warning`, `error`
4. Dedupe:
   - 10-minute dedupe window by `dedupeKey`.
5. Retention:
   - Finished items retained 30 days.
6. Dismiss behavior:
   - Banner can be manually dismissed.
   - Notification item remains until user dismisses or retention expiry.

### 5.3 Error Handling Patterns
1. Inline validation for inputs:
   - Show exact field and fix.
2. Service check failure:
   - Show missing services by region.
   - Include explicit next step and retry path.
3. Network/API failures:
   - Keep user context.
   - Offer `Retry`.
4. Timeout failures:
   - Preserve partial data.
   - Offer targeted retry for failed track/job.

## 6) Acceptance Criteria + Edge Cases

### 6.1 Findings
1. Each finding shows:
   - `Fix this finding`
   - `View PR bundle group`
2. If action/group unavailable:
   - Button disabled with explicit reason.
3. Grouped findings cards expose inline `Suppress Group`, `Acknowledge Risk`, and `Mark False Positive` controls instead of hiding them behind an overflow menu.
4. Multi-level `Group by` selections re-render nested buckets for every active dimension, including combinations like `Severity -> Rule -> Region`.
5. Edge cases:
   - Finding has no mapped action.
   - Action exists but no bundle-run metadata.

### 6.2 Onboarding
1. Required checks cannot be bypassed.
2. Inspector is mandatory to complete onboarding.
3. Access Analyzer is not shown during onboarding; legacy saved drafts resume at final checks.
4. Edge cases:
   - Role ARN account mismatch.
   - Region removed after prior service validation.
   - Saved draft expired (>30 days).
   - Saved check timestamps stale (15m/24h thresholds).

### 6.3 First Login Processing
1. Findings page shows dual-progress module on first run.
2. Partial results are usable if actions lag.
3. Hard timeout exposes retry.
4. `Notify me when ready` creates completion notification when both tracks complete.
5. Edge cases:
   - Polling errors (transient API failures).
   - Browser reload during processing.

### 6.4 Global Async Feedback
1. Any tracked user-triggered async action creates:
   - top banner immediately
   - notification center item
2. Status transitions are reflected in both surfaces.
3. Edge cases:
   - duplicate clicks (dedupe)
   - late success after soft timeout
   - canceled jobs

### 6.5 Account Hub
1. Account area presents four sections with clear intents.
2. Connection health and status are visible at both summary and row levels.
3. Account-read checks are not executed from account/settings pages; users are routed to onboarding checks.
4. Edge cases:
   - disabled account status
   - no connected accounts
   - mixed-status multi-account tenants

### 6.6 Settings and Reporting
1. Every supported `?tab=` deep link opens the correct Settings screen.
2. Legacy Settings aliases (`profile`) normalize to canonical Settings tabs, while legacy export tab URLs (`exports-compliance`, `evidence-export`, `control-mappings`) redirect to `/exports`.
3. `Organization` never runs account validation, ReadRole checks, control-plane checks, or WriteRole flows inline.
4. Admin-only settings remain editable only for admins; members see read-only rendering where applicable.
5. `/exports` owns the export/compliance workspace while linking to `/settings?tab=baseline-report` for baseline report workflows.
6. `/baseline-report` lands on the Settings baseline-report tab through a redirect.

## 7) Implementation Notes

### 7.1 Frontend State Approach
1. Persisted onboarding draft:
   - local storage state machine keyed by version.
2. Persisted first-run processing state:
   - account id + job ids + start timestamp.
3. Background job context:
   - single source of truth for async UX states and notification rendering.

### 7.2 Notification Event Model
1. Create event:
   - `job.started` with dedupe key and actor/resource metadata.
2. Update events:
   - `job.progressed`, `job.partial`.
3. Terminal events:
   - `job.succeeded`, `job.failed`, `job.timed_out`, `job.canceled`.
4. Rendering:
   - banner rail reads `bannerVisible`.
   - notification center reads the merged timeline from `/api/notifications`.
5. Notification-center contract:
   - `GET /api/notifications` is the canonical bell feed for the authenticated dashboard shell.
   - `PUT /api/notifications/jobs/{client_key}` persists user-triggered async jobs while preserving immediate local banner feedback.
   - `PATCH /api/notifications/state` owns per-user `read`, `unread`, `archive`, and `mark_all_read`.
6. Surface behavior:
   - desktop uses an anchored bell dropdown.
   - mobile/tablet uses a bottom sheet from the same notification source.
   - active jobs are shown separately from recent alerts.
   - unread/archive state is per user, not per tenant.

### 7.3 Analytics Events (Funnel + Time-To-Value)
1. Funnel instrumentation:
   - `onboarding_step_viewed`
   - `onboarding_step_completed`
   - `onboarding_step_failed`
   - `onboarding_optional_skipped`
   - `onboarding_completed`
2. Quality/time metrics:
   - `time_to_first_findings_visible`
   - `time_to_actions_ready`
   - `first_run_soft_timeout`
   - `first_run_hard_timeout`
3. Behavioral outcomes:
   - `finding_fix_clicked`
   - `finding_pr_group_clicked`
   - `async_job_retried`
   - `notification_dismissed`

## 8) Requirement Mapping Table

| Requirement | UI location | UX behavior | Backend dependency | Acceptance criteria |
|---|---|---|---|---|
| A. Findings actions: Fix + PR bundle group | `/frontend/src/app/findings/FindingCard.tsx`, `/frontend/src/app/findings/[id]/page.tsx` | Two buttons per finding; disabled with reason when unavailable | `/backend/routers/findings.py` returns remediation hints | Both controls always present; routes resolve when mapping exists |
| B. Onboarding-only account-read checks; Inspector required; Access Analyzer deferred from onboarding | `/frontend/src/app/onboarding/page.tsx`, `/frontend/src/app/accounts/page.tsx`, `/frontend/src/app/settings/OrganizationSettingsTab.tsx` | Required checks execute only in onboarding final checks; Accounts and Settings route users there instead of running validation inline | `checkAccountServiceReadiness`, `checkAccountControlPlaneReadiness` | Onboarding cannot complete without Inspector/SecurityHub/Config/control-plane |
| C. Explicit deployment steps and ARN handling | `/frontend/src/app/onboarding/page.tsx` | Numbered steps, ARN source locations, app paste targets, validation rules and success confirmation | account register/validate/readiness APIs | New user can complete role setup without undocumented steps |
| D. Cost-efficient enablement guidance (Inspector, Security Hub, Config, standards) | `/frontend/src/app/onboarding/page.tsx` | Prescriptive defaults and scoped recommendations for required services only | service-readiness endpoint | Guidance shown before each required verify action |
| E. Onboarding persistence + stale handling | `/frontend/src/app/onboarding/page.tsx` | Restore step/inputs/check state; revalidate stale checks | local storage + readiness APIs | Reload/close returns to same onboarding progress |
| F. First login loading with dual progress + timeout/partial/notify | `/frontend/src/app/findings/page.tsx` | `Loading findings` + `Computing actions` tracks; retry + notify option | findings/actions list APIs + trigger APIs | User remains on findings with transparent progress until ready |
| G. Global async banner + notification center lifecycle | `/frontend/src/components/ui/GlobalAsyncBannerRail.tsx`, `/frontend/src/components/layout/TopBar.tsx`, `/frontend/src/contexts/BackgroundJobsContext.tsx`, `/frontend/src/contexts/NotificationCenterContext.tsx` | Start banner immediate; bell shows merged persisted jobs + governance alerts; desktop dropdown and mobile sheet share one source | `/api/notifications`, frontend job event model | Every tracked action emits banner + persisted notification item and the bell preserves unread/archive state per user |
| H. Account area redesign with health/roles/integrations/lifecycle | `/frontend/src/app/accounts/page.tsx` | Sectioned account hub with summary KPIs and actionable views | accounts API | User can locate connection health and account management paths in one place |
| I. Canonical settings admin surface | `/frontend/src/app/settings/page.tsx`, `/frontend/src/app/settings/settings-tabs.ts`, `/frontend/src/app/settings/IntegrationsSettingsTab.tsx`, `/frontend/src/app/settings/GovernanceSettingsTab.tsx`, `/frontend/src/app/settings/RemediationDefaultsTab.tsx` | Settings is the single deep-linked configuration surface for integrations, governance, and remediation defaults | `/api/integrations/settings`, `/api/users/me/governance-settings`, `/api/users/me/remediation-settings` | Admin users can manage backend-backed settings from Settings without separate hidden surfaces |
| J. Export/report route consolidation | `/frontend/src/app/settings/ExportsComplianceTab.tsx`, `/frontend/src/app/exports/page.tsx`, `/frontend/src/app/baseline-report/page.tsx` | `/exports` owns export/control-mapping workflows, legacy settings export links redirect there, and `/baseline-report` redirects into Settings | `/api/exports`, `/api/control-mappings`, `/api/baseline-report` | Export, control-mapping, and baseline-report flows stay reachable without duplicate route implementations |

## 9) Key Microcopy Examples

### 9.1 Onboarding
1. Integration role helper:
   - `Paste from IAM -> Roles -> [Role] -> ARN`
2. Validation success:
   - `Integration role validated. Continue to mandatory service enablement.`
3. Inspector failure:
   - `Inspector is still missing in: us-east-1, us-west-2. Enable Inspector, then verify again.`
4. Final checks stale:
   - `Saved checks are older than 24 hours. Running full re-validation now.`

### 9.2 Validation Errors
1. ARN format:
   - `Enter a valid IAM Role ARN. Example: arn:aws:iam::123456789012:role/RoleName`
2. Account mismatch:
   - `This ARN is from account 999999999999, but onboarding is for account 123456789012.`
3. Missing required services:
   - `Final checks failed -> Security Hub: us-east-1 | AWS Config: us-east-1`

### 9.3 Loading/Async
1. Job started:
   - `Starting findings ingestion for account 123456789012...`
2. Partial state:
   - `Actions still computing. Showing partial results.`
3. Hard timeout:
   - `Processing exceeded 15 minutes. You can keep using partial results and retry background jobs.`

## 10) Assumptions
1. Existing backend readiness endpoints remain source-of-truth for service enablement checks.
2. PR bundle group navigation is represented by action grouping metadata; direct run-level finding membership is not separately indexed yet.
3. Billing page is out of scope for this pass; account `Usage & Lifecycle` section includes current lifecycle visibility requirements.

## 11) Implemented Files (Current Pass)
1. `/frontend/src/app/onboarding/page.tsx`
2. `/frontend/src/app/findings/page.tsx`
3. `/frontend/src/app/findings/FindingCard.tsx`
4. `/frontend/src/app/findings/[id]/page.tsx`
5. `/frontend/src/app/accounts/page.tsx`
6. `/frontend/src/app/accounts/AccountDetailModal.tsx`
7. `/frontend/src/app/accounts/AccountServiceStatusCheck.tsx`
8. `/frontend/src/app/accounts/AccountCard.tsx`
9. `/frontend/src/app/accounts/AccountRowActions.tsx`
10. `/frontend/src/app/settings/page.tsx`
11. `/frontend/src/app/settings/settings-tabs.ts`
12. `/frontend/src/app/settings/TeamSettingsTab.tsx`
13. `/frontend/src/app/settings/OrganizationSettingsTab.tsx`
14. `/frontend/src/app/settings/NotificationsSettingsTab.tsx`
15. `/frontend/src/app/settings/IntegrationsSettingsTab.tsx`
16. `/frontend/src/app/settings/GovernanceSettingsTab.tsx`
17. `/frontend/src/app/settings/RemediationDefaultsTab.tsx`
18. `/frontend/src/app/settings/ExportsComplianceTab.tsx`
19. `/frontend/src/app/exports/page.tsx`
20. `/frontend/src/app/baseline-report/page.tsx`
21. `/frontend/src/components/layout/AppShell.tsx`
22. `/frontend/src/components/layout/TopBar.tsx`
23. `/frontend/src/components/ui/GlobalAsyncBannerRail.tsx`
24. `/frontend/src/contexts/BackgroundJobsContext.tsx`
25. `/frontend/src/lib/api.ts`
26. `/backend/routers/findings.py`
