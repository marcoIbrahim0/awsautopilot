# Test Results Workspace

This guide defines tracker-driven live SaaS E2E run artifacts.

## Structure

- `../test-results/live-runs/<RUN_ID>/` — One folder per full execution cycle (Wave 1 -> Wave 9)
- `test-case-template.md` — Reusable per-test evidence template
- `wave-summary-template.md` — Reusable per-wave summary template

## Run Initialization

Create a new dated run folder:

```bash
bash scripts/init_live_e2e_run.sh
```

Optional custom run id:

```bash
bash scripts/init_live_e2e_run.sh 20260228T190500Z
```

## Required Evidence per Test

Each test file should include:
- Preconditions (identity, tenant, region, account)
- Steps executed
- API calls (method, path, payload, status)
- UI-visible result and screenshot path
- Final status (`PASS` / `FAIL` / `PARTIAL` / `BLOCKED`)
- Tracker mapping (which section/row was updated)

## Tracker Link

Use `docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md` as the only issue truth source while running live E2E.
