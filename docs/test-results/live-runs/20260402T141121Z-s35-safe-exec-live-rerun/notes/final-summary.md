# S3.5 safe executable live rerun on April 2, 2026 UTC

Status: `PASS` for the bounded follow-up proof that the safe executable `S3.5` path still works on production after the BPA-aware fix.

## Scope

- Account: `696505809372`
- Region: `eu-north-1`
- Action type: `s3_bucket_require_ssl`
- Affected action: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Affected bucket: `arch1-bucket-evidence-b1-696505809372-eu-north-1`
- Remediation run: `3c5c5cf3-1190-42c9-9ad7-737d57915ba5`

## Why this rerun was needed

The April 1 retained package already closed the original `S3.5` bug for the real BPA-conflicting public-policy bucket by proving production now fails closed instead of emitting a doomed executable bundle.

What still needed proof was the separate safe branch:

- existing bucket policy is non-public or empty
- `BlockPublicPolicy` can still be effective
- production should keep the run executable
- the downloaded bundle should still apply successfully

This rerun is that missing production proof.

## Pre-run safety evidence

The authoritative request inputs are retained in `notes/request-inputs.json`.

Pre-run production evidence:

- remediation options: `evidence/api/affected-action-options.json`
- remediation preview: `evidence/api/affected-action-preview.json`
- pre-run action recompute queueing: `evidence/api/actions-compute-pre.json`

Those retained payloads prove the safe branch before bundle creation:

- `target_bucket_exists=true`
- `existing_bucket_policy_json_captured=true`
- `bucket_policy_public=false`
- `bucket_block_public_policy_enabled=true`
- `effective_block_public_policy_enabled=true`
- `block_public_policy_conflict=false`
- `executable_policy_merge_allowed=true`
- resolver decision: keep `s3_enforce_ssl_strict_deny` executable

Direct AWS readback before apply matched that decision:

- existing bucket policy was a single non-public CloudFront service-principal `Allow`
- bucket-level S3 Public Access Block had `BlockPublicPolicy=true`

## Generated artifacts

- run creation evidence: `evidence/api/single-action-run-create.json`
- final run payload: `evidence/api/single-action-run-final.json`
- downloaded bundle: `generated/single-action/pr-bundle.zip`
- extracted bundle: `generated/single-action/bundle/`
- Terraform transcript: `evidence/aws/terraform-transcript.json`

The final run payload proves:

- `status=success`
- `support_tier=deterministic_bundle`
- executable `pr_bundle` artifact emitted
- preserved existing bucket-policy JSON threaded into `terraform.auto.tfvars.json`

## Apply result

Local customer-run execution used:

- `AWS_PROFILE=test28-root`
- `AWS_REGION=eu-north-1`
- local Terraform CLI config mirror `/tmp/s35-safe-exec.tfrc` pointing at `~/.terraform.d/plugin-cache`

That mirror workaround was needed only because plain `terraform init` on this workstation timed out contacting `registry.terraform.io`; it is not a product bundle defect.

Retained execution result:

- `terraform init` succeeded
- `terraform plan` succeeded and showed the exact intended additive merge
- `terraform apply` succeeded
- created resource: `aws_s3_bucket_policy.security_autopilot`

The apply transcript is retained in `evidence/aws/terraform-transcript.json`.

## What the rerun proved

- Production still generates an executable `S3.5` PR bundle for a safe non-public-policy bucket after the BPA-aware fix.
- The generated Terraform preserved the existing non-public CloudFront read policy and added only `DenyInsecureTransport`.
- Effective `BlockPublicPolicy=true` did not cause downgrade or apply-time failure when the preserved existing policy remained non-public.
- Local live apply succeeded end to end for the authoritative safe-bucket case.

Post-apply AWS evidence is retained in:

- `evidence/aws/post-apply-bucket-policy.json`
- `evidence/aws/post-apply-public-access-block.json`

That raw AWS proof shows the bucket policy now contains:

- original `AllowCloudFrontReadOnly`
- added `DenyInsecureTransport`

## Bounded non-S3.5 follow-up observed during verification

Post-apply closure verification is currently limited by stale control-plane freshness for this live account, not by the `S3.5` bundle path:

- retained readiness snapshot: `evidence/api/post-apply-control-plane-readiness.json`
- `overall_ready=false`
- stale regions: `eu-north-1`, `us-east-1`

Because of that unrelated freshness gap, the retained post-apply action list still shows action `3970aa2f-edc5-4870-87bd-fa986dad3d98` as `open` in `evidence/api/post-apply-actions-list.json` even though raw AWS state is already compliant.

This does not reopen the April 1 `S3.5` bug and does not weaken the safe executable proof.

## Conclusion

The remaining `S3.5` follow-up from the April 2 task log is now closed.

The product now has both bounded live proofs:

- BPA-conflicting public-policy bucket: production fails closed truthfully and does not emit the old doomed executable bundle
- safe non-public-policy bucket: production still emits an executable bundle and that bundle applies successfully on the real production account
