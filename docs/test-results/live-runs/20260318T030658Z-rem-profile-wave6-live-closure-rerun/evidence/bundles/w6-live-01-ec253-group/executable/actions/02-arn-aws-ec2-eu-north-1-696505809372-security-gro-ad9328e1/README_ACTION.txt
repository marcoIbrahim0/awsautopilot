AWS Security Autopilot — Group action artifact

Action: Security groups should not allow unrestricted access to ports with high risk
Action ID: ad9328e1-faf2-4fd4-9885-c7f8c50c7d14
Tier: executable
Tier root: executable/actions
Outcome: executable_bundle_generated
Strategy: sg_restrict_public_ports_guided
Profile: close_and_revoke

Decision summary: Family resolver preserved the explicit profile 'close_and_revoke' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.
Runnable Terraform is present in this folder.
