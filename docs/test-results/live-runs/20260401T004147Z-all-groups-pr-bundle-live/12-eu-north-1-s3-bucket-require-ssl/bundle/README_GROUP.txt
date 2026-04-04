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
- 1. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-7451c997
- 2. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--f791c98c
- 3. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-dev-serverless-src-d7a6479a
- 4. S3 bucket enforces SSL requests (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-e532a4a7
- 5. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-access-logs-696505-ec2c5925
- 6. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-access-logs-696505-d33c0b28
- 7. S3 bucket enforces SSL requests (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-329b2b93
- 8. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-78237cc2
- 9. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-access-logs-696505-96bd1efb
- 11. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-6b99bb03
- 12. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-8f192c29
- 13. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-2cdace24
- 14. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/14-arn-aws-s3-security-autopilot-access-logs-696505-0886946b
- 15. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/15-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-bcd7f695
- 16. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/16-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-5bf35adb

Review-required actions:
- 10. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/10-aws-account-696505809372-2904172f

Manual-guidance actions:
- none
