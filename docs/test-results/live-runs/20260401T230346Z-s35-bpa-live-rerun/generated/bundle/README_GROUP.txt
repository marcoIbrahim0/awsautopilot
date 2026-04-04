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
- 1. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/01-arn-aws-s3-security-autopilot-w6-strict-s311-exe-0ca99079
- 2. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/02-arn-aws-s3-security-autopilot-w6-strict-s315-exe-129fa65e
- 3. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/03-arn-aws-s3-security-autopilot-w6-envready-cloudt-23bf691b
- 4. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/04-arn-aws-s3-security-autopilot-w6-strict-s315-man-4da3d806
- 5. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/05-arn-aws-s3-security-autopilot-w6-envready-s311-r-61552073
- 6. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/06-arn-aws-s3-security-autopilot-w6-strict-s311-man-967d71a9
- 7. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/07-arn-aws-s3-security-autopilot-w6-envready-s311-e-9e4562df
- 8. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/08-arn-aws-s3-security-autopilot-w6-envready-access-b84115cb
- 9. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/09-arn-aws-s3-security-autopilot-w6-envready-s315-e-b8a67bbf
- 10. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/10-arn-aws-s3-security-autopilot-w6-envready-config-c1c2ed6d
- 11. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/11-arn-aws-s3-config-bucket-696505809372-830944d9
- 12. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/12-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-3970aa2f
- 13. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/13-arn-aws-s3-arch1-bucket-website-a1-696505809372--53b7b063
- 14. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/14-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-6826cb31
- 15. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/15-aws-account-696505809372-2ac461ec
- 16. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/16-arn-aws-s3-security-autopilot-access-logs-696505-0eb4440d
- 17. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/17-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-205f94f3
- 18. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/18-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-3b2f7c5d
- 19. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/19-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-413846db
- 20. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/20-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-44920b7c
- 21. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/21-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-bd4da43a
- 22. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/22-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-ceb048a5
- 23. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/23-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-cfdc868f
- 24. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/24-arn-aws-s3-security-autopilot-config-69650580937-1b7e11a5
- 25. S3 general purpose buckets should require requests to use SSL (review_required_metadata_only) -> review_required/actions/25-arn-aws-s3-ocypheris-live-ct-20260323162333-eu-n-9444f510

Manual-guidance actions:
- none
