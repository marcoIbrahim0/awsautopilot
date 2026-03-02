# Live SaaS E2E Testing Docs (Consolidated)

This folder contains the full documentation set used for tracker-driven live SaaS E2E execution.

## Files in this Folder

- `00-BASE-ISSUE-TRACKER.md` — Primary issue tracker and go-live gate source of truth
- `live-saas-e2e-tracker-runbook.md` — End-to-end testing runbook (Wave 1 to Wave 9; Tests 01 to 35)
- `post-test-logical-solutions-backlog.md` — Control-family implementation backlog template for post-test logical-solution planning
- `root-key-safe-remediation-spec.md` — Planned root-key safe remediation state machine, API contract, data model, and acceptance tests
- `root-key-safe-remediation-acceptance-matrix.md` — MVP/Safe Rollout/GA gate matrix with pass/fail and evidence requirements
- `root-key-safe-remediation-implementation-checklist.md` — Serial implementation slices for the root-key safe remediation plan
- `test-results-workspace.md` — Evidence and artifact storage standard for each run
- `test-case-template.md` — Per-test template (preconditions, API/UI evidence, assertions, tracker mapping)
- `wave-summary-template.md` — Per-wave summary template (counts, severity, gate updates)

## Supporting Runtime Folder

Execution outputs are stored in:

- `../test-results/live-runs/<RUN_ID>/`

Generate a new run scaffold with:

```bash
bash scripts/init_live_e2e_run.sh
```
