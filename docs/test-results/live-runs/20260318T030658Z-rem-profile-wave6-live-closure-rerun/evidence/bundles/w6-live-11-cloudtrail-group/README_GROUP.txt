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
- 1. CloudTrail should be enabled and configured with at least one multi-Region trail that includes read and write management events (executable_bundle_generated) -> executable/actions/01-aws-account-696505809372-939cce27

Review-required actions:
- none

Manual-guidance actions:
- none
