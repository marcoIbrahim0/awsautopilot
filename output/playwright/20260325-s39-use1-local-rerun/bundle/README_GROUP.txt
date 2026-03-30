AWS Security Autopilot — Mixed-tier Group PR bundle

Layout version: grouped_bundle_mixed_tier/v1
Execution root: executable/actions

Only executable Terraform lives under executable/actions/.
review_required/actions/ and manual_guidance/actions/ contain metadata-only guidance.
run_all.sh executes only executable/actions/ and no-ops successfully when no runnable Terraform folders exist.

Run from bundle root:
  chmod +x ./run_all.sh
  ./run_all.sh

Shared executable setup folders:
- executable/actions/00-shared-01-sa-access-logs-696505809372-use1-r032522 (shared S3.9 destination bucket: sa-access-logs-696505809372-use1-r0325224512)

Executable actions:
- 1. S3 general purpose buckets should have server access logging enabled (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-security-autopilot-config-69650580937-c6c920fd

Review-required actions:
- none

Manual-guidance actions:
- none
