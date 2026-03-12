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

For the current serverless production path on `ocypheris.com`:
- `config/.env.ops` is the deploy-time source for backend/runtime parameters.
- `frontend/.env` is the checked-in public build-time source for Cloudflare/OpenNext.
- `frontend/.env.local` is local-only and must not leak into production builds.

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

#### Firebase Email Verification

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `FIREBASE_PROJECT_ID` | Firebase project id used for signup verification checks | `aws-security-autopilot` | CloudFormation parameter via `config/.env.ops` |
| `FIREBASE_EMAIL_CONTINUE_URL_BASE` | Public frontend origin used when generating Firebase email action links | `https://ocypheris.com` | CloudFormation parameter via `config/.env.ops` |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Runtime path to the packaged Firebase Admin SDK credential file | `/var/task/backend/.firebase/firebase-service-account.json` | Lambda environment in `saas-serverless-httpapi.yaml` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Inline Admin SDK JSON credential payload | empty in current live deploy | Not used in the current live deploy |

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

#### Frontend Public Build Variables

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `NEXT_PUBLIC_API_URL` | Public API base URL embedded into the frontend build | `https://api.ocypheris.com` | `frontend/.env` |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Firebase web app API key | `<YOUR_VALUE_HERE>` | `frontend/.env` |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Firebase Auth domain for the web app | `aws-security-autopilot.firebaseapp.com` | `frontend/.env` |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Firebase project id for the web app | `aws-security-autopilot` | `frontend/.env` |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Firebase web app id | `1:245906784078:web:264d8471a65d655c80681f` | `frontend/.env` |

#### Email Delivery (required for real verification emails)

| Variable | Description | Example | Where Set |
|----------|-------------|---------|-----------|
| `EMAIL_FROM` | Verified sender address for outgoing transactional email | `noreply@ocypheris.com` | CloudFormation parameter via `config/.env.ops` |
| `EMAIL_SMTP_HOST` | SMTP host for delivery | `email-smtp.eu-north-1.amazonaws.com` | CloudFormation parameter via `config/.env.ops` |
| `EMAIL_SMTP_PORT` | SMTP port | `587` | CloudFormation parameter via `config/.env.ops` |
| `EMAIL_SMTP_STARTTLS` | Use STARTTLS | `true` | CloudFormation parameter via `config/.env.ops` |
| `EMAIL_SMTP_CREDENTIALS_SECRET_ID` | Secrets Manager secret id/ARN with JSON `{ "user": "...", "password": "..." }` | `security-autopilot-dev/EMAIL_SMTP` | CloudFormation parameter via `config/.env.ops` |
| `EMAIL_SMTP_USER` | SMTP username injected into Lambda from `EMAIL_SMTP_CREDENTIALS_SECRET_ID` | `<YOUR_VALUE_HERE>` | Lambda runtime env (resolved by CloudFormation dynamic reference) |
| `EMAIL_SMTP_PASSWORD` | SMTP password injected into Lambda from `EMAIL_SMTP_CREDENTIALS_SECRET_ID` | `<YOUR_VALUE_HERE>` | Lambda runtime env (resolved by CloudFormation dynamic reference) |

> ❓ Needs verification: As of `2026-03-11`, `security-autopilot-dev-api` is wired to SES SMTP with `EMAIL_FROM=noreply@ocypheris.com`, `EMAIL_SMTP_HOST=email-smtp.eu-north-1.amazonaws.com`, `EMAIL_SMTP_PORT="587"`, `EMAIL_SMTP_STARTTLS="true"`, and credentials from `security-autopilot-dev/EMAIL_SMTP`. The three DKIM CNAMEs are now published in Cloudflare and externally resolvable, and `marcoibrahim11@outlook.com` is verified as a sandbox recipient, but SES still shows `VerificationStatus=PENDING` for `ocypheris.com` until AWS rechecks the sender domain, the SES production-access review still shows `DENIED`, and a fresh `put-account-details --production-access-enabled` attempt currently returns `ConflictException`.

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
| `CLOUDFORMATION_READ_ROLE_TEMPLATE_URL` | Read role template URL | `https://templates.s3.region.amazonaws.com/read-role/v1.5.4.yaml` | CloudFormation parameter |
| `CLOUDFORMATION_WRITE_ROLE_TEMPLATE_URL` | Write role template URL | `https://templates.s3.region.amazonaws.com/write-role/v1.4.2.yaml` | CloudFormation parameter |
| `CLOUDFORMATION_CONTROL_PLANE_FORWARDER_TEMPLATE_URL` | Control-plane forwarder template URL | `https://templates.s3.region.amazonaws.com/forwarder/v1.0.0.yaml` | CloudFormation parameter (optional) |

### Optional Variables

See [Local Development Environment Setup](../local-dev/environment.md) for complete list of optional variables with defaults.

## Firebase Production Notes

- Live backend origin: `https://api.ocypheris.com`
- Live frontend origin: `https://ocypheris.com`
- Current Firebase project id: `aws-security-autopilot`
- Firebase Auth authorized domains currently needed by this repo:
  - `localhost`
  - `127.0.0.1`
  - `ocypheris.com`
  - `www.ocypheris.com`
  - `dev.ocypheris.com`

### Current credential packaging model

- The live serverless stack does not inject the Firebase Admin SDK JSON through Lambda environment variables.
- Instead, the deploy/build context includes:
  - `backend/.firebase/firebase-service-account.json`
- The runtime then reads it from:
  - `/var/task/backend/.firebase/firebase-service-account.json`
- `backend/.firebase/` is ignored in the repo so the credential file is not tracked.

