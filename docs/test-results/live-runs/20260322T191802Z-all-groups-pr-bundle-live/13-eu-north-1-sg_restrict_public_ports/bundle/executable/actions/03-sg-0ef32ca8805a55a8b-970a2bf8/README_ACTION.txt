AWS Security Autopilot — Group action artifact

Action: Security groups should only allow unrestricted incoming traffic for authorized ports
Action ID: 970a2bf8-e01b-4a2c-a699-cec968652acb
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_public

Decision summary: Family resolver used the compatibility-safe default 'close_public' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
