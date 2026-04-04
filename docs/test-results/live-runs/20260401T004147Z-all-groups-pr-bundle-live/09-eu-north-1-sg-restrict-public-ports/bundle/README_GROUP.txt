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
- 1. Security group allows public SSH/RDP access (executable_bundle_generated) -> executable/actions/01-sg-02dd3aac53025646a-9569aa98
- 2. Security group allows public SSH/RDP access (executable_bundle_generated) -> executable/actions/02-sg-05394bffb02bf477c-4a1e56fe
- 3. Security groups should only allow unrestricted incoming traffic for authorized ports (executable_bundle_generated) -> executable/actions/03-arn-aws-ec2-eu-north-1-696505809372-security-gro-58a22607
- 4. Security groups should not allow ingress from 0.0.0.0/0 or ::/0 to port 22 (executable_bundle_generated) -> executable/actions/04-arn-aws-ec2-eu-north-1-696505809372-security-gro-d56365fe
- 5. Security groups should only allow unrestricted incoming traffic for authorized ports (executable_bundle_generated) -> executable/actions/05-sg-06f6252fa8a95b61d-4694e0cc
- 6. Security groups should only allow unrestricted incoming traffic for authorized ports (executable_bundle_generated) -> executable/actions/06-sg-0ef32ca8805a55a8b-6470a99a
- 7. Security groups should not allow unrestricted access to ports with high risk (executable_bundle_generated) -> executable/actions/07-arn-aws-ec2-eu-north-1-696505809372-security-gro-dfa0a526

Review-required actions:
- none

Manual-guidance actions:
- none
