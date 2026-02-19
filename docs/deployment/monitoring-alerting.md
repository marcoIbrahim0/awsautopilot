# Monitoring & Alerting

This guide covers CloudWatch monitoring, alarms, and alerting setup for AWS Security Autopilot.

## Overview

Monitoring includes:
- **CloudWatch Logs** — Application logs (API, worker)
- **CloudWatch Metrics** — SQS queue depth, ECS/Lambda metrics
- **CloudWatch Alarms** — Automated alerts for issues
- **Health Checks** — API readiness endpoint monitoring

## CloudWatch Logs

### Log Groups

Log groups are created automatically by CloudFormation:

- `/ecs/security-autopilot-dev/api` — API logs
- `/ecs/security-autopilot-dev/worker` — Worker logs
- `/aws/lambda/security-autopilot-api` — Lambda API logs (serverless)
- `/aws/lambda/security-autopilot-worker` — Lambda worker logs (serverless)

### Log Retention

Default retention: **14 days** (configurable in CloudFormation).

To change retention:

```bash
aws logs put-retention-policy \
  --log-group-name /ecs/security-autopilot-dev/api \
  --retention-in-days 30
```

### Viewing Logs

```bash
# Tail API logs
aws logs tail /ecs/security-autopilot-dev/api --follow

# Search logs
aws logs filter-log-events \
  --log-group-name /ecs/security-autopilot-dev/api \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

---

## CloudWatch Metrics

### SQS Queue Metrics

SQS queues expose metrics automatically:

- **ApproximateNumberOfMessagesVisible** — Queue depth
- **ApproximateAgeOfOldestMessage** — Oldest message age (seconds)
- **NumberOfMessagesSent** — Messages sent to queue
- **NumberOfMessagesReceived** — Messages received from queue

### ECS Metrics

ECS services expose metrics:

- **CPUUtilization** — Task CPU usage (%)
- **MemoryUtilization** — Task memory usage (%)
- **RunningTaskCount** — Number of running tasks
- **DesiredTaskCount** — Desired number of tasks

### Lambda Metrics

Lambda functions expose metrics:

- **Invocations** — Number of invocations
- **Errors** — Number of errors
- **Duration** — Function duration (ms)
- **Throttles** — Number of throttles

---

## CloudWatch Alarms

### SQS Queue Alarms

Alarms are created automatically by the SQS stack (`infrastructure/cloudformation/sqs-queues.yaml`):

#### Queue Depth Alarm

**Alarm**: `security-autopilot-ingest-queue-depth`

- **Metric**: `ApproximateNumberOfMessagesVisible`
- **Threshold**: 100 messages (configurable)
- **Action**: SNS topic (if configured)

#### Queue Age Alarm

**Alarm**: `security-autopilot-ingest-queue-age`

- **Metric**: `ApproximateAgeOfOldestMessage`
- **Threshold**: 900 seconds (15 minutes)
- **Action**: SNS topic (if configured)

#### DLQ Ingress Alarm

**Alarm**: `security-autopilot-ingest-dlq-ingress`

- **Metric**: `NumberOfMessagesSent` (to DLQ)
- **Threshold**: 1 message per 5 minutes
- **Action**: SNS topic (if configured)

**Note**: Similar alarms exist for all queues (events, inventory, export).

### ECS Service Alarms

Create custom alarms for ECS services:

```bash
# CPU utilization alarm
aws cloudwatch put-metric-alarm \
  --alarm-name security-autopilot-api-cpu-high \
  --alarm-description "API service CPU utilization high" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 70 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=security-autopilot-dev-api Name=ClusterName,Value=security-autopilot-dev-cluster
```

### Lambda Error Alarm

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name security-autopilot-api-errors \
  --alarm-description "API Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=security-autopilot-api
```

---

## Health Check Monitoring

### Readiness Endpoint

Monitor the `/ready` endpoint:

```bash
# Create health check alarm (using AWS Systems Manager or external monitoring)
# Or use Route 53 health checks (if using Route 53)

# Example: Use AWS Systems Manager Session Manager to check health
aws ssm send-command \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["curl -f http://localhost:8000/ready || exit 1"]' \
  --targets "Key=tag:Name,Values=security-autopilot-dev-api"
```

### External Monitoring

Consider using external monitoring services:
- **Pingdom** — Uptime monitoring
- **Datadog** — Application performance monitoring
- **New Relic** — APM and infrastructure monitoring

---

## SNS Topic Setup

Create SNS topic for alarm notifications:

```bash
# Create topic
aws sns create-topic --name security-autopilot-alarms

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:eu-north-1:123456789012:security-autopilot-alarms \
  --protocol email \
  --notification-endpoint admin@yourcompany.com

# Confirm subscription (check email)
```

### Update SQS Stack with SNS Topic

```bash
aws cloudformation update-stack \
  --stack-name security-autopilot-sqs-queues \
  --use-previous-template \
  --parameters ParameterKey=AlarmTopicArn,ParameterValue=arn:aws:sns:eu-north-1:123456789012:security-autopilot-alarms
```

---

## Dashboard

Create CloudWatch dashboard:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name security-autopilot \
  --dashboard-body '{
    "widgets": [
      {
        "type": "metric",
        "properties": {
          "metrics": [
            ["AWS/ECS", "CPUUtilization", {"stat": "Average", "dimensions": {"ServiceName": "security-autopilot-dev-api"}}]
          ],
          "period": 300,
          "stat": "Average",
          "region": "eu-north-1",
          "title": "API CPU Utilization"
        }
      }
    ]
  }'
```

---

## Cost Considerations

### CloudWatch Costs

- **Log ingestion**: $0.50/GB
- **Log storage**: $0.03/GB-month
- **Custom metrics**: $0.30/metric-month
- **Alarms**: $0.10/alarm-month

### Cost Optimization

- **Set log retention** — Reduce storage costs
- **Filter logs** — Reduce ingestion (use log filters)
- **Consolidate metrics** — Use fewer custom metrics
- **Use metric math** — Combine metrics instead of creating new ones

---

## Troubleshooting

### Alarms Not Firing

**Check**:
- Alarm state (`OK`, `ALARM`, `INSUFFICIENT_DATA`)
- Metric data exists
- Threshold is appropriate
- SNS topic is configured

### Logs Not Appearing

**Check**:
- Log group exists
- IAM permissions allow `logs:CreateLogStream`
- Application is writing to stdout/stderr

---

## Next Steps

- **[CI/CD](ci-cd.md)** — Set up deployment pipelines
- **[Architecture Documentation](../architecture/owner/README.md)** — Understand system architecture

---

## See Also

- [CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [SQS Monitoring](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-monitoring-using-cloudwatch.html)
