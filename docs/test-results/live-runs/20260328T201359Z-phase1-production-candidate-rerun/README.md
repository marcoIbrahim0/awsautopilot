# Phase 1 Remediation Determinism Production Candidate Rerun

- Run ID: `20260328T201359Z-phase1-production-candidate-rerun`
- Date (UTC): `2026-03-28`
- Scope: Phase 1 only (`WI-3`, `WI-6`, `WI-7`, `WI-12`, `WI-13`, `WI-14`)
- Required live surface: `https://api.ocypheris.com`
- Tenant: `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`)
- Canary account: `696505809372`
- Region: `eu-north-1`
- Outcome: `BLOCKED`

## Summary

This rerun supersedes the earlier March 28 Phase 1 package as the current authoritative production attempt.

The rerun materially advanced the live production proof set:

- Gate 0 control-plane freshness is repaired on the real production path
- `WI-13` now has retained live zero-policy proof through the production preview/create path
- `WI-14` now has retained live zero-policy proof through the production preview/create path
- the canary AWS Config recorder was restored to the intended custom S3-only scope after live mutation

Phase 1 still does not pass under the production-only contract:

- `WI-7` still has no truthful stale-`target_id` / fallback-`resource_id` S3-family candidate on the real production API path
- `WI-12` still has no truthful live `aws_config_enabled` action, even after stopping the recorder, waiting, authenticated refresh, and restoring the recorder
- the earlier retained `WI-3` / `WI-6` proof package still shows post-apply production finding/action closure lagging actual AWS state

Under the production-only signoff contract, Phase 1 remains `BLOCKED`.

## What This Run Proved

- Production bearer auth still works for tenant `Marco`
- Final service readiness still reports `overall_ready=true`
- Final control-plane readiness now reports `overall_ready=true` for `eu-north-1`
- `WI-13` zero-policy branch is proven live:
  - action `0b87839b-28f5-4150-af26-74cf2b1af3a3`
  - create run `f37145d2-e4a4-48ff-bdd5-6ac6d4871320`
  - retained run detail shows `existing_bucket_policy_statement_count=0` and `apply_time_merge=false`
- `WI-14` zero-policy branch is proven live:
  - action `96bd1efb-91ee-4b22-9e1e-29613c8492aa`
  - create run `4b63b8d7-a428-4b40-8ce0-0b134ec508fe`
  - retained run detail shows `existing_bucket_policy_statement_count=0` and `apply_time_merge=false`
- Gate 0 freshness is fixed through the real production control-plane intake:
  - rotated a fresh control-plane token through the authenticated production API
  - replayed real CloudTrail event `59dab117-4d07-4917-881b-daa4d63c6f13` (`PutConfigurationRecorder`)
  - final readiness now reports `last_event_time=2026-03-28T20:19:44Z` and `is_recent=true`
- `WI-12` is still blocked by live source-of-truth lag rather than missing API refresh:
  - AWS recorder stop was confirmed live
  - Security Hub continued to report `Config.1` as `PASSED` / `RESOLVED`
  - production findings and actions continued to expose no open `Config.1` candidate

## Remaining Blockers

- `WI-7`: no truthful production S3-family action currently combines stale/account-scoped `target_id` with bucket-truthful `resource_id` on the real API path
- `WI-12`: no truthful production `aws_config_enabled` action exists after live AWS mutation plus authenticated production refresh
- `WI-3` / `WI-6` post-apply lag remains unresolved from the earlier retained proof package:
  - live AWS apply/rollback proof exists
  - production findings/actions still lag actual AWS state after recompute

## Gate Decision

- Gate 0 preflight: `PASS`
  - service readiness passed
  - control-plane freshness passed after public control-plane intake replay
- Gate 1A local regression: `PASS`
  - retained earlier under [20260328T162829Z-remediation-determinism-phase1-production](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T162829Z-remediation-determinism-phase1-production/README.md)
- Gate 1B production scenarios: `BLOCKED`
  - `WI-3`, `WI-6`, `WI-13`, and `WI-14` now have truthful retained live proof
  - `WI-7` and `WI-12` still lack truthful production candidates
- Gate 3 live execution: `PARTIAL`
  - live production proof exists for four of the six required Phase 1 scenarios
  - the remaining blockers are candidate availability and production status lag, not bundle-generation validity
- Final decision: `BLOCKED`

## Key Artifacts

- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/summary.json)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/notes/final-summary.md)
- [Authenticated user proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/me.json)
- [Final service readiness](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/service-readiness-final.json)
- [Final control-plane readiness](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/control-plane-readiness-final.json)
- [Control-plane public intake response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/control-plane-public-put-config-response.json)
- [Recorder stop proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/aws/config-recorder-status-stopped-5s.json)
- [Recorder restored proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/aws/config-recorder-status-final.json)
- [Config.1 Security Hub after stop](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/aws/securityhub-config1-current-after-stop.json)
- [Config.1 production findings after stop](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/findings-config1-current-after-stop.json)
- [Config.1 production actions after stop](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/open-actions-current-after-stop.json)
- [WI-13 preview](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/wi13-preview-zero-policy.json)
- [WI-13 create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/wi13-zero-policy-create-response.json)
- [WI-13 run detail](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/wi13-zero-policy-run-detail.json)
- [WI-14 preview](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/wi14-preview-zero-policy.json)
- [WI-14 create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/wi14-zero-policy-create-response.json)
- [WI-14 run detail](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/evidence/api/wi14-zero-policy-run-detail.json)
