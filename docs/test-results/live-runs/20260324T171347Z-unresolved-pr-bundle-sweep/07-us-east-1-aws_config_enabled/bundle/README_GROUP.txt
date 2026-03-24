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
- 1. AWS Config should be enabled and use the service-linked role for resource recording (executable_bundle_generated) -> executable/actions/01-aws-account-696505809372-202e02c7

Review-required actions:
- none

Manual-guidance actions:
- none
