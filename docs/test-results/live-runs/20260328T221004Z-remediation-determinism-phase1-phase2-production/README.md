# Phase 1 + Phase 2 Production-Only Remediation Determinism Run

Run ID: `20260328T221004Z-remediation-determinism-phase1-phase2-production`

This retained package captures the March 28, 2026 UTC production-only Phase 2 handoff on `master` at commit `481b5a00f8ec00f26174d20350e2bf740e5d856e`, using only `https://api.ocypheris.com` against tenant `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`) and canary account `696505809372` in `eu-north-1`.

## Final Outcome

- Gate 2A local Phase 2 rerun: `PASS`
- `WI-2` EC2.53 `ssm_only`: `PASS` with retained post-apply production lag reproduced
- `WI-8` EC2.53 `bastion_sg_reference`: `PASS` with retained post-apply production lag reproduced
- Grouped mixed-tier Phase 2 run: `PASS`
- `WI-1` S3.11 captured additive lifecycle merge: `BLOCKED`
- Overall Phase 2 gate: `BLOCKED`
- Overall Phase 1 + Phase 2 production-ready decision: `NO-GO`

Phase 2 remains blocked because no truthful production `WI-1` additive-merge candidate surfaced, even after seeding a real canary bucket with a renderable lifecycle configuration and rerunning production ingest plus scoped recompute. Overall signoff remains `NO-GO` even with the `WI-2` and `WI-8` live proofs because retained Phase 1 blockers still include `WI-12` and the already-retained production post-apply lag where findings/actions stay behind actual AWS state after apply.

## Evidence Map

- Metadata: [00-run-metadata.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/00-run-metadata.md)
- Machine-readable status: [summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/summary.json)
- Human summary: [notes/final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/notes/final-summary.md)
- Local Phase 2 gate transcripts: [local-gate/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/local-gate)
- Production API captures: [evidence/api/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/evidence/api)
- AWS evidence: [evidence/aws/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/evidence/aws)
- Terraform transcripts: [evidence/terraform/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/evidence/terraform)
- Scoped recompute transcripts: [evidence/recompute/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/evidence/recompute)
- `WI-1`: [scenarios/wi1/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/scenarios/wi1)
- `WI-2`: [scenarios/wi2/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/scenarios/wi2)
- `WI-8`: [scenarios/wi8/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/scenarios/wi8)
- Grouped Phase 2 proof: [scenarios/grouped/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T221004Z-remediation-determinism-phase1-phase2-production/scenarios/grouped)

## Key Retained Findings

- The exact eight-command Phase 2 local gate reran unchanged and stayed green.
- Production preflight, auth, tenant/account resolution, and remediation-settings patching all worked through the real production API.
- `WI-2` proved the revoke-only `ssm_only` branch end-to-end: create, preview, bundle generation, bundle download, local Terraform `init` / `validate` / `plan` / `apply`, AWS mutation proof, completed ingest follow-up, and rollback.
- `WI-8` proved the bastion-backed branch end-to-end after patching tenant remediation settings with a real canary bastion SG ID: create, preview, bundle generation, bundle download, local Terraform `init` / `validate` / `plan` / `apply`, AWS mutation proof, scoped recompute follow-up, rollback, bastion SG deletion, and remediation-settings restore.
- The grouped S3.11 mixed-tier run finalized successfully through the callback contract with two executable members and five `manual_guidance_only` members. The executable portion applied cleanly and was rolled back.
- Post-apply production lag reproduced again:
  - `WI-2` action `58a22607-666e-4016-8fe3-4ce62a235a6e` stayed `open` after completed ingest.
  - `WI-8` action `dfa0a526-87b8-4670-92d7-401a611f58f5` still stayed `open` after later scoped recompute.
  - Both grouped executable S3.11 actions stayed `open` after the grouped scoped recompute.
- `WI-1` remains blocked on truthful live candidate materialization. The seeded canary lifecycle bucket never surfaced as a live production action, so no additive-merge proof was claimed.
