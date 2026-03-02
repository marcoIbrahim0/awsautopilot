# Environment Setup

This guide covers setting up your local development environment, including environment variables, Python dependencies, and database configuration.

## Environment Variables

All configuration is managed via environment variables, with split files per service/runtime.

### Canonical Env Files

- Backend runtime: `/Users/marcomaher/AWS Security Autopilot/backend/.env`
- Worker runtime: `/Users/marcomaher/AWS Security Autopilot/backend/workers/.env`
- Frontend public vars: `/Users/marcomaher/AWS Security Autopilot/frontend/.env`
- Deploy/ops scripts: `/Users/marcomaher/AWS Security Autopilot/config/.env.ops`
- Root `/Users/marcomaher/AWS Security Autopilot/.env` is backup-only and commented out.

The backend and worker settings loaders use these service-local files rather than root `.env`.

### Creating Service Env Files

If any file is missing in your local workspace:

```bash
touch backend/.env backend/workers/.env frontend/.env config/.env.ops
```

### Required Environment Variables

#### Database

```bash
# PostgreSQL connection string (asyncpg driver)
DATABASE_URL="postgresql+asyncpg://user:password@host:5432/dbname"

# Sync PostgreSQL URL for Alembic migrations (psycopg2 driver)
# If unset, derived from DATABASE_URL by replacing +asyncpg with +psycopg2
DATABASE_URL_SYNC="postgresql://user:password@host:5432/dbname"
```

**Example (Neon):**
```bash
DATABASE_URL="postgresql+asyncpg://neondb_owner:password@ep-square-queen-agyb78gw-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require"
DATABASE_URL_SYNC="postgresql://neondb_owner:password@ep-square-queen-agyb78gw-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require"
```

**Example (Local Postgres):**
```bash
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/security_autopilot"
DATABASE_URL_SYNC="postgresql://postgres:postgres@localhost:5432/security_autopilot"
```

#### Application

```bash
# Application name
APP_NAME="AWS Security Autopilot"

# Environment: local | dev | prod
ENV="local"

# Log level: DEBUG | INFO | WARNING | ERROR
LOG_LEVEL="INFO"

# CORS origins (comma-separated)
CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
```

#### AWS Configuration

```bash
# Your SaaS AWS account ID (12 digits)
SAAS_AWS_ACCOUNT_ID="029037611564"

# Default AWS region
AWS_REGION="eu-north-1"

# Session name for STS AssumeRole
ROLE_SESSION_NAME="security-autopilot-session"
```

#### SQS Queues

```bash
# Ingest queue (legacy)
SQS_INGEST_QUEUE_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-ingest-queue"
SQS_INGEST_DLQ_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-ingest-dlq"

# Events fast-lane queue
SQS_EVENTS_FAST_LANE_QUEUE_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-events-fastlane-queue"
SQS_EVENTS_FAST_LANE_DLQ_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-events-fastlane-dlq"

# Inventory reconciliation queue
SQS_INVENTORY_RECONCILE_QUEUE_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-inventory-reconcile-queue"
SQS_INVENTORY_RECONCILE_DLQ_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-inventory-reconcile-dlq"

# Export/report queue
SQS_EXPORT_REPORT_QUEUE_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-export-report-queue"
SQS_EXPORT_REPORT_DLQ_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-export-report-dlq"

# Contract quarantine queue
SQS_CONTRACT_QUARANTINE_QUEUE_URL="https://sqs.eu-north-1.amazonaws.com/ACCOUNT_ID/security-autopilot-contract-quarantine-queue"
```

**Note**: Replace `ACCOUNT_ID` with your AWS account ID. Queue URLs can be obtained from CloudFormation stack outputs (see [Deployment Guide](../deployment/infrastructure-ecs.md)).

#### Authentication & Security

```bash
# JWT secret (MUST be changed in production)
JWT_SECRET="change-me-in-production-do-not-use-in-prod"

# JWT access token expiry in minutes (default: 7 days + 1 hour = 10080)
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# SaaS admin emails (comma-separated)
SAAS_ADMIN_EMAILS="admin@example.com"

# Control-plane events secret (for POST /api/internal/control-plane-events)
CONTROL_PLANE_EVENTS_SECRET="your-secret-here"

# Weekly digest cron secret (for POST /api/internal/weekly-digest)
DIGEST_CRON_SECRET="your-secret-here"
```

#### Frontend & API URLs

```bash
# Frontend URL (for invite links, redirects)
FRONTEND_URL="http://localhost:3000"

# Public API base URL (for CloudFormation EventBridge API Destination prefill)
# Use ngrok or similar for local testing with AWS services
API_PUBLIC_URL="http://localhost:8000"
# Or with ngrok: API_PUBLIC_URL="https://your-ngrok-url.ngrok-free.app"
```

