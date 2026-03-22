AWS Security Autopilot — Group action artifact

Action: Security groups should not allow unrestricted access to ports with high risk
Action ID: 647784a7-f84b-4f64-b2f9-9e1998a86376
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_public

Decision summary: Family resolver used the compatibility-safe default 'close_public' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
