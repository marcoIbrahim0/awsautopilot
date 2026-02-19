# Phase 2 Architecture Closure Checklist

This checklist tracks closure for `ARC-002` through `ARC-007` in `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/02-architecture-plan.md`.

## Scope

- `ARC-002`: concurrent queue polling
- `ARC-003`: orchestration-based global reconciliation
- `ARC-004`: EventBridge target DLQ/retry controls
- `ARC-005`: full SQS alarm coverage
- `ARC-006`: export/report queue isolation
- `ARC-007`: schema-versioned queue contract + CI gate

## Automated Test Evidence

Run from repo root:

```bash
pytest -q \
  tests/test_sqs_utils.py \
  tests/test_worker_main_contract_quarantine.py \
  tests/test_worker_polling.py \
  tests/test_reconcile_inventory_global_orchestration_worker.py \
  tests/test_cloudformation_phase2_reliability.py \
  --noconftest
```

```bash
pytest -q \
  tests/test_internal_inventory_reconcile.py \
  -k global_all_tenants_enqueues_orchestration_jobs \
  --noconftest
```

CI workflow gate:
- `/Users/marcomaher/AWS Security Autopilot/.github/workflows/architecture-phase2.yml`

## Deployment Evidence

1. Deploy SaaS platform stack updates
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/sqs-queues.yaml`
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/reconcile-scheduler-template.yaml`

2. Deploy customer EventBridge forwarder stack updates (required per connected customer account + monitored region)
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/control-plane-forwarder-template.yaml`

3. Sync SaaS runtime queue env vars
- `/Users/marcomaher/AWS Security Autopilot/scripts/set_env_sqs_from_stack.py`

Deployment helper:
- `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_phase2_architecture.sh`

## Deployment Ownership (Required)

- SaaS admin must deploy/maintain shared SaaS-account infrastructure (`sqs-queues`, `reconcile-scheduler`) in the SaaS AWS account.
- Tenant admin must deploy/maintain `control-plane-forwarder-template.yaml` in each customer AWS account and monitored region during onboarding.
- Onboarding is complete only when control-plane readiness is healthy for required monitored regions.

Rollout evidence attachment (required onboarding gate):
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.md` (section: customer-account forwarder rollout readiness)
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-forwarder-readiness-gate-tests-20260212T130053Z.txt`

## Required Operational Proof

- [x] `ARC-002`: before/after latency and starvation window comparison under mixed queue load.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.json`
- [x] `ARC-003`: forced mid-fan-out failure followed by resume from persisted checkpoint.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-arc003-failure-resume-20260212T130046Z.txt`
- [x] `ARC-004`: failure injection proving EventBridge target message ends in target DLQ after retries.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-arc004-failure-injection-20260212T130923Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.md`
- [x] `ARC-005`: synthetic queue backlog + DLQ ingress alarm trigger proof for ingest/events/inventory/export queues.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-arc005-synthetic-alarm-drill-20260212T131050Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.md`
- [x] `ARC-006`: mixed-load comparison showing ingest latency unaffected by export/report workload spikes.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.md`
- [x] `ARC-007`: CI pass of contract compatibility tests and quarantine path checks.
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-ci-gate-20260212T130032Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-orchestration-api-gate-20260212T130038Z.txt`

## Runbooks

- Contract quarantine replay:
  - `/Users/marcomaher/AWS Security Autopilot/docs/queue-contract-quarantine-runbook.md`
- EventBridge target DLQ replay:
  - `/Users/marcomaher/AWS Security Autopilot/docs/eventbridge-target-dlq-replay-runbook.md`

## Sign-off

Sign-off package status:
- [x] test run URL or artifact
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-ci-gate-20260212T130032Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-orchestration-api-gate-20260212T130038Z.txt`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-forwarder-readiness-gate-tests-20260212T130053Z.txt`
- [x] deploy change set / stack update output
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
- [x] alarm screenshot or CloudWatch export
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.md`
- [x] on-call owner acknowledgement
  - `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.md`

Evidence snapshot helper:
- `/Users/marcomaher/AWS Security Autopilot/scripts/collect_phase2_architecture_evidence.py`

## Latest Snapshot

- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.json`

## Deployment Status (Current)

- `security-autopilot-sqs-queues`: `UPDATE_COMPLETE` (Phase 2 queue/alarm changes applied).
- `security-autopilot-reconcile-scheduler`: `CREATE_COMPLETE` (DLQ/retry/alarm controls live).
- `SecurityAutopilotControlPlaneForwarder`: `UPDATE_COMPLETE` (SaaS account stack reference only).
- Tenant forwarder rollout: required per customer account/region and tracked by onboarding control-plane readiness checks.
- DLQ backlog remediation status: `events` and `inventory` DLQs drained to `0`; DLQ depth/age alarms returned to `OK` (see latest snapshot and closure evidence).
