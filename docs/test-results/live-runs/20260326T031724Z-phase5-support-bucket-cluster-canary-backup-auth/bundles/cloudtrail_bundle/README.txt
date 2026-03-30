AWS Security Autopilot — Non-executable remediation guidance

Action
------
- action_type: cloudtrail_enabled
- strategy_id: cloudtrail_enable_guided
- support_tier: review_required_bundle

Why this bundle is non-executable
---------------------------------
- CloudTrail log bucket 'ocypheris-live-ct-20260323162333-eu-north-1' could not be verified from this account context (403).

Decision rationale
------------------
Family resolver kept compatibility profile 'cloudtrail_enable_guided' for strategy 'cloudtrail_enable_guided' but downgraded executability. CloudTrail log bucket 'ocypheris-live-ct-20260323162333-eu-north-1' could not be verified from this account context (403). Run creation did not require additional risk-only acceptance.

Operator checklist
------------------
- Preserve the current configuration or update the target resource until an executable branch becomes safe.

Contents
--------
- decision.json contains the canonical resolver decision, blocked reasons, and preservation summary.
- No Terraform or CloudFormation files were emitted because the system could not prove this change was safe to apply automatically.
