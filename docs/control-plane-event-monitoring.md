# Control-Plane Event Monitoring (Phase 1)

## Scope
- Event source: EventBridge **"AWS API Call via CloudTrail"** events filtered to target actions.
- Event class: management events only (no S3 data events in phase 1).
- Mode: shadow by default (`event_monitor_shadow`) so customer-visible findings are unchanged during comparison.

## Tenant Setup (Required Wiring For Real-Time)
Phase 1 real-time behavior requires a customer-deployed EventBridge forwarder per tenant account/region:

- CloudFormation template: `infrastructure/cloudformation/control-plane-forwarder-template.yaml`
- Delivery mechanism: **EventBridge API Destination** -> SaaS HTTPS endpoint
- Auth: per-tenant header `X-Control-Plane-Token` (validated against tenant token hash; raw token is one-time reveal at creation/rotation)
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
- `export-report`: evidence export and baseline-report jobs.
- `legacy-ingest`: existing ingest/actions/remediation jobs.

Worker pool selection is controlled by `WORKER_POOL` (`legacy`, `events`, `inventory`, `export`, `all`).

## Cross-Account / Multi-Region Event Bus Strategy
- Per customer account/region, define an EventBridge rule matching allowlisted management API actions.
- Forward matching events to centralized intake (bus/queue/API) with resource-policy or organization delegation.
- Central ingest path should preserve original `account`, `region`, `eventTime`, and `eventId`.
- Failure mode: if central intake is unavailable, events should retry/buffer locally and route to DLQ for replay.
  - Replay runbook: `docs/eventbridge-target-dlq-replay-runbook.md`
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
- `GET /api/saas/system-health` (queue lag + worker failure-rate rollup for operations)

Service health endpoints:
- `GET /health` (liveness only)
- `GET /ready` and `GET /health/ready` (DB + SQS dependency-aware readiness)

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
  - Applies shared prerequisite health gates before each `(account, region)` scope enqueue.
  - Response adds `skipped_prereq`, `prereq_reasons`, and optional scoped `prereq_failures`.
- `POST /api/internal/reconcile-inventory-global-all-tenants`
  - Enqueue the same global reconciliation sweeps for every active tenant (cron-friendly).
  - Recommended schedule: every 6 hours (or daily for small footprints).
  - Requires header `X-Control-Plane-Secret`.
  - Applies the same prerequisite gates before each `(tenant, account, region)` scope enqueue.
  - Response adds `skipped_prereq`, `prereq_reasons`, and optional scoped `prereq_failures`.

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

## 6-Hour Scheduler Deployment (CloudFormation)
- Template: `infrastructure/cloudformation/reconcile-scheduler-template.yaml`
- Deploy example:

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation/reconcile-scheduler-template.yaml \
  --stack-name security-autopilot-reconcile-scheduler \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    SaaSBaseUrl=https://api.example.com \
    ControlPlaneSecret=<same_as_CONTROL_PLANE_EVENTS_SECRET_or_internal_secret> \
    ScheduleExpression='rate(6 hours)' \
    ServicesJson='[]' \
    RegionsJson='[]' \
    PrecheckAssumeRole=false \
    QuarantineOnAssumeRoleFailure=false
```

- Template resources created:
  - EventBridge Connection (API key auth header: `X-Control-Plane-Secret`)
  - EventBridge API Destination (`POST ${SaaSBaseUrl}/api/internal/reconcile-inventory-global-all-tenants`)
  - EventBridge Rule (`rate(6 hours)` by default)
- Outputs:
  - `RuleArn`
  - `ApiDestinationArn`
  - `ConnectionArn`

## Shared Prerequisite Gate Semantics
Before enqueueing reconciliation shard jobs, the control plane evaluates:
- control-plane freshness/readiness for `(tenant, account, region)` using recent intake (`last_intake_time`)
- in-scope Security Hub findings with missing `canonical_control_id` must be `0`
- in-scope Security Hub findings with missing `resource_key` must be `0`
- inventory queue depth must be `<= CONTROL_PLANE_PREREQ_MAX_QUEUE_DEPTH`
- inventory DLQ depth must be `<= CONTROL_PLANE_PREREQ_MAX_DLQ_DEPTH`

Config knobs:
- `CONTROL_PLANE_PREREQ_MAX_STALENESS_MINUTES` (default `30`)
- `CONTROL_PLANE_PREREQ_MAX_QUEUE_DEPTH` (default `100`)
- `CONTROL_PLANE_PREREQ_MAX_DLQ_DEPTH` (default `0`)

Stable reason codes:
- `control_plane_stale`
- `missing_canonical_keys`
- `missing_resource_keys`
- `inventory_queue_backlog`
- `inventory_dlq_backlog`
- `prerequisite_check_error`

## Post-Apply Reconcile Behavior
After a successful PR-bundle `apply` execution:
- if `CONTROL_PLANE_POST_APPLY_RECONCILE_ENABLED=true`, worker attempts immediate enqueue
- scope is constrained to the run’s `tenant/account/region`
- targeted shards are derived from affected actions when possible:
  - service families: `s3_`, `ec2_`, `iam_`, `rds_`, `ebs_`, `eks_`, `ssm_`, `guardduty_`, `cloudtrail_`, `config_`
  - resource IDs from `action.resource_id` or fallback `action.target_id`
- mode behavior:
  - `CONTROL_PLANE_POST_APPLY_RECONCILE_MODE=targeted_then_global`: targeted first; if derivation is incomplete, fallback to global service sweeps
  - `CONTROL_PLANE_POST_APPLY_RECONCILE_MODE=global_only`: enqueue global service sweeps directly
- prerequisite gate is enforced before enqueue; prereq failures are logged and do not fail remediation apply

## Operator Verification Steps
1. Verify scheduler deployment:
   - `aws cloudformation describe-stacks --stack-name security-autopilot-reconcile-scheduler`
   - Confirm `RuleArn`, `ApiDestinationArn`, `ConnectionArn` outputs are present.
2. Verify 6-hour rule target:
   - `aws events list-targets-by-rule --rule SecurityAutopilotReconcileGlobalAllTenants-<region>`
   - Confirm API Destination ARN and JSON input values.
3. Trigger one manual run to validate endpoint behavior:
   - `POST /api/internal/reconcile-inventory-global-all-tenants` with `X-Control-Plane-Secret`
   - Confirm response includes `skipped_prereq` and `prereq_reasons`.
4. Verify post-apply enqueue logs:
   - success log: `post_apply_reconcile_enqueue_success ... service=... sweep_mode=... count=...`
   - prereq skip log: `post_apply_reconcile_prereq_skip ... reason_codes=[...]`

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
