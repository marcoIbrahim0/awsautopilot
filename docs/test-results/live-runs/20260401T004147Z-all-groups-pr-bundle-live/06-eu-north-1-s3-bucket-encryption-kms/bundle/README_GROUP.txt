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
- 1. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-f47a11cd
- 2. S3 bucket uses SSE-KMS by default (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--45d79702
- 3. S3 bucket uses SSE-KMS by default (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-39732b9a
- 4. S3 bucket uses SSE-KMS by default (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-8130621f
- 5. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-998b9663
- 6. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-90a9507a
- 7. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-ba07da99
- 8. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-45d7dd83
- 9. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-15891d06
- 10. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-access-logs-696505-4fe5d11f
- 11. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-c5c8cb79
- 12. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-security-autopilot-access-logs-696505-7249615a
- 13. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-security-autopilot-access-logs-696505-b74b1748
- 14. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/14-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-a7f92106
- 15. S3 general purpose buckets should be encrypted at rest with AWS KMS keys (executable_bundle_generated) -> executable/actions/15-arn-aws-s3-security-autopilot-access-logs-696505-398a13c7

Review-required actions:
- none

Manual-guidance actions:
- none
