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
- 1. AWS Config should be enabled and use the service-linked role for resource recording (review_required_metadata_only) -> review_required/actions/01-aws-account-696505809372-202e02c7
- 2. Synthetic Config finding with trusted threat intel (review_required_metadata_only) -> review_required/actions/02-arn-aws-config-us-east-1-696505809372-config-rul-73097c11
- 3. Synthetic Config finding with low-confidence threat intel (review_required_metadata_only) -> review_required/actions/03-arn-aws-config-us-east-1-696505809372-config-rul-5acc7d0e
- 4. Synthetic Config finding without trusted threat intel (review_required_metadata_only) -> review_required/actions/04-arn-aws-config-us-east-1-696505809372-config-rul-a3d1ad9b
- 5. Synthetic Config finding with aged trusted threat intel (review_required_metadata_only) -> review_required/actions/05-arn-aws-config-us-east-1-696505809372-config-rul-18de803d

Manual-guidance actions:
- none
