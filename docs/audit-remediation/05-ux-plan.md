# UX and Operator Experience Remediation Plan

## Scope

This workstream covers backlog IDs `UX-001`, `UX-002`, `UX-004`, `UX-005`, and `UX-006`.

Shared security dependency:
- Token reveal/rotation and secret-safe onboarding behavior is tracked under `SEC-005`.

Shared architecture dependency:
- Control-plane forwarder deployment/readiness per customer account-region is required onboarding criteria (`ARC-004`), so UX fast-path design must not bypass that gate.

## Workstream Outcomes

This plan must deliver:
- Reachable and trustworthy settings workflows for high-value reporting actions.
- Accurate UI affordances that reflect real backend behavior.
- Deterministic, shareable navigation state for operator and support use cases.
- Accessibility and onboarding improvements that strengthen enterprise readiness and activation.

## Sequencing

1. `UX-001` immediate fix so key product outcomes are reachable.
2. `UX-002` and `UX-006` next to restore predictable operator workflows.
3. `UX-004` add accessibility automation.
4. `UX-005` redesign onboarding path for faster first value.

## Delivery Plan by Phase

| Phase | In-Scope IDs | Expected Outputs |
| --- | --- | --- |
| Phase 1 | `UX-001` | Evidence export and baseline report paths are reachable from primary settings navigation |
| Phase 2 | `UX-002`, `UX-006` | Settings actions align with real behavior and URL state is deterministic/shareable |
| Phase 3 | `UX-004`, `UX-005` | Accessibility controls in CI and faster onboarding time-to-value with measured outcomes |

## Deliverable and Evidence Matrix

| ID | Primary Deliverable | Expected Output | Evidence Required |
| --- | --- | --- | --- |
| UX-001 | Settings navigation and deep-link correction | Users can access report/export flows directly and consistently | Integration tests, manual smoke validation, release screenshots |
| UX-002 | Read-role validation UX correctness | No misleading action label or no-op behavior remains | E2E behavior tests, UX copy review sign-off |
| UX-004 | Accessibility automation baseline | Accessibility regressions surface in CI before release | Axe/Lighthouse CI outputs, baseline conformance report |
| UX-005 | Onboarding fast-path redesign | Faster first-value experience with non-blocking hardening checks | Funnel metrics before/after, onboarding completion report |
| UX-006 | URL-backed settings state management | Back/forward/refresh maintain consistent tab context | Route-state tests and support workflow validation |

## Detailed Plan

### UX-001: Evidence export and baseline report are unreachable

**Implementation actions**
1. Add `Evidence Export` and `Baseline Report` entries to Settings navigation.
2. Support route-based deep links (`/settings?tab=evidence-export` and `/settings?tab=baseline-report`).
3. Ensure tab state initialization from URL query params.
4. Add integration tests for navigation, refresh, and direct-link behavior.

**Code touchpoints**
- `frontend/src/app/settings/page.tsx`

**Validation**
- Manual smoke test confirms both views accessible from primary settings flow.
- Automated tests cover click navigation and direct URL load.

**Acceptance criteria**
- Users can reliably access export/report workflows without hidden UI paths.

### UX-002: "Validate Read Role" action is no-op

**Implementation actions**
1. Connect button to real backend validation endpoint.
2. If immediate backend integration is not ready, relabel as informational and remove action affordance.
3. Display actionable result states (`success`, `warnings`, `failed`) with next steps.
4. Add telemetry event for validation usage and outcomes.

**Code touchpoints**
- `frontend/src/app/settings/page.tsx`
- related backend validation endpoint wiring if needed

**Validation**
- E2E test verifies click triggers actual validation behavior.
- UX copy review ensures no misleading call-to-action remains.

**Acceptance criteria**
- UI affordance accurately matches actual system behavior.

### UX-004: Accessibility readiness unknown

**Implementation actions**
1. Add automated accessibility checks (`axe` and/or Lighthouse CI) for key flows.
2. Define minimum conformance baseline and failure threshold in CI.
3. Fix high-impact violations in onboarding/settings/findings pages.
4. Publish accessibility status in release notes and docs.

**Code touchpoints**
- frontend test/CI configuration
- critical page components under `frontend/src/app/`

**Validation**
- CI runs accessibility checks on PRs.
- Baseline report artifact stored for audit evidence.

**Acceptance criteria**
- Accessibility regressions are detected automatically before release.

**Execution status (2026-02-17)**
- Completed: automated accessibility gate added for onboarding/settings/findings using Playwright + axe.
- CI workflow: `/Users/marcomaher/AWS Security Autopilot/.github/workflows/frontend-accessibility.yml`
- Baseline evidence:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-ux004-a11y-baseline-20260217T191445Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-ux004-a11y-baseline-20260217T191445Z.json`

### UX-005: Onboarding time-to-value is slower than necessary

**Implementation actions**
1. Introduce a fast path: role registration -> immediate first ingest trigger.
2. Keep required onboarding gates blocking (Inspector, Security Hub, AWS Config, control-plane readiness), and move only non-critical checks to asynchronous background validation.
3. Show progress and actionable warnings without blocking initial value delivery.
4. Add guidance for "minimum successful path" vs "full hardening path".

**Code touchpoints**
- `frontend/src/app/onboarding/page.tsx`
- supporting backend endpoints for non-blocking checks

**Validation**
- Measure time from account connect to first findings shown.
- Compare completion and drop-off before/after rollout.

**Acceptance criteria**
- New users can reach first value significantly faster with clear follow-up actions.

**Execution status (2026-02-17)**
- Completed: first-value fast path shipped in onboarding with earlier safe ingest trigger and async optional-check handling.
- Required blocking gates preserved for onboarding completion:
  - Inspector
  - Security Hub
  - AWS Config
  - Control-plane readiness
- Non-critical check moved async:
  - Access Analyzer verification can continue in background without blocking required gate progression.
- Code changes:
  - `/Users/marcomaher/AWS Security Autopilot/frontend/src/app/onboarding/page.tsx`
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/aws_accounts.py`
- New backend support endpoint:
  - `POST /api/aws/accounts/{account_id}/onboarding-fast-path`
- Metric evidence:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-ux005-ttv-metrics-20260217T193137Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-ux005-ttv-metrics-20260217T193137Z.json`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-ux005-ttv-command-log-20260217T193137Z.txt`

### UX-006: Settings context is not URL-stable

**Implementation actions**
1. Bind tab state to query params.
2. Keep browser back/forward behavior deterministic.
3. Preserve selected tab on refresh and support links.
4. Add tests for route parsing and state synchronization.

**Code touchpoints**
- `frontend/src/app/settings/page.tsx`

**Validation**
- Deep links open correct tab consistently.
- Support team can share reproducible settings links.

**Acceptance criteria**
- Settings navigation state is stable, shareable, and support-friendly.

## Milestones

- Milestone U1 (end Phase 1): `UX-001` complete.
- Milestone U2 (end Phase 2): `UX-002` and `UX-006` complete.
- Milestone U3 (end Phase 3): `UX-004` and `UX-005` complete.

## Workstream Sign-Off Criteria

1. Core reporting and settings workflows are reachable without hidden UI paths.
2. User-facing actions are behaviorally accurate and test-verified.
3. Accessibility and onboarding improvements are measured, not anecdotal.
4. Support and operator teams can rely on deterministic URL-based state sharing.
