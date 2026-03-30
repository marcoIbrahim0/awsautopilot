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
- 1. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-4fc6db43
- 2. S3 general purpose buckets should require requests to use SSL (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-config-69650580937-b9d3ffd9

Review-required actions:
- 3. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/03-aws-account-696505809372-1e453177

Manual-guidance actions:
- none
