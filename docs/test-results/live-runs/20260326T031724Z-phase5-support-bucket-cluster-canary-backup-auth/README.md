# Phase 5 Support-Bucket Cluster Canary Via Backup Auth

> ⚠️ Superseded: this package captures the pre-fix March 26 backup-auth canary. See the implemented full rerun at [20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/README.md) and the focused CloudTrail postdeploy recheck at [20260326T052354Z-phase5-cloudtrail-postdeploy-recheck](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/README.md) for the current Phase 5 state.

- Run ID: `20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth`
- Date (UTC): `2026-03-26`
- Frontend: `https://ocypheris.com`
- API: `https://api.ocypheris.com`
- Auth path: isolated authenticated browser/API session for `Valens Local Backup`
- Live tenant/account used: tenant `Valens Local Backup`, account `696505809372`, region `eu-north-1`
- Default canary target from the Phase 5 plan: account `029037611564`, region `eu-north-1`
- Outcome: `PARTIAL`
- Failure bucket: `live_canary_revealed_runtime_and_resolver_gaps`

## Summary

This retained run resumed the blocked March 26, 2026 Phase 5 rollout using a fresh authenticated backup-tenant session instead of the broken live login path.

The run proved:
- live auth is no longer the immediate blocker from this workspace
- fresh live PR-bundle runs can be created for `Config.1`, `S3.9`, and `CloudTrail.1`
- `Config.1` still exposes a real live gap: the executable account-local bundle applies successfully, preserves the support-bucket baseline, but does not close the control because it keeps the existing selective recorder scope that excludes required IAM resource types
- `S3.9` and `CloudTrail.1` still resolve to `review_required_bundle` on this tenant/account, so they do not yet promote to executable live rollout

## Family Outcomes

- `Config.1`
  - remediation run `f5858299-3f08-4100-8c32-130736e427db`
  - result: executable PR bundle generated and applied locally with `AWS_PROFILE=test28-root`
  - live gap: finding [dd46ab79-1ea5-4ea7-a754-0d5e7335cbc1](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth/api/config_finding_post.json) remained `NEW` with `CONFIG_RECORDER_MISSING_REQUIRED_RESOURCE_TYPES`
  - support-bucket posture after apply:
    - public access block: enabled
    - encryption: `aws:kms` with bucket key
    - lifecycle: multipart-abort rule present
    - SSL-only deny policy present
    - Config delivery statements present

- `S3.9`
  - remediation run `cd1b5f43-a971-4c78-ba37-1492804d66e7`
  - result: non-executable guidance bundle only
  - selected profile: `s3_enable_access_logging_create_destination_bucket`
  - final support tier: `review_required_bundle`
  - blocking reason: destination bucket `security-autopilot-phase5-access-logs-696505809372-canary` could not be verified from this account context (`404`)

- `CloudTrail.1`
  - remediation run `91176ee9-6db1-42c1-aaa8-036b2f2b0d94`
  - result: non-executable guidance bundle only
  - selected profile: `cloudtrail_enable_guided`
  - final support tier: `review_required_bundle`
  - blocking reason: existing trail bucket `ocypheris-live-ct-20260323162333-eu-north-1` could not be verified from this account context (`403`)

## Sibling S3 Finding Check

No new sibling S3 findings were introduced on the Config helper bucket during this canary.

Observed post-apply state for `arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1`:
- existing `RESOLVED`: `S3.2`, `S3.3`, `S3.5`, `S3.8`, `S3.9`, `S3.17`
- existing `NEW`: `S3.13`

The post-apply query did not introduce any new `NEW` sibling findings beyond the pre-existing `S3.13`.

## Rollout Decision

- Local acceptance criteria: met
- Live auth blocker: worked around
- Canary acceptance criteria: not met
- Rollout decision: keep Phase 5 `in progress`; do not promote the support-bucket family cluster yet

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth/notes/final-summary.md)
- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T031724Z-phase5-support-bucket-cluster-canary-backup-auth/summary.json)
- [Initial auth-blocked attempt](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T025813Z-phase5-support-bucket-cluster-canary-blocked/README.md)
- [Phase 5 support-bucket implementation plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/phase-5-support-bucket-family-implementation-plan.md)
