# Decision Log

## 1. Security groups should not allow unrestricted access to ports with high risk
- Action ID: 2a1c9d2f-b05d-48b3-bcec-d7645c5fd017
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: sg_restrict_public_ports_guided / ssm_only
- Summary: Family resolver preserved the explicit profile 'ssm_only' for strategy 'sg_restrict_public_ports_guided'. Downgrade reasons: Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented. Run creation did not require additional risk-only acceptance.

## 2. Security groups should not allow unrestricted access to ports with high risk
- Action ID: ad9328e1-faf2-4fd4-9885-c7f8c50c7d14
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: sg_restrict_public_ports_guided / close_and_revoke
- Summary: Family resolver preserved the explicit profile 'close_and_revoke' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.

