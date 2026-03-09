# Features Documentation

This folder now serves as the active entrypoint for feature-level documentation.

## Current status

The previous Wave-2 feature inventory outputs were historical snapshots and have been moved to:

- `/Users/marcomaher/AWS Security Autopilot/docs/archive/2026-02-doc-cleanup/features/`

See archive index:

- [`docs/archive/2026-02-doc-cleanup/README.md`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/archive/2026-02-doc-cleanup/README.md)

## Current implementation truth

For live implementation behavior, use:

- Backend route source: `/Users/marcomaher/AWS Security Autopilot/backend/routers/`
- Frontend API client contracts: `/Users/marcomaher/AWS Security Autopilot/frontend/src/lib/api.ts`
- Live execution tracker/runbook:
  - [`docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md)
  - [`docs/live-e2e-testing/live-saas-e2e-tracker-runbook.md`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/live-saas-e2e-tracker-runbook.md)

## Feature docs

- [Root-key remediation lifecycle UI](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/root-key-remediation-lifecycle-ui.md)
- [Communication + Governance layer](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/communication-governance-layer.md)
- [Shared Security + Engineering execution guidance](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/shared-execution-guidance.md)
- [Handoff-free closure](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/handoff-free-closure.md)
- [Secret migration connectors](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/secret-migration-connectors.md)

## Notes

If a new feature inventory snapshot is generated later, place it in a dated archive folder and add a short index note rather than treating it as evergreen API contract documentation.
