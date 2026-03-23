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
- none

Review-required actions:
- 1. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/01-arn-aws-s3-security-autopilot-w6-envready-cloudt-318c8b1d
- 2. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/02-arn-aws-s3-security-autopilot-w6-envready-s311-r-6ba6522c
- 3. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/03-arn-aws-s3-security-autopilot-w6-envready-s315-e-770a4f18
- 4. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/04-arn-aws-s3-security-autopilot-w6-envready-access-82072bfa
- 5. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/05-arn-aws-s3-security-autopilot-w6-strict-s311-man-8499e226
- 6. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/06-arn-aws-s3-security-autopilot-w6-strict-s315-exe-a8a06ade
- 7. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-e97ffef8
- 8. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/08-arn-aws-s3-security-autopilot-w6-strict-s311-exe-ece8a96e
- 9. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/09-arn-aws-s3-security-autopilot-w6-envready-config-f67a9064
- 10. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/10-arn-aws-s3-security-autopilot-w6-strict-s315-man-f9535173
- 11. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/11-arn-aws-s3-config-bucket-696505809372-8f64dd84
- 12. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/12-aws-account-696505809372-257bc11e

Manual-guidance actions:
- none
