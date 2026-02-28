# Live SaaS E2E Testing Docs (Consolidated)

This folder contains the full documentation set used for tracker-driven live SaaS E2E execution.

## Files in this Folder

- `00-BASE-ISSUE-TRACKER.md` — Primary issue tracker and go-live gate source of truth
- `live-saas-e2e-tracker-runbook.md` — End-to-end testing runbook (Wave 1 to Wave 9; Tests 01 to 35)
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
