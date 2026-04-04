# S3.5 post-apply freshness debug on April 2, 2026 UTC

Status: `PASS` for bounded issue reduction, with no new code change required from this run.

## Scope

- Account: `696505809372`
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- User: `7c43e0b3-6e98-43af-826f-f4eeaa5af674`
- Region focus: `eu-north-1`
- Action: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Bucket: `arch1-bucket-evidence-b1-696505809372-eu-north-1`
- Prior safe bundle proof: `3c5c5cf3-1190-42c9-9ad7-737d57915ba5`

## Why this rerun was needed

The earlier April 2 retained chain already proved:

- the safe executable `S3.5` bundle path works on production
- the exact bucket can be reconciled truthfully to `RESOLVED`
- the original BPA-conflicting `S3.5` bug stays closed

What remained ambiguous was the residual freshness/debug issue:

- readiness still showed `overall_ready=false`
- the last retained generic/global reconcile path had surfaced a shard `IntegrityError`
- it was not yet clear whether the true remaining blocker was control-plane freshness, worker execution, compute lag, stale finding materialization, generic reconcile reliability, or another product bug

## Raw AWS reconfirmation

Fresh raw AWS evidence:

- `evidence/aws/pre-verify-bucket-policy.json`
- `evidence/aws/pre-verify-public-access-block.json`

Those payloads reconfirm the bucket still holds the expected compliant state:

- preserved `AllowCloudFrontReadOnly`
- added `DenyInsecureTransport`
- bucket-level Public Access Block still enabled

## Required live API flow

Fresh API evidence:

- `evidence/api/readiness-pre.json`
- `evidence/api/actions-list-pre.json`
- `evidence/api/findings-list-pre.json`
- `evidence/api/account-ingest.json`
- `evidence/api/actions-compute.json`
- `evidence/api/readiness-post-30s.json`
- `evidence/api/actions-list-post-30s.json`
- `evidence/api/findings-list-post-30s.json`
- `evidence/api/actions-reconcile.json`
- `evidence/api/readiness-reconcile-post-60s.json`
- `evidence/api/actions-list-reconcile-post-60s.json`
- `evidence/api/findings-list-reconcile-post-60s.json`

What this rerun proved:

- `POST /api/aws/accounts/696505809372/ingest` still returns `202`
- `POST /api/actions/compute` still returns `202`
- `POST /api/actions/reconcile` still returns `202`
- readiness stayed stale through the whole normal refresh flow
- action `3970aa2f-edc5-4870-87bd-fa986dad3d98` remained `resolved`
- the matching finding remained `RESOLVED` with effective shadow `RESOLVED`

So the old targeted bucket reconcile is no longer needed to keep this resource truthful. The truthful closure persisted.

## Control-plane freshness classification

Fresh database evidence before synthetic input:

- `evidence/api/control-plane-ingest-status.tsv`

That shows the account-level readiness rows were still stuck at:

- `eu-north-1`: last intake `2026-03-24T17:15:12.987+00`
- `us-east-1`: last intake `2026-03-24T17:19:33.690+00`

Fresh synthetic-event evidence:

- `evidence/api/control-plane-synthetic-event-eu-north-1.json`
- `evidence/api/control-plane-synthetic-event-us-east-1.json`
- `evidence/api/readiness-post-synthetic.json`
- `evidence/api/control-plane-ingest-status-post-synthetic.tsv`

Those retained payloads prove:

- both supported synthetic control-plane events were accepted with `enqueued=1`
- readiness immediately flipped to `overall_ready=true`
- both region rows updated to fresh April 2, 2026 UTC timestamps

That narrows the residual issue sharply:

- the current product pipeline can update control-plane readiness
- the stale readiness in normal operation is not explained by action compute lag
- it is not explained by stale `S3.5` finding materialization
- it is not explained by the safe bundle path regressing
- it is not explained by a currently reproduced generic/global reconcile crash in this run window

## Generic/global reconcile status in this run

Fresh worker evidence:

- `evidence/logs/worker-window.json`

The current run did not reproduce the older retained `reconcile_inventory_shard` `IntegrityError`.

Observed worker output in this window was limited to:

- ordinary Lambda invocations
- two unrelated `shadow overlay update matched zero rows` warnings for `RDS.PUBLIC_ACCESS` and `RDS.ENCRYPTION`

So the historical shard `IntegrityError` remains retained evidence, but it was not the active blocker during this rerun.

## Exact bounded remaining issue

The remaining issue is now reduced to:

`Account 696505809372 is not receiving fresh live allowlisted control-plane events, so readiness becomes stale even though the current runtime can update readiness immediately when given fresh supported control-plane input.`

> ❓ Needs verification: Why did live upstream control-plane freshness stop advancing for account `696505809372` after March 24, 2026 UTC? The supported synthetic path proves the SaaS-side readiness update still works.

## Conclusion

No new `S3.5` code bug was reproduced.

The safe `S3.5` bucket remains truthful end to end:

- raw AWS is compliant
- action state is `resolved`
- finding state is `RESOLVED`
- generic product refresh calls do not reopen it

The residual ambiguity is no longer in `S3.5` execution, compute, or finding materialization. It is a separate control-plane freshness signal gap for the live account.
