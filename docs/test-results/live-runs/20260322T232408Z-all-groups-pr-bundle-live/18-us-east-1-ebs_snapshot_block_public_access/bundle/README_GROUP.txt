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
- 1. Amazon EBS Snapshots should not be publicly accessible (review_required_metadata_only) -> review_required/actions/01-arn-aws-ec2-us-east-1-696505809372-snapshotblock-442e46ac

Manual-guidance actions:
- none
