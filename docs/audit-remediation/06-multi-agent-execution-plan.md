# Multi-Agent Execution Plan

## Objective

Close all open remediation work with parallel agents, starting from the highest-risk regressions discovered in current code and AWS state.

Date baseline: 2026-02-17

## Agent Startup Required Reads (Mandatory For Every Agent)

Before starting any scoped task, each agent must read these files in full:

- `/Users/marcomaher/AWS Security Autopilot/.cursor/notes/task_log.md`
- `/Users/marcomaher/AWS Security Autopilot/.cursor/rules/core-behavior.mdc`
- `/Users/marcomaher/AWS Security Autopilot/.cursor/rules/console-protocol.mdc`
- `/Users/marcomaher/AWS Security Autopilot/.cursor/notes/project_status.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/README.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/README.md`

Required completion criteria before task execution:

- Confirm startup reads are complete in the agent's first task note or handoff comment.
- Do not begin implementation, deployment, or evidence updates until the read set is complete.

## Current Open Scope

- Re-opened security/implementation regressions:
  - `SEC-005`: control-plane token still plaintext and returned in auth responses.
  - `IMP-004`: signup leaks raw exception text.
- Open Phase 3 architecture/security closure:
  - `ARC-008`, `ARC-009`, `SEC-008`, `SEC-010`.
- Open Phase 3 implementation/UX:
  - `IMP-007`, `IMP-008`, `IMP-009`, `UX-004`, `UX-005`.
- Open Phase 4:
  - regression guardrails, sign-off package, backlog closure.

## Phases and Agent Allocation

### Phase A (Start Now): Critical Re-opened Fixes and Security Control Integrity

Goal: eliminate known regressions before broader Phase 3 closure evidence.

Agent A1 - Security token lifecycle (`SEC-005`)
- Scope:
  - Replace plaintext `control_plane_token` storage with hashed token fingerprint model.
  - One-time reveal on creation/rotation only.
  - Add rotate/revoke endpoints and audit logging.
  - Remove persistent token exposure from `/api/auth/me` and login responses.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/backend/models/tenant.py`
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/auth.py`
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/saas_admin.py`
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/control_plane.py`
  - `/Users/marcomaher/AWS Security Autopilot/alembic/versions/*` (new migration)
  - `/Users/marcomaher/AWS Security Autopilot/tests/*` (token lifecycle tests)
- Done when:
  - DB no longer stores recoverable token.
  - Existing token is never returned by read endpoints.
  - Rotate/revoke flow tested and documented.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent A2 - Signup error sanitization (`IMP-004`)
- Scope:
  - Replace raw exception response with generic client-safe error and correlation id.
  - Keep full detail in server logs only.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/auth.py`
  - `/Users/marcomaher/AWS Security Autopilot/tests/test_auth_api.py` (or equivalent auth test file)
- Done when:
  - HTTP response does not include raw exception text.
  - Regression tests pass.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

### Phase B: Architecture and Security Operational Closure (`ARC-008`, `ARC-009`, `SEC-010`)

Goal: close all unchecked operational checklist evidence with live AWS proof.

Agent B1 - DR controls and restore drill (`ARC-008`)
- Scope:
  - Deploy DR stack.
  - Execute restore drill with start/end timestamps and output capture.
  - Capture stack output evidence for retention and copy settings.
- Commands:
  - `AWS_REGION=eu-north-1 ./scripts/deploy_phase3_architecture.sh`
  - `python3 scripts/collect_phase3_architecture_evidence.py --region eu-north-1`
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/dr-backup-controls.yaml`
  - `/Users/marcomaher/AWS Security Autopilot/docs/disaster-recovery-runbook.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-*.md`
- Done when:
  - DR stack exists and checklist proof items are checked.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent B2 - Readiness dependency validation (`ARC-009`)
- Scope:
  - Run readiness failure simulation and recovery checks.
  - Capture `/ready` non-200 and 200 behavior evidence.
  - Verify queue lag and worker failure SLO visibility in admin system health.
- Commands:
  - `./venv/bin/pytest -q tests/test_health_readiness.py tests/test_saas_system_health_phase3.py tests/test_cloudformation_phase3_resilience.py --noconftest`
  - `python3 scripts/check_api_readiness.py --url "$API_PUBLIC_URL/ready"`
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/backend/services/health_checks.py`
  - `/Users/marcomaher/AWS Security Autopilot/backend/main.py`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-architecture-*.md`
- Done when:
  - All `ARC-009` checklist boxes are checked with attached artifacts.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent B3 - WAF association and alarm drill (`SEC-010`)
