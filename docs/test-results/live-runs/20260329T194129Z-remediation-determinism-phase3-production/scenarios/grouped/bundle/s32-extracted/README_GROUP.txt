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
- 1. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-688f5ed0
- 2. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-w6-envready-s315-e-0b87839b

Review-required actions:
- none

Manual-guidance actions:
- 3. S3 general purpose buckets should block public access (manual_guidance_metadata_only) -> manual_guidance/actions/03-arn-aws-s3-security-autopilot-w6-envready-s311-r-352ac9b2
- 4. S3 general purpose buckets should block public write access (manual_guidance_metadata_only) -> manual_guidance/actions/04-aws-account-696505809372-08a9f629
- 5. S3 general purpose buckets should block public read access (manual_guidance_metadata_only) -> manual_guidance/actions/05-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-e88846fa
- 6. S3 general purpose buckets should block public read access (manual_guidance_metadata_only) -> manual_guidance/actions/06-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-7522bc9f
- 7. S3 general purpose buckets should block public access (manual_guidance_metadata_only) -> manual_guidance/actions/07-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-4a965fac
- 8. S3 general purpose buckets should block public write access (manual_guidance_metadata_only) -> manual_guidance/actions/08-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-cdb53f5c
- 9. S3 general purpose buckets should block public access (manual_guidance_metadata_only) -> manual_guidance/actions/09-arn-aws-s3-security-autopilot-access-logs-696505-5571e909
- 10. S3 general purpose buckets should block public access (manual_guidance_metadata_only) -> manual_guidance/actions/10-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-bdfa85bc
