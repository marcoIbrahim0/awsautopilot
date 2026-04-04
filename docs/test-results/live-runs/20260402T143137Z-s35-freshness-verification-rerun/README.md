# S3.5 freshness-verification rerun on April 2, 2026 UTC

- Run ID: `20260402T143137Z-s35-freshness-verification-rerun`
- Date: `2026-04-02` UTC
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- Account: `696505809372`
- Region: `eu-north-1`
- Mutation profile: `test28-root`
- Affected action: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Final result: `PASS`

Primary retained summary:

- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T143137Z-s35-freshness-verification-rerun/notes/final-summary.md)

Key evidence folders:

- [API evidence](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T143137Z-s35-freshness-verification-rerun/evidence/api)
- [AWS evidence](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T143137Z-s35-freshness-verification-rerun/evidence/aws)
- [Log evidence](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T143137Z-s35-freshness-verification-rerun/evidence/logs)

High-level outcome:

- Raw AWS still shows the already-applied safe `S3.5` fix on bucket `arch1-bucket-evidence-b1-696505809372-eu-north-1`.
- Fresh `POST /api/aws/accounts/696505809372/ingest` plus `POST /api/actions/compute` did not clear `overall_ready=false`; `eu-north-1` and `us-east-1` remained stale in control-plane readiness.
- During that refresh cycle, the canonical Security Hub finding resolved, but the product still appeared open because the `event_monitor_shadow` overlay remained stale and `OPEN`.
- Public `POST /api/actions/reconcile` did not truthfully close the exact bucket and the worker logs captured an unrelated `reconcile_inventory_shard` `IntegrityError`.
- A direct targeted inventory reconcile for the exact S3 bucket succeeded, refreshed `inventory_assets`, flipped the shadow row to `RESOLVED` with `inventory_confirmed_compliant`, and closed the product-facing action/finding while readiness remained stale.

Acceptance note:

- This package closes the remaining post-apply verification ambiguity from [20260402T141121Z-s35-safe-exec-live-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T141121Z-s35-safe-exec-live-rerun/notes/final-summary.md) without reopening the already-closed BPA conflict bug from [20260401T230346Z-s35-bpa-live-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260401T230346Z-s35-bpa-live-rerun/notes/final-summary.md).
