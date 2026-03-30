# Phase 3 Remediation Determinism Production Attempt

- Run ID: `20260329T003200Z-remediation-determinism-phase3-production`
- Date (UTC): `2026-03-29`
- Scope: Phase 3 apply-time data-source wave only (`WI-4`, `WI-5`, `WI-9`, `WI-10`, `WI-11`)
- Required live surface: `https://api.ocypheris.com`
- Tenant: `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`)
- Canary account: `696505809372`
- Region: `eu-north-1`
- Outcome: `BLOCKED`

## Summary

This retained package is the first production-only execution attempt for the new Phase 3 gate. It materially advances the Phase 3 closure state, but it does not make Phase 3 production-ready.

What this run proved on production:

- Gate 3B local regression passed after one stale create-path test was corrected to include `risk_acknowledged=true`.
- `WI-5` production deploy parity now exists after updating the canary read-role baseline to include `s3:GetBucketWebsite`.
- `WI-9` production parity is live: preview and create stay executable and surface `apply_time_merge=true` when bucket-policy capture fails concretely.
- `WI-11` production parity is live, and one retained single-run proof completed end to end:
  - production create kept `apply_time_merge=true`
  - Terraform `init`, `validate`, `plan`, and `apply` succeeded
  - AWS showed the managed abort-incomplete-multipart lifecycle rule live
  - the bundle-local restore helper returned the bucket to `NoSuchLifecycleConfiguration`
- `WI-4` production parity is live, and one retained single-run proof completed end to end:
  - production create kept `apply_time_merge=true`
  - Terraform `init`, `validate`, `plan`, `apply`, and `destroy` succeeded
  - the bundle-local policy restore helper restored the exact deny-only pre-apply policy
  - final cleanup returned the bucket to its original no-policy state

What still blocks Phase 3:

- `WI-10` still has no truthful production-backed candidate. A strict truth test showed:
  - bucket-level public access block was disabled on the candidate bucket
  - account-level S3 Block Public Access still had `BlockPublicPolicy=true`
  - AWS therefore rejected a fresh unconditional public policy on the canary account
  - without a truthful public non-website candidate, the production scrub branch could not be proven
- `WI-5` and `WI-9` have parity proof in this package, but not yet full retained create/apply/rollback proof.
- Gate 3D grouped mixed-tier production proof was not executed in this run.

Under the production-only contract, Phase 3 remains `BLOCKED`.

## Gate Decision

- Gate 3A preflight and deploy parity: `BLOCKED`
  - health, readiness, production auth, canary AWS access, and `s3:GetBucketWebsite` baseline all passed
  - `WI-5`, `WI-9`, and `WI-11` parity passed
  - `WI-10` remained blocked because no truthful production candidate could be seeded under account-level `BlockPublicPolicy`
- Gate 3B non-live regression: `PASS`
- Gate 3C required production scenarios: `PARTIAL`
  - `WI-4`: PASS
  - `WI-11`: PASS
  - `WI-5`: parity only
  - `WI-9`: parity only
  - `WI-10`: blocked
- Gate 3D grouped production proof: `NOT RUN`
- Gate 3E retained evidence: `PARTIAL`
  - retained package, transcripts, API captures, AWS captures, and final summary exist
  - final grouped proof and remaining scenario packages are still missing
- Final decision: `BLOCKED`

## Key Artifacts

- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/summary.json)
- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/notes/final-summary.md)
- [Local gate transcripts](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/local-gate/)
- [WI-4 create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/evidence/api/wi4-create-response.json)
- [WI-4 apply transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/evidence/aws/wi4-terraform-apply.txt)
- [WI-4 rollback transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/evidence/aws/wi4-terraform-destroy.txt)
- [WI-11 create response](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/evidence/api/wi11-create-response.json)
- [WI-11 apply transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/evidence/aws/wi11-terraform-apply.txt)
- [WI-11 restore transcript](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/evidence/aws/wi11-rollback-restore.txt)
- [WI-10 account-level S3 Block Public Access proof](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/evidence/aws/wi10-account-public-access-block.json)
