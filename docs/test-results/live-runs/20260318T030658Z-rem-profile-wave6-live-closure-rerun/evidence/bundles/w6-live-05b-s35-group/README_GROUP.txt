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
- 3. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-cloudt-332a7d6f
- 4. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-envready-s315-e-4ca36a85
- 6. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-envready-s311-e-64650bcf
- 7. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-envready-config-8e4a902d
- 8. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-w6-strict-s311-exe-8f1b6cf5
- 10. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-w6-envready-access-eabfe19e
- 11. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-security-autopilot-w6-envready-s311-r-f3110269

Review-required actions:
- 1. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/01-arn-aws-s3-config-bucket-696505809372-0a562f26
- 2. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/02-arn-aws-s3-security-autopilot-w6-strict-s311-man-2b020c20
- 5. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/05-arn-aws-s3-security-autopilot-w6-strict-s315-man-61c4ed80
- 9. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/09-arn-aws-s3-security-autopilot-w6-strict-s315-exe-9c99cd7e
- 12. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/12-aws-account-696505809372-c89e2c01

Manual-guidance actions:
- none
