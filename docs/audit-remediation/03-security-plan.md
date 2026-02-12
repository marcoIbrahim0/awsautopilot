# Security Hardening Remediation Plan

## Scope

This workstream covers backlog IDs `SEC-001` through `SEC-010`.

## Workstream Outcomes

This plan must deliver:
- Fail-closed runtime security posture for environment, secrets, and transport.
- Strict least-privilege and segmented trust boundaries across internal and cross-account controls.
- Secure token/session lifecycle for both backend and frontend surfaces.
- Auditable edge and repository controls that meet compliance scrutiny.

## Sequencing

1. `SEC-001`, `SEC-002`, `SEC-007`, `SEC-009` are immediate fail-closed controls.
2. `SEC-003` and `SEC-004` close high blast-radius and auditability risks.
3. `SEC-005` and `SEC-006` harden internal and control-plane trust boundaries.
4. `SEC-008` and `SEC-010` complete browser/edge defense-in-depth.

## Delivery Plan by Phase

| Phase | In-Scope IDs | Expected Outputs |
| --- | --- | --- |
| Phase 0/1 | `SEC-001`, `SEC-002`, `SEC-003`, `SEC-004`, `SEC-007`, `SEC-009` | Fail-closed startup and TLS posture, least-privilege runtime roles, repository secret-hygiene controls |
| Phase 2 | `SEC-005`, `SEC-006` | Secure control-plane token lifecycle and segmented internal secret model |
| Phase 3 | `SEC-008`, `SEC-010` | Cookie-based auth posture and explicit edge protections in IaC/runbooks |

## Deliverable and Evidence Matrix

| ID | Primary Deliverable | Expected Output | Evidence Required |
| --- | --- | --- | --- |
| SEC-001 | Verified DB TLS configuration | Production DB connections enforce certificate and hostname validation | TLS config tests, staging validation logs |
| SEC-002 | Explicit environment mode enforcement | No accidental fall-open local auth behavior in deployed environments | Config validation tests, startup failure proof |
| SEC-003 | Least-privilege role policy redesign | Removal of overbroad destructive IAM actions from assumed runtime roles | IAM diff review, security approval record |
| SEC-004 | Repository hygiene and secret control hardening | Secrets/artifacts excluded, scanning enforced, rotations complete | Secret scan report, `.gitignore`, rotation completion list |
| SEC-005 | Hashed token storage and one-time reveal/rotate flow | No persistent plaintext token visibility in DB or UI | Migration proof, API/UI tests, audit log samples |
| SEC-006 | Secret segmentation for internal endpoints | One secret class compromise cannot unlock unrelated flows | Endpoint auth tests, rotation drill report |
| SEC-007 | Strong JWT secret policy enforcement | Startup fails on weak/default secret in non-local environments | Config tests, deployment smoke verification |
| SEC-008 | Secure cookie-based browser auth | Browser no longer stores bearer token in `localStorage` | Frontend tests, E2E session flow evidence |
| SEC-009 | Centralized startup validation controls | Misconfiguration blocked before serving traffic | Startup test matrix, error log examples |
| SEC-010 | Edge protections in architecture and IaC | WAF/rate limiting/IP policy controls are explicit and auditable | IaC deployment output, runbook + dashboard links |

## Detailed Plan

### SEC-001: DB TLS verification disabled

**Implementation actions**
1. Remove `ssl.CERT_NONE` and hostname bypass from `backend/database.py`.
2. Enforce CA trust chain and hostname verification in non-local environments.
3. Fail startup if required TLS settings are missing or invalid outside local mode.
4. Document local-dev override behavior separately from staging/prod defaults.

**Validation**
- Unit tests for TLS config validation.
- Staging connection test with valid certificate chain.
- Negative test proving startup fails on invalid cert/hostname.

**Acceptance criteria**
- Production DB traffic uses verified TLS with hostname checks enabled.

### SEC-002: `ENV` default can fail open

**Implementation actions**
1. Remove implicit `ENV=local` default from production code path.
2. Require explicit environment value with allowlist validation.
3. Block startup for unknown/missing env in deployed environments.
4. Remove unauthenticated tenant fallback when not explicitly local-dev.

**Validation**
- Config tests for missing/invalid `ENV`.
- Endpoint tests proving fallback is impossible outside explicit local mode.

**Acceptance criteria**
- Runtime cannot accidentally enter local-auth semantics in production.

### SEC-003: Overbroad IAM delete permissions in assumed roles

**Implementation actions**
1. Remove cleanup IAM delete actions from customer-assumed read/write runtime roles.
2. Move cleanup-only permissions to dedicated deployment/custom-resource role.
3. Scope all permissions to explicit resources and narrow conditions.
4. Re-run least-privilege review with action/resource matrix.

