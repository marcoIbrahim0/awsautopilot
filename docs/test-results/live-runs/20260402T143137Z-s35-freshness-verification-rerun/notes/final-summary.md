# S3.5 freshness-verification rerun on April 2, 2026 UTC

Status: `PASS` for truthful product-side closure verification of the already-applied safe `S3.5` fix, with stale control-plane freshness reduced to a separate bounded issue.

## Scope

- Account: `696505809372`
- Region: `eu-north-1`
- Action type: `s3_bucket_require_ssl`
- Affected action: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Affected bucket: `arch1-bucket-evidence-b1-696505809372-eu-north-1`
- Prior successful remediation run: `3c5c5cf3-1190-42c9-9ad7-737d57915ba5`

## Why this rerun was needed

The earlier safe executable rerun already proved the bounded `S3.5` product path:

- production generated a real executable bundle
- the bundle downloaded successfully
- local `terraform init`, `plan`, and `apply` succeeded against live AWS
- raw AWS showed the preserved CloudFront `Allow` plus added `DenyInsecureTransport`

What remained open was product-side verification. The retained post-apply readiness snapshot in the earlier package stayed stale, so the action could still appear open in product state even though raw AWS was already compliant.

This rerun closes that freshness/verification ambiguity without re-litigating the already-closed BPA bug.

## Inputs and guardrails

- Request inputs: `notes/request-inputs.json`
- Prior safe executable proof: [20260402T141121Z-s35-safe-exec-live-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T141121Z-s35-safe-exec-live-rerun/notes/final-summary.md)
- Prior BPA fail-closed proof: [20260401T230346Z-s35-bpa-live-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T230346Z-s35-bpa-live-rerun/notes/final-summary.md)

Important debugging constraint:

- `GET /api/actions/{id}` was not used because it still returns `500` for this action due to an unrelated action-detail serialization defect.

## Raw AWS reconfirmation

Fresh AWS readback retained in:

- `evidence/aws/post-verify-bucket-policy.json`
- `evidence/aws/post-verify-public-access-block.json`

Those retained payloads reconfirm the bucket is still compliant on raw AWS:

- preserved `AllowCloudFrontReadOnly`
- added `DenyInsecureTransport`
- bucket-level Public Access Block still enabled

## Product refresh attempts

Retained refresh evidence:

- pre-refresh readiness: `evidence/api/readiness-pre.json`
- pre-refresh actions list: `evidence/api/actions-list-pre.json`
- pre-refresh findings list: `evidence/api/findings-list-pre.json`
- ingest queueing: `evidence/api/account-ingest.json`
- action recompute queueing: `evidence/api/actions-compute.json`
- post-refresh readiness polls:
  - `evidence/api/readiness-post-5s.json`
  - `evidence/api/readiness-post-15s.json`
  - `evidence/api/readiness-post-30s.json`
- post-refresh action polls:
  - `evidence/api/actions-list-post-5s.json`
  - `evidence/api/actions-list-post-15s.json`
  - `evidence/api/actions-list-post-30s.json`
- post-refresh finding polls:
  - `evidence/api/findings-list-post-5s.json`
  - `evidence/api/findings-list-post-15s.json`
  - `evidence/api/findings-list-post-30s.json`

Those reruns prove:

- `POST /api/aws/accounts/696505809372/ingest` returned `202` and queued both `eu-north-1` and `us-east-1`
- `POST /api/actions/compute` returned `202`
- control-plane readiness stayed stale with `overall_ready=false`
- the action could still appear open after ingest plus compute

## What actually kept the action open

The critical retained finding was not an `S3.5` policy defect. It was status-layer disagreement.

Retained evidence shows:

- the canonical Security Hub finding later resolved during the rerun window
- but the `event_monitor_shadow` overlay stayed `OPEN`
- that stale shadow kept the effective product state open even after canonical resolution

Key proof files:

- `evidence/api/findings-list-reconcile-post-15s.json`
- `evidence/api/findings-list-reconcile-post-30s.json`
- `evidence/api/findings-list-reconcile-post-60s.json`
- `evidence/api/findings-list-reconcile-post-90s.json`
- `evidence/api/findings-list-reconcile-post-120s.json`

## Global reconcile result

Public reconcile evidence:

- `evidence/api/actions-reconcile.json`
- `evidence/api/actions-list-reconcile-post-15s.json`
- `evidence/api/actions-list-reconcile-post-30s.json`
- `evidence/api/actions-list-reconcile-post-60s.json`
- `evidence/api/actions-list-reconcile-post-90s.json`
- `evidence/api/actions-list-reconcile-post-120s.json`
- `evidence/api/readiness-reconcile-post-15s.json`
- `evidence/api/readiness-reconcile-post-30s.json`
- `evidence/api/readiness-reconcile-post-60s.json`
- `evidence/api/readiness-reconcile-post-90s.json`
- `evidence/api/readiness-reconcile-post-120s.json`

That retained sequence shows:

- public `POST /api/actions/reconcile` enqueued work successfully
- the exact bucket still did not close through that generic path
- readiness remained stale

Worker/API log evidence retained in:

- `evidence/logs/api-last-30m.json`
- `evidence/logs/worker-reconcile-integrity-error.json`
- `evidence/logs/worker-reconcile-shard-last-15m.json`

The worker logs also captured a bounded unrelated failure during the global reconcile path:

- `reconcile_inventory_shard` logged `Handler failed (IntegrityError) job_type=reconcile_inventory_shard. Message will retry/DLQ.`

That error did not reopen the `S3.5` bug, but it explains why the generic/global reconcile path is not a clean closure proof for this exact bucket.

## Targeted reconcile that truthfully closed the action

Targeted reconcile evidence:

- payload: `evidence/api/targeted-reconcile-shard-payload.json`
- enqueue result: `evidence/api/targeted-reconcile-shard-enqueue.json`

The targeted shard was scoped to:

- service `s3`
- region `eu-north-1`
- resource ARN `arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1`

Fresh post-target evidence:

- readiness: `evidence/api/readiness-targeted-post.json`
- actions list: `evidence/api/actions-list-targeted-post.json`
- findings list: `evidence/api/findings-list-targeted-post.json`

Those retained payloads prove the truthful product-side closure state:

- the finding is now `status=RESOLVED`
- `effective_status=RESOLVED`
- shadow status is `RESOLVED`
- shadow reason is `inventory_confirmed_compliant`
- remediation action `3970aa2f-edc5-4870-87bd-fa986dad3d98` is now `status=resolved`

## What remains bounded but separate

Fresh readiness proof in `evidence/api/readiness-targeted-post.json` still shows:

- `overall_ready=false`
- stale regions: `eu-north-1`, `us-east-1`

So control-plane freshness is still a real separate issue for this account. However, this rerun proves that stale readiness no longer blocks truthful closure of this already-remediated `S3.5` resource once the exact bucket inventory shadow is reconciled.

The remaining bounded non-`S3.5` issues are:

- stale control-plane event freshness for account `696505809372`
- unreliable generic/global inventory reconcile for this exact closure path, with a retained unrelated shard `IntegrityError`
- unrelated `GET /api/actions/{id}` serialization `500`

## Conclusion

The success condition for this task is met.

Product-side closure is now truthfully verified for the already-applied safe `S3.5` remediation:

- raw AWS remains compliant
- canonical Security Hub state is resolved
- shadow overlay is resolved
- product-facing finding is resolved
- product-facing action is resolved

The original BPA-conflicting `S3.5` bug remains closed, and the remaining residual work is a separate freshness/reconcile reliability follow-up, not a reopened `S3.5` defect.
