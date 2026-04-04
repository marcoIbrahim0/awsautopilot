# S3.5 BPA-aware live rerun on April 1-2, 2026 UTC

Status: `FAIL` with a new bounded blocker, and the old April 1 executable-bundle bug is closed.

## Scope

- Account: `696505809372`
- Region: `eu-north-1`
- Action type: `s3_bucket_require_ssl`
- Affected action: `53b7b063-8531-4829-9b23-f03b1796b23d`
- Affected bucket: `arch1-bucket-website-a1-696505809372-eu-north-1`
- Final deployed runtime tag: `20260401T232040Z-s35-hotfix2`

## Request inputs

- Canonical request inputs are retained in `notes/request-inputs.json`.
- Production deploy evidence is retained in `deploy/deploy-transcript.txt`, `deploy/postdeploy-api-lambda.json`, and `deploy/postdeploy-worker-lambda.json`.
- The grouped rerun path hit the unchanged-group dedupe guard for group `c5920987-fba3-4ea5-8363-8ccae8f39c08`, so the authoritative proof reran the exact affected action through the real single-action `pr_only` production path instead.

## Selected remediation profile and dependency checks

- Selected strategy: `s3_enforce_ssl_strict_deny`
- Live action-options evidence: `evidence/api/affected-action-options.json`
- Returned dependency checks:
  - `s3_non_tls_client_breakage` = `warn`
  - `s3_policy_merge_risk` = `warn`

## Generated artifacts

- Single-action live remediation run: `b926c7bc-0080-4a0e-832b-321b144b2b46`
- Run creation evidence: `evidence/api/single-action-run-create.json`
- Final run payload: `evidence/api/single-action-run-final.json`
- Downloaded bundle: `generated/single-action/pr-bundle.zip`
- Extracted bundle: `generated/single-action/bundle/`
- Bundle inspection: `generated/single-action/bundle-inspection.json`

## Apply output

- Bundle generation succeeded.
- No executable Terraform or shell apply payload was emitted for the affected action.
- The retained apply transcript is `generated/single-action/bundle-execution-transcript.json`, which correctly shows no runnable apply step because the bundle is downgrade-only.

## What the rerun proved

- The old April 1 failure mode is gone: production did not emit a doomed executable bundle and did not reach `PutBucketPolicy` `AccessDenied` at apply time.
- The affected bucket is now classified earlier and correctly:
  - `target_bucket_exists=true`
  - `existing_bucket_policy_json_captured=true`
  - `bucket_policy_public=true`
  - `bucket_block_public_policy_enabled=true`
  - `effective_block_public_policy_enabled=true`
- The final production decision is `review_required_bundle`, not executable, because preserving the current public bucket policy would conflict with S3 Block Public Access.

## Bounded blocker

The bounded blocker is now explicit and truthful in the generated decision package:

`Current bucket policy is public and S3 Block Public Access prevents public policies, so merge-preserving SSL enforcement would be rejected by PutBucketPolicy.`

That decision is retained in:

- `evidence/api/single-action-run-final.json`
- `generated/single-action/bundle/decision.json`
- `generated/single-action/bundle/README.txt`

## Conclusion

This rerun is a successful product-behavior proof even though the live outcome remains `FAIL` for executable apply on this exact bucket. The important change is that production now fails closed before bundle execution for the real BPA-conflicting customer case, instead of generating the April 1 executable bundle shape that S3 rejected at apply time.
