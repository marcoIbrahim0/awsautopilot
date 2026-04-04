AWS Security Autopilot — Group action artifact

Action: S3 general purpose buckets should block public access
Action ID: f497bc0c-ddcb-4191-8fa5-c6ed21bbe134
Tier: manual_guidance
Tier root: manual_guidance/actions
Outcome: manual_guidance_metadata_only
Strategy: s3_migrate_cloudfront_oac_private
Profile: s3_migrate_cloudfront_oac_private_manual_preservation

Decision summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Target bucket 'security-autopilot-w6-envready-s315-exec-696505809372' existence could not be verified from this account context (403). Do not keep the existing-bucket remediation path executable until bucket existence is proven. Run creation did not require additional risk-only acceptance.
This folder is metadata only and does not contain runnable Terraform.
