# Decision Log

## 1. Security groups should not allow unrestricted access to ports with high risk
- Action ID: baa158fa-53f5-4a61-a226-e25779c49fa7
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: sg_restrict_public_ports_guided / ssm_only
- Summary: Family resolver preserved the explicit profile 'ssm_only' for strategy 'sg_restrict_public_ports_guided'. Downgrade reasons: Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented. Run creation did not require additional risk-only acceptance.

## 2. Security groups should not allow unrestricted access to ports with high risk
- Action ID: fb98ee94-f68b-41c0-84af-64afbbb014b4
- Tier: review_required/actions
- Outcome: review_required_metadata_only
- Strategy/Profile: sg_restrict_public_ports_guided / close_and_revoke
- Summary: Family resolver preserved the explicit profile 'close_and_revoke' for strategy 'sg_restrict_public_ports_guided'. Run creation was accepted after risk_acknowledged=true satisfied review-required checks.

