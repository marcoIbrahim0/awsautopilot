# Control-Plane Event Monitoring (Phase 1)

## Scope
- Event source: EventBridge **"AWS API Call via CloudTrail"** events filtered to target actions.
- Event class: management events only (no S3 data events in phase 1).
- Mode: shadow by default (`event_monitor_shadow`) so customer-visible findings are unchanged during comparison.

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

## Rollout
1. Keep `CONTROL_PLANE_SHADOW_MODE=true` and ingest to shadow tables only.
2. Compare shadow metrics/state against legacy findings for pilot controls.
3. Flip selected controls to authoritative mode only after precision/freshness targets are met.
