# Control-Plane Event Monitoring (Phase 1)

## Scope
- Event source: EventBridge **"AWS API Call via CloudTrail"** events filtered to target actions.
- Event class: management events only (no S3 data events in phase 1).
- Mode: shadow by default (`event_monitor_shadow`) so customer-visible findings are unchanged during comparison.

## Tenant Setup (Recommended Wiring)
Phase 1 is designed to be enabled per tenant via a customer-deployed EventBridge forwarder:

- CloudFormation template: `infrastructure/cloudformation/control-plane-forwarder-template.yaml`
- Delivery mechanism: **EventBridge API Destination** -> SaaS HTTPS endpoint
- Auth: per-tenant header `X-Control-Plane-Token` (stored on the tenant; rotate if leaked)
- SaaS intake endpoint: `POST /api/control-plane/events`

Validation endpoint (tenant-facing):
- `GET /api/aws/accounts/{account_id}/control-plane-readiness`
  - Returns last seen event time / intake time per configured region.

## Event + Targeted Enrichment
Phase 1 is intentionally not event-only:
1. Event arrives (for example `AuthorizeSecurityGroupIngress`).
2. Service reads current resource state synchronously (for example `DescribeSecurityGroups`).
3. Control posture is evaluated on effective state.
4. Shadow finding state is upserted by fingerprint.

Resolution semantics:
- Resolution is confirmed by enrichment fetch (or later inventory reconciliation), not by trusting the change event alone.

## Deterministic State Machine
- Correlation key: `fingerprint = (account_id, region, resource_id, control_id)`.
- Guard: apply transitions only when `incoming_event_time >= last_observed_event_time`.
- State fields include `status`, `status_reason`, `evidence_ref`, `last_observed_event_time`, `state_confidence`.

## Queue Topology and Worker Pools
- `events-fast-lane`: near-real-time control-plane event jobs.
- `inventory-reconcile`: reconciliation and targeted inventory jobs.
- `legacy-ingest`: existing ingest/actions/remediation jobs.

Worker pool selection is controlled by `WORKER_POOL` (`legacy`, `events`, `inventory`, `all`).

## Cross-Account / Multi-Region Event Bus Strategy
- Per customer account/region, define an EventBridge rule matching allowlisted management API actions.
- Forward matching events to centralized intake (bus/queue/API) with resource-policy or organization delegation.
- Central ingest path should preserve original `account`, `region`, `eventTime`, and `eventId`.
- Failure mode: if central intake is unavailable, events should retry/buffer locally and route to DLQ for replay.
- Region isolation: keep per-region forwarding and queue/DLQ so one region outage does not block all control-plane signals.

## SLO Telemetry
Per-event telemetry is persisted in `control_plane_events`:
- CloudTrail delivery lag
- queue lag
- handler latency
- end-to-end freshness
- resolution freshness (when applicable)
- duplicate/drop accounting

Admin endpoint:
- `GET /api/saas/control-plane/slo`
- `GET /api/saas/control-plane/shadow-summary` (shadow-state comparison helper)

## Phase 2 Reconciliation Orchestration
Inventory reconciliation is split into shard jobs plus orchestration endpoints:

- `POST /api/internal/reconcile-inventory-shard`
  - Enqueue one or more explicit `(tenant, account, region, service)` shard jobs.
  - Supports `sweep_mode` (`targeted` or `global`) and `max_resources`.
- `POST /api/internal/reconcile-recently-touched`
  - Enqueue targeted reconciliation based on recent control-plane events.
  - Supports `lookback_minutes`, service filter, and per-shard resource cap.
- `POST /api/internal/reconcile-inventory-global`
  - Enqueue global reconciliation across all active accounts/regions for a tenant.
  - Builds `(account, region, service)` shards and marks each as `sweep_mode=global`.
- `POST /api/internal/reconcile-inventory-global-all-tenants`
  - Enqueue the same global reconciliation sweeps for every active tenant (cron-friendly).
  - Recommended schedule: every 6 hours (or daily for small footprints).
  - Requires header `X-Control-Plane-Secret`.

Phase-2 defaults are configurable via:
- `CONTROL_PLANE_INVENTORY_SERVICES`
- `CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD`

## Rollout
1. Keep `CONTROL_PLANE_SHADOW_MODE=true` and ingest to shadow tables only.
2. Compare shadow metrics/state against legacy findings for pilot controls.
3. Flip selected controls to authoritative mode only after precision/freshness targets are met.
   - Set `CONTROL_PLANE_SHADOW_MODE=false`
   - Set `CONTROL_PLANE_AUTHORITATIVE_CONTROLS=EC2.53,S3.1,...` (comma-separated canonical control IDs)
   - When enabled, shadow state will auto-resolve and reopen canonical `security_hub` findings for promoted controls.

