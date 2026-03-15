AWS Security Autopilot — Non-executable remediation guidance

Action
------
- action_type: s3_bucket_require_ssl
- strategy_id: s3_enforce_ssl_strict_deny
- support_tier: review_required_bundle

Why this bundle is non-executable
---------------------------------
- AccessDenied
- Bucket policy preservation evidence is missing for merge-safe SSL enforcement.
- Existing bucket policy capture failed (AccessDenied).

Decision rationale
------------------
Family resolver downgraded S3.5 strategy 's3_enforce_ssl_strict_deny' because merge-safe bucket policy preservation evidence is incomplete. AccessDenied Bucket policy preservation evidence is missing for merge-safe SSL enforcement. Existing bucket policy capture failed (AccessDenied). Run creation did not require additional risk-only acceptance.

Contents
--------
- decision.json contains the canonical resolver decision, blocked reasons, and preservation summary.
- No Terraform or CloudFormation files were emitted because this branch is downgrade-only in Wave 6.
