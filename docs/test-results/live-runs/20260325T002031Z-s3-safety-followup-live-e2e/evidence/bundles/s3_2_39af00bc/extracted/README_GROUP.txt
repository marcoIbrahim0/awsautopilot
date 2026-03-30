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
- 1. S3 general purpose buckets should block public access (review_required_metadata_only) -> review_required/actions/01-arn-aws-s3-security-autopilot-w6-envready-s315-e-b0ec883a
- 2. S3 general purpose buckets should block public access (review_required_metadata_only) -> review_required/actions/02-arn-aws-s3-security-autopilot-w6-envready-s311-r-c1a8dbfb
- 3. S3 general purpose buckets should block public write access (review_required_metadata_only) -> review_required/actions/03-aws-account-696505809372-fb0b3cc7

Manual-guidance actions:
- none
