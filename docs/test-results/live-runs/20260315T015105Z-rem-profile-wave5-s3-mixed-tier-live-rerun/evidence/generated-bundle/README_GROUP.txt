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
- 1. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-config-bucket-696505809372-bb487cfd

Review-required actions:
- 2. S3 general purpose buckets should have server access logging enabled (review_required_metadata_only) -> review_required/actions/02-aws-account-696505809372-47c023ae

Manual-guidance actions:
- none
