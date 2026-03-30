AWS Security Autopilot — Group action artifact

Action: Security groups should only allow unrestricted incoming traffic for authorized ports
Action ID: 719d9e88-e83c-4fab-9f25-29cd6bae10a7
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_public

Decision summary: Family resolver matched the explicit legacy access_mode 'close_public' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
