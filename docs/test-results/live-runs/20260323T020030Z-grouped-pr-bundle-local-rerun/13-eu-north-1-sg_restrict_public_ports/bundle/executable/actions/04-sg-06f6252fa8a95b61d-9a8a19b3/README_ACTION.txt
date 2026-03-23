AWS Security Autopilot — Group action artifact

Action: Security groups should only allow unrestricted incoming traffic for authorized ports
Action ID: 9a8a19b3-b1c4-44af-9c66-a3b01432a116
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_public

Decision summary: Family resolver matched the explicit legacy access_mode 'close_public' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
