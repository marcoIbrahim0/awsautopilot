# Secrets & Configuration Management

This guide covers environment variable management and AWS Secrets Manager configuration for production deployments.

## Overview

AWS Security Autopilot uses environment variables for configuration. In production:
- **Secrets** (passwords, tokens) → AWS Secrets Manager
- **Non-secret config** → CloudFormation parameters or environment variables
- **Local development / ops** → split env files:
  - `/Users/marcomaher/AWS Security Autopilot/backend/.env`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/.env`
  - `/Users/marcomaher/AWS Security Autopilot/frontend/.env`
  - `/Users/marcomaher/AWS Security Autopilot/config/.env.ops`
  - Root `/Users/marcomaher/AWS Security Autopilot/.env` is backup-only and commented out.

## Environment Variables Reference

### Required Variables

#### Database

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) | `postgresql+asyncpg://user:pass@host:5432/db` | Secrets Manager |
| `DATABASE_URL_SYNC` | PostgreSQL connection string (psycopg2, for Alembic) | `postgresql://user:pass@host:5432/db` | Secrets Manager (optional, auto-derived if unset) |

#### Authentication & Security

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `JWT_SECRET` | Secret for signing JWT tokens | `your-random-secret-here` | Secrets Manager |
| `CONTROL_PLANE_EVENTS_SECRET` | Secret for control-plane event ingestion | `your-secret-here` | Secrets Manager |
| `DIGEST_CRON_SECRET` | Secret for weekly digest cron endpoint | `your-secret-here` | Secrets Manager |
| `SAAS_ADMIN_EMAILS` | Comma-separated SaaS admin emails | `admin@example.com,admin2@example.com` | CloudFormation parameter |

#### AWS Configuration

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `SAAS_AWS_ACCOUNT_ID` | Your SaaS AWS account ID (12 digits) | `029037611564` | CloudFormation parameter |
| `AWS_REGION` | Default AWS region | `eu-north-1` | CloudFormation parameter |
| `ROLE_SESSION_NAME` | Session name for STS AssumeRole | `security-autopilot-session` | CloudFormation parameter |

#### SQS Queues

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `SQS_INGEST_QUEUE_URL` | Ingest queue URL | `https://sqs.region.amazonaws.com/account/queue` | CloudFormation (imported from SQS stack) |
| `SQS_INGEST_DLQ_URL` | Ingest DLQ URL | `https://sqs.region.amazonaws.com/account/dlq` | CloudFormation (imported) |
| `SQS_EVENTS_FAST_LANE_QUEUE_URL` | Events fast-lane queue URL | `https://sqs.region.amazonaws.com/account/events` | CloudFormation (imported) |
| `SQS_EVENTS_FAST_LANE_DLQ_URL` | Events fast-lane DLQ URL | `https://sqs.region.amazonaws.com/account/events-dlq` | CloudFormation (imported) |
| `SQS_INVENTORY_RECONCILE_QUEUE_URL` | Inventory reconcile queue URL | `https://sqs.region.amazonaws.com/account/inventory` | CloudFormation (imported) |
| `SQS_INVENTORY_RECONCILE_DLQ_URL` | Inventory reconcile DLQ URL | `https://sqs.region.amazonaws.com/account/inventory-dlq` | CloudFormation (imported) |
| `SQS_EXPORT_REPORT_QUEUE_URL` | Export/report queue URL | `https://sqs.region.amazonaws.com/account/export` | CloudFormation (imported) |
| `SQS_EXPORT_REPORT_DLQ_URL` | Export/report DLQ URL | `https://sqs.region.amazonaws.com/account/export-dlq` | CloudFormation (imported) |
| `SQS_CONTRACT_QUARANTINE_QUEUE_URL` | Contract quarantine queue URL | `https://sqs.region.amazonaws.com/account/quarantine` | CloudFormation (imported) |

#### Application Configuration

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `APP_NAME` | Application name | `AWS Security Autopilot` | CloudFormation parameter |
| `ENV` | Environment (local/dev/prod) | `prod` | CloudFormation parameter |
| `LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) | `INFO` | CloudFormation parameter |
| `FRONTEND_URL` | Frontend base URL | `https://app.yourcompany.com` | CloudFormation parameter |
| `CORS_ORIGINS` | Comma-separated CORS origins | `https://app.yourcompany.com` | CloudFormation parameter |
| `API_PUBLIC_URL` | Public API base URL | `https://api.yourcompany.com` | CloudFormation parameter (derived from ALB/API Gateway) |
| `WORKER_POOL` | Worker queue pool selector | `all` | CloudFormation parameter |

