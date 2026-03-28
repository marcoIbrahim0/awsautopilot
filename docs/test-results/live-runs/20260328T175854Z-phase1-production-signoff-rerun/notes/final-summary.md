# Final Summary

## Outcome

- Run ID: `20260328T175854Z-phase1-production-signoff-rerun`
- Final decision: `BLOCKED`
- Required surface: `https://api.ocypheris.com`

## What Changed From The Earlier March 28 Live Run

- `WI-3` `CloudTrail.1` and `WI-6` bucket-scoped `S3.9` no longer fail `terraform validate`
- Production `S3.9` options/create contract is now consistent:
  - public `remediation-options` only advertises `log_bucket_name`
  - live run artifacts still resolve `create_log_bucket=true` internally
- Both families now have retained live `plan`, `apply`, and rollback proof on real AWS

## WI-3 CloudTrail

- Fresh create run: `e398cfea-afa0-409f-a19b-0ec3f60fc2f7`
- Apply-safe rerun: `53f0e041-4154-423f-8174-79a73b124377`
- Validation result: [cloudtrail-terraform-validate.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/cloudtrail-terraform-validate.txt) shows `Success! The configuration is valid.`
- Apply result: unique trail `security-autopilot-trail-20260328t181200z` and bucket `ocypheris-live-ct-20260328t181200z-eu-north-1` were created successfully
- Post-apply live surface:
  - action still `open`
  - findings split into one `RESOLVED` and one `NEW`
- Rollback result:
  - Terraform removed the trail cleanly
  - bucket deletion initially failed because CloudTrail had already delivered versioned objects
  - manual version/object deletion plus `aws s3 rb` completed cleanup

## WI-6 S3.9

- Fresh create run: `1f5c2002-1c81-476b-919f-8ce260263bfd`
- Validation result: [s39-terraform-validate.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/evidence/aws/s39-terraform-validate.txt) shows `Success! The configuration is valid.`
- Apply result: source bucket `security-autopilot-access-logs-696505809372-r221001` was configured to log into `security-autopilot-access-logs-696505809372-r221001-access-logs`
- Post-apply live surface:
  - action still `open`
  - finding still `NEW`
- Rollback result:
  - Terraform destroy removed the destination bucket and disabled logging cleanly

## Remaining Missing Phase 1 Candidates

- `WI-7`
  - refreshed production action set still has no truthful stale-`target_id` / fallback-`resource_id` S3-family candidate
- `WI-12`
  - no production `aws_config_enabled` action exists after authenticated ingest + recompute
- `WI-13`
  - probed `S3.2` bucket-scoped actions `0b87839b-28f5-4150-af26-74cf2b1af3a3` and `352ac9b2-d343-40ac-b427-4c4f285615ef`
  - both live run artifacts persisted `existing_bucket_policy_statement_count=2`, so neither exercised the required zero-policy `GetBucketPolicyStatus` branch
- `WI-14`
  - probed `S3.5` bucket-scoped actions `96bd1efb-91ee-4b22-9e1e-29613c8492aa` and `d33c0b28-2a54-4623-8a5d-1f9bffc4884d`
  - one stayed on `AccessDenied` capture failure without zero-policy normalization and the other carried explicit non-zero policy evidence

## Why The Gate Is Still Blocked

1. Control-plane freshness is still stale for `eu-north-1`.
2. `WI-7`, `WI-12`, `WI-13`, and `WI-14` still do not have truthful production-backed candidate proofs.
3. Even after successful AWS apply for `WI-3` and `WI-6`, the production finding/action surface still lags actual AWS state.
