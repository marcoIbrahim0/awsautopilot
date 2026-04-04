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
- 3. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/03-arn-aws-s3-security-autopilot-access-logs-696505-0ca962a2
- 4. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/04-arn-aws-s3-security-autopilot-access-logs-696505-0dc8756d
- 5. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/05-arn-aws-s3-security-autopilot-access-logs-696505-0ff2bc8f
- 6. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/06-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e
- 7. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/07-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-21c09e7f
- 8. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/08-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-2c8ba273
- 9. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/09-arn-aws-s3-sa-wi7-seed-696505809372-202603282058-3ae05cd4
- 10. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/10-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-3ce30a5c
- 11. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/11-arn-aws-s3-security-autopilot-access-logs-696505-496f8cc3
- 12. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/12-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-499adc8a
- 13. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/13-arn-aws-s3-security-autopilot-access-logs-696505-4c631219
- 14. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/14-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-51f0f65a
- 15. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/15-arn-aws-s3-security-autopilot-dev-serverless-src-5b77d9d9
- 16. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/16-arn-aws-s3-arch1-bucket-website-a1-696505809372--7f361ff6
- 17. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/17-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-8f162041
- 18. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/18-arn-aws-s3-security-autopilot-access-logs-696505-9fa9f7b4
- 19. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/19-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-a76d1974
- 20. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/20-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-a781c11d
- 21. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/21-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-ad9bdd8f
- 22. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/22-arn-aws-s3-ocypheris-live-ct-20260328t181200z-eu-d03ad604
- 23. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/23-arn-aws-s3-sa-wi13-14-nopolicy-696505809372-2026-d3cf0cc7
- 24. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/24-arn-aws-s3-security-autopilot-access-logs-696505-dda812ab
- 25. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/25-arn-aws-s3-wi1-noncurrent-lifecycle-696505809372-dedc7b1c
- 26. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/26-arn-aws-s3-security-autopilot-access-logs-696505-deff1612
- 27. S3 general purpose buckets should block public read access (executable_bundle_generated) -> executable/actions/27-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-dfdf129a
- 28. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/28-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-e7f23835
- 29. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/29-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-ed8274a5
- 30. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/30-arn-aws-s3-phase2-wi1-lifecycle-696505809372-202-fb27abe2
- 31. S3 general purpose buckets should block public write access (executable_bundle_generated) -> executable/actions/31-arn-aws-s3-arch1-bucket-evidence-b1-696505809372-fddd2631
- 32. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/32-arn-aws-s3-security-autopilot-w6-envready-s311-r-abf5eb48
- 33. S3 general purpose buckets should block public access (executable_bundle_generated) -> executable/actions/33-arn-aws-s3-security-autopilot-w6-envready-s315-e-f497bc0c

Review-required actions:
- none

Manual-guidance actions:
- 1. S3 general purpose buckets should block public write access (manual_guidance_metadata_only) -> manual_guidance/actions/01-aws-account-696505809372-19337c80
- 2. S3 general purpose buckets should block public access (manual_guidance_metadata_only) -> manual_guidance/actions/02-arn-aws-s3-arch1-bucket-website-a1-696505809372--da0d429e
