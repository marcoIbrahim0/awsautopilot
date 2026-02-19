# Implementation and Code Quality Remediation Plan

## Scope

This workstream covers backlog IDs `IMP-001`, `IMP-003`, `IMP-004`, `IMP-005`, `IMP-007`, `IMP-008`, and `IMP-009`.

Shared findings are implemented in other plans:
- Settings report tab accessibility: `UX-001`
- Queue contract drift handling: `ARC-001`, `ARC-007`

## Deployment Ownership Boundary

- SaaS admin changes in this plan apply to shared SaaS platform code/config and must not be used as proxy evidence for customer-account onboarding rollout.
- Customer-account forwarder rollout ownership is per tenant admin during onboarding and is tracked in architecture/UX/security plans.
- Any status/readiness logic implemented in this plan must remain scoped to the tenant/account/region under evaluation.

## Workstream Outcomes

This plan must deliver:
- Strict tenant integrity and authorization safety for mutable compliance data.
- Accurate operational semantics in account validation and API error handling.
- Reliable production compatibility through configuration correctness and CI quality gates.
- Sustainable maintainability through targeted refactoring and regression coverage.

## Sequencing

1. `IMP-001` and `IMP-004` first (tenant integrity and error leakage).
2. `IMP-003` and `IMP-005` next (status correctness and deploy compatibility).
3. `IMP-007` then `IMP-009` (quality gates and regression safety).
4. `IMP-008` as controlled refactor once tests are in place.

## Delivery Plan by Phase

| Phase | In-Scope IDs | Expected Outputs |
| --- | --- | --- |
| Phase 1 | `IMP-001`, `IMP-004` | Tenant-safe control mapping integrity and sanitized API error behavior |
| Phase 2 | `IMP-003`, `IMP-005` | Accurate account validation semantics and configuration-driven CORS behavior |
| Phase 3 | `IMP-007`, `IMP-008`, `IMP-009` | Expanded CI and dependency controls, safer service-layer architecture, tenant isolation regression gates |

## Deliverable and Evidence Matrix

| ID | Primary Deliverable | Expected Output | Evidence Required |
| --- | --- | --- | --- |
| IMP-001 | Control mapping data/authorization redesign | No cross-tenant evidence integrity mutation path | Authorization tests, migration evidence, export isolation tests |
| IMP-003 | Expanded account validation status model | Operators see capability-accurate account state | API and UI tests for each status path |
| IMP-004 | Client-safe auth error handling | No raw exception detail is returned to API consumers | Unit tests, structured log/correlation evidence |
| IMP-005 | Config-driven CORS enforcement | Deployments honor configured origin policy with fail-safe checks | Integration tests for allowed/denied origins |
| IMP-007 | Full-stack CI and dependency governance | Regressions and supply-chain drift detected before release | CI workflow outputs, SCA reports, lock-policy docs |
| IMP-008 | Service-layer extraction from oversized routers | Reduced change risk without API contract drift | Contract test suite, complexity reduction snapshot |
| IMP-009 | Tenant isolation regression suite | Continuous prevention of cross-tenant authorization regressions | Required CI check logs and test reports |

## Detailed Plan

### IMP-001: Global control mappings writable by tenant admins

**Implementation actions**
1. Decide authoritative model:
   - Option A: tenant-scoped mappings with `tenant_id`.
   - Option B: global mappings editable only by SaaS admin with immutable versioning.
2. Implement schema and API authorization to match selected model.
3. Add audit trail for mapping changes (actor, before, after, reason).
4. Update compliance pack export builder to use tenant-safe mapping source.
5. Backfill migration for existing rows and permissions.

**Code touchpoints**
- `backend/models/control_mapping.py`
- `backend/routers/control_mappings.py`
- `backend/services/compliance_pack_spec.py`
- Alembic migrations

**Validation**
- Authorization tests for tenant admin vs SaaS admin mutation rights.
- Export tests proving tenant A changes cannot affect tenant B outputs.

**Acceptance criteria**
- Cross-tenant mapping integrity risk is eliminated and auditable.

### IMP-003: Account validation status semantics are misleading