Reason:
- The initial inline-JSON attempt exceeded AWS Lambda's `UpdateFunctionConfiguration` request-size limit (`5120` bytes).

### Cloudflare/OpenNext build rule

- Keep production-safe public values in `frontend/.env`.
- Keep workstation overrides in `frontend/.env.local`.
- Use `npm run opennext:build:prod`, `npm run preview`, `npm run deploy`, or `npm run upload` from `frontend/` for any production-style OpenNext build.
- Those commands now run `frontend/scripts/run-opennext-production.mjs`, which:
  - strips inherited `NEXT_PUBLIC_*` shell variables before invoking OpenNext,
  - temporarily hides `frontend/.env.local`,
  - validates `.open-next/cloudflare/next-env.mjs` after build, and
  - fails the build if `production.NEXT_PUBLIC_API_URL` is missing or points at `localhost` / `127.0.0.1`.
- Do not use raw `npx opennextjs-cloudflare build`, `deploy`, `preview`, or `upload` for live builds unless you intentionally reproduce the same safeguards.

### Current production blocker

- The API runtime now has:
  - `EMAIL_FROM=noreply@ocypheris.com`
  - `EMAIL_SMTP_HOST=email-smtp.eu-north-1.amazonaws.com`
  - `EMAIL_SMTP_PORT=587`
  - `EMAIL_SMTP_STARTTLS=true`
  - `EMAIL_SMTP_USER` and `EMAIL_SMTP_PASSWORD` resolved from the `security-autopilot-dev/EMAIL_SMTP` Secrets Manager secret
- The serverless deploy path supports:
  - non-secret SMTP inputs in `config/.env.ops`
  - a Secrets Manager credential secret referenced by `EMAIL_SMTP_CREDENTIALS_SECRET_ID`
  - CloudFormation dynamic references that resolve `EMAIL_SMTP_USER` and `EMAIL_SMTP_PASSWORD` into the Lambda environment
- The remaining blocker is now SES account state, not app wiring:
  - live signup/resend attempts reach the SMTP provider
  - `aws sesv2 get-email-identity --region eu-north-1 --email-identity ocypheris.com` returns `VerifiedForSendingStatus=false`, `VerificationStatus=PENDING`, and `VerificationInfo.ErrorType=HOST_NOT_FOUND`
  - the published DKIM CNAMEs already resolve publicly, so the current `HOST_NOT_FOUND` result is waiting on the next SES verification poll
  - `aws sesv2 get-account --region eu-north-1` returns `ProductionAccessEnabled=false`
  - `aws sesv2 get-account --region eu-north-1` also returns `Details.ReviewDetails.Status=DENIED` with case `177318726300086`
  - a fresh `aws sesv2 put-account-details --region eu-north-1 ... --production-access-enabled` call currently returns `ConflictException`
  - `aws sesv2 get-email-identity --region eu-north-1 --email-identity marcoibrahim11@outlook.com` now returns `VerificationStatus=SUCCESS` and `VerifiedForSendingStatus=true`
  - CloudWatch shows SES rejecting sends with `554 Message rejected: Email address is not verified`
  - `backend/services/email.py` therefore returns delivery failure in `ENV=prod`, and the live signup route rejects the request with `503 verification_email_delivery_unavailable` instead of falsely returning `202`

### Current SES DKIM DNS records

These DKIM records are now published for `ocypheris.com`:

| Name | Type | Value |
|------|------|-------|
| `3nnjfxd3pc3ccswvgj5xpfe7ftkdhb3w._domainkey.ocypheris.com` | `CNAME` | `3nnjfxd3pc3ccswvgj5xpfe7ftkdhb3w.dkim.amazonses.com` |
| `sy2ubheakio36fszurdsdvm4k6cjlcdy._domainkey.ocypheris.com` | `CNAME` | `sy2ubheakio36fszurdsdvm4k6cjlcdy.dkim.amazonses.com` |
| `oxsp5xif66qvsvn6pq6sqquj2dgsnmb3._domainkey.ocypheris.com` | `CNAME` | `oxsp5xif66qvsvn6pq6sqquj2dgsnmb3.dkim.amazonses.com` |

Next steps after the DNS publish:

- Wait for SES to recheck the domain and clear `VerificationStatus=PENDING`.
- Revisit production access after domain verification; the current review is `DENIED` under case `177318726300086`, and the current CLI resubmission path returns `ConflictException`.
- While sandbox is still enabled, both sender and recipient identities must be verified for any live delivery test.
- `marcoibrahim11@outlook.com` is already verified as a recipient identity in SES; the remaining sandbox blocker is the sender identity for `noreply@ocypheris.com`.

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

#### 5. EMAIL_SMTP credentials (JSON secret)

```bash
aws secretsmanager create-secret \
  --name security-autopilot-dev/EMAIL_SMTP \
  --secret-string '{"user":"<YOUR_VALUE_HERE>","password":"<YOUR_VALUE_HERE>"}' \
  --region eu-north-1
```

Then set these non-secret deploy inputs in `config/.env.ops` before redeploying:

```bash
EMAIL_FROM="noreply@ocypheris.com"
EMAIL_SMTP_HOST="email-smtp.eu-north-1.amazonaws.com"
EMAIL_SMTP_PORT="587"
EMAIL_SMTP_STARTTLS="true"
EMAIL_SMTP_CREDENTIALS_SECRET_ID="security-autopilot-dev/EMAIL_SMTP"
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
FIREBASE_PROJECT_ID="aws-security-autopilot"
FIREBASE_EMAIL_CONTINUE_URL_BASE="https://ocypheris.com"
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
backend/.firebase/
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
- [Backend development guide](../local-dev/backend.md)
