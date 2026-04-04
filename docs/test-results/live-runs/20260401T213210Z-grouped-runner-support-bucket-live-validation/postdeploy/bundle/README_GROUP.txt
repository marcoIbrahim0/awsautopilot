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
- 1. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/01-arn-aws-s3-security-autopilot-config-69650580937-4c8c904a
- 2. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/02-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-e57d1452
- 3. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/03-arn-aws-s3-security-autopilot-w6-envready-s311-r-6ba6522c
- 4. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/04-arn-aws-s3-security-autopilot-w6-envready-s315-e-770a4f18
- 5. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/05-arn-aws-s3-security-autopilot-w6-envready-access-82072bfa
- 6. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/06-arn-aws-s3-security-autopilot-w6-envready-s311-e-e97ffef8
- 7. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/07-arn-aws-s3-security-autopilot-w6-envready-config-f67a9064
- 8. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/08-arn-aws-s3-config-bucket-696505809372-8f64dd84
- 9. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/09-arn-aws-s3-security-autopilot-w6-envready-cloudt-318c8b1d
- 10. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/10-arn-aws-s3-security-autopilot-w6-strict-s311-man-8499e226
- 11. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/11-arn-aws-s3-security-autopilot-w6-strict-s315-exe-a8a06ade
- 12. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/12-arn-aws-s3-security-autopilot-w6-strict-s311-exe-ece8a96e
- 13. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/13-arn-aws-s3-security-autopilot-w6-strict-s315-man-f9535173
- 14. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/14-aws-account-696505809372-257bc11e

Manual-guidance actions:
- none
