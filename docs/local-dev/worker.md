# Worker Development

This guide covers running the SQS worker locally for development and testing.

## Overview

The worker (`backend/workers/main.py`) is a Python application that:
- Polls SQS queues for background jobs
- Routes jobs by `job_type` to appropriate handlers
- Processes jobs (ingestion, action computation, remediation, exports, etc.)
- Handles retries, DLQ routing, and contract violations

## Running the Worker

### Basic Startup

From the project root:

```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Run worker (canonical entrypoint)
PYTHONPATH=. python -m backend.workers.main
```

The worker will:
1. **Load configuration** from `backend/workers/.env` (via `backend/workers/config.py`)
2. **Check database revision** — Fails fast if DB revision != Alembic head
3. **Resolve queue configs** — Based on `WORKER_POOL` environment variable
4. **Start polling** — Long-poll SQS queues (20s wait time)

### Runtime Environment Files

- Worker runtime: `/Users/marcomaher/AWS Security Autopilot/backend/workers/.env`
- Backend runtime (shared variables used by some jobs): `/Users/marcomaher/AWS Security Autopilot/backend/.env`
- Frontend public vars: `/Users/marcomaher/AWS Security Autopilot/frontend/.env`
- Deploy/ops scripts: `/Users/marcomaher/AWS Security Autopilot/config/.env.ops`
- Root `/Users/marcomaher/AWS Security Autopilot/.env` is backup-only and commented out.

### Worker Pool Configuration

Configure which queues to poll via `WORKER_POOL`:

```bash
# Poll all queues (default for local dev)
WORKER_POOL=all

# Poll specific queue pool
WORKER_POOL=legacy      # security-autopilot-ingest-queue
WORKER_POOL=events      # security-autopilot-events-fastlane-queue
WORKER_POOL=inventory   # security-autopilot-inventory-reconcile-queue
WORKER_POOL=export      # security-autopilot-export-report-queue
```

### Queue Configuration

The worker reads queue URLs from environment variables:

- `SQS_INGEST_QUEUE_URL` — Legacy ingestion queue
- `SQS_EVENTS_FAST_LANE_QUEUE_URL` — Events fast-lane queue
- `SQS_INVENTORY_RECONCILE_QUEUE_URL` — Inventory reconciliation queue
- `SQS_EXPORT_REPORT_QUEUE_URL` — Export/report queue
- `SQS_CONTRACT_QUARANTINE_QUEUE_URL` — Contract quarantine queue

See [Environment Setup](environment.md) for configuration details.

---

## Worker Architecture

### Queue Polling

The worker uses **long polling** (20s wait time) to reduce empty polls:

- **Visibility timeout**: 300s (5 minutes)
- **Max messages per poll**: 10
- **Concurrency**: Configurable via `WORKER_MAX_IN_FLIGHT_PER_QUEUE` (default: 10)

### Job Routing

Jobs are routed by `job_type` field:

- `ingest` — Security Hub findings ingestion (`backend/workers/jobs/ingest_findings.py`)
- `ingest_access_analyzer` — IAM Access Analyzer ingestion (`backend/workers/jobs/ingest_access_analyzer.py`)
- `ingest_inspector` — Inspector ingestion (`backend/workers/jobs/ingest_inspector.py`)
- `ingest_control_plane_events` — Control-plane event ingestion (`backend/workers/jobs/ingest_control_plane_events.py`)
- `compute_actions` — Action computation (`backend/workers/jobs/compute_actions.py`)
- `remediation_run` — Remediation execution (`backend/workers/jobs/remediation_run.py`)
- `generate_export` — Evidence/compliance pack generation (`backend/workers/jobs/evidence_export.py`)
- `generate_baseline_report` — Baseline report generation (`backend/workers/jobs/generate_baseline_report.py`)
- `weekly_digest` — Weekly digest email/Slack (`backend/workers/jobs/weekly_digest.py`)
- `reconcile_inventory_shard` — Inventory reconciliation shard (`backend/workers/jobs/reconcile_inventory_shard.py`)
- `reconcile_inventory_global_orchestration` — Global orchestration (`backend/workers/jobs/reconcile_inventory_global_orchestration.py`)
- `reconcile_recently_touched_resources` — Recently touched resources (`backend/workers/jobs/reconcile_recently_touched_resources.py`)
- `backfill_finding_keys` — Finding key backfill (`backend/workers/jobs/backfill_finding_keys.py`)
- `backfill_action_groups` — Action group backfill (`backend/workers/jobs/backfill_action_groups.py`)

### Error Handling

The worker classifies errors:

- **Transient errors** (retried): Throttling, ServiceUnavailable, InternalError
- **Permission errors** (non-retryable): AccessDenied, UnauthorizedOperation
- **Other errors**: Logged, retried via SQS (up to `maxReceiveCount=3`)

After 3 retries, messages go to DLQ (dead-letter queue).

### Contract Violations

Malformed or unknown jobs are quarantined:

- **Invalid JSON** — `CONTRACT_VIOLATION_INVALID_JSON`
- **Missing fields** — `CONTRACT_VIOLATION_MISSING_FIELDS`
- **Unknown job type** — `CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE`
- **Unsupported schema version** — `CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION`

Quarantined messages are sent to `security-autopilot-contract-quarantine-queue` for triage.

---

## Development Mode

### Logging

Set `LOG_LEVEL=DEBUG` for verbose logs:

```bash
LOG_LEVEL=DEBUG
```

Worker logs include:
- Queue connection status
- Job processing start/end
- Error details and stack traces
- Queue metrics (every 60s by default)

### Queue Metrics

The worker logs queue metrics periodically:

