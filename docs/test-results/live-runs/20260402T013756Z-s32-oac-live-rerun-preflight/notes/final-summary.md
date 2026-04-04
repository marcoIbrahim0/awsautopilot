# Final summary

## Verdict

- Final result: `FAIL`
- This is a new bounded failure, not `OriginAccessControlAlreadyExists`.

## What was fixed and proven

- The Terraform `hashicorp/external` startup timeout was removed from the `S3.2` CloudFront/OAC execution path by moving discovery into runner preflight.
- The fresh grouped rerun proved the real affected customer action `1dc66e7e-efe9-4fd6-9335-3197211b289f` is no longer downgraded.
- During local bundle execution, the real affected action used:
  - `CloudFront/OAC reuse preflight mode=reuse_distribution`
  - existing CloudFront distribution `E3T188CQ1IH26W`
  - existing domain `d3ekvpk3f7zt5e.cloudfront.net`
- The real affected action applied successfully and only needed the bucket policy plus public-access-block resources.

## Fresh live rerun details

- account: `696505809372`
- region: `eu-north-1`
- action group: `9200b6d5-b209-443f-9d78-28a4e60f6fb1`
- group run: `d92861be-cbb7-4508-8f3e-2ddaf87df362`
- remediation run: `f124f569-9391-4f74-85df-23e64b83fa92`
- head branch: `20260402t013756z-s32-oac-live-rerun-preflight`

## Local runner terminal outcome

- command used:
  - `AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh`
- terminal local result:
  - `RC=1`
  - `Successful action folders: 31/32`
  - `Failed action folders: 1/32`

The only executable folder that failed was:

- `executable/actions/23-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e`

Concrete error:

- Terraform failed on `aws_s3_bucket_policy.security_autopilot`
- AWS error:
  - `PutBucketPolicy`
  - `403 AccessDenied`
  - `because public policies are prevented by the BlockPublicPolicy setting in S3 Block Public Access`

## Why the grouped run is still terminal `failed`

The server-side grouped run finalized as:

- group run status: `failed`
- group run finished_at: `2026-04-02 03:07:00+00:00`
- remediation run status: `success`
- remediation run outcome: `Group PR bundle generated (33 actions)`

The grouped run is truthfully `failed` because the local bundle returned non-zero after that single website-bucket policy error.

## Important control-plane nuance

The persisted `action_group_run_results` rows for this run are coarse:

- once `run_actions.sh` exited non-zero, the callback recorded executable members as `bundle_runner_failed`
- this flattened even the members that had already applied successfully, including the real affected customer action

Therefore, for this rerun:

- the group-run terminal status in [api/group-run-terminal.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/api/group-run-terminal.json) is authoritative for overall run outcome
- the exact per-folder truth is in [apply/run_all.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/apply/run_all.stdout.log)

## Conclusion

This task closed both prior blockers called out in the April 2 handoff:

- the real affected `HeadBucket 403` downgrade path is fixed
- the Terraform `external` provider timeout path is removed from the fresh runnable bundle

The remaining blocker is different and narrower:

- some website-style `S3.2` bucket-policy shapes are still rejected by S3 Block Public Access during `PutBucketPolicy`

That is the truthful reason the fresh grouped rerun remains `FAIL`.