#### S3 Storage

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `S3_EXPORT_BUCKET` | Export bucket name | `security-autopilot-exports` | CloudFormation parameter |
| `S3_EXPORT_BUCKET_REGION` | Export bucket region | `eu-north-1` | CloudFormation parameter |
| `S3_SUPPORT_BUCKET` | Support bucket name | `autopilot-s3-support-bucket` | CloudFormation parameter |
| `S3_SUPPORT_BUCKET_REGION` | Support bucket region | `eu-north-1` | CloudFormation parameter |

#### CloudFormation Templates

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `CLOUDFORMATION_READ_ROLE_TEMPLATE_URL` | Read role template URL | `https://templates.s3.region.amazonaws.com/read-role/v1.5.1.yaml` | CloudFormation parameter |
| `CLOUDFORMATION_WRITE_ROLE_TEMPLATE_URL` | Write role template URL | `https://templates.s3.region.amazonaws.com/write-role/v1.4.0.yaml` | CloudFormation parameter |
| `CLOUDFORMATION_CONTROL_PLANE_FORWARDER_TEMPLATE_URL` | Control-plane forwarder template URL | `https://templates.s3.region.amazonaws.com/forwarder/v1.0.0.yaml` | CloudFormation parameter (optional) |

### Optional Variables

See [Local Development Environment Setup](../local-dev/environment.md) for complete list of optional variables with defaults.

---

## AWS Secrets Manager Setup

### Creating Secrets

#### 1. DATABASE_URL

```bash
aws secretsmanager create-secret \
  --name security-autopilot-dev/DATABASE_URL \
  --secret-string "postgresql+asyncpg://user:password@host:5432/dbname" \
  --region eu-north-1
```

**Note**: Replace `security-autopilot-dev` with your stack name prefix.

#### 2. JWT_SECRET

Generate a secure random secret:

```bash
# Generate random secret (32 bytes, base64)
openssl rand -base64 32

# Create secret
aws secretsmanager create-secret \
  --name security-autopilot-dev/JWT_SECRET \
  --secret-string "your-generated-secret-here" \
  --region eu-north-1
```

#### 3. CONTROL_PLANE_EVENTS_SECRET

```bash
# Generate random secret
openssl rand -base64 32

# Create secret
aws secretsmanager create-secret \
  --name security-autopilot-dev/CONTROL_PLANE_EVENTS_SECRET \
  --secret-string "your-generated-secret-here" \
  --region eu-north-1
```

#### 4. DIGEST_CRON_SECRET (Optional)

```bash
# Generate random secret
openssl rand -base64 32

# Create secret
aws secretsmanager create-secret \
  --name security-autopilot-dev/DIGEST_CRON_SECRET \
  --secret-string "your-generated-secret-here" \
  --region eu-north-1
```

### Updating Secrets

```bash
aws secretsmanager update-secret \
  --secret-id security-autopilot-dev/DATABASE_URL \
  --secret-string "new-connection-string" \
  --region eu-north-1
```

**Note**: After updating secrets, restart ECS tasks or Lambda functions to pick up new values.

### Secret Naming Convention

Use format: `{stack-name-prefix}/{SECRET_NAME}`

Examples:
- `security-autopilot-dev/DATABASE_URL`
- `security-autopilot-dev/JWT_SECRET`
- `security-autopilot-prod/DATABASE_URL`

---

## CloudFormation Integration

### ECS Fargate Deployment

Secrets are referenced in CloudFormation template (`infrastructure/cloudformation/saas-ecs-dev.yaml`):

```yaml
Secrets:
  - Name: DATABASE_URL
    ValueFrom: !Ref DatabaseUrlSecret
  - Name: JWT_SECRET
    ValueFrom: !Ref JwtSecretSecret
  - Name: CONTROL_PLANE_EVENTS_SECRET
    ValueFrom: !Ref ControlPlaneEventsSecretSecret
```

Secrets are created in CloudFormation:

```yaml
DatabaseUrlSecret:
  Type: AWS::SecretsManager::Secret
  Properties:
    Name: !Sub "${NamePrefix}/DATABASE_URL"
    SecretString: !Ref DatabaseUrl  # Parameter (NoEcho)
```

