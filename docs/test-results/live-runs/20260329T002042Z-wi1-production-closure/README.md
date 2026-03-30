# WI-1 Production Closure Run

Run ID: `20260329T002042Z-wi1-production-closure`

This retained package captures the March 29, 2026 UTC WI-1 production-closure follow-up on `master` at commit `481b5a00f8ec00f26174d20350e2bf740e5d856e`, using only [https://api.ocypheris.com](https://api.ocypheris.com) against tenant `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`) and canary account `696505809372` in `eu-north-1`.

## Final Outcome

- Focused local regression slice for the WI-1 fix: `PASS`
- Production runtime deploy: `PASS`
- Missing WI-1 finding materialization on the reconcile path: `FIXED`
- Truthful WI-1 additive-merge candidate: `STILL BLOCKED`
- Overall WI-1 production-closure decision: `BLOCKED`

The key production change is that the seeded lifecycle bucket now materializes truthfully through the live reconcile path as a bucket-scoped `event_monitor_shadow` finding. The gate is still blocked because that finding resolves as compliant, so production still does not expose a truthful open S3.11 action to preview, create, or apply for additive-merge proof.

## Evidence Map

- Metadata: [00-run-metadata.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/00-run-metadata.md)
- Machine-readable status: [summary.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/summary.json)
- Human summary: [notes/final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/notes/final-summary.md)
- Production API captures: [evidence/api/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/evidence/api)
- AWS evidence: [evidence/aws/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/evidence/aws)
- Terraform placeholder folder: [evidence/terraform/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/evidence/terraform)
- WI-1 scenario captures: [scenarios/wi1/](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/scenarios/wi1)
- Runtime deploy transcript: [notes/deploy-runtime.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/notes/deploy-runtime.log)

## Key Retained Findings

- Security Hub ingest still did not surface the seeded bucket. The retained post-deploy ingest window ended `no_changes_detected` with `updated_findings_count=0`.
- The shipped fix in [shadow_state.py](/Users/marcomaher/AWS%20Security%20Autopilot/backend/workers/services/shadow_state.py) now lets production reconcile create a truthful inventory-backed finding when no Security Hub finding exists for the same canonical bucket/control pair.
- The live seeded bucket now appears as finding `e14c5cb6-9ccd-413a-9dbe-f0b49a6e47d3` with:
  - `source=event_monitor_shadow`
  - `control_id=S3.11`
  - `resource_id=arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157`
  - `status=RESOLVED`
  - `shadow.status_reason=inventory_confirmed_compliant`
- Because the seeded lifecycle rule is already compliant under the current S3.11 inventory semantics, production correctly exposes no open action for that bucket even after explicit `POST /api/actions/reconcile` and `POST /api/actions/compute`.
- No preview, create, bundle download, Terraform apply, or rollback proof was claimed in this retained run because there was no truthful open action to execute.
- Both temporary WI-1 seed buckets were deleted at the end of the run.
