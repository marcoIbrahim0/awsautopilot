# S3.11 stale-action grouped rerun

Status: `PASS` on April 2-3, 2026 UTC.

This retained package closes the remaining April 1 stale-action reconciliation handoff truthfully for deleted or drifted S3 bucket targets on the live grouped path.

It proves all of the following on a fresh grouped rerun for action group `eefe66d1-91e6-49cd-a27a-5c1afa72557d`:

- historical stale or deleted S3.11 bucket targets no longer survive as misleading executable grouped members
- the fresh grouped bundle contains `0` executable actions, `8` `manual_guidance_only` actions, and `13` `review_required_bundle` actions
- the exact stale bucket names from the April 1 handoff remain represented only as truthful metadata-only members with explicit blocked reasons
- the scoped recompute reliability issue was separate from stale-target handling and is fixed in this pass on the primary database path

Primary retained summary:

- [notes/final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/notes/final-summary.md)

Key evidence:

- [api/create-group-run-request.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/api/create-group-run-request.json)
- [api/create-group-run-response.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/api/create-group-run-response.json)
- [api/group-run-after-local-callback.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/api/group-run-after-local-callback.json)
- [api/remediation-run-after-local-callback.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/api/remediation-run-after-local-callback.json)
- [bundle/pr-bundle.zip](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/bundle/pr-bundle.zip)
- [bundle/inspection-summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/bundle/inspection-summary.json)
- [bundle/extracted/decision_log.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/bundle/extracted/decision_log.md)
- [apply/run_all.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/apply/run_all.stdout.log)
- [apply/run_all.result.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/apply/run_all.result.json)
- [recompute/primary-path-pre-fix-timeout.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/recompute/primary-path-pre-fix-timeout.json)
- [recompute/fallback-only-success.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/recompute/fallback-only-success.json)
- [recompute/primary-path-post-fix-success.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T215309Z-s311-stale-action-rerun/recompute/primary-path-post-fix-success.json)
