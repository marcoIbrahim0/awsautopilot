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
- 3. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-strict-s311-exe-1df0126d
- 4. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-envready-config-3f68cef8
- 5. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-w6-envready-s315-e-7df28662
- 6. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-envready-access-7f624e07
- 7. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-81625b6a
- 9. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-cloudt-9c62231f

Review-required actions:
- none

Manual-guidance actions:
- 1. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/01-arn-aws-s3-config-bucket-696505809372-006b6ba6
- 2. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/02-arn-aws-s3-security-autopilot-w6-strict-s315-exe-00b8c39c
- 8. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/08-arn-aws-s3-security-autopilot-w6-strict-s315-man-92f5f5a3
- 10. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/10-arn-aws-s3-security-autopilot-w6-strict-s311-man-d6eb9cb9
- 11. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/11-aws-account-696505809372-c9716eb3
