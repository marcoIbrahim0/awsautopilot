# March 25, 2026 live follow-up summary

## Scope

This retained run covers the approved March 25, 2026 follow-up for the safety-downgrade product work:

- `S3.2` should no longer dead-end as vague manual-only when the product cannot safely prove website/public-access state.
- `S3.9` should stay executable by creating a hardened destination log bucket when the source bucket is known but the destination bucket is missing or unverifiable.

The run used the deployed production stack, the real browser flow, and customer-run Terraform bundles. No local recompute shortcut was used as proof.

## Deployed runtime

- Backend/serverless runtime redeployed to image tag `20260325T012906Z`.
- Frontend Cloudflare runtime promoted to version `2892423b-ecbd-4209-b6bb-ce8888a093c9`.
- A deploy-path regression was found and fixed during rollout: the serverless deploy path was not propagating `DATABASE_URL_FALLBACK`, which caused the first March 25 backend rollout to boot without a usable fallback DB URL and return `500` on `/health` and `/ready`.
- After the deploy-path fix, live health recovered:
  - `https://api.ocypheris.com/health` => `200`
  - `https://api.ocypheris.com/ready` => `200`

## S3.2 result

`S3.2` now behaves as the product change intended. The retained March 25 run evidence shows:

- the grouped live flow no longer strands the family as an unexplained dead-end
- the outcome is a truthful review/metadata-only result
- the callback path converges that outcome instead of leaving the family stuck in `not_run_yet`
- the grouped UI explains why no automatic changes were included

This is the successful production proof point for the S3.2 side of the change.

## S3.9 result

`S3.9` partially passed and then exposed a new production runtime defect.

### What passed

- Real Playwright flow reached the live grouped action page.
- First create attempt returned the expected risk-acknowledgement warning.
- Second create attempt with acknowledgement returned `201`.
- Production created:
  - group id `8d0b831d-8c37-48eb-b1f2-099d6271faaa`
  - group run id `67a6b727-808f-4f82-a7c4-ee711203cf72`
  - remediation run id `715d4f2a-0d41-4432-a2db-94075df38dc2`
- Bundle download succeeded.
- Bundle contents were structurally correct:
  - `bundle_manifest.json`
  - `decision_log.md`
  - `run_all.sh`
  - `replay_group_run_reports.sh`
- Bundle decisions proved the new branch is live in production:
  - `13` executable members selected profile `s3_enable_access_logging_create_destination_bucket`
  - `1` account-scoped member remained `review_required_metadata_only`
  - the generated destination bucket name was `security-autopilot-access-logs-696505809372`

### Where it failed

The downloaded production bundle failed during customer-run execution.

- Running `AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh` created the shared destination bucket successfully for the first executable action.
- The remaining executable actions then failed with `BucketAlreadyOwnedByYou` because each action folder tried to create that same shared destination bucket again.
- The grouped callback truthfully finalized the live group run as failed.

Retained production evidence:

- Bundle transcript:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260325T002031Z-s3-safety-followup-live-e2e/evidence/api/s3_9-run-all.log`
- Final group-run API truth:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260325T002031Z-s3-safety-followup-live-e2e/evidence/api/s3_9-group-runs-post-run-all.json`
- Final group-detail API truth:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260325T002031Z-s3-safety-followup-live-e2e/evidence/api/s3_9-group-detail-post-run-all.json`
- Final browser-visible grouped state:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260325T002031Z-s3-safety-followup-live-e2e/evidence/playwright/s3_9-post-run-failure.png`
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260325T002031Z-s3-safety-followup-live-e2e/evidence/playwright/s3_9-post-run-failure-body.txt`

### Final live state after the failed run

- Group counters:
  - `run_successful = 0`
  - `run_not_successful = 13`
  - `metadata_only = 1`
  - `not_run_yet = 0`
- Group run `67a6b727-808f-4f82-a7c4-ee711203cf72`:
  - status `failed`
  - started `2026-03-25T01:46:37.954243+00:00`
  - finished `2026-03-25T01:52:10+00:00`
- The remediation run remained `success` because bundle generation/download succeeded; the failure happened later in the customer-run Terraform step.

## Failure classification

This stop is a `bundle/runtime regression`.

The newly deployed resolver/generation path is live and reachable. The broken part is the generated grouped bundle shape for the multi-member S3.9 create-destination case: every executable action owns the same destination-bucket creation resource instead of creating that shared bucket once and then reusing it.

The retained bundle confirms this directly: all `13` executable action folders contain `resource "aws_s3_bucket" "log_destination"` targeting the same bucket name `security-autopilot-access-logs-696505809372`.

## Next required product fix

Narrow fix scope:

- keep the new S3.9 create-destination branch
- generate the shared destination bucket exactly once per grouped bundle
- let the remaining executable members depend on or reuse that shared bucket instead of recreating it
- retain the review-only account member as-is
- redeploy
- rerun the same live S3.9 family on production

Until that fix lands, the truthful production statement is:

- `S3.2` is fixed live
- `S3.9` create-destination generation is live, but the grouped customer-run Terraform bundle is not yet safe for multi-member execution
