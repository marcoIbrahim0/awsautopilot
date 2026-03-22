AWS Security Autopilot — Group action artifact

Action: Security groups should not allow unrestricted access to ports with high risk
Action ID: 0abc603d-b75a-4b49-9a5f-431a0aa82a4e
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_public

Decision summary: Family resolver used the compatibility-safe default 'close_public' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
