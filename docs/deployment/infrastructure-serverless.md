# Infrastructure Deployment: Lambda Serverless

This guide covers deploying AWS Security Autopilot on **Lambda** with API Gateway HTTP API. This is an alternative to ECS Fargate, suitable for cost-efficient scaling at low traffic.

## Overview

Lambda serverless deployment includes:
- **API Gateway HTTP API** — HTTP endpoint for API
- **Lambda Functions** — API and worker functions
- **SQS Triggers** — Lambda triggers for worker queues
- **ECR** — Container images for Lambda (container image deployment)

The deploy script now normalizes Lambda drift after each runtime deploy:
- clears stale reserved concurrency from the API Lambda
- applies the requested worker reserved concurrency
- re-enables or disables worker event source mappings to match `EnableWorker`
- clears reserved concurrency from ReadRole/WriteRole helper Lambdas
- verifies runtime-vs-DB Alembic alignment before deploy, after Lambda image rollout, and again after the DB upgrade
- waits for the live API and worker Lambdas to report the new image URI before advancing the target DB to the repo heads

Current API Lambda runtime posture:
- API Lambda `MemorySize` is `1536` MB in the checked-in serverless template.
- `/ready` queue-lag fields are backed by CloudWatch `GetMetricStatistics`, so the API execution role now includes that read permission.
- The serverless API runtime no longer performs FastAPI bootstrap or the DB revision guard during Lambda module import. Both are memoized on first invoke in [`backend/lambda_handler.py`](/Users/marcomaher/AWS%20Security%20Autopilot/backend/lambda_handler.py), which removes the March 20, 2026 init-time timeout burst class while preserving the schema/runtime guard.

Lean always-on cost controls currently baked into the repo:
- Build source zips in the serverless source bucket auto-expire after `7` days.
- The build stack ECR repositories retain only the latest `5` images and expire older images automatically.
- Lambda log groups use `14`-day retention; keep the CodeBuild log group on finite retention as well when operating the live stack.
- The low-cost production posture assumes external PostgreSQL and does not require ECS, RDS, ALB, NAT, or WAF for the current low-traffic phase.

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
export BUNDLE_REPORTING_TOKEN_SECRET="your-separate-reporting-secret"
export CONTROL_PLANE_EVENTS_SECRET="your-secret"

# Run deployment script
./scripts/deploy_saas_serverless.sh \
  --region eu-north-1 \
  --stack security-autopilot-serverless \
  --api-image-uri 123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:dev \
  --worker-image-uri 123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:dev
```

The checked-in serverless deploy script now performs the guarded sequence itself:

```mermaid
flowchart TD
    A["Verify DB is not ahead of repo/runtime heads"] --> B["Deploy Lambda images and config"]
    B --> C["Wait for API and worker Lambdas to report the new image URI"]
    C --> D["Re-run runtime/DB alignment check against the target DB"]
    D --> E["Run alembic upgrade heads against the same DB"]
    E --> F["Require DB == repo heads before exit"]
```

If you need to run the alignment check manually outside the deploy wrapper, use:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/python scripts/check_runtime_db_alignment.py'
```

To require the DB to be exactly at repo head after a manual upgrade:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/python scripts/check_runtime_db_alignment.py --require-at-head'
```

### Runtime State Drift Recovery

If a stop profile or manual AWS CLI action left the API/worker/helper Lambdas throttled or the worker mappings disabled, run:

```bash
./scripts/normalize_serverless_runtime_state.sh \
  --region eu-north-1 \
  --name-prefix security-autopilot-dev \
  --enable-worker true \
  --worker-reserved-concurrency 10
```

This is required because out-of-band `put-function-concurrency 0` and event-source-mapping state changes are not always reconciled by a later CloudFormation deploy when the template properties themselves are unchanged.

If `/health` or `/ready` starts failing immediately after a runtime deploy, check the API/worker logs for the first-invoke database guard message from [`backend/services/migration_guard.py`](/Users/marcomaher/AWS%20Security%20Autopilot/backend/services/migration_guard.py). In this repo, the recovery command is:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; alembic upgrade heads'
```

Then confirm the DB/runtime pair is aligned:

```bash
/bin/zsh -lc 'set -a; source config/.env.ops; set +a; ./venv/bin/python scripts/check_runtime_db_alignment.py --require-at-head'
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

- **Cold starts** — Lambda still has cold-start latency, but the current `1536` MB API config plus lazy first-invoke bootstrap removed the March 20, 2026 init-time timeout bursts. The retained post-fix live proof shows successful `Init Duration` lines at `595.09 ms`, `207.37 ms`, and `216.44 ms`; the first cold request can still pay several seconds of app bootstrap on invoke.
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
