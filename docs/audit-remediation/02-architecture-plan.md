# Architecture Reliability Remediation Plan

## Scope

This workstream covers backlog IDs `ARC-001` through `ARC-009`.

## Workstream Outcomes

This plan must deliver:
- Deterministic and replayable queue processing under producer/consumer drift.
- Predictable worker throughput under mixed queue utilization.
- Explicit delivery guarantees and alarms for event and queue infrastructure.
- Auditable HA/DR and readiness controls suitable for SOC 2 / ISO evidence.

## Sequencing

1. `ARC-001` and `ARC-007` first (contract integrity and replay safety).
2. `ARC-002`, `ARC-003`, and `ARC-006` next (throughput and fan-out scale).
3. `ARC-004` and `ARC-005` in parallel (delivery guarantees and observability).
4. `ARC-008` and `ARC-009` to close compliance and readiness gaps.

## Delivery Plan by Phase

| Phase | In-Scope IDs | Expected Outputs |
| --- | --- | --- |
| Phase 1 | `ARC-001` | Quarantine/replay architecture in production with no silent message drops |
| Phase 2 | `ARC-002`, `ARC-003`, `ARC-004`, `ARC-005`, `ARC-006`, `ARC-007` | Concurrency-safe worker polling, orchestration-based reconciliation, complete queue/event reliability controls, versioned contracts |
| Phase 3 | `ARC-008`, `ARC-009` | DR architecture and recovery evidence; readiness/SLO dependency checks live |

## Deliverable and Evidence Matrix

| ID | Primary Deliverable | Expected Output | Evidence Required |
| --- | --- | --- | --- |
| ARC-001 | Contract-violation quarantine + replay tooling | Invalid/unknown jobs are retained and recoverable | Unit/integration tests, replay runbook, queue alarm proof |
| ARC-002 | Concurrent queue polling model | Reduced queue starvation and lower tail latency | Load test report with before/after metrics |
| ARC-003 | Worker-orchestrated reconciliation fan-out | Request path remains short and resilient to partial failure | Endpoint latency check, checkpoint/resume integration test |
| ARC-004 | EventBridge DLQ/retry policy wiring | Explicit target delivery behavior and replay path | CloudFormation diff, failure injection test |
| ARC-005 | Complete queue alarm inventory | Early detection of queue lag/degradation | Alarm list export, synthetic alarm trigger evidence |
| ARC-006 | Dedicated export/report queue and worker pool | Ingest traffic isolated from heavy report workloads | Routing tests, mixed-load latency comparison |
| ARC-007 | Versioned queue payload contract | Backward-compatible deploy behavior and safe unknown-version handling | Contract tests in CI, quarantine validation |
| ARC-008 | HA/DR control set and restore runbooks | Documented/tested restore posture with RTO/RPO targets | DR exercise report, backup/restore evidence artifacts |
| ARC-009 | Dependency-aware readiness endpoint and SLOs | Health reflects true dependency state | Readiness failure test, dashboard snapshot |

## Phase 2 Closure Tracking

Use `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/phase2-architecture-closure-checklist.md`
as the required closure checklist and evidence index for `ARC-002` through `ARC-007`.

## Phase 2 Finalization (2026-02-12)

`ARC-002` through `ARC-007` are implemented and closed with attached operational evidence:

- Closure evidence index:
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.json`
- Latest architecture snapshot (all queues + alarms healthy):
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.json`

Closure highlights:
- DLQ alarm backlog from prior snapshot is remediated (`events` and `inventory` DLQs back to `0`, alarms `OK`).
- EventBridge target failure-injection drill (`ARC-004`) validated target DLQ + retry behavior with captured error metadata.
- Synthetic alarm trigger and recovery drill (`ARC-005`) completed for queue-backlog and DLQ-ingress alarms across ingest/events/inventory/export.
- Customer-account forwarder readiness gate evidence is attached (stack state, rule target config, readiness gate tests).
- CI gate evidence (`ARC-007`) is attached with all required tests passing.

## Phase 3 Closure Tracking

