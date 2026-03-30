AWS Security Autopilot — Mixed-tier Group PR bundle

Layout version: grouped_bundle_mixed_tier/v1
Execution root: executable/actions

Only executable Terraform lives under executable/actions/.
review_required/actions/ and manual_guidance/actions/ contain metadata-only guidance.
run_all.sh executes only executable/actions/ and no-ops successfully when no runnable Terraform folders exist.

Run from bundle root:
  chmod +x ./run_all.sh
  ./run_all.sh

Shared executable setup folders:
- executable/actions/00-shared-01-security-autopilot-access-logs-696505809 (shared S3.9 destination bucket: security-autopilot-access-logs-696505809372-s9fix1)

Executable actions:
- 1. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-config-bucket-696505809372-01557e04
- 2. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-w6-strict-s311-man-0b75c532
- 3. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-access-1dc612d8
- 4. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-strict-s315-man-3dd66962
- 5. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-config-69650580937-4d6a1520
- 6. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-envready-config-4d81e63b
- 7. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-501021f0
- 8. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-w6-strict-s315-exe-6069ec49
- 9. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-cloudt-dcd9aac0
- 10. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-e03f9f63
- 11. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-security-autopilot-w6-envready-s315-e-e7eb463d
- 12. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-security-autopilot-w6-strict-s311-exe-e8ae2a41
- 13. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-security-autopilot-w6-envready-s311-r-e9ca4a12

Review-required actions:
- 14. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/14-aws-account-696505809372-0c490240

Manual-guidance actions:
- none
