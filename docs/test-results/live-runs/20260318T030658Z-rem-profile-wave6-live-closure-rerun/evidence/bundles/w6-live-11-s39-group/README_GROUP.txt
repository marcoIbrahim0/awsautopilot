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
- 9. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-config-d74e91e3

Review-required actions:
- 1. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/01-arn-aws-s3-security-autopilot-w6-strict-s311-man-153ff5f9
- 2. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/02-arn-aws-s3-security-autopilot-w6-strict-s311-exe-26a3f7f0
- 3. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/03-arn-aws-s3-security-autopilot-w6-envready-s315-e-63b65b24
- 4. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/04-arn-aws-s3-config-bucket-696505809372-6476e319
- 5. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/05-arn-aws-s3-security-autopilot-w6-strict-s315-man-73e55a5b
- 6. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/06-arn-aws-s3-security-autopilot-w6-strict-s315-exe-c3c57258
- 7. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/07-arn-aws-s3-security-autopilot-w6-envready-access-cb4e035c
- 8. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/08-arn-aws-s3-security-autopilot-w6-envready-cloudt-cf808204
- 10. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/10-arn-aws-s3-security-autopilot-w6-envready-s311-r-ea1fda0c
- 11. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/11-arn-aws-s3-security-autopilot-w6-envready-s311-e-f90e7d9d
- 12. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/12-aws-account-696505809372-3d31d678

Manual-guidance actions:
- none
