AWS Security Autopilot — Group action artifact

Action: Security groups should not allow unrestricted access to ports with high risk
Action ID: 2a1c9d2f-b05d-48b3-bcec-d7645c5fd017
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: sg_restrict_public_ports_guided
Profile: ssm_only

Decision summary: Family resolver preserved the explicit profile 'ssm_only' for strategy 'sg_restrict_public_ports_guided'. Downgrade reasons: Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