### Lambda Serverless Deployment

Secrets are referenced in Lambda environment:

```yaml
Environment:
  Variables:
    # Non-secret config
    APP_NAME: !Ref AppName
    # ...
Secrets:
  - Name: DATABASE_URL
    ValueFrom: !Ref DatabaseUrlSecret
```

---

## Local Development

For local development and ops scripts, use split env files (never commit secrets to Git):

```bash
# backend/.env (backend runtime)
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db"
JWT_SECRET="change-me-in-production-do-not-use-in-prod"
CONTROL_PLANE_EVENTS_SECRET="local-dev-secret"

# backend/workers/.env (worker runtime)
WORKER_POOL="all"
SQS_INGEST_QUEUE_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-ingest-queue"

# frontend/.env (public frontend vars)
NEXT_PUBLIC_API_URL="http://localhost:8000"

# config/.env.ops (deploy/ops scripts)
AWS_REGION="eu-north-1"
SQS_STACK_NAME="security-autopilot-sqs-queues"
```

Root `.env` remains a backup-only commented file and should not be used as a runtime source.

**Security**: Add service env files to `.gitignore`:

```bash
# .gitignore
backend/.env
backend/workers/.env
frontend/.env
frontend/.env.local
frontend/.env.*.local
config/.env.ops
```

---

## Secret Rotation

### Manual Rotation

1. **Generate new secret**:
   ```bash
   openssl rand -base64 32
   ```

2. **Update secret in Secrets Manager**:
   ```bash
   aws secretsmanager update-secret \
     --secret-id security-autopilot-dev/JWT_SECRET \
     --secret-string "new-secret"
   ```

3. **Restart services** to pick up new secret:
   - **ECS**: Update service (forces new task deployment)
   - **Lambda**: Redeploy function

### Automated Rotation (Future)

Consider using AWS Secrets Manager automatic rotation for:
- Database passwords
- JWT secrets (if rotation supported)

**Note**: Automatic rotation requires Lambda rotation function. Not implemented by default.

---

## Security Best Practices

### 1. Never Commit Secrets

- ✅ Use split env files for local development and ops (`backend/.env`, `backend/workers/.env`, `frontend/.env`, `config/.env.ops`)
- ✅ Use Secrets Manager for production
- ❌ Never commit secrets to Git
- ❌ Never hardcode secrets in code

### 2. Least Privilege Access

- **ECS Task Role**: Only permissions needed for application (SQS send, Secrets Manager read)
- **Lambda Execution Role**: Only permissions needed for function
- **Secrets Manager**: Restrict access to specific IAM roles

### 3. Secret Naming

- Use consistent naming convention (`{stack-prefix}/{SECRET_NAME}`)
- Include environment in name (`dev`, `prod`)
- Document secret purpose in Secrets Manager description

### 4. Audit & Monitoring

- Enable CloudTrail for Secrets Manager API calls
- Monitor secret access via CloudWatch metrics
- Alert on unauthorized access attempts

---

## Troubleshooting

### Secret Not Found

**Error**: `SecretsManagerException: Secrets Manager can't find the specified secret`

**Solution**:
- Verify secret name matches CloudFormation reference
- Check secret exists in same region as stack
- Verify IAM permissions allow `secretsmanager:GetSecretValue`

### Secret Access Denied

**Error**: `AccessDeniedException: User is not authorized to perform: secretsmanager:GetSecretValue`

**Solution**:
- Verify ECS task role or Lambda execution role has `secretsmanager:GetSecretValue` permission
- Check resource-based policy on secret (if using)

### Secret Not Updating

**Issue**: Service still using old secret value

**Solution**:
- Restart ECS service: `aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment`
- Redeploy Lambda function
- Verify secret was actually updated: `aws secretsmanager get-secret-value --secret-id <secret-id>`

---

## Next Steps

- **[Infrastructure: ECS](infrastructure-ecs.md)** — Deploy ECS infrastructure with secrets
- **[Infrastructure: Serverless](infrastructure-serverless.md)** — Deploy Lambda infrastructure with secrets
- **[Database Setup](database.md)** — Configure database connection string

---

## See Also

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Local Development Environment Setup](../local-dev/environment.md)
- [Backend Configuration](../architecture/owner/backend-services.md)
