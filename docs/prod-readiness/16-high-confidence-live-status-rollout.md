# Item 16 High-Confidence Live Status Rollout Policy

This document defines the production rollout policy for Item `16` (high-confidence live status updates), in PM/ops language, and maps directly to current runtime guardrails.

Cross-reference:
- [Important To Do](important-to-do.md)
- [Control-Plane Event Monitoring](../control-plane-event-monitoring.md)
- [Reconciliation Quality Review](../reconciliation_quality_review.md)
- [`backend/config.py`](../../backend/config.py)
- [`backend/workers/services/shadow_state.py`](../../backend/workers/services/shadow_state.py)

## Policy Summary (Plain Language)

Only high-confidence controls are allowed to update customer-visible canonical finding status in production.  
If a read is uncertain, the platform keeps the existing canonical status unchanged and only records shadow evidence.

## Pilot Scope

Use a tenant-scoped pilot before global rollout:

1. Start with one or two internal pilot tenants that have stable control-plane intake in at least one active region.
2. Limit control scope to this initial high-confidence set:
   - `S3.1`
   - `SecurityHub.1`
   - `GuardDuty.1`
3. Keep medium/low-confidence controls out of live promotion during this pilot.
4. Run the pilot for at least `7` consecutive days before global enablement.

## Success Metrics (Must Pass)

For pilot tenants, all of the following must hold during the pilot window:

1. `0` confirmed false-resolved canonical findings for pilot controls.
2. In-scope `NEW` match rate is `>= 95%`.
3. Shadow freshness lag stays `< 6 hours`.
4. Missing canonical/resource keys remain `0`.
5. Inventory reconciliation health stays within configured prerequisites:
   - queue depth `<= 100`
   - DLQ depth `= 0`

Metric sources:
- `GET /api/saas/control-plane/slo`
- `GET /api/saas/control-plane/unmatched-report`
- Reconciliation prerequisite counters and queue metrics documented in [Control-Plane Event Monitoring](../control-plane-event-monitoring.md).

## Rollback Triggers

Rollback immediately if any trigger occurs:

1. Any confirmed false-resolved canonical finding in pilot controls.
2. In-scope `NEW` match rate drops below `95%` for `2` consecutive 6-hour windows.
3. Shadow freshness lag reaches `>= 6 hours` for `2` consecutive windows.
4. Inventory DLQ depth is non-zero for more than one scheduler interval.
5. Missing canonical/resource keys are non-zero after two consecutive global reconciliation sweeps.

Immediate rollback actions:

1. Set `CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED=false` and deploy API + worker.
2. If signal quality remains unstable, also set `CONTROL_PLANE_SHADOW_MODE=true` to force shadow-only behavior.
3. Re-run reconciliation and verify KPI recovery before any re-enable attempt.

## Fallback Behavior For Uncertain Reads

Uncertain reads are fail-closed for canonical status:

1. Collectors may emit `SOFT_RESOLVED` or lower `state_confidence` when access is denied or signal quality is uncertain.
2. With `CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED=false` and `CONTROL_PLANE_PROMOTION_MIN_CONFIDENCE=95`, these evaluations do not promote/reopen canonical findings.
3. Shadow overlay fields still update for audit/debug visibility (`shadow_status_*`, `shadow_fingerprint`, event time).
4. Promotion blocks are logged with stable reason codes:
   - `confidence_below_threshold`
   - `soft_resolved_not_allowed`
   - `control_not_high_confidence`
   - `tenant_not_in_pilot`
   - `promotion_disabled`
   - `shadow_mode_enabled`

## Prompt 1 Config Knobs (Exact)

Prompt 1 (Item `16` core behavior implementation) introduced these environment knobs in [`backend/config.py`](../../backend/config.py):

| Env var | Type | Default | Pilot recommendation | Purpose |
| --- | --- | --- | --- | --- |
| `CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED` | `bool` | `false` | `true` | Master switch for canonical status promotion/reopen from shadow evaluations. |
| `CONTROL_PLANE_HIGH_CONFIDENCE_CONTROLS` | `str` (CSV control IDs) | `""` | `S3.1,SecurityHub.1,GuardDuty.1` | Allowlist of controls eligible for live promotion/reopen. |
| `CONTROL_PLANE_PROMOTION_MIN_CONFIDENCE` | `int` | `95` | `95` | Minimum `state_confidence` required to promote/reopen canonical status. |
| `CONTROL_PLANE_PROMOTION_PILOT_TENANTS` | `str` (CSV tenant UUIDs) | `""` | `<YOUR_TENANT_UUID_HERE>` (or comma-separated list) | Optional tenant pilot allowlist. Empty means all tenants. |
| `CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED` | `bool` | `false` | `false` | Controls whether `SOFT_RESOLVED` can promote canonical status. |

Companion setting required for live promotion path:

| Env var | Type | Default | Required rollout value | Purpose |
| --- | --- | --- | --- | --- |
| `CONTROL_PLANE_SHADOW_MODE` | `bool` | `true` | `false` for pilot/live | Canonical promotion is blocked when shadow mode is enabled. |

Legacy note:
- `CONTROL_PLANE_AUTHORITATIVE_CONTROLS` is kept for backward-compatible references, but Item `16` promotion logic gates on the high-confidence knob set above.

## Go/No-Go Checklist (Production Enablement)

Go only when every item is checked:

- [ ] Pilot tenant allowlist is explicitly configured in `CONTROL_PLANE_PROMOTION_PILOT_TENANTS` (or written approval exists for global scope).
- [ ] `CONTROL_PLANE_HIGH_CONFIDENCE_CONTROLS` contains only approved high-confidence controls.
- [ ] `CONTROL_PLANE_PROMOTION_MIN_CONFIDENCE=95` and `CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED=false` are confirmed in deployed API/worker runtime.
- [ ] Pilot window (`>= 7` days) completed with `0` confirmed false-resolved findings.
- [ ] SLO/KPI targets met: in-scope `NEW` match rate `>=95%`, shadow freshness lag `<6h`, missing key counts `0`.
- [ ] Inventory queue/DLQ stayed within prerequisite thresholds for the pilot period.
- [ ] On-call rollback path is tested: operator can disable promotion in one deploy cycle.

No-Go if any checklist item is unmet.
