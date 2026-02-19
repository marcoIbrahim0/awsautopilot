# ARC-004 Failure Injection Evidence

Generated at: `2026-02-12T13:09:23Z`  
Region: `eu-north-1`

## Drill Configuration

- Rule ARN: `arn:aws:events:eu-north-1:029037611564:rule/SecurityAutopilotArc004FiRule20260212130820`
- API destination ARN: `arn:aws:events:eu-north-1:029037611564:api-destination/SecurityAutopilotArc004FiDest20260212130820/3b754c29-86e2-4f89-af32-c780897df850`
- Retry policy: `MaximumRetryAttempts=1`, `MaximumEventAgeInSeconds=60`
- Target DLQ URL: `https://sqs.eu-north-1.amazonaws.com/029037611564/security-autopilot-arc004-fi-dlq-20260212130820`

## Result

- `PutEvents` event id: `31fa71a0-370e-83fd-0af0-db3bc639c350`
- DLQ visible messages after retry window: `1`
- Sample DLQ message id: `52dd3412-7455-4da9-a2d9-1e567c97d9cb`
- Message attribute `ERROR_CODE`: `SDK_CLIENT_ERROR`
- Message attribute `ERROR_MESSAGE`: `Unable to invoke ApiDestination endpoint: API destination endpoint cannot be reached.`

## Cleanup

- Temporary rule, target, API destination, connection, IAM role/policy, and DLQ were removed after evidence capture.
