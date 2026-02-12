# EventBridge Target DLQ Replay Runbook

This runbook covers replaying events from EventBridge API Destination target DLQs used by:
- `infrastructure/cloudformation/control-plane-forwarder-template.yaml`
- `infrastructure/cloudformation/reconcile-scheduler-template.yaml`

## When to Use

Use this when either target DLQ alarm fires:
- control-plane forwarder target DLQ depth alarm
- reconcile scheduler target DLQ depth alarm

## Prerequisites

- AWS CLI access to the affected account/region.
- Stack name for the EventBridge template deployment.
- Root cause addressed first (network outage, auth/token issue, endpoint error, etc.).

## 1. Identify DLQ URL and Approximate Backlog

```bash
aws cloudformation describe-stacks \
  --stack-name <stack-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`TargetDLQUrl`].OutputValue' \
  --output text
```

```bash
aws sqs get-queue-attributes \
  --queue-url <target-dlq-url> \
  --attribute-names ApproximateNumberOfMessages ApproximateAgeOfOldestMessage
```

## 2. Inspect Sample Message Safely

```bash
aws sqs receive-message \
  --queue-url <target-dlq-url> \
  --max-number-of-messages 1 \
  --wait-time-seconds 5 \
  --attribute-names All \
  --message-attribute-names All
```

Validate:
- Event payload shape is expected.
- Failure cause is now resolved.

## 3. Replay Strategy

Preferred replay approach is to re-trigger the same event source:
- For control-plane forwarder: trigger or wait for equivalent CloudTrail management events.
- For reconcile scheduler: trigger `/api/internal/reconcile-inventory-global-all-tenants` once manually with the same input.

If direct replay is required, republish the `Body` from each DLQ message to the intended EventBridge API target path using your operational replay tooling (or an approved one-off script), then delete from DLQ only after confirmed success.

## 4. Drain + Verify

```bash
aws sqs get-queue-attributes \
  --queue-url <target-dlq-url> \
  --attribute-names ApproximateNumberOfMessages
```

Verify all of the following:
- DLQ depth returns to `0` (or accepted steady state).
- EventBridge `FailedInvocations` alarm returns to `OK`.
- API endpoint receives events successfully again.

## 5. Evidence to Capture

- Alarm trigger timestamp and clear timestamp.
- Root cause summary.
- Replay method used.
- Message count replayed.
- Post-recovery verification output.
