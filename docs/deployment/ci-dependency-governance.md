# CI Dependency Governance Policy

This document defines the dependency versioning and vulnerability gate policy used by CI.

Related docs:
- [CI/CD Pipeline Setup](ci-cd.md)
- [Owner Deployment Guide](README.md)
- [Local Test Guide](../local-dev/tests.md)

## Required CI Checks

The following GitHub Actions status checks are required for merges to `main`:

1. `Backend CI Matrix / Backend Required Gate`
2. `Worker CI Matrix / Worker Required Gate`
3. `Frontend CI Matrix / Frontend Required Gate`
4. `Security Phase 3 Cookie Auth and Edge Controls / Phase 3 Security Tests`
5. `Architecture Phase 2 Reliability / Architecture Phase 2 Required Gate`
6. `Architecture Phase 3 Readiness and DR / Phase 3 Architecture Tests`
7. `Frontend Accessibility CI / Accessibility Gate`
8. `Dependency Governance / Dependency Governance Required Gate`
9. `Migration Gate / Migration Gate`

Canonical matrix and branch-protection guidance:
- [Phase 4 Required Check Governance](../audit-remediation/phase4-required-check-governance.md)

## Versioning and Lock Policy

### Python services (`backend`, `worker`)

Policy:
- Do not use loose-only minimum bounds (for example `package>=1.0.0` with no upper bound).
- Every requirement must be either:
  - Exact pin (`==`), or
  - Bounded range including an explicit upper bound (`<`), or
  - Compatible release (`~=`).
- Direct URL or VCS dependencies are not allowed in service requirement files.

Implemented in:
- `backend/requirements.txt`
- `worker/requirements.txt`
- `.github/workflows/dependency-governance.yml` (`Dependency Policy` job validation)

### Frontend (`frontend`)

Policy:
- `next`, `react`, and `react-dom` must remain exact version pins in `package.json`.
- `frontend/package-lock.json` is mandatory and must be committed.
- CI installs with `npm ci` (never `npm install`) to enforce lockfile fidelity.
- Wildcard, `latest`, URL-based, and git/file dependency specifiers are disallowed.

Implemented in:
- `frontend/package.json`
- `frontend/package-lock.json`
- `.github/workflows/frontend-ci.yml`
- `.github/workflows/dependency-governance.yml` (`Dependency Policy` job validation)

## Vulnerability Gates

### Python

- Scanner: `pip-audit`
- Scope: `backend/requirements.txt`, `worker/requirements.txt`
- Gate behavior: workflow fails when known vulnerabilities are found.

### Frontend

- Scanner: `npm audit`
- Scope: `frontend/package-lock.json` dependency graph
- Gate behavior: workflow fails on `high` or `critical` vulnerabilities.

## Update Procedure

When updating dependencies:

1. Update bounded ranges in `backend/requirements.txt` and/or `worker/requirements.txt`.
2. For frontend changes, update `frontend/package.json` and regenerate `frontend/package-lock.json`.
3. Run local targeted checks:
   - Backend/worker pytest subsets
   - `npm run lint` and `npm run build` in `frontend`
4. Ensure all required CI checks above pass on the PR.
