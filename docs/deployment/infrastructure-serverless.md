# Infrastructure Deployment: Lambda Serverless

This guide covers deploying AWS Security Autopilot on **Lambda** with API Gateway HTTP API. This is an alternative to ECS Fargate, suitable for cost-efficient scaling at low traffic.

## Overview

Lambda serverless deployment includes:
- **API Gateway HTTP API** — HTTP endpoint for API
- **Lambda Functions** — API and worker functions
- **SQS Triggers** — Lambda triggers for worker queues
- **ECR** — Container images for Lambda (container image deployment)

## Prerequisites

- ✅ [Prerequisites](prerequisites.md) completed
- ✅ [SQS Queues](infrastructure-ecs.md#step-1-deploy-sqs-queues) deployed
- ✅ [Database](database.md) provisioned
- ✅ [Secrets](secrets-config.md) created

## Quick Deployment

### Using Deployment Script

```bash
# Set required variables
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
export JWT_SECRET="your-jwt-secret"
export CONTROL_PLANE_EVENTS_SECRET="your-secret"

# Run deployment script
./scripts/deploy_saas_serverless.sh \
  --region eu-north-1 \
  --stack security-autopilot-serverless \
  --api-image-uri 123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:dev \
  --worker-image-uri 123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:dev
```

### Manual Deployment

```bash
aws cloudformation deploy \
  --stack-name security-autopilot-serverless \
  --template-file infrastructure/cloudformation/saas-serverless-httpapi.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    NamePrefix=security-autopilot \
    ApiImageUri=123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:dev \
    WorkerImageUri=123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:dev \
    SqsStackName=security-autopilot-sqs-queues \
    DatabaseUrl="postgresql+asyncpg://user:pass@host:5432/db" \
    JwtSecret="your-jwt-secret" \
    ControlPlaneEventsSecret="your-secret"
```

## Key Differences from ECS

- **Cold starts** — Lambda may have cold start latency (~1-2s)
- **Timeout limits** — 15 minutes max (API Gateway: 30s for HTTP API)
- **Concurrency** — Limited by account quotas (default: 1,000)
- **Cost** — Pay per request (cheaper at low traffic)

## Cost Comparison

**Lambda** (low traffic): ~$10-30/month
**ECS Fargate** (always-on): ~$50-100/month

Choose Lambda if traffic is low/intermittent. Choose ECS for consistent traffic or lower latency requirements.

## See Also

- [Infrastructure: ECS](infrastructure-ecs.md) — ECS Fargate deployment (recommended)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