#### S3 Storage

```bash
# Export bucket for evidence packs and baseline reports
S3_EXPORT_BUCKET="security-autopilot-exports"
S3_EXPORT_BUCKET_REGION="eu-north-1"

# Support bucket for admin→tenant files
S3_SUPPORT_BUCKET="autopilot-s3-support-bucket"
S3_SUPPORT_BUCKET_REGION="eu-north-1"
```

#### CloudFormation Templates

```bash
# Read role template URL (default: project S3 bucket)
CLOUDFORMATION_READ_ROLE_TEMPLATE_URL="https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.1.yaml"

# Write role template URL
CLOUDFORMATION_WRITE_ROLE_TEMPLATE_URL="https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/write-role/v1.4.0.yaml"

# Control-plane forwarder template URL (optional)
CLOUDFORMATION_CONTROL_PLANE_FORWARDER_TEMPLATE_URL="https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/control-plane-forwarder/v1.0.0.yaml"

# Default region for Launch Stack console links
CLOUDFORMATION_DEFAULT_REGION="eu-north-1"
```

#### Control-Plane Configuration

```bash
# Shadow mode (true = write only to shadow tables)
CONTROL_PLANE_SHADOW_MODE="false"

# Source label for control-plane pipeline outputs
CONTROL_PLANE_SOURCE="event_monitor_shadow"

# Master switch for canonical status promotion/reopen from shadow evaluations
CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED="true"

# Only these controls are eligible for live canonical promotion/reopen
CONTROL_PLANE_HIGH_CONFIDENCE_CONTROLS="S3.1,SecurityHub.1,GuardDuty.1"

# Medium/low controls considered for Item 17 quality-gated promotion (blank keeps them non-promoting)
CONTROL_PLANE_MEDIUM_LOW_CONFIDENCE_CONTROLS=""

# Minimum state_confidence required for promotion/reopen
CONTROL_PLANE_PROMOTION_MIN_CONFIDENCE="95"

# Optional tenant pilot allowlist (blank = all tenants)
CONTROL_PLANE_PROMOTION_PILOT_TENANTS=""

# Keep SOFT_RESOLVED from promoting unless explicitly enabled
CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED="false"

# Item 17 medium/low quality gates (0-100 percentages)
CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_COVERAGE="95"
CONTROL_PLANE_MEDIUM_LOW_PROMOTION_MIN_PRECISION="95"
CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_COVERAGE="0"
CONTROL_PLANE_MEDIUM_LOW_PROMOTION_OBSERVED_PRECISION="0"

# Emergency fail-closed medium/low rollback switch
CONTROL_PLANE_MEDIUM_LOW_PROMOTION_ROLLBACK_TRIGGERED="false"

# Legacy authoritative control list (kept for backward compatibility references)
CONTROL_PLANE_AUTHORITATIVE_CONTROLS="S3.1,SecurityHub.1,GuardDuty.1"

# Recent touch lookback window (minutes)
CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES="60"

# Inventory services (comma-separated)
CONTROL_PLANE_INVENTORY_SERVICES="ec2,s3,cloudtrail,config,iam,ebs,rds,eks,ssm,guardduty"

# Maximum resources per inventory shard
CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD="500"
```

#### Worker Configuration

```bash
# Worker queue pool selector: legacy | events | inventory | export | all
WORKER_POOL="all"

# Maximum concurrent in-flight messages per queue poller
WORKER_MAX_IN_FLIGHT_PER_QUEUE="10"

# Queue metrics log interval (seconds)
WORKER_QUEUE_METRICS_LOG_INTERVAL_SECONDS="60"
```

#### Email Configuration

```bash
# From address for outgoing emails
EMAIL_FROM="noreply@example.com"

# SMTP settings (required for real email delivery in non-local env)
EMAIL_SMTP_HOST="<YOUR_VALUE_HERE>"
EMAIL_SMTP_PORT="587"
EMAIL_SMTP_USER="<YOUR_VALUE_HERE>"
EMAIL_SMTP_PASSWORD="<YOUR_VALUE_HERE>"
EMAIL_SMTP_STARTTLS="true"

# Enable/disable weekly digest emails
DIGEST_ENABLED="true"
```

#### Feature Flags

```bash
# Filter findings/actions to in-scope controls only
ONLY_IN_SCOPE_CONTROLS="true"

# Tenant reconciliation enabled globally
TENANT_RECONCILIATION_ENABLED="true"

# Or use pilot tenants (comma-separated tenant UUIDs)
# TENANT_RECONCILIATION_PILOT_TENANTS="tenant-uuid-1,tenant-uuid-2"
```

