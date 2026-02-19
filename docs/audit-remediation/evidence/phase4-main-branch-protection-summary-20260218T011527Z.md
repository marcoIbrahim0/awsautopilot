# Phase 4 Main Branch Protection Summary (20260218T011527Z)

Generated at: 2026-02-18T01:15:27Z

## Snapshot Outcome

- Repository owner/name from git remote: **Blocked** (`git remote -v` returned no remotes).
- GitHub API branch-protection snapshot for `main`: **Blocked**.
- Raw snapshot artifact: `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase4-main-branch-protection-20260218T011527Z.json`
- Blocked command transcript: `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase4-main-branch-protection-blocked-20260218T011527Z.txt`

## Required Check Matrix Assessment (Pass/Fail)

| Domain | Required Check Context | Result | Notes |
| --- | --- | --- | --- |
| Backend | `Backend CI Matrix / Backend Required Gate` | Fail | Blocked: live branch-protection settings not retrievable. |
| Worker | `Worker CI Matrix / Worker Required Gate` | Fail | Blocked: live branch-protection settings not retrievable. |
| Frontend | `Frontend CI Matrix / Frontend Required Gate` | Fail | Blocked: live branch-protection settings not retrievable. |
| Security | `Security Phase 3 Cookie Auth and Edge Controls / Phase 3 Security Tests` | Fail | Blocked: live branch-protection settings not retrievable. |
| Architecture | `Architecture Phase 2 Reliability / Architecture Phase 2 Required Gate` | Fail | Blocked: live branch-protection settings not retrievable. |
| Architecture | `Architecture Phase 3 Readiness and DR / Phase 3 Architecture Tests` | Fail | Blocked: live branch-protection settings not retrievable. |
| Accessibility | `Frontend Accessibility CI / Accessibility Gate` | Fail | Blocked: live branch-protection settings not retrievable. |
| Dependency Scans and Policy | `Dependency Governance / Dependency Governance Required Gate` | Fail | Blocked: live branch-protection settings not retrievable. |
| Database Migration Safety | `Migration Gate / Migration Gate` | Fail | Blocked: live branch-protection settings not retrievable. |

## Branch Protection Baseline Assessment (Pass/Fail)

| Baseline Control | Result | Notes |
| --- | --- | --- |
| Require pull request before merge | Fail | Blocked: could not fetch live protection settings. |
| Require approvals before merge | Fail | Blocked: could not fetch live protection settings. |
| Require conversation resolution before merge | Fail | Blocked: could not fetch live protection settings. |
| Require status checks before merge | Fail | Blocked: could not fetch live protection settings. |
| Required checks configured from matrix | Fail | Blocked: could not fetch live protection settings. |
| Restrict direct pushes to `main` | Fail | Blocked: could not fetch live protection settings. |

> ❓ Needs verification: add a valid GitHub remote in this worktree and re-authenticate GitHub CLI (`gh auth login`) before rerunning the snapshot command.
