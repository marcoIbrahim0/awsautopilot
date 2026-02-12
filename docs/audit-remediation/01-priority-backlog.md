# Audit Remediation Backlog and Traceability

## Priority Model

- `P0` = immediate containment / critical risk (start now)
- `P1` = high-priority production risk
- `P2` = recommendation/maturity work

## Backlog Operating Model

Each backlog item is managed as a controlled remediation ticket with these required fields:
- `ID`
- `Owner`
- `Status` (`Not Started`, `In Progress`, `Blocked`, `Ready for Review`, `Done`)
- `Target Phase`
- `Target Completion Date`
- `Linked PR(s)`
- `Test Evidence`
- `Operational Evidence` (alarms, dashboards, runbooks where relevant)
- `Risk Disposition` (`Resolved`, `Accepted`, `Deferred with date`)

## Execution Rules

1. `P0` items start immediately and cannot be displaced by `P1` or `P2`.
2. No item is marked complete without test evidence and owner sign-off.
3. `Blocked` items require explicit unblock owner and resolution date.
4. Any `Critical` or `High` item delayed beyond phase target requires written risk acceptance by engineering and security leads.

## Expected Outputs by Phase

| Phase | Backlog Objective | Expected Output | Required Evidence |
| --- | --- | --- | --- |
| Phase 0 | Immediate containment | Fail-closed startup controls and secret hygiene containment in place | Config validation tests, security sign-off, rotation records |
| Phase 1 | Close critical findings | All `Critical` IDs moved to `Done` with remediation artifacts | PR links, integration tests, runbooks, architecture/security approval |
| Phase 2 | Close high-priority risk | High-impact reliability/security/UX behavior corrected in production | Load tests, alarm inventory, E2E tests, operational readiness sign-off |
| Phase 3 | Maturity and compliance | Medium recommendations implemented with audit-quality evidence | DR drill artifacts, a11y reports, expanded CI evidence, compliance review |
| Phase 4 | Regression prevention | Controls institutionalized in SDLC and release process | Required CI gates, branch protections, final closure report |

## Reporting Cadence and Deliverables

| Cadence | Deliverable | Audience | Format |
| --- | --- | --- | --- |
| Daily | Critical/High status and blocker report | Engineering leads, security lead | Short status summary with open blockers |
| Weekly | Backlog burndown and phase health | Engineering, product, operations | Updated table plus risk commentary |
| Bi-weekly | Audit evidence pack delta | Compliance/security stakeholders | Evidence index with links to artifacts |
| Phase close | Formal phase gate review | Leadership + domain owners | Sign-off checklist and residual risk record |

## Normalized Remediation Backlog

| ID | Domain | Severity | Impact | Effort | Priority | Target Phase | Summary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ARC-001 | Architecture | Critical | Scalability | M | P0 | Phase 1 | Poison/invalid messages are deleted instead of quarantined or redriven. |
| ARC-002 | Architecture | High | Scalability | M | P1 | Phase 2 | `WORKER_POOL=all` polling is serialized and causes head-of-line blocking. |
| ARC-003 | Architecture | High | Scalability | L | P1 | Phase 2 | Global reconcile fan-out executes synchronously in API request path. |
| ARC-004 | Architecture | High | Compliance | M | P1 | Phase 2 | EventBridge API Destination targets lack explicit DLQ/retry policies. |
| ARC-005 | Architecture | High | Scalability | S | P1 | Phase 2 | Queue alarming only covers inventory queue metrics. |
| ARC-006 | Architecture | High | Cost | M | P1 | Phase 2 | Export/report workloads compete with ingest traffic on same queue. |
| ARC-007 | Architecture | Medium | Scalability | M | P1 | Phase 2 | Queue payloads have no versioning/compatibility contract. |
| ARC-008 | Architecture | Medium | Compliance | L | P2 | Phase 3 | HA/DR architecture, RTO/RPO, and restore testing are undocumented/unknown. |
| ARC-009 | Architecture | Medium | Compliance | S | P2 | Phase 3 | `/health` does not validate DB/SQS readiness dependencies. |
| SEC-001 | Security | Critical | Security | M | P0 | Phase 1 | DB TLS verification and hostname checks are disabled. |
| SEC-002 | Security | Critical | Security | S | P0 | Phase 1 | `ENV` default allows fail-open local auth behavior when omitted. |
| SEC-003 | Security | Critical | Security | M | P0 | Phase 1 | Assumed read/write role policies include broad IAM delete on `*`. |
| SEC-004 | Security | Critical | Compliance | M | P0 | Phase 1 | Repo tracks `.env`, lacks root `.gitignore`, and includes artifact footprints. |
| SEC-005 | Security | High | Security | M | P1 | Phase 2 | Control-plane token stored plaintext and exposed in UI without rotation flow. |
| SEC-006 | Security | High | Security | M | P1 | Phase 2 | Internal endpoints use static shared secrets; scheduler secret can fall back. |
| SEC-007 | Security | High | Security | S | P0 | Phase 1 | JWT secret has insecure default and no non-local startup guard. |
| SEC-008 | Security | High | Security | L | P1 | Phase 3 | Browser auth token is persisted in `localStorage` (XSS exfil risk). |
| SEC-009 | Security | Medium | Security | S | P0 | Phase 1 | Fail-closed startup validators are incomplete for env + secret controls. |
| SEC-010 | Security | Medium | Security | M | P2 | Phase 3 | Edge protections (WAF/rate limits/IP constraints) are unknown in IaC/docs. |
| IMP-001 | Implementation | Critical | Compliance | M | P0 | Phase 1 | Global control mappings are mutable by tenant admins (cross-tenant risk). |
| IMP-003 | Implementation | High | Compliance | M | P1 | Phase 2 | Account status can be marked `validated` with missing permissions. |
| IMP-004 | Implementation | High | Security | S | P0 | Phase 1 | Signup endpoint returns raw exception text to clients. |
| IMP-005 | Implementation | High | UX | S | P1 | Phase 2 | CORS middleware ignores configurable settings values. |
| IMP-007 | Implementation | High | Compliance | M | P1 | Phase 3 | Test/CI coverage is thin and dependency versions are loosely bounded. |
| IMP-008 | Implementation | Medium | Scalability | L | P2 | Phase 3 | Oversized routers need service-layer extraction and domain error consistency. |
| IMP-009 | Implementation | Medium | Compliance | M | P2 | Phase 3 | Missing tenant isolation regression tests for mutable shared artifacts. |
| UX-001 | UX | Critical | UX | S | P0 | Phase 1 | Evidence export and baseline report views are unreachable in Settings nav. |
| UX-002 | UX | High | UX | S | P1 | Phase 2 | "Validate Read Role" action is a no-op with misleading affordance. |
| UX-004 | UX | High | Compliance | M | P1 | Phase 3 | Accessibility readiness is unknown; no automated a11y verification in CI. |
| UX-005 | UX | Medium | UX | M | P2 | Phase 3 | Onboarding flow delays time-to-value with strict sequential checks. |
| UX-006 | UX | Medium | UX | S | P2 | Phase 2 | Settings tab state is local-only and not URL/deep-link stable. |

