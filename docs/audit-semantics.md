# Remediation audit semantics (Step 7.5)

## Primary audit record: `remediation_runs`

The **`remediation_runs`** table is the source of truth for every remediation run. It records:

- **Who:** `approved_by_user_id` (user who approved/started the run)
- **When:** `started_at`, `completed_at`, `created_at`, `updated_at`
- **What:** `action_id`, `mode` (currently `pr_only`; historical runs may still show `direct_fix`)
- **Outcome:** `status`, `outcome`, `logs`, `artifacts`

## Immutability of completed runs

Once a run reaches **status = success** or **status = failed**, the following fields are **immutable**:

- `outcome`
- `logs`
- `artifacts`

No updates or overwrites are allowed after completion. This gives an append-only audit feel and satisfies the remediation safety rule: **"Full audit log for every run."**

- **Enforcement:** Application logic in `backend/services/remediation_audit.py`:
  - `is_run_completed(status)` — true when status is success or failed
  - `allow_update_outcome(run)` — false when run is completed; use before writing outcome/logs/artifacts
- The worker (remediation_run job) checks `allow_update_outcome(run)` before writing and skips idempotently when the run is already completed.
- Any future PATCH API for remediation runs must reject updates to `outcome`, `logs`, or `artifacts` when the run is completed.

## Optional: `audit_log` table

For compliance dashboards and search, an optional **`audit_log`** table stores one-line summary events:

- `tenant_id`, `event_type`, `entity_type`, `entity_id`, `user_id`, `timestamp`, `summary`
- Example event: `event_type=remediation_run_completed`, `entity_type=remediation_run`, `summary="run_id=... action_id=... status=success outcome=..."`

The worker writes one row to `audit_log` when a remediation run completes. This is a denormalized summary; **`remediation_runs` remains the primary audit record.**

## Operational visibility

When a remediation run completes, the worker logs a structured line for CloudWatch/operational visibility:

```
RemediationRun completed run_id=<uuid> action_id=<uuid> status=success
```

This supports metrics, alarms, and dashboards without querying the database.
