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

Phase-2 defaults are configurable via:
- `CONTROL_PLANE_INVENTORY_SERVICES`
- `CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD`

## Rollout
1. Keep `CONTROL_PLANE_SHADOW_MODE=true` and ingest to shadow tables only.
2. Compare shadow metrics/state against legacy findings for pilot controls.
3. Flip selected controls to authoritative mode only after precision/freshness targets are met.
