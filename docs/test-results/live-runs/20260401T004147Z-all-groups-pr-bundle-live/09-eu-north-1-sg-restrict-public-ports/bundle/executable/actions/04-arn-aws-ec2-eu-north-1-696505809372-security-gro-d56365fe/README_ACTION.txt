AWS Security Autopilot — Group action artifact

Action: Security groups should not allow ingress from 0.0.0.0/0 or ::/0 to port 22
Action ID: d56365fe-16be-4239-9b2f-d6ca7e246d35
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_public

Decision summary: Family resolver used the compatibility-safe default 'close_public' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