### Optional Environment Variables

These have defaults and can be omitted for local development:

- `DB_REVISION_GUARD_ENABLED` — Fail-fast if DB revision != Alembic head (default: `true`)
- `SAAS_BUNDLE_EXECUTOR_ENABLED` — Enable SaaS-managed Terraform runner (default: `false`)
- `CONTROL_PLANE_POST_APPLY_RECONCILE_ENABLED` — Post-apply reconciliation (default: `true`)
- `CONTROL_PLANE_AUTO_DISABLE_ASSUME_ROLE_FAILURES` — Auto-disable accounts on AssumeRole failures (default: `true`)

---

## Python Dependencies

### Installation

Install dependencies using `pip`:

```bash
# Install backend dependencies
pip install -r backend/requirements.txt

# Install worker dependencies
pip install -r backend/workers/requirements.txt
```

Or use a virtual environment (recommended):

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# Or: venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r backend/requirements.txt
pip install -r backend/workers/requirements.txt
```

### Key Dependencies

**Backend** (`backend/requirements.txt`):
- `fastapi>=0.109.0` — Web framework
- `uvicorn[standard]>=0.27.0` — ASGI server
- `sqlalchemy>=2.0.0` — ORM
- `alembic>=1.13.0` — Database migrations
- `asyncpg>=0.29.0` — Async PostgreSQL driver
- `psycopg2-binary>=2.9.9` — Sync PostgreSQL driver (for Alembic)
- `boto3>=1.34.0` — AWS SDK
- `pydantic>=2.5.0` — Data validation
- `pyjwt>=2.8.0` — JWT tokens
- `bcrypt>=4.0.0` — Password hashing

**Worker** (`backend/workers/requirements.txt`):
- `boto3>=1.34.0` — AWS SDK (SQS, Security Hub)
- `sqlalchemy>=2.0.0` — ORM (sync)
- `psycopg2-binary>=2.9.9` — PostgreSQL driver
- `pydantic>=2.5.0` — Config validation
- `tenacity>=8.2.0` — Retry logic

---

## Database Setup

### Option 1: Local PostgreSQL

1. **Install PostgreSQL** (if not already installed):
   ```bash
   # macOS (Homebrew)
   brew install postgresql@14
   brew services start postgresql@14

   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   sudo systemctl start postgresql
   ```

2. **Create database**:
   ```bash
   createdb security_autopilot
   ```

3. **Update `backend/.env`**:
   ```bash
   DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/security_autopilot"
   DATABASE_URL_SYNC="postgresql://postgres:postgres@localhost:5432/security_autopilot"
   ```

### Option 2: Cloud-Hosted (Neon)

1. **Create Neon account** at https://neon.tech
2. **Create project** and copy connection string
3. **Update `backend/.env`** with Neon connection string (see example above)

**Note**: Neon requires SSL. The application automatically configures SSL for Neon connections (`backend/database.py`).

### Apply Migrations

After setting up the database:

```bash
# Check current revision
alembic current

# Apply all migrations
alembic upgrade head

# Create new migration (after model changes)
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## AWS Credentials

For SQS queue access, configure AWS credentials:

```bash
# Configure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-north-1"
```

**Note**: For local development, you can use mocked queues or real AWS queues. Real queues require valid AWS credentials with SQS permissions.

---

## Verification

Verify your environment setup:

```bash
# Check Python version
python --version  # Should be 3.10+

# Check PostgreSQL connection
psql $DATABASE_URL -c "SELECT 1"

# Check AWS credentials
aws sts get-caller-identity

# Check SQS queue access (if using real queues)
aws sqs get-queue-attributes --queue-url $SQS_INGEST_QUEUE_URL --attribute-names All
```

---

## Next Steps

- **[Backend Development](backend.md)** — Run the FastAPI API locally
- **[Worker Development](worker.md)** — Run the SQS worker locally
- **[Testing](tests.md)** — Run tests

---

## Troubleshooting

### Database Connection Errors

- **SSL errors**: Ensure `sslmode=require` is in `DATABASE_URL` for cloud-hosted databases
- **Connection refused**: Verify PostgreSQL is running and `DATABASE_URL` host/port are correct
- **Authentication failed**: Check username/password in `DATABASE_URL`

### AWS Credential Errors

- **No credentials found**: Run `aws configure` or set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- **Access denied**: Ensure IAM user/role has SQS permissions

### Environment Variable Not Loading

- Ensure these files exist and are readable:
  - `backend/.env`
  - `backend/workers/.env`
  - `frontend/.env`
  - `config/.env.ops`
- Root `.env` is backup-only and not used as a runtime source.
- Check file permissions (should be readable)
- Verify variable name matches exactly (case-sensitive for some variables)
