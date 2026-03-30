# Final Summary

## Outcome

- Run ID: `20260329T003200Z-remediation-determinism-phase3-production`
- Final decision: `BLOCKED`
- Required surface: `https://api.ocypheris.com`

## What Passed

- Gate 3B local regression passed after correcting one stale create-path test in [tests/test_remediation_run_resolution_create.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_remediation_run_resolution_create.py).
- `WI-5` production parity now works once the canary read role can call `s3:GetBucketWebsite`.
- `WI-9` production preview/create parity now preserves executable `apply_time_merge=true` on a truthful OAC bucket-policy capture failure.
- `WI-11` now has retained production single-run proof:
  - create run `5c63c954-1ec3-44e5-b36b-55b1b9410371`
  - production run detail preserved `apply_time_merge=true`
  - Terraform `init`, `validate`, `plan`, and `apply` succeeded
  - AWS showed the managed abort rule live
  - bundle-local rollback restored exact no-lifecycle pre-state
- `WI-4` now has retained production single-run proof:
  - create run `dd8d9b9d-4dd8-4587-a7ed-00f17e1a48bb`
  - production run detail preserved `apply_time_merge=true`
  - Terraform `init`, `validate`, `plan`, `apply`, and `destroy` succeeded
  - bundle-local policy restore returned the bucket to the deny-only pre-apply policy
  - final cleanup returned the bucket to its original no-policy state

## What Blocked Phase 3

1. `WI-10` still has no truthful production candidate.
2. AWS itself rejected a fresh unconditional public bucket policy on the canary account because account-level S3 Block Public Access still has `BlockPublicPolicy=true`.
3. `WI-5` and `WI-9` have parity proof only; this run did not complete their retained apply/rollback packages.
4. Gate 3D grouped mixed-tier production proof was not executed.

## Important Notes

- `WI-11` parity was eventually consistent across production surfaces:
  - `remediation-options` showed the lifecycle apply-time merge branch immediately after the deny mutation
  - the first preview read still showed the stale zero-lifecycle branch
  - a retry after propagation returned the correct `apply_time_merge=true` branch
- The canary read-role baseline change to include `s3:GetBucketWebsite` should be treated as intentional retained environment state unless a later run explicitly supersedes it.
