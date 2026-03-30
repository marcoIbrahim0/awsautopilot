# Final Summary

## Outcome

`PASS`

WI-4 is now closed for its intended scope.

The retained March 28, 2026 package proves the S3.5 Terraform apply-time merge branch end to end on a real AWS account, including single-run preview/create/apply/rollback and grouped create/generate/execute/callback finalization.

## What Passed

- Current-head local regressions are green for the WI-4 slice and the grouped replay-safe callback path:
  - `tests/test_remediation_profile_options_preview.py -k 's3_5'`
  - `tests/test_remediation_run_resolution_create.py -k 's3_5'`
  - `tests/test_step7_components.py -k 's3_5 or apply_time_merge'`
  - `tests/test_grouped_remediation_run_service.py -k 's3_ssl'`
  - `tests/test_remediation_run_worker.py -k 'apply_time_merge or executable_actions'`
  - `tests/test_internal_group_run_report.py -k 'replay or repair'`
- Single-run S3.5 action `7a438b0e-37e8-444e-a211-04a906891a69` produced deterministic WI-4 resolution and successful remediation run `1d71393a-4250-4e3c-bf24-9e07a7d69f41`.
- The generated single-run bundle proved the apply-time Terraform branch directly:
  - `data "aws_s3_bucket_policy" "existing"` present
  - no `terraform.auto.tfvars.json`
  - rollback helper scripts present
- Real single-run AWS execution succeeded with `AWS_PROFILE=test28-root`, and the exact pre-apply bucket policy for `r221001` was restored after rollback.
- Grouped create succeeded for group `78d0ba9d-a8ad-4d40-9623-153acb0cb9bb`, producing remediation run `447bf598-d864-4d0c-9311-d7cf63e47f90` and group run `a08746a9-4461-4144-84fe-d3bd23656309`.
- The grouped mixed-tier bundle placed the three bucket-scoped S3.5 apply-time members under `executable/actions` and the account-scoped member under `review_required/actions`.
- Executing the grouped bundle through `run_all.sh` succeeded, and the callback finalized the group run to `finished` with:
  - `3` executable successes
  - `1` metadata-only result
  - final group counters `run_successful=3`, `metadata_only=1`

## Important Scope Note

The proof used the plan-approved isolated fallback environment rather than the currently deployed production runtime.

Production was attempted first against the same target account, but the deployed runtime did not expose the WI-4 branch for the target S3.5 case. That did not invalidate the closure plan because the plan explicitly allowed a fresh isolated current-head environment when live production auth or dataset shape blocked the primary path.

## Non-Blocking Follow-Up Note

The grouped runner’s temp-workspace cleanup means execution-time `.s3-rollback` snapshots are not retained in the extracted grouped artifact after the run. That did not block WI-4 closure because:

- exact rollback proof was required and captured on the single-run path
- grouped proof required executable layout, local execution, and callback finalization, all of which passed

For the retained grouped cleanup:

- `r221001` was restored exactly from the retained single-run pre-apply snapshot
- `r222018` and `r94854` were restored functionally by removing only the managed `DenyInsecureTransport` statement added during grouped apply

## Closure Decision

- WI-4 code path: complete
- WI-4 retained live proof: complete
- WI-4 grouped execution proof: complete
- CloudFormation-without-captured-policy boundary: unchanged and intentionally fail-closed
- Decision: mark WI-4 closed for the intended Terraform-only scope
