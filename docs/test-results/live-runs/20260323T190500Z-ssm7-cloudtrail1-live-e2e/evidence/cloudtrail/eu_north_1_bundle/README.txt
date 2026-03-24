AWS Security Autopilot — Non-executable remediation guidance

Action
------
- action_type: cloudtrail_enabled
- strategy_id: cloudtrail_enable_guided
- support_tier: review_required_bundle

Why this bundle is non-executable
---------------------------------
- CloudTrail log bucket name is unresolved. Configure cloudtrail.default_bucket_name or provide strategy_inputs.trail_bucket_name.

Decision rationale
------------------
Family resolver kept compatibility profile 'cloudtrail_enable_guided' for strategy 'cloudtrail_enable_guided' but downgraded executability. CloudTrail log bucket name is unresolved. Configure cloudtrail.default_bucket_name or provide strategy_inputs.trail_bucket_name. Run creation did not require additional risk-only acceptance.

Contents
--------
- decision.json contains the canonical resolver decision, blocked reasons, and preservation summary.
- No Terraform or CloudFormation files were emitted because this branch is downgrade-only in Wave 6.