## Shared Findings (Intentionally Merged)

| Shared Area | Canonical ID(s) | Duplicate Source Findings Covered |
| --- | --- | --- |
| Unreachable Settings report tabs | UX-001 | Implementation High #1 and UX Critical #1 |
| Queue contract drift and unknown payload handling | ARC-001, ARC-007 | Architecture Critical #1 and Implementation High #5 |
| Control-plane token exposure and onboarding handling | SEC-005 | Security High #1 and UX High #2 |
| Environment/secret fail-closed startup controls | SEC-002, SEC-007, SEC-009 | Security Critical #2 and Security Recommendations #1 |

## Traceability Matrix (Source Finding -> Plan ID)

### AWS Architecture Review

| Source Finding | Mapped Plan ID(s) |
| --- | --- |
| Critical #1 Poison-message bypasses DLQ | ARC-001 |
| High #1 `WORKER_POOL=all` serialized polling | ARC-002 |
| High #2 Reconcile fan-out in API path | ARC-003 |
| High #3 EventBridge target DLQ/retry missing | ARC-004 |
| High #4 Queue alarm coverage incomplete | ARC-005 |
| High #5 Export/report jobs share ingest queue | ARC-006 |
| Recommendation #1 Queue payload versioning strategy missing | ARC-007 |
| Recommendation #2 HA/DR posture unknown | ARC-008 |
| Recommendation #3 Health/SLO dependency checks | ARC-009 |

### Security Review

| Source Finding | Mapped Plan ID(s) |
| --- | --- |
| Critical #1 DB TLS verification disabled | SEC-001 |
| Critical #2 `ENV` defaults local and can fail open | SEC-002, SEC-009 |
| Critical #3 Broad IAM delete in assumed roles | SEC-003 |
| Critical #4 Repo hygiene and secret risk | SEC-004 |
| High #1 Plaintext control-plane token and UI exposure | SEC-005 |
| High #2 Shared static internal secrets | SEC-006 |
| High #3 Insecure JWT default | SEC-007, SEC-009 |
| High #4 Auth token in localStorage | SEC-008 |
| Recommendation #1 Fail-closed startup controls | SEC-009 |
| Recommendation #2 Edge protections unknown | SEC-010 |

### Implementation and Code Review

| Source Finding | Mapped Plan ID(s) |
| --- | --- |
| Critical #1 Global control mappings writable by tenant admin | IMP-001 |
| High #1 Settings views unreachable | UX-001 |
| High #2 Account validation status mismatch | IMP-003 |
| High #3 Signup leaks raw exception detail | IMP-004 |
| High #4 CORS config ignores settings | IMP-005 |
| High #5 Queue contract drift brittle | ARC-001, ARC-007 |
| High #6 Thin CI/tests and loose deps | IMP-007 |
| Recommendation #1 Oversized router refactor | IMP-008 |
| Recommendation #2 Tenant isolation regression tests | IMP-009 |

### UX Review

| Source Finding | Mapped Plan ID(s) |
| --- | --- |
| Critical #1 Settings report paths unreachable | UX-001 |
| High #1 Validate Read Role is no-op | UX-002 |
| High #2 Manual secret handling and token visibility | SEC-005 |
| High #3 Accessibility readiness unknown | UX-004 |
| Recommendation #1 Faster onboarding time-to-value | UX-005 |
| Recommendation #2 URL state persistence for Settings | UX-006 |

## Milestone Checklist

- [ ] Phase 0 complete (all `P0` containment controls shipped and verified)
- [ ] Phase 1 complete (all critical IDs complete)
- [ ] Phase 2 complete (all high IDs complete)
- [ ] Phase 3 complete (all medium recommendation IDs complete)
- [ ] Phase 4 complete (regression guardrails and evidence package finalized)

## Formal Closure Criteria

A backlog item is `Done` only when all are true:
1. Code change merged and deployed to target environment.
2. Automated tests prove the prior failure mode is prevented.
3. Monitoring/runbook updates are completed where operationally relevant.
4. Domain owner confirms acceptance criteria are met.
5. Traceability from source finding to evidence is intact in this document set.