Use `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/phase3-architecture-closure-checklist.md`
as the required closure checklist and evidence index for `ARC-008` and `ARC-009`.

Phase 3 implementation artifacts added in-repo:
- DR backup/restore IaC:
  - `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/dr-backup-controls.yaml`
- Dependency-aware readiness endpoints:
  - `/Users/marcomaher/AWS Security Autopilot/backend/main.py` (`/ready`, `/health/ready`)
  - `/Users/marcomaher/AWS Security Autopilot/backend/services/health_checks.py`
- DR runbook + deployment/evidence scripts:
  - `/Users/marcomaher/AWS Security Autopilot/docs/disaster-recovery-runbook.md`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_phase3_architecture.sh`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/check_api_readiness.py`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/collect_phase3_architecture_evidence.py`

## Detailed Plan

### ARC-001: Poison-message handling bypasses DLQ

**Implementation actions**
1. Add explicit quarantine path for contract violations in `worker/main.py`.
2. Stop deleting malformed/unknown payloads in `_process_message`; route to quarantine or leave for redrive.
3. Include metadata envelope: `reason_code`, `original_message_id`, `payload_sha256`, `seen_at`.
4. Add replay utility script for quarantined payloads with dry-run mode.
5. Add CloudWatch alarms for quarantine queue depth and age.

**Code touchpoints**
- `worker/main.py`
- `backend/config.py` and `worker/config` equivalent (queue URL settings)
- `infrastructure/cloudformation/sqs-queues.yaml`
- new script under `scripts/` for replay

**Validation**
- Unit tests for invalid JSON, missing fields, and unknown `job_type`.
- Integration test proving malformed payload is retained for replay.
- Runbook for quarantine triage and replay (`docs/queue-contract-quarantine-runbook.md`).

**Acceptance criteria**
- No contract-violating message is silently dropped.
- Operators can inspect and replay quarantined messages.

### ARC-002: Serialized `WORKER_POOL=all` queue polling

**Implementation actions**
1. Replace sequential polling loop with concurrent pollers per queue pool.
2. Keep independent long-poll loops to prevent one queue stalling others.
3. Add per-queue worker metrics: receive rate, empty poll rate, processing latency.
4. Add guardrails for max in-flight messages per pool.

**Code touchpoints**
- `worker/main.py` (`run_worker`, `_receive_messages`)

**Validation**
- Load test at 10x message rate with mixed queue utilization.
- Confirm no queue experiences > configured max poll starvation window.

**Acceptance criteria**
- Empty queues no longer block active queues.
- P95 enqueue-to-start latency drops under mixed traffic.

### ARC-003: Reconciliation fan-out in synchronous API request path

**Implementation actions**
1. Convert `/api/internal/reconcile-inventory-global-all-tenants` into orchestration enqueue only.
2. Introduce orchestration job type with checkpoint model (tenant/account/region cursor).
3. Move fan-out batching into worker with idempotent checkpoint writes.
4. Add partial-failure retry logic and resumable execution.

**Code touchpoints**
- `backend/routers/internal.py`
- worker job handlers for reconciliation
- DB migration for orchestration checkpoint state

**Validation**
- API endpoint returns quickly and only schedules orchestration.
- Worker resumes correctly after forced failure mid-fan-out.

**Acceptance criteria**
- No long-running reconciliation loop remains in request thread.
- Reconciliation completion is resilient to partial failure.

### ARC-004: EventBridge API Destination targets lack explicit DLQ/retry

**Implementation actions**
1. Add `DeadLetterConfig` for API destination targets.
2. Add explicit `RetryPolicy` with bounded retry age/attempts.
3. Add alarms for EventBridge failed invocations and target DLQ depth.
4. Document replay procedure for DLQ events.
5. Require control-plane forwarder onboarding verification per customer account/region before onboarding completion.

**Code touchpoints**
- `infrastructure/cloudformation/control-plane-forwarder-template.yaml`
- `infrastructure/cloudformation/reconcile-scheduler-template.yaml`
- `frontend/src/app/onboarding/page.tsx`

**Validation**
- Template deploy diff confirms DLQ/retry config on both targets.
- Failure injection test routes undeliverable events to DLQ.
- Onboarding cannot complete until control-plane readiness is healthy for monitored regions.

**Acceptance criteria**
- Delivery failure behavior is explicit, monitored, and replayable.

### ARC-005: Incomplete queue alarm coverage

**Implementation actions**
1. Add alarms for ingest/events queues and all DLQs.
2. Track depth, oldest-message age, and DLQ ingress rate.
3. Add runbook links and severity-specific paging thresholds.

**Code touchpoints**
- `infrastructure/cloudformation/sqs-queues.yaml`
- runbook docs in `docs/`

**Validation**
- Alarm resources exist for inventory, ingest, and events + DLQs.
- Synthetic queue backlog test triggers expected alert path.

**Acceptance criteria**
- No critical queue lacks depth/age/DLQ monitoring.

### ARC-006: Export/report workloads share ingest queue

**Implementation actions**
1. Create dedicated queue + DLQ for export/report jobs.
2. Route export/report producers to new queue URLs.
3. Add dedicated worker pool and autoscaling policies.
4. Add queue-level concurrency limits tuned for heavy jobs.

**Code touchpoints**
- `backend/routers/exports.py`
- `backend/routers/baseline_report.py`
- queue config and worker queue resolution
- CloudFormation queue resources

**Validation**
- Export/report jobs no longer enter ingest queue.
- Ingest latency remains stable under concurrent export load.

**Acceptance criteria**
- Ingest/remediation traffic is isolated from heavy export workloads.

### ARC-007: Missing queue payload versioning strategy

**Implementation actions**
1. Add `schema_version` to all queue payload builders.
2. Implement worker compatibility matrix by `job_type` + `schema_version`.
3. Route unknown versions/types to quarantine path.
4. Add producer/consumer contract tests in CI.

**Code touchpoints**
- `backend/utils/sqs.py`
- `worker/main.py`
- CI workflow definitions

**Validation**
- Contract tests fail when producer and consumer payloads drift.
- Unknown versions are quarantined, not dropped.

**Acceptance criteria**
- Deploy skew no longer causes silent message loss.

### ARC-008: HA/DR posture unknown

**Implementation actions**
1. Define target RTO/RPO per critical service.
2. Add IaC for backup retention, snapshots, and restore permissions.
3. Document restore procedure with command-level steps.
4. Schedule and record periodic recovery tests.

**Code touchpoints**
- `infrastructure/cloudformation/` (RDS/backup resources)
- `docs/` DR architecture and runbook docs

**Validation**
- Successful restore exercise documented with timestamps and outcome.
- Evidence artifact stored for SOC 2 / ISO audits.

**Acceptance criteria**
- DR controls are explicit, automated where possible, and tested.

### ARC-009: Health/SLO checks are not dependency-aware

**Implementation actions**
1. Keep lightweight liveness endpoint.
2. Add readiness endpoint verifying DB and SQS dependencies.
3. Expose queue lag and failure-rate SLO metrics.
4. Gate deployment health checks on readiness, not liveness.

**Code touchpoints**
- `backend/main.py`
- health service helper module
- observability dashboard definitions

**Validation**
- Readiness returns non-200 on DB/SQS dependency failure.
- Dashboards include queue lag and worker failure SLOs.

**Acceptance criteria**
- Green status can no longer mask dependency outage.

## Milestones

- Milestone A (end Phase 1): `ARC-001` complete.
- Milestone B (end Phase 2): `ARC-002` to `ARC-007` complete.
- Milestone C (end Phase 3): `ARC-008` and `ARC-009` complete with audit evidence.

## Workstream Sign-Off Criteria

1. No queue contract violation path results in silent deletion.
2. Worker throughput and queue fairness improvements are demonstrated in load evidence.
3. Event and queue delivery failure paths are explicitly governed by DLQ/retry/alarm controls.
4. DR and readiness controls are documented, tested, and linked to operational ownership.