**Validation**
- Policy diff review showing removal of wildcard delete from assumed roles.
- Integration tests for expected read/write workflows after policy tightening.

**Acceptance criteria**
- Assumed runtime roles no longer contain unnecessary destructive IAM permissions.

### SEC-004: Repo hygiene and secret exposure risk

**Implementation actions**
1. Add root `.gitignore` for `.env`, virtualenvs, caches, and artifacts.
2. Remove tracked secrets/artifacts from current tree.
3. Rotate any credentials found in tracked files.
4. Add pre-commit hooks for secret scanning and dependency checks.
5. Add CI secret scanning and block merges on findings.
6. Plan controlled history rewrite for already-committed sensitive material.

**Validation**
- Secret scanner returns clean on current branch.
- CI blocks reintroduction of `.env` and artifact patterns.

**Acceptance criteria**
- Repository state and automation prevent recurrence of secret/artifact leaks.

### SEC-005: Control-plane token plaintext storage and UI exposure

**Implementation actions**
1. Replace plaintext token column with hashed fingerprint storage.
2. Implement one-time token reveal flow at creation/regeneration only.
3. Add rotate/revoke endpoint and UI path.
4. Remove persistent token display from onboarding/settings.
5. Add audit logs for token generation and rotation events.

**Validation**
- DB does not store recoverable token values.
- UI never displays existing token after initial creation event.

**Acceptance criteria**
- Token compromise window and exposure surface are significantly reduced.

### SEC-006: Shared static internal secrets and fallback reuse

**Implementation actions**
1. Separate secrets per internal endpoint class.
2. Remove scheduler fallback to control-plane secret.
3. Add independent rotation schedule and expiry metadata per secret.
4. Prefer SigV4 or mTLS for service-to-service invocations where feasible.

**Validation**
- Endpoint tests confirm wrong secret class is rejected.
- Rotation drill shows isolated secret replacement does not break other paths.

**Acceptance criteria**
- Compromise of one secret cannot unlock unrelated internal workflows.

### SEC-007: Insecure JWT secret default

**Implementation actions**
1. Remove placeholder default JWT secret.
2. Enforce minimum secret entropy/length in non-local environments.
3. Fail startup when secret is missing, weak, or known placeholder.

**Validation**
- Config tests for weak/default JWT secret rejection.
- Deployment smoke test verifies explicit strong secret requirement.

**Acceptance criteria**
- JWT signing key cannot silently use insecure defaults in production.

### SEC-008: Auth token in `localStorage`

**Implementation actions**
1. Migrate browser auth to secure `HttpOnly`, `Secure`, `SameSite` cookies.
2. Add CSRF protections for state-changing endpoints.
3. Remove token storage/read logic from `AuthContext.tsx` and API helper.
4. Add CSP hardening and document XSS threat assumptions.

**Validation**
- Frontend tests verify no auth token remains in `localStorage`.
- E2E auth flow tests pass with cookie-based session behavior.

**Acceptance criteria**
- Bearer token exfil risk via browser JS storage is removed.

### SEC-009: Missing fail-closed startup validators

**Implementation actions**
1. Add centralized startup validation routine.
2. Validate `ENV`, JWT secret strength, internal secret segregation, and TLS config.
3. Emit explicit structured startup errors and fail process on invalid state.
4. Add operator docs listing required env vars per environment.

**Validation**
- Startup test matrix covers local/staging/prod.
- Invalid config causes deterministic startup failure.

**Acceptance criteria**
- Misconfiguration is blocked at startup, not discovered at runtime.

### SEC-010: Edge protections unknown in IaC/docs

**Implementation actions**
1. Add edge architecture doc: API exposure path, WAF policies, rate limits, IP controls.
2. Add corresponding IaC resources for WAF/rate-limit where applicable.
3. Add runbooks for incident response on abusive traffic.
4. Add dashboard and alerts for edge-level blocked/allowed anomalies.

**Validation**
- IaC deploy includes explicit edge protections.
- Security runbook links to operational metrics and response steps.

**Acceptance criteria**
- Public endpoint protections are explicit, auditable, and reproducible.

## Milestones

- Milestone S1 (end Phase 1): `SEC-001`, `SEC-002`, `SEC-003`, `SEC-004`, `SEC-007`, `SEC-009` complete.
- Milestone S2 (end Phase 2): `SEC-005` and `SEC-006` complete.
- Milestone S3 (end Phase 3): `SEC-008` and `SEC-010` complete with rollout docs and tests.

## Workstream Sign-Off Criteria

1. No known security-critical control depends on insecure defaults.
2. Runtime trust boundaries are segmented and least-privilege principles are verifiable.
3. Token/session handling is secure by design in both backend and browser contexts.
4. Security controls are supported by repeatable evidence suitable for external audit review.
