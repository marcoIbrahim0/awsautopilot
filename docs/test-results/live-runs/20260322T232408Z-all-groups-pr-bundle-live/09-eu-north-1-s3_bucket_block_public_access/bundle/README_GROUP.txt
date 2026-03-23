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
- none

Review-required actions:
- none

Manual-guidance actions:
- 1. S3 general purpose buckets should block public access (manual_guidance_metadata_only) -> manual_guidance/actions/01-arn-aws-s3-security-autopilot-w6-envready-s311-r-abf5eb48
- 2. S3 general purpose buckets should block public access (manual_guidance_metadata_only) -> manual_guidance/actions/02-arn-aws-s3-security-autopilot-w6-envready-s315-e-f497bc0c
- 3. S3 general purpose buckets should block public write access (manual_guidance_metadata_only) -> manual_guidance/actions/03-aws-account-696505809372-19337c80
