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
- 1. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-60a49649
- 2. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-a7ad353b
- 3. S3 bucket access logging enabled (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-arch1-bucket-website-a1-696505809372--6cf8c5a0
- 4. S3 bucket access logging enabled (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-adc31819
- 5. S3 bucket access logging enabled (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-5ab0ba1e
- 6. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-dev-serverless-src-9ce4c3bd
- 7. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-access-logs-696505-19a9b0f0
- 8. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-access-logs-696505-51038315
- 9. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-access-logs-696505-cc3ba387
- 11. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-f704085e
- 12. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-1f3adb89
- 13. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-6efea359
- 15. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/15-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-0197deac
- 16. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/16-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-d32172a1

Review-required actions:
- 10. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/10-aws-account-696505809372-0fd42f91
- 14. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/14-arn-aws-s3-security-autopilot-access-logs-696505-bed34478

Manual-guidance actions:
- none
