# Production Deployment Profile

> ⚠️ Change Control: `/docs/Production/` is high-importance documentation.  
> Edit this folder only when an explicit command is given.

## Purpose

This file defines the production deployment baseline for this repository:

- **Default profile:** cost-efficient / lower throughput (for early-stage traffic).
- **Scale-up profile:** increase worker throughput when user volume grows.
- **Rollout + rollback:** command-first process to keep service live during changes.

All commands use:

- Script: `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_saas_serverless.sh`
- Region: `eu-north-1`
- Build stack: `security-autopilot-saas-serverless-build`
- Runtime stack: `security-autopilot-saas-serverless-runtime`
- Name prefix: `security-autopilot-dev`
- SQS stack: `security-autopilot-sqs-queues`
- Env file: `config/.env.ops`

## 1) Standard Profile (Low Cost)

Use this as the default deployment profile while traffic is low.

```bash
export RELEASE_TAG="$(date -u +%Y%m%dT%H%M%SZ)"

SAAS_ENV_FILE='config/.env.ops' \
SAAS_SERVERLESS_IMAGE_TAG="$RELEASE_TAG" \
SAAS_SERVERLESS_ENABLE_WORKER='true' \
SAAS_SERVERLESS_WORKER_RESERVED_CONCURRENCY='1' \
TENANT_RECONCILIATION_ENABLED='false' \
CONTROL_PLANE_SHADOW_MODE='true' \
./scripts/deploy_saas_serverless.sh \
  --region 'eu-north-1' \
  --build-stack 'security-autopilot-saas-serverless-build' \
  --runtime-stack 'security-autopilot-saas-serverless-runtime' \
  --name-prefix 'security-autopilot-dev' \
  --sqs-stack 'security-autopilot-sqs-queues' \
  --enable-worker 'true' \
  --worker-reserved-concurrency '1'
```

### Why this is low-cost

- Worker concurrency is capped at `1`.
- Reconciliation is disabled globally.
- Control plane remains in shadow mode.

## 2) Scale-Up Profile (When Growth Starts)

Use this when queue latency rises or onboarding volume increases.

```bash
export RELEASE_TAG="$(date -u +%Y%m%dT%H%M%SZ)"

SAAS_ENV_FILE='config/.env.ops' \
SAAS_SERVERLESS_IMAGE_TAG="$RELEASE_TAG" \
SAAS_SERVERLESS_ENABLE_WORKER='true' \
SAAS_SERVERLESS_WORKER_RESERVED_CONCURRENCY='10' \
TENANT_RECONCILIATION_ENABLED='true' \
CONTROL_PLANE_SHADOW_MODE='false' \
./scripts/deploy_saas_serverless.sh \
  --region 'eu-north-1' \
  --build-stack 'security-autopilot-saas-serverless-build' \
  --runtime-stack 'security-autopilot-saas-serverless-runtime' \
  --name-prefix 'security-autopilot-dev' \
  --sqs-stack 'security-autopilot-sqs-queues' \
  --enable-worker 'true' \
  --worker-reserved-concurrency '10'
```

Tune `SAAS_SERVERLESS_WORKER_RESERVED_CONCURRENCY` upward in stages (`10` -> `20` -> `30`) based on queue depth and latency.

## 3) Rollout Procedure (Keep Service Live)

1. Capture the current deployed tag (for rollback):

```bash
CURRENT_API_IMAGE="$(aws cloudformation describe-stacks \
  --region eu-north-1 \
  --stack-name security-autopilot-saas-serverless-runtime \
  --query \"Stacks[0].Parameters[?ParameterKey=='ApiImageUri'].ParameterValue\" \
  --output text)"
CURRENT_TAG="${CURRENT_API_IMAGE##*:}"
echo "CurrentTag=$CURRENT_TAG"
```

2. If the release includes DB changes, run migrations first:

```bash
alembic upgrade head
```

3. Deploy using **Standard Profile** (or **Scale-Up Profile** if needed).

4. Validate immediately:

```bash
curl -sS -i "https://api.valensjewelry.com/health"
curl -sS -i -X OPTIONS "https://api.valensjewelry.com/api/auth/login" \
  -H "Origin: https://dev.valensjewelry.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-csrf-token,authorization"
```

5. Watch logs during rollout window:

```bash
aws logs tail "/aws/lambda/security-autopilot-dev-api" --since 30m --follow
aws logs tail "/aws/lambda/security-autopilot-dev-worker" --since 30m --follow
```

## 4) Rollback Procedure

Rollback is a normal redeploy using the previous known-good tag.

```bash
export ROLLBACK_TAG="$CURRENT_TAG"

SAAS_ENV_FILE='config/.env.ops' \
SAAS_SERVERLESS_IMAGE_TAG="$ROLLBACK_TAG" \
SAAS_SERVERLESS_ENABLE_WORKER='true' \
SAAS_SERVERLESS_WORKER_RESERVED_CONCURRENCY='1' \
TENANT_RECONCILIATION_ENABLED='false' \
CONTROL_PLANE_SHADOW_MODE='true' \
./scripts/deploy_saas_serverless.sh \
  --region 'eu-north-1' \
  --build-stack 'security-autopilot-saas-serverless-build' \
  --runtime-stack 'security-autopilot-saas-serverless-runtime' \
  --name-prefix 'security-autopilot-dev' \
  --sqs-stack 'security-autopilot-sqs-queues' \
  --enable-worker 'true' \
  --worker-reserved-concurrency '1'
```

After rollback, repeat health/CORS checks and log monitoring.
