AWS Security Autopilot — Group action artifact

Action: Security groups should not allow unrestricted access to ports with high risk
Action ID: 0d5b9a29-bd79-4454-a9c4-c0a5c62479e0
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: sg_restrict_public_ports_guided
Profile: ssm_only

Decision summary: Family resolver preserved the explicit profile 'ssm_only' for strategy 'sg_restrict_public_ports_guided'. Downgrade reasons: Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
