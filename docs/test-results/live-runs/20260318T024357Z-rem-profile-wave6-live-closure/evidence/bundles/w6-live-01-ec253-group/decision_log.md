# Decision Log

## 1. Security groups should not allow unrestricted access to ports with high risk
- Action ID: 0d5b9a29-bd79-4454-a9c4-c0a5c62479e0
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: sg_restrict_public_ports_guided / ssm_only
- Summary: Family resolver preserved the explicit profile 'ssm_only' for strategy 'sg_restrict_public_ports_guided'. Downgrade reasons: Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented. Run creation did not require additional risk-only acceptance.

## 2. Security groups should not allow unrestricted access to ports with high risk
- Action ID: d740b079-2fe0-40ec-baa0-efe3e0e01a2b
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: sg_restrict_public_ports_guided / close_and_revoke
- Summary: Family resolver preserved the explicit profile 'close_and_revoke' for strategy 'sg_restrict_public_ports_guided'. Run creation did not require additional risk-only acceptance.

