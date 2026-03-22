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
- 2. Security groups should not allow unrestricted access to ports with high risk (executable_bundle_generated) -> executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-d740b079

Review-required actions:
- none

Manual-guidance actions:
- 1. Security groups should not allow unrestricted access to ports with high risk (manual_guidance_metadata_only) -> manual_guidance/actions/01-arn-aws-ec2-eu-north-1-696505809372-security-gro-0d5b9a29
