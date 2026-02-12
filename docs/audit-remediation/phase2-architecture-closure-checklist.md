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

1. Deploy SQS stack updates
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/sqs-queues.yaml`

2. Deploy EventBridge stack updates
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/control-plane-forwarder-template.yaml`
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/reconcile-scheduler-template.yaml`

3. Sync runtime queue env vars
- `/Users/marcomaher/AWS Security Autopilot/scripts/set_env_sqs_from_stack.py`

## Required Operational Proof

- `ARC-002`: before/after latency and starvation window comparison under mixed queue load.
- `ARC-003`: forced mid-fan-out failure followed by resume from persisted checkpoint.
- `ARC-004`: failure injection proving EventBridge target message ends in target DLQ after retries.
- `ARC-005`: synthetic queue backlog + DLQ ingress alarm trigger proof for ingest/events/inventory/export queues.
- `ARC-006`: mixed-load comparison showing ingest latency unaffected by export/report workload spikes.
- `ARC-007`: CI pass of contract compatibility tests and quarantine path checks.

## Runbooks

- Contract quarantine replay:
  - `/Users/marcomaher/AWS Security Autopilot/docs/queue-contract-quarantine-runbook.md`
- EventBridge target DLQ replay:
  - `/Users/marcomaher/AWS Security Autopilot/docs/eventbridge-target-dlq-replay-runbook.md`

## Sign-off

Mark each item complete only when all are attached:
- test run URL or artifact
- deploy change set / stack update output
- alarm screenshot or CloudWatch export
- on-call owner acknowledgement
