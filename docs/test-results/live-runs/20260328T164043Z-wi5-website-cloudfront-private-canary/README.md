# WI-5 Production Canary Blocker Package

## Summary

- Run ID: `20260328T164043Z-wi5-website-cloudfront-private-canary`
- Date: March 28, 2026
- Runtime under test: `https://api.ocypheris.com`
- Target AWS account: `696505809372`
- Target region: `eu-north-1`
- Outcome: `BLOCKED`

This retained package captures the first truthful production canary attempt for `WI-5` after the local/current-head implementation landed.

The canary proved two distinct points:

1. The production resolver can classify a website-enabled `S3.2` bucket once the canary account read role is allowed to call `s3:GetBucketWebsite`.
2. The production API still rejects `strategy_id=s3_migrate_website_cloudfront_private` as unknown, so the new WI-5 branch is not yet deployed on production even though it exists on current `master`.

## Final Outcome

The canary did not reach a real WI-5 run because production create failed closed with:

- `Unknown strategy_id 's3_migrate_website_cloudfront_private' for action_type 's3_bucket_block_public_access'.`

Evidence:

- [create-remediation-run-wi5.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/api/create-remediation-run-wi5.json)
- [remediation-options-after-getbucketwebsite.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/api/remediation-options-after-getbucketwebsite.json)

For comparison, the older production-deployed branch still generated a run successfully:

- run `dd2d80c0-81ca-4940-ade5-cee658a3c879`
- [create-remediation-run-oac-baseline.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/api/create-remediation-run-oac-baseline.json)
- [oac-baseline-run-poll.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/api/oac-baseline-run-poll.json)

That successful baseline proves the production create path itself was healthy. The blocker was specifically missing production deployment of the new WI-5 strategy.

## Important Secondary Finding

The canary account read role policy was also missing `s3:GetBucketWebsite`, so the first production options call could not detect website hosting and failed with `Unable to inspect bucket website configuration (AccessDenied)`.

Evidence before the temporary repair:

- [remediation-options.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/api/remediation-options.json)
- [read-role-policy-version.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/aws/read-role-policy-version.json)

After temporarily adding `s3:GetBucketWebsite`, production correctly detected `website_configured=true` but still did not expose the new strategy:

- [remediation-options-after-getbucketwebsite.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/api/remediation-options-after-getbucketwebsite.json)
- [read-role-policy-create-v9.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/aws/read-role-policy-create-v9.json)

This temporary permission change was rolled back before closing the canary.

## Cleanup

All temporary canary resources and temporary IAM mutations were removed:

- website bucket deleted
- hosted zone deleted
- imported ACM certificate deleted
- temporary backup read role deleted
- canary account-level S3 Public Access Block restored
- canonical read-role trust restored
- temporary `GetBucketWebsite` permission removed
- backup-tenant account row set back to `disabled`

Verification:

- [head-bucket-after-delete.stderr.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/aws/head-bucket-after-delete.stderr.txt)
- [get-hosted-zone-after-delete.stderr.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/aws/get-hosted-zone-after-delete.stderr.txt)
- [describe-certificate-after-delete.stderr.txt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/aws/describe-certificate-after-delete.stderr.txt)
- [get-account-public-access-block-restored.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/aws/get-account-public-access-block-restored.json)
- [read-role-restored.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/aws/read-role-restored.json)
- [account-disable-after-canary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T164043Z-wi5-website-cloudfront-private-canary/evidence/api/account-disable-after-canary.json)

## Next Step

Deploy the current WI-5 backend/runtime changes to production and re-run this same canary flow. Until that deploy happens, this package should be treated as a production-runtime parity blocker, not as a failure of the landed WI-5 code on current `master`.
