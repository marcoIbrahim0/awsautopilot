AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public read access
Action ID: deff1612-54f9-4b10-85ae-afc1e557e571
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private_manual_preservation

Decision summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Target bucket 'security-autopilot-access-logs-696505809372-r94854-access-logs' existence could not be verified from this account context (403). Do not keep the existing-bucket remediation path executable until bucket existence is proven. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
