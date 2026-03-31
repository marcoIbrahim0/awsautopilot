# Phase 5 Support-Bucket Cluster Validation And Canary Rollout

- Run ID: `20260326T025813Z-phase5-support-bucket-cluster-canary-blocked`
- Date (UTC): `2026-03-26`
- Frontend: `https://ocypheris.com`
- API: `https://api.ocypheris.com`
- Default canary target from the Phase 5 plan: account `029037611564`, region `eu-north-1`
- Outcome: `BLOCKED`
- Failure bucket: `operator access / live auth`

## Summary

This retained run completed the full local Phase 5 cluster gate and the focused `Config.1`, `S3.9`, and `CloudTrail.1` family revalidation, then stopped before live canary run creation because no current production operator auth path was usable on March 26, 2026.

The local cluster gate was green:
- full Phase 5 cluster suite: `353 passed in 1.47s`
- focused `Config.1` slice: `16 passed`
- focused `S3.9` slice: `6 passed`
- focused `CloudTrail.1` slice: `8 passed`

The live canary was blocked by reproducible auth/access failures:
- decrypted Chrome `api.ocypheris.com` cookie bearer returned `401 {"detail":"User not found"}`
- production login for `maromaher54@gmail.com / <REDACTED_PASSWORD>` returned `Verify your email before signing in`
- production login for `marco.ibrahim@ocypheris.com / <REDACTED_PASSWORD>` returned `Login failed`
- read-only production DB lookup for same-operator bearer minting was blocked by Neon quota exhaustion
- retained March 23, 2026 `Valens` bearer from [SSM.7 and CloudTrail.1 live E2E](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260323T190500Z-ssm7-cloudtrail1-live-e2e/notes/final-summary.md) now returns `401 {"detail":"User not found"}`

No new live remediation runs were created in this rollout attempt.

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T025813Z-phase5-support-bucket-cluster-canary-blocked/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T025813Z-phase5-support-bucket-cluster-canary-blocked/notes/final-summary.md)
- [Phase 5 support-bucket implementation plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/phase-5-support-bucket-family-implementation-plan.md)
- [SSM.7 and CloudTrail.1 live E2E on March 23, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260323T190500Z-ssm7-cloudtrail1-live-e2e/notes/final-summary.md)
- [CloudTrail.1 live generate/download/apply validation on March 23, 2026 UTC](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260323T162259Z/notes/final-summary.md)
