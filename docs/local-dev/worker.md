# Worker Development

## Run Worker

```bash
PYTHONPATH=. ./venv/bin/python -m backend.workers.main
```

Worker loads settings from:
- `/Users/marcomaher/AWS Security Autopilot/backend/workers/.env`
- shared vars from `/Users/marcomaher/AWS Security Autopilot/backend/.env`

## Pool Selector

`WORKER_POOL` supports:
- `legacy`
- `events`
- `inventory`
- `export`
- `all`

## Main Job Types

- `ingest`
- `ingest_access_analyzer`
- `ingest_inspector`
- `ingest_control_plane_events`
- `compute_actions`
- `remediation_run`
- `generate_export`
- `generate_baseline_report`
- `weekly_digest`
- reconciliation and backfill jobs

## Queue Contract Safety

Malformed or unsupported jobs are quarantined to `SQS_CONTRACT_QUARANTINE_QUEUE_URL` with reason metadata.

## Related

- [Queue quarantine runbook](/Users/marcomaher/AWS%20Security%20Autopilot/docs/queue-contract-quarantine-runbook.md)
- [Testing](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/tests.md)
