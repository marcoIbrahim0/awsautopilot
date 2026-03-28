# Phase 1 Remediation Determinism Production Gate Rerun

- Run ID: `20260328T175854Z-phase1-production-signoff-rerun`
- Date (UTC): `2026-03-28`
- Scope: Phase 1 only (`WI-3`, `WI-6`, `WI-7`, `WI-12`, `WI-13`, `WI-14`)
- Required live surface: `https://api.ocypheris.com`
- Tenant: `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`)
- Canary account: `696505809372`
- Region: `eu-north-1`
- Outcome: `BLOCKED`

## Summary

This rerun supersedes the earlier March 28 authenticated package as the current authoritative Phase 1 production attempt.

The previously reported live defects for `WI-3` and `WI-6` are fixed on production:

- fresh production `CloudTrail.1` and bucket-scoped `S3.9` bundles both passed local `terraform validate`
- production `S3.9` `remediation-options` no longer advertises the stale `create_log_bucket` input at create time
- both refreshed bundles reached live `terraform plan`, `terraform apply`, and rollback proof with real AWS credentials

Phase 1 still does not pass under the production-only contract:

- Gate 0 control-plane freshness remains stale for `eu-north-1`
- `WI-7` still has no truthful stale-`target_id` / fallback-`resource_id` S3-family candidate in the refreshed production action set
- `WI-12` still has no live `aws_config_enabled` action after authenticated ingest plus recompute
- the currently exposed bucket-scoped `S3.2` and `S3.5` actions do not satisfy the required zero-policy branches for `WI-13` or `WI-14`
- post-apply production recompute still lagged the actual AWS state for `WI-3` and `WI-6`, so finding/action closure is not yet reliable enough for signoff

Under the production-only signoff contract, the Phase 1 gate remains `BLOCKED`.

## What This Run Proved

- Production API health, readiness, and bearer-auth access all worked for tenant `Marco`
- Service readiness still passed while control-plane freshness remained stale in `eu-north-1`
- `WI-3` live bundle generation is fixed on production:
  - create run `e398cfea-afa0-409f-a19b-0ec3f60fc2f7`
  - apply-safe rerun `53f0e041-4154-423f-8174-79a73b124377`
  - generated Terraform now references `local.arn_prefix_cloudtrail_logs`
  - unique-trail apply succeeded and rollback succeeded, with the final bucket cleanup requiring explicit deletion of delivered object versions before bucket removal
- `WI-6` live bundle generation is fixed on production:
  - create run `1f5c2002-1c81-476b-919f-8ce260263bfd`
  - generated Terraform now references `local.arn_prefix_access_logs`
  - create-time API contract now accepts the truthful public input set (`log_bucket_name` only) while the run still resolves `create_log_bucket=true` internally
  - apply succeeded and rollback succeeded cleanly
- `WI-13` and `WI-14` were probed live on the currently exposed bucket-scoped actions, but those actions carried non-zero existing bucket policy evidence rather than the required zero-policy branches

## Remaining Blockers

- `WI-7`: no truthful production S3-family action currently combines stale/account-scoped `target_id` with bucket-truthful `resource_id`
- `WI-12`: no production `Config.1` / `aws_config_enabled` action exists after refresh, so the auto-promotion path still lacks a truthful live candidate
- `WI-13`: both bucket-scoped `S3.2` candidates persisted `existing_bucket_policy_statement_count=2`; neither exercised the zero-policy `GetBucketPolicyStatus` branch
- `WI-14`: the probed bucket-scoped `S3.5` candidates persisted either `existing_bucket_policy_capture_error=AccessDenied` or explicit non-zero policy evidence; neither exercised the empty-policy `GetBucketPolicyStatus` branch
- `WI-3` / `WI-6` post-apply production state remained behind actual AWS state:
  - `S3.9` source-bucket logging was enabled in AWS, but the live `S3.9` finding and action remained `NEW` / `open` after ingest + recompute
  - `CloudTrail.1` showed one resolved finding and one still-new finding after ingest + recompute, while the action stayed `open`

## Gate Decision

- Gate 0 preflight: `BLOCKED`
  - service readiness passed
  - control-plane freshness failed for `eu-north-1`
- Gate 1A local regression: `PASS`
  - retained earlier under [20260328T162829Z-remediation-determinism-phase1-production](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T162829Z-remediation-determinism-phase1-production/README.md)
- Gate 1B production scenarios: `BLOCKED`
  - `WI-3` and `WI-6` now pass live bundle-generation and live apply/rollback proof
  - `WI-7`, `WI-12`, `WI-13`, and `WI-14` still lack the required truthful production candidates
- Gate 3 live execution: `PARTIAL`
  - live apply/rollback proof now exists for `WI-3` and `WI-6`
  - production finding/action closure still lags actual AWS state
- Final decision: `BLOCKED`

## Key Artifacts

- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/summary.json)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/notes/final-summary.md)
- [Authenticated user and tenant proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/api/me.json)
- [Service readiness](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/api/service-readiness.json)
- [Control-plane readiness](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/api/control-plane-readiness.json)
- [Open actions after refresh](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/api/open-actions-immediate.json)
- [CloudTrail create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/api/cloudtrail-create-response.json)
- [CloudTrail validate output](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/cloudtrail-terraform-validate.txt)
- [CloudTrail apply transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/cloudtrail-apply-terraform-apply.txt)
- [CloudTrail rollback transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/cloudtrail-apply-terraform-destroy.txt)
- [S3.9 create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/api/s39-create-response.json)
- [S3.9 validate output](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/s39-terraform-validate.txt)
- [S3.9 apply transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/s39-terraform-apply.txt)
- [S3.9 rollback transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/s39-terraform-destroy.txt)
