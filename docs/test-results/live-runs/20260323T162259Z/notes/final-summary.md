# March 23, 2026 Live E2E: `CloudTrail.1` generate, download, and local apply

## Scope

- Live UI/API: `https://ocypheris.com`, `https://api.ocypheris.com`
- Account: `696505809372`
- Target action: `2ea6f141-6134-4dcd-8c82-4f0d0b6e582d`
- Region: `eu-north-1`
- AWS execution profile: `test28-root`

## Outcome

- Bundle generation: PASS
- Bundle download: PASS
- Local Terraform apply: PASS
- Full control-family closure: PARTIAL

## What was exercised

- Logged into the live API and selected the current `CloudTrail.1` `eu-north-1` action.
- Created a new approval-gated PR-bundle remediation run with:
  - `strategy_id = cloudtrail_enable_guided`
  - `trail_name = security-autopilot-trail`
  - `trail_bucket_name = ocypheris-live-ct-20260323162333-eu-north-1`
  - `create_bucket_if_missing = true`
  - `create_bucket_policy = true`
  - `bucket_creation_acknowledged = true`
- Live remediation run `64a6bd18-abff-4cc8-aef7-f7f8dddb4171` returned `201` and reached terminal `success`.
- Downloaded the live bundle ZIP and unpacked it locally.
- Ran local Terraform execution from the retained bundle directory with `AWS_PROFILE=test28-root`:
  - `terraform init`
  - `terraform plan -out=tfplan`
  - `terraform apply -auto-approve tfplan`

## AWS apply result

- Terraform apply succeeded:
  - `6 added, 0 changed, 0 destroyed`
- Created resources:
  - S3 bucket `ocypheris-live-ct-20260323162333-eu-north-1`
  - S3 bucket policy for CloudTrail delivery
  - S3 versioning
  - S3 SSE configuration
  - S3 public access block
  - CloudTrail trail `security-autopilot-trail`
- AWS verification after apply:
  - `describe-trails` shows `security-autopilot-trail`
  - `S3BucketName = ocypheris-live-ct-20260323162333-eu-north-1`
  - `IsMultiRegionTrail = true`
  - `get-trail-status` shows `IsLogging = true`

## Live platform verification

- Triggered live refresh after apply:
  - `POST /api/aws/accounts/696505809372/ingest`
  - `POST /api/actions/compute`
  - `POST /api/actions/reconcile`
- Post-refresh finding state:
  - `eu-north-1` findings are now `RESOLVED`
  - `us-east-1` still has one `CloudTrail.1` finding in `NEW`
- Because the family still has an unresolved `us-east-1` finding, the action family has not fully converged yet.

## Important execution notes

Two real bundle/runtime gaps were exposed during this run:

1. The generated bundle references `null_resource.cloudtrail_bucket_policy` even when `create_bucket_if_missing = true`, which forces Terraform to install `hashicorp/null` for a path that is inactive at runtime.
2. The generated bundle does not pin `hashicorp/null`, and local execution needed a manual local provider-mirror workaround before `terraform init` and `terraform plan` would run reliably in this environment.

Those are bundle execution quality issues, not AWS apply failures. After the local provider workaround, the generated Terraform itself applied successfully.

## Conclusion

The approved create-if-missing `CloudTrail.1` path is now live-valid through generation, download, and local AWS apply. The remaining gap is not bundle generation anymore:

- one execution-quality issue in the generated Terraform bundle around unnecessary `hashicorp/null` provider usage
- one post-apply convergence gap where `us-east-1` `CloudTrail.1` still remains `NEW` even after the multi-region trail was created and the live refresh cycle was triggered
