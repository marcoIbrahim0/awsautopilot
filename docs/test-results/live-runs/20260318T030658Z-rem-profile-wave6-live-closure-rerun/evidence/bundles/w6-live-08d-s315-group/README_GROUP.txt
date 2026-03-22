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
- 1. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-config-bucket-696505809372-33bd3255
- 2. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-w6-envready-cloudt-3575f46f
- 3. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-strict-s315-exe-44f6df0a
- 4. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-envready-access-478ebc2f
- 6. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-strict-s311-man-66a5dd43
- 7. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-strict-s311-exe-7a0e2c57
- 8. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-s315-e-7b9ca8b1
- 9. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-s311-e-7bf8c034
- 10. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-w6-envready-s311-r-7f85a353
- 11. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-security-autopilot-w6-envready-config-d5646c71

Review-required actions:
- 5. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (review_required_metadata_only) -> review_required/actions/05-arn-aws-s3-security-autopilot-w6-strict-s315-man-52947557

Manual-guidance actions:
- none
