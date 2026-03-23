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
- 1. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-security-autopilot-w6-envready-s315-e-26b6f037
- 2. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-w6-envready-cloudt-27b03b08
- 3. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-s311-r-2a74e447
- 4. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-strict-s315-man-2aa81941
- 5. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-w6-envready-access-5612223f
- 6. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-strict-s315-exe-56ab9e32
- 7. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-6bfdbc7b
- 8. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-config-96d2e53b
- 9. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-strict-s311-man-cce5e3c4
- 10. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-w6-strict-s311-exe-cef91c15
- 11. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-config-bucket-696505809372-d9e9b47f

Review-required actions:
- none

Manual-guidance actions:
- none
