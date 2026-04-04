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
- none

Review-required actions:
- 9. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/09-arn-aws-s3-security-autopilot-access-logs-696505-0ebbf82c
- 10. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/10-arn-aws-s3-security-autopilot-w6-strict-s311-exe-3b58320d
- 11. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/11-arn-aws-s3-security-autopilot-w6-envready-s315-e-46d8436f
- 12. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/12-arn-aws-s3-security-autopilot-w6-envready-config-7c75dd09
- 13. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/13-arn-aws-s3-security-autopilot-w6-envready-cloudt-838f4503
- 14. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/14-arn-aws-s3-security-autopilot-w6-envready-access-b8506dba
- 15. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/15-arn-aws-s3-security-autopilot-w6-envready-s311-e-ea2b71a1
- 16. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/16-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-03bbb5fd
- 17. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/17-arn-aws-s3-security-autopilot-config-69650580937-bc116f71
- 18. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/18-arn-aws-s3-security-autopilot-w6-strict-s311-man-82ed26b1
- 19. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/19-arn-aws-s3-security-autopilot-w6-strict-s315-man-a1d8f3bf
- 20. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/20-arn-aws-s3-security-autopilot-w6-strict-s315-exe-c533dff3
- 21. S3 general purpose buckets should have Lifecycle configurations (review_required_metadata_only) -> review_required/actions/21-arn-aws-s3-config-bucket-696505809372-e55dca93

Manual-guidance actions:
- 1. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/01-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-06464919
- 2. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/02-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-14ffeb41
- 3. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/03-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-3bab593b
- 4. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/04-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-63f91a78
- 5. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/05-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-d8b98d62
- 6. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/06-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-e4bf59d8
- 7. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/07-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-e65afccb
- 8. S3 general purpose buckets should have Lifecycle configurations (manual_guidance_metadata_only) -> manual_guidance/actions/08-aws-account-696505809372-4a5a765e
