# Queue Contract Quarantine Runbook

This runbook covers triage and replay for queue payloads quarantined by the worker when jobs are malformed or unknown.

## Purpose

The worker sends contract-violating messages to `SQS_CONTRACT_QUARANTINE_QUEUE_URL` with metadata:
- `reason_code`
- `original_message_id`
- `payload_sha256`
- `seen_at`
- `original_queue_url`
- `original_body`

This prevents silent drops while preserving replayability.

## Quarantine Reason Codes

- `invalid_json`: message body is not valid JSON.
- `missing_fields`: required contract fields are missing.
- `unknown_job_type`: no worker handler exists for `job_type`.

## Triage Checklist

1. Inspect CloudWatch alarm state for quarantine depth/age.
2. Sample messages from the quarantine queue and group by `reason_code` and `job_type`.
3. Confirm producer contract state (payload builder version, deploy skew, schema drift).
4. Choose replay target queue (usually `original_queue_url`).
5. Replay using dry-run first, then execute mode.

## Replay Script

Use `scripts/replay_quarantined_messages.py`.

Dry-run (default):

```bash
PYTHONPATH=. python3 scripts/replay_quarantined_messages.py \
  --quarantine-queue-url "$SQS_CONTRACT_QUARANTINE_QUEUE_URL" \
  --polls 2
```

Execute replay to original queues:

```bash
PYTHONPATH=. python3 scripts/replay_quarantined_messages.py \
  --quarantine-queue-url "$SQS_CONTRACT_QUARANTINE_QUEUE_URL" \
  --execute \
  --polls 2
```

Execute replay and delete quarantined message after publish succeeds:

```bash
PYTHONPATH=. python3 scripts/replay_quarantined_messages.py \
  --quarantine-queue-url "$SQS_CONTRACT_QUARANTINE_QUEUE_URL" \
  --execute \
  --delete-on-success \
  --polls 2
```

Replay only one reason code:

```bash
PYTHONPATH=. python3 scripts/replay_quarantined_messages.py \
  --quarantine-queue-url "$SQS_CONTRACT_QUARANTINE_QUEUE_URL" \
  --reason-code unknown_job_type
```

## Post-Replay Verification

1. Verify replayed queue depth changes as expected.
2. Confirm worker processing logs for replayed message IDs/payload hashes.
3. Ensure quarantine queue depth decreases only when using `--delete-on-success`.
4. Capture evidence (alarm screenshots + command output + root-cause notes) for remediation tracking.
