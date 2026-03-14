# Live SaaS E2E Testing Docs (Consolidated)

This folder contains the full documentation set used for tracker-driven live SaaS E2E execution.

> ⚠️ Local evidence note (March 14, 2026): `docs/test-results/live-runs/` was deleted from this workspace to reclaim disk space. Historical run links below may no longer resolve locally; use `.cursor/notes/task_log.md` and `.cursor/notes/task_index.md` for retained run summaries.

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

## Recent Targeted Runs

- [Remediation-profile Wave 2 focused local validation on March 14, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260314T144353Z-rem-profile-wave2-e2e/notes/final-summary.md) — partial local proof: all targeted Wave 2 API contracts passed on `codex/rem-profile-w2-integrate`, including options/preview profile metadata, create-time canonical `artifacts.resolution`, legacy run hydration, duplicate guard, direct-fix regression smoke, auth boundaries, and remediation-settings influence, but the local `/actions/[id]` UI route hit an `ActionDetailDrawer` hydration mismatch that blocked visual remediation-options/remediation-preview validation and kept the gate decision at `stop for fixes`.
- [Phase 3 P2 grouped-action + UI closure validation on March 12, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260312T165611Z-phase3-p2-grouped-fix-validation/notes/final-summary.md) — PASS: the remaining March 12 P2 blockers are now closed on production. The filtered grouped findings API maps the trusted synthetic Config finding to the correct action, standard recompute succeeds, no synthetic actions remain open after recompute, and the live drawer visibly renders `Threat-intel provenance`, `CVE-2026-9001`, `CISA KEV`, confidence, applied points, and decay.
- [Phase 3 P2 live rerun on March 12, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260312T152625Z-phase3-p2-live-rerun/notes/final-summary.md) — partial live proof: the rerun’s synthetic findings proved the core `P2.1` weighting and `P2.2` decay/provenance API contracts on production, and the fresh Playwright session showed all six synthetic actions plus a trusted-config action drawer at `Priority 26`, but the human-readable `exploit_signals` explanation is inaccurate on the trusted-config case, UI provenance is not surfaced, the standard recompute still fails on the production security-graph defect, and post-cleanup app state still retained `4` archived synthetic actions.
- [Phase 3 P2 live validation on March 12, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260312T143138Z-phase3-p2-live/notes/final-summary.md) — blocked at the threat-intel candidate gate: the live tenant currently has only `7` configuration-style Security Hub findings and `6` config remediation actions, none of the inspected action details exposes the P2 threat-intel or provenance fields, and AWS-side vulnerability/threat-intel scenarios are required before `P2.1` or `P2.2` can be positively validated.
- [Phase 3 P1 post-deploy validation on March 12, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260312T021444Z-phase3-p1-postdeploy/notes/final-summary.md) — PASS for the previously missing live P1 contract surface: both Lambdas now run image tag `20260312T020548Z`, the live DB now reports both `0042` heads, `graph_context` / `business_impact` / `recommendation` are live, repo-aware PR artifacts now generate successfully, and only full P1.6 drift reconciliation remains blocked by the tenant having no configured test provider.
- [Phase 3 P1 live validation on March 12, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260312T013435Z-phase3-p1-live/notes/final-summary.md) — `NO` for full live validation right now: only the externally observable P1.4 rejection behavior passed; P1.1/P1.2/P1.3/P1.5/P1.7/P1.8 failed on missing live contracts or artifacts, and P1.6 was blocked because the integration/sync surface is absent on the deployed runtime.
- [P0.8 PR-only live validation on March 11, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T231949Z-p0-8-pr-only-live/notes/final-summary.md) — PASS: created live PR-only remediation run `88e08e11-0b86-4f7d-bf4e-fd24a5870ad1` for action `0ca64b94-9dcb-4a97-91b0-27b0341865bc`, run completed `success`, action detail now exposes executable `implementation_artifacts[]`, and run detail exposes populated `artifact_metadata` plus closure/evidence metadata without using `WriteRole`.
- [P0.3 post-deploy live validation on March 11, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T224012Z-p0-3-postdeploy-validation/notes/final-summary.md) — PASS: backend and worker redeployed from tag `20260311T181012Z` to `20260311T224136Z`, scoped backfill/recompute updated `26` live findings, both target findings now show complete `relationship_context`, and anchor action `442e46ac-f31c-4242-82ca-9e47081a3adb` shows a live toxic-combination boost from `69` to `84`.
- [P0.3 relationship-context producer-path validation on March 11, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T223155Z-p0-3-relationship-context-validation/notes/final-summary.md) — blocked early: scoped dry-run proved `26` live findings are in scope for backfill, but both live Lambdas still run image tag `20260311T181012Z`, which predates the March 12 producer-path implementation, so no live backfill/recompute was executed.
- [Phase 3 P0 live validation on March 11, 2026](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260311T215615Z-phase3-p0-live/notes/final-summary.md) — partial validation on live prod: `P0.1`, `P0.2`, `P0.4`, `P0.5`, `P0.6`, and `P0.7` passed; `P0.3` and `P0.8` were not testable from current live data; supplied browser password was rejected on live.

Generate a new run scaffold with:

```bash
bash scripts/init_live_e2e_run.sh
```