- Scope:
  - Associate Web ACL to active API Gateway stage ARN.
  - Run blocked/rate-limit alarm drill and capture recovery.
  - Confirm on-call route evidence attachment.
- Commands:
  - `AWS_REGION=eu-north-1 EDGE_API_GATEWAY_STAGE_ARN='arn:aws:apigateway:eu-north-1::/apis/g1frb5hhfg/stages/$default' ./scripts/deploy_phase3_security.sh`
  - `python3 scripts/collect_phase3_security_evidence.py --region eu-north-1`
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/edge-protection.yaml`
  - `/Users/marcomaher/AWS Security Autopilot/docs/edge-traffic-incident-runbook.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-security-*.md`
- Done when:
  - WAF is attached and `SEC-010` checklist boxes are checked.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

### Phase C: Remaining Phase 3 Engineering (`IMP-007`, `IMP-008`, `IMP-009`, `UX-004`, `UX-005`)

Goal: close engineering maturity work with measurable CI and UX outcomes.

Agent C1 - CI and dependency governance (`IMP-007`)
- Scope:
  - Add required CI jobs for backend, worker, and frontend.
  - Add dependency vulnerability scan in CI.
  - Move to locked dependency strategy and policy doc.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/.github/workflows/*`
  - `/Users/marcomaher/AWS Security Autopilot/backend/requirements.txt`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/requirements.txt`
  - `/Users/marcomaher/AWS Security Autopilot/frontend/package.json`
- Done when:
  - Full test matrix and dependency scans run on pull requests.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent C2 - Router/service refactor (`IMP-008`)
- Scope:
  - Extract large orchestration logic from oversized routers.
  - Keep API contracts stable with contract tests.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/internal.py`
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/aws_accounts.py`
  - `/Users/marcomaher/AWS Security Autopilot/backend/services/*`
- Done when:
  - Router complexity reduced and tests show no API contract regressions.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent C3 - Tenant isolation regression suite (`IMP-009`)
- Scope:
  - Add cross-tenant negative tests for mutable compliance artifacts.
  - Ensure tests are required in CI.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/tests/test_control_mappings_api.py`
  - `/Users/marcomaher/AWS Security Autopilot/tests/test_evidence_export_s3.py`
  - `/Users/marcomaher/AWS Security Autopilot/.github/workflows/*`
- Done when:
  - Cross-tenant mutation/access regressions fail CI reliably.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent C4 - Accessibility CI baseline (`UX-004`)
- Scope:
  - Add `axe` or Lighthouse CI checks to PR flow.
  - Fix high-impact violations in onboarding/settings/findings.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/frontend/package.json`
  - `/Users/marcomaher/AWS Security Autopilot/.github/workflows/*`
  - `/Users/marcomaher/AWS Security Autopilot/frontend/src/app/*`
- Done when:
  - Accessibility checks run in CI with artifact output.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent C5 - Onboarding fast-path (`UX-005`)
- Scope:
  - Reduce time-to-value while preserving hard security gates.
  - Add measured before/after funnel metrics.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/frontend/src/app/onboarding/page.tsx`
  - `/Users/marcomaher/AWS Security Autopilot/backend/routers/aws_accounts.py`
- Done when:
  - Faster first ingest path shipped with evidence metrics.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

### Phase D: Phase 4 Closure and Governance

Goal: lock in non-regression controls and complete formal closure.

Agent D1 - Required checks and branch protections
- Scope:
  - Mark all critical workflows as required status checks.
  - Document governance and release gate matrix.
- Done when:
  - Phase 4 evidence includes branch protection snapshot and required checks list.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

Agent D2 - Final remediation closure package
- Scope:
  - Update backlog statuses and closure checklists.
  - Attach evidence index and owner sign-offs.
- Primary files:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/01-priority-backlog.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/phase3-architecture-closure-checklist.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/phase3-security-closure-checklist.md`
- Done when:
  - Phase 3 and Phase 4 are checked complete in backlog.
- Startup requirements:
  - Complete all files listed in `Agent Startup Required Reads (Mandatory For Every Agent)` before starting.

## Parallel Start Order

1. Start `A1` and `A2` immediately.
2. In parallel, start `B3` (WAF association) because it is independent and fast.
3. Start `B1` and `B2` once API is stable after Phase A merges.
4. Run `C1`, `C3`, and `C4` in parallel after Phase A.
5. Run `C2` and `C5` after `C1` baseline CI is in place.
6. Finish with `D1` and `D2`.

## Daily Control Checklist

- Every agent updates one evidence artifact or checklist section per day.
- No item marked done without test evidence and operational proof.
- Critical reopen regressions (`SEC-005`, `IMP-004`) block all phase-close declarations.
