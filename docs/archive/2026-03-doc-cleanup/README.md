# 2026-03 Documentation Cleanup Archive

This archive preserves documentation that was removed from active navigation during the March 2026 docs cleanup.

## Why these files were archived

- They captured point-in-time planning, brainstorming, or implementation-task state rather than current product behavior.
- Several files had become noisy in the active tree because later docs, code, and runbooks replaced them as the current source of truth.
- Keeping them here preserves project history without advertising them as live operator or developer guidance.

## Archived in this cleanup

### Root planning/spec documents
- `business-plan.md`
- `landing-assets.md`
- `local-terminal-agent-mvp.md`

### Historical phase planning
- `phase-2/`
- `phase-3/todo.md`

## Re-homed instead of archived

These docs remain active, but they were moved into `docs/runbooks/` for cleaner taxonomy:

- `e2e_no_ui_agent_debug_reference.md` -> `docs/runbooks/e2e-no-ui-agent-debug-reference.md`
- `manual-test-use-cases.md` -> `docs/runbooks/manual-test-use-cases.md`

## Current sources of truth

Use these active sources for current behavior:

- Primary docs index: `/Users/marcomaher/AWS Security Autopilot/docs/README.md`
- Runbooks index: `/Users/marcomaher/AWS Security Autopilot/docs/runbooks/README.md`
- Backend routes: `/Users/marcomaher/AWS Security Autopilot/backend/routers/`
- Frontend API contracts: `/Users/marcomaher/AWS Security Autopilot/frontend/src/lib/api.ts`
- Live E2E tracker and runbook:
  - `/Users/marcomaher/AWS Security Autopilot/docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/live-e2e-testing/live-saas-e2e-tracker-runbook.md`

## Notes

- Archived planning docs intentionally preserve historical wording and may still mention their original pre-archive paths.
- Nothing under `/docs/Production/` was changed in this cleanup.
