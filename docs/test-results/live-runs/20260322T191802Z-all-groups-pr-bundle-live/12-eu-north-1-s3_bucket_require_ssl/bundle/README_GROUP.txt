AWS Security Autopilot — Mixed-tier Group PR bundle

Layout version: grouped_bundle_mixed_tier/v1
Execution root: executable/actions

Only executable Terraform lives under executable/actions/.
review_required/actions/ and manual_guidance/actions/ contain metadata-only guidance.
run_all.sh executes only executable/actions/ and no-ops successfully when no runnable Terraform folders exist.

Run from bundle root:
  chmod +x ./run_all.sh
  ./run_all.sh

Executable actions:
- 1. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-security-autopilot-w6-strict-s311-exe-0ca99079
- 2. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-w6-strict-s315-exe-129fa65e
- 3. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-cloudt-23bf691b
- 4. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-strict-s315-man-4da3d806
- 5. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-w6-envready-s311-r-61552073
- 6. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-strict-s311-man-967d71a9
- 7. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-9e4562df
- 8. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-access-b84115cb
- 9. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-s315-e-b8a67bbf
- 10. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-w6-envready-config-c1c2ed6d
- 11. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-config-bucket-696505809372-830944d9

Review-required actions:
- 12. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/12-aws-account-696505809372-2ac461ec

Manual-guidance actions:
- none
