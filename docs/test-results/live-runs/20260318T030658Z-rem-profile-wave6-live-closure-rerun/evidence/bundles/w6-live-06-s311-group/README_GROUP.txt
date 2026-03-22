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
- 3. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-strict-s315-exe-d3be1c75

Review-required actions:
- none

Manual-guidance actions:
- 1. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/01-arn-aws-s3-security-autopilot-w6-strict-s311-man-a105bf6a
- 2. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/02-arn-aws-s3-config-bucket-696505809372-a62cdfeb
- 4. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/04-arn-aws-s3-security-autopilot-w6-strict-s315-man-e755b2ce
- 5. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/05-aws-account-696505809372-aba1694d