```
Queue metrics queue=ingest polls=10 empty_polls=5 empty_poll_rate=0.50 messages_received=5 messages_processed=5 in_flight=0 avg_processing_ms=1234.56 receive_errors=0
```

Configure interval via `WORKER_QUEUE_METRICS_LOG_INTERVAL_SECONDS` (default: 60s).

### Graceful Shutdown

The worker handles `SIGTERM` and `SIGINT` gracefully:

- Finishes processing current messages
- Drains in-flight work
- Exits cleanly

Press `Ctrl+C` to stop the worker.

---

## Testing Jobs Locally

### Sending Test Messages

You can send test messages to SQS queues using AWS CLI:

```bash
# Send ingest job
aws sqs send-message \
  --queue-url $SQS_INGEST_QUEUE_URL \
  --message-body '{
    "schema_version": 2,
    "job_type": "ingest",
    "tenant_id": "00000000-0000-0000-0000-000000000000",
    "account_id": "123456789012",
    "region": "us-east-1",
    "created_at": "2024-01-01T00:00:00Z"
  }'
```

### Mocking SQS (Advanced)

For testing without real SQS queues, consider:
- **LocalStack** — Local AWS service emulator
- **Moto** — AWS service mocking library for tests

See [Testing](tests.md) for test-specific mocking.

---

## Common Development Tasks

### Adding a New Job Type

1. **Define job type constant** in `backend/utils/sqs.py`:
   ```python
   MY_NEW_JOB_TYPE = "my_new_job"
   ```

2. **Create job handler** in `backend/workers/jobs/my_new_job.py`:
   ```python
   from backend.utils.sqs import MY_NEW_JOB_TYPE
   
   def handle_my_new_job(job: dict) -> None:
       tenant_id = job["tenant_id"]
       # Process job...
   ```

3. **Register handler** in `backend/workers/jobs/__init__.py`:
   ```python
   from backend.workers.jobs.my_new_job import handle_my_new_job
   
   JOB_HANDLERS = {
       MY_NEW_JOB_TYPE: handle_my_new_job,
       # ... other handlers
   }
   ```

4. **Update required fields** in `backend/workers/main.py`:
   ```python
   MY_NEW_JOB_REQUIRED_FIELDS = {"job_type", "tenant_id", "created_at"}
   ```

5. **Send job** from API or test:
   ```python
   from backend.utils.sqs import send_job_message
   await send_job_message(queue_url, {
       "schema_version": 2,
       "job_type": MY_NEW_JOB_TYPE,
       "tenant_id": tenant_id,
       "created_at": datetime.now(timezone.utc).isoformat(),
   })
   ```

### Debugging Job Failures

1. **Check worker logs** for error messages
2. **Check DLQ** if message was retried 3 times:
   ```bash
   aws sqs receive-message --queue-url $SQS_INGEST_DLQ_URL
   ```
3. **Check quarantine queue** for contract violations:
   ```bash
   aws sqs receive-message --queue-url $SQS_CONTRACT_QUARANTINE_QUEUE_URL
   ```

### Testing Long-Running Jobs

For jobs that take > 5 minutes (visibility timeout):

- The worker sends **visibility heartbeat** every 120s to extend visibility
- If heartbeat fails, message becomes visible again and may be retried

---

## Performance Tuning

### Concurrency

Adjust `WORKER_MAX_IN_FLIGHT_PER_QUEUE`:

```bash
# Process up to 20 messages concurrently per queue
WORKER_MAX_IN_FLIGHT_PER_QUEUE=20
```

**Note**: Higher concurrency increases database connection usage. Monitor connection pool size.

### Queue Polling

The worker uses long polling (20s wait) to reduce empty polls. For faster processing:

- Use multiple worker instances (each polls independently)
- Reduce `WaitTimeSeconds` in code (not recommended; increases empty polls)

### Database Connections

The worker uses sync SQLAlchemy (not async). Ensure connection pool is sized appropriately:

```python
# In backend/workers/database.py (if customizing)
engine = create_engine(
    DATABASE_URL_SYNC,
    pool_size=10,
    max_overflow=20,
)
```

---

## Production Considerations

For production deployment, see [Owner Deployment Guide](../deployment/infrastructure-ecs.md). Key differences:

- **Deployment**: ECS Fargate task or Lambda function (not `python -m backend.workers.main` directly)
- **Scaling**: Multiple worker tasks for parallel processing
- **Monitoring**: CloudWatch logs and metrics
- **DLQ Alarms**: CloudWatch alarms for DLQ depth

---

## Next Steps

- **[Testing](tests.md)** — Run tests
- **[Backend Development](backend.md)** — Run the API locally
- **[API Reference](../api/README.md)** — API documentation

---

## Troubleshooting

### No Queues Configured

Error: `No worker queue configured for WORKER_POOL=...`

**Solution**: Set queue URLs in `backend/workers/.env`:
```bash
SQS_INGEST_QUEUE_URL="https://sqs.region.amazonaws.com/account/queue-name"
```

### Database Connection Errors

- Verify `DATABASE_URL` is correct
- Check PostgreSQL is running (if local)
- Ensure `DATABASE_URL_SYNC` is set (worker uses sync driver)

### AWS Credential Errors

- Run `aws configure` or set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- Verify IAM permissions allow SQS access

### Job Not Processing

1. **Check queue URL** is correct
2. **Check job schema** matches expected format
3. **Check worker logs** for errors
4. **Check DLQ** if message was retried 3 times

### High Memory Usage

- Reduce `WORKER_MAX_IN_FLIGHT_PER_QUEUE`
- Process jobs in batches
- Optimize database queries (avoid N+1 queries)
