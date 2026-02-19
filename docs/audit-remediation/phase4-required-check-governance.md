# Phase 4 Required Check Governance

This document defines the final required-check matrix and branch-protection baseline for `main` as part of Phase 4 regression guardrails.

Related docs:
- [Program Plan](00-program-plan.md)
- [Priority Backlog](01-priority-backlog.md)
- [CI/CD Pipeline Setup](../deployment/ci-cd.md)
- [CI Dependency Governance Policy](../deployment/ci-dependency-governance.md)

## Final Required Check Matrix

Mark the following status checks as **required** on `main`:

| Domain | Required Check Context | Workflow Source |
| --- | --- | --- |
| Backend | `Backend CI Matrix / Backend Required Gate` | `.github/workflows/backend-ci.yml` |
| Worker | `Worker CI Matrix / Worker Required Gate` | `.github/workflows/worker-ci.yml` |
| Frontend | `Frontend CI Matrix / Frontend Required Gate` | `.github/workflows/frontend-ci.yml` |
| Security | `Security Phase 3 Cookie Auth and Edge Controls / Phase 3 Security Tests` | `.github/workflows/security-phase3.yml` |
| Architecture | `Architecture Phase 2 Reliability / Architecture Phase 2 Required Gate` | `.github/workflows/architecture-phase2.yml` |
| Architecture | `Architecture Phase 3 Readiness and DR / Phase 3 Architecture Tests` | `.github/workflows/architecture-phase3.yml` |
| Accessibility | `Frontend Accessibility CI / Accessibility Gate` | `.github/workflows/frontend-accessibility.yml` |
| Dependency Scans and Policy | `Dependency Governance / Dependency Governance Required Gate` | `.github/workflows/dependency-governance.yml` |
| Database Migration Safety | `Migration Gate / Migration Gate` | `.github/workflows/migration-gate.yml` |

## Branch Protection Baseline (`main`)

Configure branch protection (or ruleset enforcement) with:

1. Require a pull request before merge.
2. Require approvals before merge.
3. Require conversation resolution before merge.
4. Require status checks to pass before merge.
5. Enable the required status checks from the matrix above.
6. Restrict direct pushes to `main`.

## Configuration Guidance

### GitHub UI Path

Use **Settings > Branches > Branch protection rules > Add/Edit rule** for `main`, then enable the baseline controls and required checks from this document.

### CLI Snapshot and Validation

Use GitHub CLI to capture and review current protection settings:

```bash
gh api \
  repos/<YOUR_GITHUB_ORG>/<YOUR_GITHUB_REPO>/branches/main/protection \
  > docs/audit-remediation/evidence/<YOUR_TIMESTAMP>-main-branch-protection.json
```

`<YOUR_GITHUB_ORG>`, `<YOUR_GITHUB_REPO>`, and `<YOUR_TIMESTAMP>` are environment-specific values and must be set by the repository owner running the command.

## Current Phase 4 Verification Status (2026-02-18)

- Gate status: `Not Closed`.
- Closure condition 1 status: `Not Satisfied` (live branch-protection proof for required-check matrix/baseline enforcement on `main` is not available).
  - Evidence: `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase4-main-branch-protection-summary-20260218T012807Z.md`
  - Assessment in that artifact: required-check and baseline controls are all `Fail`; `origin` is missing, `gh auth status` is invalid, and live GitHub branch-protection settings could not be retrieved.
- Closure condition 2 status: `Not Satisfied` (final leadership residual-risk `Approve`/`Reject` artifact with required fields is missing).
  - Evidence: `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase4-leadership-signoff-request-20260218T011355Z.md`
  - Current artifact is a blocked request (`decision=Blocked`) with placeholder `owner_arn`/`owner_name`; final `Approve`/`Reject` decision artifact with `owner_arn`, `owner_name`, `decision_timestamp_utc`, `scope`, and `evidence_basis` is still required.

> ❓ Needs verification: After the first PR run with these workflow updates, do the status check context names in GitHub exactly match the matrix values above?
