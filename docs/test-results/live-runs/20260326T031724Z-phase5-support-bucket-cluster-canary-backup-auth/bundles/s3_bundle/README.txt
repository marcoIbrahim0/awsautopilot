AWS Security Autopilot — Non-executable remediation guidance

Action
------
- action_type: s3_bucket_access_logging
- strategy_id: s3_enable_access_logging_guided
- support_tier: review_required_bundle

Why this bundle is non-executable
---------------------------------
- Destination log bucket 'security-autopilot-phase5-access-logs-696505809372-canary' could not be verified from this account context (404).

Decision rationale
------------------
Family resolver kept S3.9 executable by switching to dedicated destination-bucket creation with secure defaults. Destination log bucket 'security-autopilot-phase5-access-logs-696505809372-canary' could not be verified from this account context (404). Run creation was accepted after risk_acknowledged=true satisfied review-required checks.

Operator checklist
------------------
- Confirm the source bucket scope is correct for this logging change.
- Confirm whether 'security-autopilot-phase5-access-logs-696505809372-canary' should receive access logs before retrying.
- If the destination bucket should be auto-created, rerun the executable create-destination branch instead of the review-only path.

Contents
--------
- decision.json contains the canonical resolver decision, blocked reasons, and preservation summary.
- No Terraform or CloudFormation files were emitted because the system could not prove this change was safe to apply automatically.
