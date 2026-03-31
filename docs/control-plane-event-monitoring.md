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

Token-rotation operational rule:
- Any time `POST /api/auth/control-plane-token/rotate` is used for a tenant, every deployed `SecurityAutopilotControlPlaneForwarder` stack for that tenant must be updated immediately with the new `ControlPlaneToken` parameter.
- The production backend now keeps accepting the immediately previous tenant token for a bounded grace window (`CONTROL_PLANE_PREVIOUS_TOKEN_GRACE_HOURS`, default `72`) after rotation, so a just-rotated stack does not fail closed instantly if the operator updates the stack shortly after the rotate.
- That grace applies only to the single immediately previous token. Older forwarder tokens still fail authorization and still require a real stack update.
- If the stack is not refreshed after rotation, EventBridge delivery can fail authorization while the SaaS readiness endpoint itself remains healthy, and `control_plane_event_ingest_status.last_intake_time` will eventually go stale even though no code path changed.
- The March 30, 2026 `POI-010` production investigation on account `696505809372` narrowed the stale-readiness symptom to this exact failure mode: manual tenant-scoped synthetic intake and direct public `/api/control-plane/events` intake both restored freshness immediately, so the remaining fault domain was the deployed forwarder path rather than the readiness calculation.
- The March 30, 2026 live mitigation deploy then proved the grace-window behavior on production by rotating the tenant token again and immediately reusing the previous token on `POST /api/control-plane/events`, which still returned `{"enqueued":1,"dropped":0,"drop_reasons":{}}`.
- The March 30, 2026 live closure for `POI-010` completed after the existing `SecurityAutopilotControlPlaneForwarder` stack in account `696505809372` / `eu-north-1` was updated with the current token; real `AuthorizeSecurityGroupIngress` and `RevokeSecurityGroupIngress` events then refreshed readiness through the normal EventBridge path at `2026-03-30T22:04:53.224831Z` and `2026-03-30T22:05:44.882249Z` intake time respectively.

Automated verification script (console-free):
- `scripts/verify_control_plane_forwarder.sh`
- Verifies:
  - Phase 1 wiring (`Rule ENABLED`, `API Destination ACTIVE`, endpoint path, `Connection AuthorizationType=API_KEY`, DLQ depth)
  - Phase 2 synthetic management event injection (`security.autopilot.synthetic` source with allowlisted `eventName`)
  - Phase 3 tenant readiness poll (`overall_ready` + region `is_recent`)
  - Phase 4 CloudWatch/DLQ diagnosis on timeout
- Example:

```bash
./scripts/verify_control_plane_forwarder.sh \
  --stack-name SecurityAutopilotControlPlaneForwarder \
  --account-id 029037611564 \
  --region eu-north-1 \
  --saas-api-url https://api.ocypheris.com \
  --saas-token <YOUR_SAAS_BEARER_TOKEN_HERE>
```

## Canonical Event Allowlist (Parity Contract)
- Source of truth: `backend/services/control_plane_event_allowlist.py`
- Forwarder contract: `infrastructure/cloudformation/control-plane-forwarder-template.yaml`
- Parity enforcement:
  - `tests/test_control_plane_allowlist_parity.py`
  - `tests/test_cloudformation_phase2_reliability.py`

Allowlisted `detail.eventName` values:
- `AuthorizeSecurityGroupIngress`
- `RevokeSecurityGroupIngress`
- `ModifySecurityGroupRules`
- `UpdateSecurityGroupRuleDescriptionsIngress`
- `PutBucketPolicy`
- `DeleteBucketPolicy`
- `PutBucketAcl`
- `PutBucketPublicAccessBlock`
- `DeleteBucketPublicAccessBlock`
- `PutPublicAccessBlock`
- `DeletePublicAccessBlock`
- `PutAccountPublicAccessBlock`
- `DeleteAccountPublicAccessBlock`
- `PutBucketEncryption`
- `DeleteBucketEncryption`
- `EnableSecurityHub`
- `CreateDetector`
- `UpdateDetector`
- `CreateTrail`
- `UpdateTrail`
- `StartLogging`
- `StopLogging`
- `PutConfigurationRecorder`
- `PutDeliveryChannel`
- `StartConfigurationRecorder`

Debug evidence from the 2026-02-20 readiness incident:
- `control_plane_event_ingest_status.last_intake_time` for `eu-north-1` stayed at `2026-02-20T00:50:29.897235Z`.
- CloudTrail showed `PutAccountPublicAccessBlock`, which was previously absent from the allowlist.
- Readiness then failed with `missing_regions=["eu-north-1"]` during no-UI campaigns.

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
- `GET /api/saas/control-plane/promotion-guardrail-health` (tenant or global rollout guardrail health)
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
   - Set `CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED=true`
   - Set `CONTROL_PLANE_HIGH_CONFIDENCE_CONTROLS=EC2.53,S3.1,...` (comma-separated canonical control IDs)
   - Set `CONTROL_PLANE_PROMOTION_MIN_CONFIDENCE=95` (or your approved confidence floor)
   - Keep `CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED=false` unless explicitly approved
   - Optionally set `CONTROL_PLANE_PROMOTION_PILOT_TENANTS=<tenant_uuid_1>,<tenant_uuid_2>` for tenant-scoped rollout
   - When enabled, shadow state will auto-resolve and reopen canonical `security_hub` findings only for evaluations that pass all promotion guardrails.
4. Keep medium/low controls fail-closed until Item 17 quality gates are explicitly satisfied:
   - Keep `CONTROL_PLANE_MEDIUM_LOW_CONFIDENCE_CONTROLS=""` by default
   - Set `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_COVERAGE` and `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_PRECISION`
   - Publish measured values into `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_COVERAGE` and `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_PRECISION`
   - Keep `CONTROL_PLANE_MEDIUM_LOW_PROMOTION_ROLLBACK_TRIGGERED=false`; set to `true` to immediately block all medium/low promotion on rollback

PM/ops rollout policy, rollback triggers, and go/no-go checklist are documented in:
- [Item 16 High-Confidence Live Status Rollout Policy](./prod-readiness/16-high-confidence-live-status-rollout.md)
- [Item 17 Medium/Low-Confidence Control Coverage Plan](./prod-readiness/17-medium-low-confidence-control-coverage-plan.md)

## Deployment Safety (No Schema Drift)
- API and worker now run a hard startup guard: DB revision must match the repo Alembic heads or the process exits.
- CI gate runs:
  - `alembic heads`
  - `alembic current`
  - and fails if current does not match the repo heads.
- Deployment order is mandatory:
  1. `alembic upgrade heads`
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
- ReadRole template rollout target: `v1.5.9`.
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
  - `GET /api/saas/control-plane/promotion-guardrail-health`
  - `GET /api/saas/control-plane/unmatched-report`

`GET /api/saas/control-plane/promotion-guardrail-health` response includes rollout decision metrics:
- promotion attempts/successes/blocked counts (blocked split by stable reason codes)
- shadow-vs-canonical mismatch rate for configured high-confidence controls
- soft-resolved frequency for configured high-confidence controls
- stale shadow freshness indicators (threshold, stale count/rate, oldest/latest evaluation times)

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
