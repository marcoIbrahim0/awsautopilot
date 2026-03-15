AWS Security Autopilot — Non-executable remediation guidance

Action
------
- action_type: s3_bucket_block_public_access
- strategy_id: s3_bucket_block_public_access_standard
- support_tier: manual_guidance_only

Why this bundle is non-executable
---------------------------------
- Runtime evidence could not prove the bucket is private and website hosting is disabled.
- Missing bucket identifier for access-path validation.

Decision rationale
------------------
Family resolver preserved explicit S3.2 profile 's3_bucket_block_public_access_manual_preservation' but downgraded it to non-executable guidance. Runtime evidence could not prove the bucket is private and website hosting is disabled. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.

Contents
--------
- decision.json contains the canonical resolver decision, blocked reasons, and preservation summary.
- No Terraform or CloudFormation files were emitted because this branch is downgrade-only in Wave 6.
