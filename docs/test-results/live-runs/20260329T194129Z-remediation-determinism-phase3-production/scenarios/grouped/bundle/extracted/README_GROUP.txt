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
- 1. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-4b97cf9a
- 2. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-security-autopilot-access-logs-696505-8ab29997
- 4. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-w6-envready-cloudt-04996269
- 5. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-config-bucket-696505809372-33ed3776
- 6. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-envready-s311-e-54b0d584
- 7. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-strict-s311-exe-6cb0769e
- 8. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-security-autopilot-w6-envready-access-747e6a9e
- 9. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-strict-s311-man-8ada62c8
- 10. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-8edeb7f6
- 11. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-security-autopilot-w6-strict-s315-man-971002ff
- 12. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-security-autopilot-w6-strict-s315-exe-d108dd29
- 13. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-security-autopilot-config-69650580937-d3419cb8
- 14. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/14-arn-aws-s3-security-autopilot-w6-envready-config-da9d8713
- 15. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/15-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-deb71e7d
- 16. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/16-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-176c29ed
- 17. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/17-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-a9e5a989
- 18. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/18-arn-aws-s3-security-autopilot-access-logs-696505-37e0f71d
- 19. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/19-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-abaa9de7
- 20. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/20-arn-aws-s3-security-autopilot-w6-envready-s315-e-ba09febf

Review-required actions:
- none

Manual-guidance actions:
- 3. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/03-aws-account-696505809372-cbe0d2c3
