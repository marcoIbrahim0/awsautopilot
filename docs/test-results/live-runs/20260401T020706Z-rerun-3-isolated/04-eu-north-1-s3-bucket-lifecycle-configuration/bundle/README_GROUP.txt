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
- 1. S3 bucket lifecycle rules configured (executable_bundle_generated) -> executable/actions/01-arn-aws-s3-arch1-bucket-website-a1-696505809372--c8d496fe
- 2. S3 bucket lifecycle rules configured (executable_bundle_generated) -> executable/actions/02-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-ee09b36c
- 3. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-w6-envready-cloudt-04996269
- 4. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-config-bucket-696505809372-33ed3776
- 5. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-w6-strict-s311-exe-6cb0769e
- 6. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-w6-envready-access-747e6a9e
- 7. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-security-autopilot-w6-strict-s315-exe-d108dd29
- 8. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-4b97cf9a
- 9. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-security-autopilot-w6-envready-config-da9d8713
- 10. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-security-autopilot-w6-envready-s311-e-54b0d584
- 11. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-8edeb7f6
- 12. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-security-autopilot-w6-strict-s315-man-971002ff
- 13. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-security-autopilot-w6-strict-s311-man-8ada62c8
- 14. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/14-arn-aws-s3-security-autopilot-w6-envready-s315-e-ba09febf
- 15. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/15-arn-aws-s3-security-autopilot-access-logs-696505-8ab29997
- 17. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/17-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-deb71e7d
- 18. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/18-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-176c29ed
- 19. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/19-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-a9e5a989
- 20. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/20-arn-aws-s3-security-autopilot-access-logs-696505-37e0f71d
- 21. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/21-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-abaa9de7
- 22. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/22-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-8d9e8cc1
- 23. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/23-arn-aws-s3-security-autopilot-config-69650580937-d3419cb8
- 24. S3 general purpose buckets should have Lifecycle configurations (executable_bundle_generated) -> executable/actions/24-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-53c07253

Review-required actions:
- none

Manual-guidance actions:
- 16. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/16-aws-account-696505809372-cbe0d2c3
