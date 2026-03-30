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
- 1. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-4b97cf9a
- 2. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-access-logs-696505-8ab29997

Review-required actions:
- none

Manual-guidance actions:
- 3. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/03-aws-account-696505809372-cbe0d2c3
- 4. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/04-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-176c29ed
- 5. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/05-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-a9e5a989
- 6. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/06-arn-aws-s3-security-autopilot-access-logs-696505-37e0f71d
- 7. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/07-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-abaa9de7
