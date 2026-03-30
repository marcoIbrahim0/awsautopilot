AWS Security Autopilot — Mixed-tier Group PR bundle

Layout version: grouped_bundle_mixed_tier/v1
Execution root: executable/actions

Only executable Terraform lives under executable/actions/.
review_required/actions/ and manual_guidance/actions/ contain metadata-only guidance.
run_all.sh executes only executable/actions/ and no-ops successfully when no runnable Terraform folders exist.

Run from bundle root:
  chmod +x ./run_all.sh
  ./run_all.sh

Executable actions:
- 1. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-53cda243
- 2. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-config-69650580937-a57bd4fc
- 4. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-envready-s315-e-0361bcde
- 5. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-w6-envready-s311-e-42eef23b
- 6. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-strict-s315-man-4e5dc9e9
- 7. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-strict-s315-exe-50b7681f
- 8. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-access-6a75c127
- 9. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-strict-s311-man-88c01f62
- 10. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-w6-envready-cloudt-c81bf06a
- 11. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-security-autopilot-w6-strict-s311-exe-cbb438f0
- 12. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-security-autopilot-w6-envready-config-d42826b3
- 13. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-config-bucket-696505809372-d5f1fd68

Review-required actions:
- none

Manual-guidance actions:
- 3. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/03-aws-account-696505809372-7be937c3
