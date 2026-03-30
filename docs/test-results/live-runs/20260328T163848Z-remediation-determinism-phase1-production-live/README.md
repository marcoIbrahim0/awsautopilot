# Phase 1 Remediation Determinism Production Gate

- Run ID: `20260328T163848Z-remediation-determinism-phase1-production-live`
- Date (UTC): `2026-03-28`
- Scope: Phase 1 only (`WI-3`, `WI-6`, `WI-7`, `WI-12`, `WI-13`, `WI-14`)
- Required live surface: `https://api.ocypheris.com`
- Tenant: `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`)
- Canary account: `696505809372`
- Region: `eu-north-1`
- Outcome: `BLOCKED`

## Summary

This retained package supersedes the earlier same-day auth-blocked attempt. Production SaaS authentication succeeded, the live canary account refreshed successfully, and production now exposes truthful `CloudTrail.1` and bucket-scoped `S3.9` Phase 1 candidates.

The Phase 1 gate still does not pass. The reasons are now concrete:

- Gate 0 control-plane freshness remained stale for `eu-north-1`
- `WI-3` and `WI-6` both generated live `deterministic_bundle` runs, but the generated Terraform failed local `terraform validate`
- production did not expose truthful candidates for `WI-7`, `WI-12`, `WI-13`, or `WI-14` after authenticated ingest plus action recompute

Under the production-only signoff contract, the Phase 1 gate remains `BLOCKED`.

## What This Run Proved

- Production operator auth worked for `marco.ibrahim@ocypheris.com`
- Tenant `Marco` has the connected canary account `696505809372` in `eu-north-1`
- Production `CloudTrail.1` action `456f845e-da64-43cf-8dc2-d738c3a770df` exists after refresh
- Production bucket-scoped `S3.9` action `19a9b0f0-de47-4a5b-982f-8d3c876c2064` exists and resolves to `deterministic_bundle`
- `WI-3` live create path succeeded on production:
  - remediation run `d16be6ee-2297-41c2-88b4-5dbac9ade2b6`
  - production resolved `create_bucket_if_missing=true`
- `WI-6` live create path succeeded on production:
  - remediation run `83461a94-e216-48bf-8a38-d4900fe657a5`
  - production resolved the source-bucket-derived default destination `security-autopilot-access-logs-696505809372-r221001-access-logs`

## Live Defects Found

- `WI-3` bundle defect: [cloudtrail-terraform-validate.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/aws/cloudtrail-terraform-validate.txt) shows invalid references at `cloudtrail_enabled.tf` lines `102` and `103` (`${arn_prefix_cloudtrail_logs}` should reference `local.arn_prefix_cloudtrail_logs`)
- `WI-6` bundle defect: [s39-terraform-validate.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/aws/s39-terraform-validate.txt) shows invalid references at `s3_bucket_access_logging.tf` lines `82` and `83` (`${arn_prefix_access_logs}` should reference `local.arn_prefix_access_logs`)
- `WI-6` API contract defect: production `remediation-options` advertises `context.default_inputs.create_log_bucket=true`, but `POST /api/remediation-runs` rejects `create_log_bucket` as an unknown strategy input

Because `terraform validate` failed on both generated bundles, no apply, recompute-after-apply, or rollback execution was attempted for these two live runs.

## Missing Required Phase 1 Candidates

- `WI-7` no truthful stale-`target_id` / fallback-`resource_id` S3-family candidate was present in the refreshed production action set
- `WI-12` no `aws_config_enabled` production action was present after authenticated ingest plus action recompute
- `WI-13` no production `S3.2` candidate matched the zero-policy / `GetBucketPolicyStatus` executable branch
- `WI-14` no production `S3.5` candidate matched the empty-policy / `GetBucketPolicyStatus` executable branch

## Gate Decision

- Gate 0 preflight: `BLOCKED`
  - service readiness passed
  - control-plane freshness failed for `eu-north-1`
- Gate 1A local regression: `PASS`
  - retained earlier under [20260328T162829Z-remediation-determinism-phase1-production](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T162829Z-remediation-determinism-phase1-production/README.md)
- Gate 1B production scenarios: `BLOCKED`
- Gate 3 live execution: `PARTIAL`
  - authenticated create paths executed for `WI-3` and `WI-6`
  - apply stopped at `terraform validate` failure
- Final decision: `BLOCKED`

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/00-run-metadata.md)
- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/summary.json)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/notes/final-summary.md)
- [Authenticated account list](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/aws/accounts.json)
- [Service readiness](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/api/service-readiness.json)
- [Control-plane readiness](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/api/control-plane-readiness.json)
- [Open actions after refresh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/actions/open-actions-post-refresh.json)
- [CloudTrail create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/api/cloudtrail-create-response.json)
- [CloudTrail final run detail](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/api/cloudtrail-run-detail-final.json)
- [S3.9 create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/api/s39-create-response-v2.json)
- [S3.9 final run detail](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/evidence/api/s39-run-detail-final.json)
