# Live Attack Path Phases 1-4 Run

This folder contains the production-SaaS live campaign for the shipped Attack Path Phases 1-4 surface.

Live targets:

- Frontend: `https://ocypheris.com`
- Backend: `https://api.ocypheris.com`

This is a single combined smoke run with four phase waves. If a phase fails, add narrow rerun evidence in the same run folder and update `notes/final-summary.md`.

## Primary execution files

- [00-run-metadata.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/00-run-metadata.md)
- [phase-1-attack-path-engine.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/phase-1-attack-path-engine.md)
- [phase-2-ranking-and-linking.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/phase-2-ranking-and-linking.md)
- [phase-3-product-surface.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/phase-3-product-surface.md)
- [phase-4-bounded-enterprise-projections.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/phase-4-bounded-enterprise-projections.md)
- [notes/final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260322T000000Z-attack-path-phases-1-4-live/notes/final-summary.md)

## Evidence layout

- `evidence/api/`
- `evidence/ui/`
- `evidence/screenshots/`
- `notes/`

Store browser console dumps for every UI-visible phase assertion. Treat React errors, hydration mismatches, unexpected `404/500`, or contract-shape mismatches as failures unless `notes/final-summary.md` explicitly waives them.

## Execution order

1. Fill in the dataset section in `00-run-metadata.md`.
2. Execute the Phase 1 wave first and lock representative `action_id`, `path_id`, `account_id`, and region values.
3. Reuse the same live path(s) across later phases wherever possible.
4. Update `notes/final-summary.md` after each phase with `PASS`, `FAIL`, `PARTIAL`, or `BLOCKED`.

## Existing generic scaffold

The generated `wave-01` through `wave-09` files remain in this run folder for compatibility with the broader live E2E workspace, but this campaign is driven by the four Attack Path phase files above.