## Deployment Safety (No Schema Drift)
- API and worker now run a hard startup guard: DB revision must equal Alembic head or process exits.
- CI gate runs:
  - `alembic heads`
  - `alembic current`
  - and fails if current != head.
- Deployment order is mandatory:
  1. `alembic upgrade head`
  2. restart API
  3. restart workers

## Automatic Canonical Key Backfill
- New internal endpoint:
  - `POST /api/internal/backfill-finding-keys`
  - Supports optional filters: `tenant_id`, `account_id`, `region`
  - Supports chunking controls: `chunk_size`, `max_chunks`, `auto_continue`, `include_stale`
- New worker job type:
  - `backfill_finding_keys`
  - idempotent; updates only null or stale `canonical_control_id` / `resource_key` values.
- Schedule recommendation:
  - Run every 6 hours until missing-key metrics stay at zero for multiple periods.
  - Keep a daily run after stabilization as regression guard.

## Queue Reliability and Operational Policy
- Keep `POST /api/internal/reconcile-inventory-global-all-tenants` on a 6-hour schedule.
- Inventory queue now has explicit CloudWatch alarm recommendations/resources for:
  - main queue depth
  - oldest message age
  - DLQ non-empty
- Worker logs now emit retry visibility with `receive_count`, `tenant`, `account`, and `region`.
- Policy for repeated AssumeRole failures:
  - after repeated retries (default receive count >= 3), auto-disable account (configurable) until fixed.

## IAM/Trust Hardening
- ReadRole template rollout target: `v1.5.1`.
- Account validation output now includes:
  - `required_permissions`
  - `authoritative_mode_allowed`
  - `authoritative_mode_block_reasons`
- Global sweeps now enforce:
  - tenant/account external-id consistency checks
  - optional AssumeRole precheck
  - authoritative-mode block when required permissions are missing.

## Expected Unmatched Classes Policy
- Expected unmatched class:
  - historical resolved findings where no current shadow row is expected.
- Current policy:
  - keep historical rows (`expected_historical_resolved`) for audit history
  - exclude these from "new in-scope match-rate" KPI calculations
  - report separately in unmatched breakdown.

## Observability and SLO Targets
- Dashboard/alert primitives:
  - missing canonical/resource key counts
  - in-scope match coverage
  - in-scope NEW match rate
  - shadow freshness lag
  - reconcile sweep failures
- Suggested targets:
  - `missing_canonical` = 0
  - `missing_resource_key` = 0
  - in-scope `NEW` match rate >= 95%
  - shadow freshness lag < 6h
- SaaS admin endpoints:
  - `GET /api/saas/control-plane/slo`
  - `GET /api/saas/control-plane/unmatched-report`

## Standard Verification SQL
```sql
SELECT COUNT(*) AS in_scope,
COUNT(*) FILTER (WHERE canonical_control_id IS NULL) AS missing_canonical,
COUNT(*) FILTER (WHERE resource_key IS NULL) AS missing_resource_key
FROM findings
WHERE tenant_id = '<tenant_uuid>' AND source='security_hub' AND in_scope IS TRUE;
```

```sql
SELECT COUNT(*) AS in_scope_total,
COUNT(*) FILTER (WHERE shadow_fingerprint IS NOT NULL AND shadow_fingerprint <> '') AS matched,
COUNT(*) FILTER (WHERE shadow_fingerprint IS NULL OR shadow_fingerprint = '') AS unmatched
FROM findings
WHERE tenant_id = '<tenant_uuid>' AND source='security_hub' AND in_scope IS TRUE;
```

```sql
SELECT MAX(updated_at) AS last_shadow_update, COUNT(*) AS shadow_rows
FROM finding_shadow_states
WHERE tenant_id = '<tenant_uuid>';
```

```sql
WITH u AS (
  SELECT tenant_id, account_id, region, canonical_control_id, resource_key
  FROM findings
  WHERE tenant_id = '<tenant_uuid>' AND source='security_hub' AND in_scope IS TRUE
    AND (shadow_fingerprint IS NULL OR shadow_fingerprint = '')
)
SELECT CASE WHEN s.id IS NULL THEN 'no_shadow_row' ELSE 'shadow_exists_but_not_attached' END AS reason,
COUNT(*) AS cnt
FROM u
LEFT JOIN finding_shadow_states s
  ON s.tenant_id=u.tenant_id AND s.account_id=u.account_id AND s.region=u.region
 AND s.canonical_control_id=u.canonical_control_id AND s.resource_key=u.resource_key
GROUP BY 1;
```
