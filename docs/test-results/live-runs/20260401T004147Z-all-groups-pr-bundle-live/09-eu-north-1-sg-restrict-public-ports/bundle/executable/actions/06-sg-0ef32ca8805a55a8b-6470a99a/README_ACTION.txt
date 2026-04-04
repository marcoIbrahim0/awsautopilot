AWS Security Autopilot — Group action artifact

Action: Security groups should only allow unrestricted incoming traffic for authorized ports
Action ID: 6470a99a-ea73-48a0-ba1d-75c1ebd8ba59
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_public

Decision summary: Family resolver used the compatibility-safe default 'close_public' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