**Implementation actions**
1. Expand status model: `validated`, `validated_with_warnings`, `insufficient_permissions`.
2. Update validation endpoint to set status based on permission completeness.
3. Ensure downstream workflows respect degraded/insufficient states.
4. Update UI labels and operator guidance for new states.
5. Ensure control-plane readiness and related status checks are derived from the customer tenant/account/region scope, not SaaS-owner AWS account stack state.

**Code touchpoints**
- `backend/routers/aws_accounts.py`
- account status model/enum definitions
- frontend account status display components

**Validation**
- API tests for each status transition path.
- UI tests ensure warning/insufficient states are not shown as healthy.
- Regression tests confirm one tenant/account readiness cannot be satisfied by unrelated SaaS-account infrastructure state.

**Acceptance criteria**
- Account status accurately reflects real capability and risk.

### IMP-004: Signup returns raw exception details

**Implementation actions**
1. Replace `detail=str(e)` with generic client-safe error response.
2. Generate correlation/error ID in response for support.
3. Log full stack context server-side only.
4. Add consistent error translation utility for auth routes.

**Code touchpoints**
- `backend/routers/auth.py`
- shared error handling utilities/middleware

**Validation**
- Unit test confirms internal exception message is never returned in HTTP body.
- Log assertion test includes correlation ID linkage.

**Acceptance criteria**
- Client responses are sanitized while preserving debugging traceability.

### IMP-005: CORS setup ignores config settings

**Implementation actions**
1. Replace hardcoded origin list with `settings.cors_origins_list`.
2. Add startup guard for empty/invalid CORS config in non-local env.
3. Document environment-specific CORS configuration.

**Code touchpoints**
- `backend/main.py`
- `backend/config.py`

**Validation**
- Config parsing tests for CSV/list formats.
- Integration test for allowed and denied origins.

**Acceptance criteria**
- Production CORS behavior is config-driven and validated at startup.

### IMP-007: CI/test posture is thin and dependency bounds are loose

**Implementation actions**
1. Add backend API test workflow (unit + integration).
2. Add worker test workflow for queue handlers and contract checks.
3. Add frontend test workflow (unit + minimal E2E smoke).
4. Add dependency lock strategy and update policy.
5. Add SCA/dependency vulnerability scanning in CI.

**Code touchpoints**
- `.github/workflows/`
- `backend/requirements*.txt` or lock artifacts
- `worker/requirements*.txt` or lock artifacts
- frontend test config files

**Validation**
- CI pipeline runs full test matrix on PRs.
- Dependency scanner fails builds on high-severity vulnerabilities.

**Acceptance criteria**
- Regression and supply-chain drift risks are actively controlled.

### IMP-008: Oversized routers require service-layer refactor

**Implementation actions**
1. Extract orchestration/business logic from routers into domain services.
2. Standardize domain error types and API translation.
3. Keep routers thin: auth, input validation, response mapping only.
4. Add contract tests per endpoint group before/after refactor.

**Code touchpoints**
- `backend/routers/internal.py`
- `backend/routers/aws_accounts.py`
- new/existing service modules

**Validation**
- No API contract regressions in endpoint contract tests.
- Reduced router complexity metrics (function size/cyclomatic complexity).

**Acceptance criteria**
- Router code is maintainable and lower-risk to modify.

### IMP-009: Missing tenant isolation regression tests

**Implementation actions**
1. Add tenant isolation test suite for mutable compliance artifacts.
2. Add negative authorization tests for cross-tenant access/mutation.
3. Tie tests to CI required checks.
4. Add fixture strategy for multi-tenant scenarios.

**Code touchpoints**
- backend test directories under `tests/`
- authorization and compliance pack test fixtures

**Validation**
- Tests fail on any cross-tenant mutation/access regression.

**Acceptance criteria**
- Tenant isolation assumptions are continuously enforced in automation.

## Milestones

- Milestone I1 (end Phase 1): `IMP-001` and `IMP-004` complete.
- Milestone I2 (end Phase 2): `IMP-003` and `IMP-005` complete.
- Milestone I3 (end Phase 3): `IMP-007`, `IMP-008`, and `IMP-009` complete.

## Workstream Sign-Off Criteria

1. Tenant integrity is enforced by schema, authorization logic, and tests.
2. API behavior is client-safe and operationally truthful.
3. CI gates and dependency controls are mandatory and measurable.
4. Refactor outcomes improve maintainability without functional regression.
