# Bundle inspection

## Fresh grouped rerun identifiers

- Group run: `d92861be-cbb7-4508-8f3e-2ddaf87df362`
- Remediation run: `f124f569-9391-4f74-85df-23e64b83fa92`
- Head branch: `20260402t013756z-s32-oac-live-rerun-preflight`

## Bundle shape

- Fresh remediation run finished `success` and produced a PR bundle covering `33` grouped members.
- Extracted bundle layout:
  - `32` executable Terraform folders under `bundle/extracted/executable/actions/`
  - `1` manual-guidance folder under `bundle/extracted/manual_guidance/actions/`

## Contract checks for the preflight refactor

The extracted executable `S3.2` folders now show the intended preflight contract:

- each executable `S3.2` folder ships `cloudfront_reuse_query.json`
- each executable `S3.2` folder ships `scripts/cloudfront_oac_discovery.py`
- generated Terraform contains explicit reuse variables instead of `data.external`
- generated `providers.tf` no longer includes `hashicorp/external`
- generated runner templates use preflight discovery before Terraform

## Real affected customer path

For the real affected action folder:

- action folder:
  - [bundle/extracted/executable/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/bundle/extracted/executable/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e)
- retained log evidence shows:
  - `INFO: CloudFront/OAC reuse preflight mode=reuse_distribution`
  - Terraform read the existing target bucket successfully
  - apply completed successfully
  - outputs reused distribution `E3T188CQ1IH26W`

This proves the fresh rerun no longer downgraded the real affected customer action because of unverifiable bucket existence from a `HeadBucket 403` path.

## New bounded failing path

The only executable folder that failed in local execution was:

- [bundle/extracted/executable/actions/23-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/bundle/extracted/executable/actions/23-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e)

Retained apply evidence:

- S3 Block Public Access `block_public_policy = true` was created first
- `PutBucketPolicy` then failed with `403 AccessDenied`
- AWS reported the generated policy was prevented because public policies are blocked by `BlockPublicPolicy`

See:

- [apply/run_all.stdout.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/apply/run_all.stdout.log)
