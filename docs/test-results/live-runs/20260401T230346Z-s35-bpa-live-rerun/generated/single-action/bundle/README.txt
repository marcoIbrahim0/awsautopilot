AWS Security Autopilot — Non-executable remediation guidance

Action
------
- action_type: s3_bucket_require_ssl
- strategy_id: s3_enforce_ssl_strict_deny
- support_tier: review_required_bundle

Why this bundle is non-executable
---------------------------------
- Current bucket policy is public and S3 Block Public Access prevents public policies, so merge-preserving SSL enforcement would be rejected by PutBucketPolicy.

Decision rationale
------------------
Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because preserving the current public bucket policy would conflict with S3 Block Public Access. Current bucket policy is public and S3 Block Public Access prevents public policies, so merge-preserving SSL enforcement would be rejected by PutBucketPolicy. Run creation did not require additional risk-only acceptance.

Contents
--------
- decision.json contains the canonical resolver decision, blocked reasons, and preservation summary.
- No Terraform or CloudFormation files were emitted because this branch is downgrade-only in Wave 6.
