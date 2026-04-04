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
- 1. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-0960aba7
- 2. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--1e28dbb1
- 3. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-s315-e-0b87839b
- 4. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-688f5ed0
- 5. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-w6-envready-s311-r-352ac9b2
- 7. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-7522bc9f
- 8. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-4a965fac
- 9. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-cdb53f5c
- 10. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-access-logs-696505-5571e909
- 11. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-bdfa85bc
- 12. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-52afd4d2
- 13. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-security-autopilot-dev-serverless-src-d4872e19
- 14. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/14-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-39d7ad12
- 15. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/15-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-e88846fa

Review-required actions:
- none

Manual-guidance actions:
- 6. S3 general purpose buckets should block public write access (manual_guidance_metadata_only) -> manual_guidance/actions/06-aws-account-696505809372-08a9f629
