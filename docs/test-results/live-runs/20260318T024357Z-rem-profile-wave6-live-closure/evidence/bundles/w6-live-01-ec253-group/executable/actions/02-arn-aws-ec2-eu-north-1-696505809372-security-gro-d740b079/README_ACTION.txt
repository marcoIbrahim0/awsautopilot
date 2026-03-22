AWS Security Autopilot — Group action artifact

Action: Security groups should not allow unrestricted access to ports with high risk
Action ID: d740b079-2fe0-40ec-baa0-efe3e0e01a2b
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_and_revoke

Decision summary: Family resolver preserved the explicit profile 'close_and_revoke' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
