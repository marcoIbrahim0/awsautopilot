# Full implementation plan

## A) System architecture
### Components

**Frontend** (React/Next.js)
- accounts onboarding
- actions/finding views
- exceptions
- approvals
- evidence exports

**API** (FastAPI)
- auth + tenancy
- AWS account registry
- findings/actions APIs
- remediation approvals APIs
- exports APIs

**Worker** (Python)
- SQS consumers:
  - ingest findings
  - compute actions
  - run remediation
  - generate exports

**Data**
- Postgres (core relational data)
- S3 (export artifacts and evidence packs)
- CloudWatch logs/metrics

**Data plane in customer AWS**
- ReadRole (required): Security Hub read + minimal AWS describes
- WriteRole (optional): only actions you support for direct fixes

## B) Core workflows
### 1) Onboard account

- customer deploys CloudFormation stack (role + external id trust)
- your app stores account id + role arn + region set
- worker validates access with sts:GetCallerIdentity

### 2) Ingest → normalize → actions

- worker pulls Security Hub findings (required); optional: IAM Access Analyzer, Inspector (see Step 2B)
- multi-region: one job per account–region (see Step 2.7)
- store raw JSON + normalized fields
- action engine groups:
  - by resource + rule
  - dedupe across regions/accounts where possible
  - action priority score = severity + exploitability signals + exposure (simple scoring is enough)

### 3) Exceptions / suppression

- exceptions are first-class:
  - reason, approved_by, expiry
  - optional ticket link
- exceptions reduce noise and become part of evidence pack

### 4) Hybrid remediation

- **direct fix:** requires approval + write role + safety checks
- **PR-only:** generate patch bundle (Terraform/CFN) + steps + "apply checklist"
- every remediation run writes a full audit trail

### 5) Evidence pack

export includes:
- service enablement/config snapshots
- actions (open/closed)
- remediation run history
- exceptions with approvals and expiries

## C) Database schema (MVP)

Tables to implement early:
- tenants, users
- aws_accounts (tenant_id, account_id, role_read_arn, role_write_arn, external_id, regions)
- findings (tenant_id, account_id, region, severity, resource_id, control_id, title, status, updated_at, raw_json)
- actions (tenant_id, action_type, target_id, account_id, region, priority, status, timestamps)
- action_findings (many-to-many)
- exceptions (scope + reason + expiry + approvals)
- remediation_runs (mode, logs, outcome, artifacts)

## D) Remediation safety rules (non-negotiable)

Implement these before "auto-fix" is real:
- Approval required for any write action (at least initially)
- Allowlist-based exceptions (e.g., permitted CIDRs)
- Idempotent remediations (safe to re-run)
- Pre-check and post-check for each remediation
- Dry-run / preview output shown to user
- Full audit log for every run

## E) MVP scope (sellable) and exclusions
### MVP includes

- onboarding (read role)
- Security Hub ingestion (multi-region supported; configure regions per account — see Step 2.7)
- optional: IAM Access Analyzer and Inspector ingestion (see Step 2B)
- actions + dedupe + priority
- exceptions with expiry
- remediation:
  - PR-only for most actions
  - **7 real action types** (3 direct fix + 4 PR bundle): S3 account-level, Security Hub, GuardDuty, S3 bucket block, S3 bucket encryption, SG restrict public ports, CloudTrail enabled
- evidence export (CSV/JSON + zipped bundle)

### MVP excludes (initially)

- deep container runtime security
- custom detection language beyond your rules
- complex auto-remediations that can break workloads
- heavy SIEM integrations

## F) Build roadmap (phase-based)
### Phase 0 — Foundation (first milestone)

**Deliverables**
- repo setup (FastAPI + worker + migrations)
- tenancy + auth
- SQS queues + worker runner
- AWS assume-role utility with ExternalId
- Postgres schema + CRUD for accounts

**Definition of done**
- you can connect a test AWS account and validate STS assume role

### Phase 1 — Ingest + UI visibility

**Deliverables**
- ingest Security Hub findings into Postgres
- UI: findings list, filters, per-account view
- basic scoring and "Top risks" view

**Definition of done**
- customer can connect and see findings within minutes

### Phase 2 — Actions + exceptions

**Deliverables**
- action engine (dedupe, group, prioritize)
- exceptions workflow (approve + expiry)
- weekly digest (email or Slack) — See Step 11

**Definition of done**
- user sees 10–30 "Actions" instead of 500 noisy findings

### Phase 3 — Hybrid remediation v1

**Deliverables**
- remediation run model + audit logs
- PR bundle generator: **real** Terraform/CloudFormation per action type (not placeholder)
- **7 real action types** (see Step 9.8 in-scope table):
  - **Direct fix (3):** S3 Block Public Access (account-level), enable Security Hub, enable GuardDuty
  - **PR bundle only (4):** S3 bucket-level block public access, S3 bucket encryption, SG restrict public ports (22/3389), CloudTrail enabled
  - SG restrict optional direct fix later with strict allowlist and guardrails
- PR bundle download (zip or files) so users can apply IaC in their pipeline
- "Next steps" guidance in UI after PR bundle or direct fix completes
- "Recompute actions" button to refresh action status after fixes are applied

**Definition of done**
- user can approve a safe fix and see before/after checks + logs
- user can generate a PR bundle with **applyable** IaC, download it, apply in pipeline, and verify via Recompute

### Phase 4 — Evidence pack + billing

**Deliverables**
- evidence pack export to S3
- downloadable bundle
- compliance pack add-on (exception attestations, control mapping, auditor summary) — See Step 12
- Stripe billing (fast) + plan gating
- (later) AWS Marketplace listing

**Definition of done**
- paying customer flow is complete end-to-end

## G) Hosting and deployment on AWS
### Recommended AWS services

- ECS Fargate: API service + worker service
- RDS Postgres
- SQS
- S3 exports
- Secrets Manager
- CloudWatch logs + alarms
- ALB for API
- CloudFront for frontend if hosted on AWS (or Vercel for speed)

### Deployment process

- Infrastructure as code (Terraform recommended)
- CI/CD:
  - build Docker images
  - deploy to ECS
  - run migrations safely (one-off task)

## H) Security implementation checklist

- STS assume-role only; no static AWS keys
- ExternalId unique per tenant
- encrypt secrets (Secrets Manager)
- encrypt DB at rest (RDS default) and in transit (TLS)
- row-level tenant access control in API
- strict audit logging (write once)
- rate limiting and basic WAF for public endpoints
- background job idempotency + DLQ handling

## I) Team plan (minimal)

To ship MVP efficiently:
- 1 backend (you)
- 1 frontend (can be you or contractor)
- optional part-time: DevOps (ECS/RDS/SQS wiring) + security reviewer for IAM policies

## J) Alpha → Beta → GA launch plan

- **Alpha:** 3–5 friendly AWS startups (read-only + PR-only); use 48h baseline report (Step 13) as lead magnet: connect → ingest → report → propose onboarding
- **Beta:** 10–20 paying SMBs (add safe direct fixes + evidence packs)
- **GA:** AWS Marketplace + MSP partnerships

## Implementation starter (what to build first)

If you want the fastest "first demo" path:

1. CloudFormation ReadRole template + externalId trust
2. FastAPI endpoint to register AWS account + test assume role
3. SQS ingestion job + worker that fetches Security Hub findings
4. Postgres storage + simple UI list
5. Action grouping + "approve exception"
6. Evidence export (CSV/JSON zipped)
7. (GTM lead magnet) 48h baseline report — connect read-only → ingest → request report → 48h report → propose onboarding (see Step 13)

## Detailed Implementation Steps

### Step 1: AWS Account Connect Flow + STS Assume-Role Validation (ReadRole only)

This step establishes the foundation for connecting customer AWS accounts securely using STS AssumeRole with ExternalId. No long-lived keys are used.

#### 1.1 Create CloudFormation template for ReadRole

**Purpose:** Provide a copy-paste template that customers deploy in their AWS account to create the ReadRole.

**What it does:**
- Creates an IAM Role with read-only permissions for Security Hub
- Trusts your SaaS AWS account (your account ID)
- Requires an ExternalId parameter (unique per tenant)
- Includes minimal permissions needed for Security Hub ingestion

**Why this matters:** This removes manual IAM mistakes and ensures consistent, secure role creation across all customers.

**Deliverable:** `infrastructure/cloudformation/read-role-template.yaml` or similar

**Key components:**
- IAM Role resource
- Trust policy allowing your SaaS account to assume the role
- ExternalId condition in trust policy
- IAM policy with Security Hub read permissions (`securityhub:GetFindings`, `securityhub:ListFindings`, `securityhub:BatchGetFindings`)
- Optional: `sts:GetCallerIdentity` for validation

**Customer deployment flow:**
1. Customer receives CloudFormation template (`infrastructure/cloudformation/read-role-template.yaml`) and your **SaaS AWS Account ID** (12-digit number)
2. Customer receives their unique **ExternalId** (generated when tenant is created in your system, stored in `tenants.external_id`)
3. Customer deploys the CloudFormation stack in their AWS account via:
   - AWS Console: CloudFormation > Create Stack > Upload template > Enter parameters (SaaSAccountId, ExternalId)
   - AWS CLI: `aws cloudformation create-stack --stack-name SecurityAutopilotReadRole --template-body file://read-role-template.yaml --parameters ParameterKey=SaaSAccountId,ParameterValue=YOUR_ACCOUNT_ID ParameterKey=ExternalId,ParameterValue=CUSTOMER_EXTERNAL_ID`
4. Stack creates IAM Role with trust policy and permissions
5. Customer copies the **ReadRoleArn** from CloudFormation stack Outputs
6. Customer pastes ReadRoleArn into your SaaS UI when clicking "Connect AWS Account" (Step 1.5)
7. Your backend (Step 1.4/1.5) uses the ARN + same ExternalId to call `sts:AssumeRole`, then validates with `sts:GetCallerIdentity`

**Why this flow matters:** This ensures secure, consistent role creation across all customers. The ExternalId prevents confused deputy attacks, and the CloudFormation template eliminates manual IAM configuration errors.

#### 1.2 Set up FastAPI project structure

**Purpose:** Create the backend skeleton with proper organization.

**File structure to create:**
```
backend/
├── main.py              # API entry point, FastAPI app initialization
├── routers/             # API endpoint definitions
│   ├── __init__.py
│   └── aws_accounts.py  # Account registration endpoints
├── models/              # SQLAlchemy database models
│   ├── __init__.py
│   ├── tenant.py        # Tenant model
│   ├── user.py          # User model
│   └── aws_account.py   # AWS account model
├── services/            # Business logic layer
│   ├── __init__.py
│   └── aws.py           # STS assume-role utility
├── database.py          # Database connection setup
├── config.py            # Configuration management
└── requirements.txt     # Python dependencies
```

**Why this matters:** This is your backend skeleton. Proper structure from the start makes scaling easier.

**Key dependencies:**
- `fastapi` - Web framework
- `sqlalchemy` - ORM
- `alembic` - Database migrations
- `boto3` - AWS SDK
- `pydantic` - Data validation

#### 1.3 Create database models (tenants, users, aws_accounts)

**Purpose:** Establish multi-tenant data model foundation.

**Tables needed:**

**tenants** (companies/organizations):
- `id` (UUID, primary key)
- `name` (string)
- `created_at`, `updated_at` (timestamps)
- `external_id` (string, unique) - Used in STS AssumeRole ExternalId

**users** (people in companies):
- `id` (UUID, primary key)
- `tenant_id` (foreign key to tenants)
- `email` (string, unique)
- `name` (string)
- `created_at`, `updated_at` (timestamps)

**aws_accounts** (linked AWS accounts):
- `id` (UUID, primary key)
- `tenant_id` (foreign key to tenants)
- `account_id` (string, AWS account ID)
- `role_read_arn` (string, IAM role ARN for read access)
- `role_write_arn` (string, optional, IAM role ARN for write access)
- `external_id` (string, matches tenant.external_id)
- `regions` (JSON array, list of regions to monitor)
- `status` (enum: pending, validated, error)
- `last_validated_at` (timestamp)
- `created_at`, `updated_at` (timestamps)

**Why this matters:** Without this, you can't scale beyond 1 customer. Multi-tenancy is essential for SaaS.

**Deliverable:** SQLAlchemy models in `backend/models/` with Alembic migration

#### 1.4 Implement STS assume-role utility

**Purpose:** Core AWS integration function that securely assumes customer roles.

**Function signature:**
```python
def assume_role(
    role_arn: str,
    external_id: str,
    session_name: str = "security-autopilot-session"
) -> boto3.Session:
    """
    Assumes an IAM role using STS and returns a boto3 session.
    
    Args:
        role_arn: The ARN of the role to assume
        external_id: The ExternalId value (from tenant)
        session_name: Identifier for this assume-role session
        
    Returns:
        boto3.Session with assumed role credentials
        
    Raises:
        ClientError: If assume role fails (invalid ARN, wrong ExternalId, etc.)
    """
```

**What it does:**
- Calls `sts.assume_role()` with role ARN and ExternalId
- Returns a boto3 Session with temporary credentials
- Handles retries for transient errors
- Logs errors for debugging

**Error handling:**
- Invalid role ARN → clear error message
- Wrong ExternalId → security error (don't expose details)
- Access denied → permission error
- Retry logic for throttling/transient failures

**Why this matters:** This is the core AWS integration. One clean, reusable function that all AWS operations use.

**Deliverable:** `backend/services/aws.py` with `assume_role()` function

#### 1.5 Create API endpoint for account registration

**Purpose:** React calls this when user clicks "Connect AWS" in the UI.

**Endpoint:** `POST /api/aws/accounts`

**Request body:**
```json
{
  "account_id": "123456789012",
  "role_read_arn": "arn:aws:iam::123456789012:role/SecurityAutopilotReadRole",
  "regions": ["us-east-1", "us-west-2"]
}
```

**What the endpoint does:**
1. Validates request (account_id format, ARN format, regions list)
2. Gets current tenant from auth context
3. Creates/updates `aws_accounts` record in database
4. Calls STS assume-role utility to test connection
5. If successful, calls `sts.get_caller_identity()` to verify account_id matches
6. Updates account status to "validated"
7. Returns success response with account details

**Response (success):**
```json
{
  "id": "uuid",
  "account_id": "123456789012",
  "status": "validated",
  "last_validated_at": "2026-01-29T10:00:00Z"
}
```

**Response (error):**
```json
{
  "error": "Failed to assume role",
  "details": "Invalid ExternalId or role ARN"
}
```

**Why this matters:** This is the user-facing entry point. It must be reliable and provide clear feedback.

**Deliverable:** `backend/routers/aws_accounts.py` with registration endpoint

#### 1.6 Add validation endpoint

**Purpose:** Allows re-testing roles and debugging permission changes.

**Endpoint:** `POST /api/aws/accounts/{account_id}/validate`

**What it does:**
1. Looks up account by ID (scoped to current tenant)
2. Calls STS assume-role with stored role ARN and ExternalId
3. Verifies `sts.get_caller_identity()` returns expected account_id
4. Optionally: Tests Security Hub access by calling `securityhub.get_findings()` (limit 1)
5. Updates `last_validated_at` timestamp
6. Updates `status` (validated or error)
7. Returns validation result

**Response:**
```json
{
  "status": "validated",
  "account_id": "123456789012",
  "last_validated_at": "2026-01-29T10:00:00Z",
  "permissions_ok": true
}
```

**Use cases:**
- Re-testing roles after customer changes IAM policies
- Debugging permission issues
- Support workflows (validate customer setup)
- Periodic health checks (cron job)

**Why this matters:** Customers will have permission issues. This endpoint makes debugging and support much easier.

**Deliverable:** `backend/routers/aws_accounts.py` with validation endpoint

#### Step 1 Definition of Done

✅ Customer can deploy CloudFormation template in their AWS account  
✅ Customer can register account via API with role ARN  
✅ System successfully assumes role using STS + ExternalId  
✅ Validation endpoint confirms role works  
✅ Account stored in database with proper tenant isolation  
✅ Error handling provides clear feedback for common issues

### Step 2: SQS + Worker to Ingest Security Hub Findings into Postgres

This step establishes the asynchronous ingestion pipeline that fetches Security Hub findings from customer AWS accounts and stores them in Postgres. SQS decouples the API from the worker, allowing scalable, reliable processing.

#### 2.1 Set up SQS queues

**Purpose:** Create message queues for asynchronous job processing between the API and worker services.

**What it does:**
- Creates SQS queues for different job types:
  - `security-autopilot-ingest-queue` (standard queue) - For ingestion jobs
  - `security-autopilot-ingest-dlq` (dead-letter queue) - For failed jobs after max retries
- Configures queue attributes:
  - Visibility timeout (30 seconds default, adjustable based on job duration)
  - Message retention period (14 days)
  - Receive message wait time (long polling enabled)
  - Dead-letter queue redrive policy (max receives: 3)
- Sets up IAM policies for worker service to read from queue
- Sets up IAM policies for API service to send messages to queue

**Why this matters:** SQS provides reliable, scalable message delivery. If the worker crashes, messages remain in the queue. Dead-letter queues help identify problematic accounts or permission issues.

**Deliverable:** 
- Infrastructure as Code (Terraform or CloudFormation) defining SQS queues
- IAM roles/policies for API and worker services
- Queue configuration in `backend/config.py` (queue URLs, region)

**Key components:**
- Standard SQS queue (not FIFO - ordering not required for ingestion)
- Dead-letter queue with redrive policy
- IAM policies with least-privilege access
- Queue URLs stored in environment variables or Secrets Manager

**Message format:**
```json
{
  "tenant_id": "uuid",
  "account_id": "123456789012",
  "region": "us-east-1",
  "job_type": "ingest_findings",
  "created_at": "2026-01-29T10:00:00Z"
}
```

#### 2.2 Create worker structure

**Purpose:** Build the worker service that consumes SQS messages and processes ingestion jobs.

**File structure to create:**
```
worker/
├── main.py              # Worker entry point, SQS consumer loop
├── jobs/                # Job handlers
│   ├── __init__.py
│   └── ingest_findings.py  # Security Hub ingestion job
├── services/            # Business logic
│   ├── __init__.py
│   ├── security_hub.py  # Security Hub API client wrapper
│   └── aws.py           # Reuse from backend/services/aws.py (or shared module)
├── database.py          # Database connection (shared with backend or separate)
├── config.py            # Configuration management
└── requirements.txt     # Python dependencies
```

**What the worker does:**
- Polls SQS queue using long polling (20 second wait time)
- Receives messages, parses job payload
- Routes to appropriate job handler based on `job_type`
- Processes job (calls Security Hub, stores in Postgres)
- Deletes message from queue on success
- On failure: retries up to max attempts, then sends to DLQ
- Logs all operations to CloudWatch

**Worker loop pattern:**
```python
while True:
    messages = sqs.receive_message(...)
    for message in messages:
        try:
            job = parse_message(message)
            handler = get_job_handler(job.job_type)
            handler.execute(job)
            sqs.delete_message(message)
        except Exception as e:
            log_error(e)
            # Message remains in queue, will retry
```

**Why this matters:** The worker is the core processing engine. It must be reliable, handle errors gracefully, and scale horizontally (multiple worker instances can process different messages).

**Deliverable:** `worker/main.py` with SQS consumer loop and job routing

**Key dependencies:**
- `boto3` - AWS SDK (SQS, Security Hub)
- `sqlalchemy` - Database access
- `psycopg2` or `asyncpg` - Postgres driver
- `tenacity` or similar - Retry logic

**Error handling:**
- Transient AWS errors (throttling) → retry with exponential backoff
- Permission errors → log, send to DLQ, notify via API (update account status)
- Database errors → retry, then DLQ
- Invalid messages → log, delete (don't retry)

#### 2.3 Implement Security Hub findings fetcher

**Purpose:** Fetch Security Hub findings from customer AWS accounts using the assumed role.

**Function signature:**
```python
def fetch_security_hub_findings(
    session: boto3.Session,
    region: str,
    account_id: str,
    max_results: int = 100,
    next_token: str = None
) -> dict:
    """
    Fetches Security Hub findings using the assumed role session.
    
    Args:
        session: boto3.Session with assumed role credentials
        region: AWS region to query
        account_id: AWS account ID (for logging)
        max_results: Maximum findings per page (max 100)
        next_token: Pagination token for subsequent pages
        
    Returns:
        dict with 'Findings' list and 'NextToken' if more pages exist
        
    Raises:
        ClientError: If Security Hub access fails
    """
```

**What it does:**
- Uses `securityhub.get_findings()` API with filters:
  - `RecordState: ACTIVE` (only active findings)
  - `WorkflowStatus: NEW, NOTIFIED` (exclude resolved)
  - Optionally filter by severity: `SeverityLabel: CRITICAL, HIGH, MEDIUM`
- Handles pagination (Security Hub returns max 100 findings per call)
- Implements pagination loop to fetch all findings
- Transforms raw Security Hub JSON into normalized structure
- Handles rate limiting (Security Hub has API limits)

**Pagination pattern:**
```python
all_findings = []
next_token = None
while True:
    response = securityhub.get_findings(
        Filters={...},
        MaxResults=100,
        NextToken=next_token
    )
    all_findings.extend(response['Findings'])
    next_token = response.get('NextToken')
    if not next_token:
        break
```

**Why this matters:** Security Hub findings are the core data source. This function must be reliable, handle large result sets, and respect API limits.

**Deliverable:** `worker/services/security_hub.py` with `fetch_security_hub_findings()` function

**Key considerations:**
- Rate limiting: Security Hub allows ~10 TPS per account
- Large accounts may have thousands of findings (pagination is critical)
- Findings are updated frequently (need incremental sync strategy later)
- Some findings may be duplicates across regions (deduplication happens in Step 4)

**Error handling:**
- Security Hub not enabled → clear error, update account status
- Access denied → permission error, send to DLQ
- Throttling → exponential backoff retry
- Invalid region → skip region, log warning

#### 2.4 Create findings database model

**Purpose:** Define the database schema for storing Security Hub findings with proper normalization, indexing, and multi-tenant isolation.

**What it does:**
- Creates a `findings` table that stores normalized Security Hub findings data
- Extracts key fields from Security Hub JSON for efficient querying
- Stores full raw JSON for flexibility and future schema changes
- Implements proper indexes for common query patterns
- Enforces multi-tenant isolation through `tenant_id` foreign key
- Supports deduplication through unique constraint on `finding_id` + `account_id` + `region`
- Tracks both Security Hub timestamps and our database timestamps

**Table: findings**

**Columns:**

**Primary key and tenant isolation:**
- `id` (UUID, primary key) - Unique identifier for each finding record
- `tenant_id` (UUID, foreign key to tenants, NOT NULL) - Multi-tenant isolation, all queries must filter by tenant_id

**AWS account and region:**
- `account_id` (string(12), NOT NULL) - AWS account ID where finding was discovered
- `region` (string(20), NOT NULL) - AWS region (e.g., "us-east-1", "eu-west-1")

**Finding identification:**
- `finding_id` (string(255), NOT NULL) - Security Hub finding ID (e.g., "arn:aws:securityhub:us-east-1:123456789012:subscription/aws-foundational-security-best-practices/v/1.0/S3.1/finding/abc123")
- Unique constraint on `(finding_id, account_id, region)` - Prevents duplicate findings per account+region

**Severity fields:**
- `severity_label` (enum: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL, NOT NULL) - Human-readable severity from Security Hub
- `severity_normalized` (integer, 0-100, NOT NULL) - Numeric severity for sorting and filtering (CRITICAL=100, HIGH=75, MEDIUM=50, LOW=25, INFORMATIONAL=0)

**Finding content:**
- `title` (string(500), NOT NULL) - Finding title from Security Hub
- `description` (text) - Full finding description (can be long)
- `resource_id` (string(500)) - AWS resource ARN or ID (e.g., "arn:aws:s3:::my-bucket")
- `resource_type` (string(100)) - Resource type (e.g., "AwsS3Bucket", "AwsEc2Instance", "AwsIamRole")

**Security standard and control:**
- `control_id` (string(50)) - Security Hub control ID (e.g., "S3.1", "EC2.2")
- `standard_name` (string(200)) - Security standard name (e.g., "AWS Foundational Security Best Practices", "CIS AWS Foundations Benchmark")

**Status tracking:**
- `status` (enum: NEW, NOTIFIED, RESOLVED, SUPPRESSED, NOT NULL) - Workflow status from Security Hub
- `first_observed_at` (timestamp with timezone) - When Security Hub first detected this finding
- `last_observed_at` (timestamp with timezone) - Most recent observation time from Security Hub
- `updated_at` (timestamp with timezone) - When Security Hub last updated this finding

**Raw data and audit:**
- `raw_json` (JSONB) - Complete Security Hub finding JSON stored as-is for reference and future schema changes
- `created_at` (timestamp with timezone, NOT NULL, default=now()) - When record was created in our database
- `updated_at` (timestamp with timezone, NOT NULL, default=now()) - When record was last updated in our database

**Indexes:**

**Composite index for tenant-scoped queries:**
- `idx_findings_tenant_account_region` on `(tenant_id, account_id, region)` - Enables fast queries like "show all findings for tenant X in account Y, region Z"

**Composite index for filtering and dashboards:**
- `idx_findings_tenant_severity_status` on `(tenant_id, severity_label, status)` - Enables fast queries like "show all HIGH severity NEW findings for tenant X"

**Unique constraint for deduplication:**
- `uq_findings_id_account_region` on `(finding_id, account_id, region)` - Ensures no duplicate findings per account+region combination

**Index for incremental sync:**
- `idx_findings_tenant_updated` on `(tenant_id, updated_at)` - Enables efficient queries for "findings updated since timestamp X" (for incremental ingestion)

**Additional indexes (optional, add if query patterns require):**
- `idx_findings_control_id` on `(tenant_id, control_id)` - If filtering by control ID is common
- `idx_findings_resource_id` on `(tenant_id, resource_id)` - If querying by resource is common

**SQLAlchemy model example:**

```python
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import enum

class SeverityLabel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"

class FindingStatus(str, enum.Enum):
    NEW = "NEW"
    NOTIFIED = "NOTIFIED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"

class Finding(Base):
    __tablename__ = "findings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    
    account_id = Column(String(12), nullable=False)
    region = Column(String(20), nullable=False)
    finding_id = Column(String(255), nullable=False)
    
    severity_label = Column(Enum(SeverityLabel), nullable=False)
    severity_normalized = Column(Integer, nullable=False)
    
    title = Column(String(500), nullable=False)
    description = Column(Text)
    resource_id = Column(String(500))
    resource_type = Column(String(100))
    
    control_id = Column(String(50))
    standard_name = Column(String(200))
    
    status = Column(Enum(FindingStatus), nullable=False)
    first_observed_at = Column(DateTime(timezone=True))
    last_observed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))  # Security Hub updated_at
    
    raw_json = Column(JSONB)
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at_db = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('finding_id', 'account_id', 'region', name='uq_findings_id_account_region'),
        Index('idx_findings_tenant_account_region', 'tenant_id', 'account_id', 'region'),
        Index('idx_findings_tenant_severity_status', 'tenant_id', 'severity_label', 'status'),
        Index('idx_findings_tenant_updated', 'tenant_id', 'updated_at'),
    )
```

**Why this matters:** This schema is the foundation for all finding-related features. Without proper normalization, indexes, and multi-tenant isolation, queries will be slow and data integrity will suffer. The raw JSON storage provides flexibility for future Security Hub schema changes, while normalized fields enable fast queries and filtering.

**Deliverable:** 
- SQLAlchemy model in `backend/models/finding.py`
- Alembic migration file in `backend/alembic/versions/`
- Migration script that creates table, indexes, and constraints

**Key design decisions:**

**Normalized vs. raw data:**
- Store both normalized fields (for fast queries) and raw JSON (for flexibility)
- Security Hub schema may evolve; raw JSON ensures we don't lose data
- Normalized fields enable efficient filtering without parsing JSON

**Severity normalization:**
- Convert Security Hub severity labels to integers (0-100) for consistent sorting
- Enables queries like "findings with severity > 50" without string comparisons
- Makes priority scoring easier in action engine (Step 4)

**Unique constraint strategy:**
- `finding_id` alone is not unique (same finding can exist in multiple regions)
- Composite unique constraint on `(finding_id, account_id, region)` prevents duplicates
- Supports upsert logic in ingestion job (Step 2.5)

**Timestamp tracking:**
- `first_observed_at` / `last_observed_at` / `updated_at` track Security Hub lifecycle
- `created_at` / `updated_at_db` track our database lifecycle
- Enables incremental sync: only fetch findings where `updated_at > last_sync_time`

**Multi-tenant isolation:**
- Every query must include `tenant_id` filter
- Indexes start with `tenant_id` for efficient tenant-scoped queries
- Prevents data leakage between tenants

**Migration considerations:**

**Alembic migration steps:**
1. Create `findings` table with all columns
2. Add foreign key constraint to `tenants` table
3. Create enum types for `SeverityLabel` and `FindingStatus`
4. Create unique constraint on `(finding_id, account_id, region)`
5. Create composite indexes (tenant_id + other columns)
6. Add check constraints if needed (e.g., `severity_normalized` between 0-100)

**Performance considerations:**
- Indexes are critical: large accounts may have 10,000+ findings
- Composite indexes support common query patterns (tenant + filter)
- Consider partial indexes if filtering by status is common (e.g., only index NEW findings)
- Monitor index usage; drop unused indexes to improve write performance

**Scaling considerations:**
- If table grows beyond 10M rows, consider partitioning by `tenant_id` or `account_id`
- JSONB column (`raw_json`) can be large; monitor storage usage
- Consider archiving old RESOLVED findings to separate table after 90 days
- Vacuum and analyze regularly to maintain index efficiency

**Error handling in model:**
- Validate `severity_normalized` matches `severity_label` (use SQLAlchemy validators)
- Ensure `account_id` is exactly 12 digits
- Validate `region` against AWS region list
- Handle NULL values gracefully (some Security Hub fields may be missing)

#### 2.5 Store findings in Postgres

**Purpose:** Implement the job handler that fetches Security Hub findings from customer AWS (via the fetcher from 2.3), normalizes them into the schema from 2.4, and persists them in Postgres with correct upsert semantics so repeated runs are idempotent and updates from Security Hub are reflected.

**What it does:**
- Receives an ingestion job payload from SQS (tenant_id, account_id, region, job_type)
- Loads the corresponding `aws_accounts` row to get `role_read_arn` and `external_id`
- Assumes the customer ReadRole via STS and obtains a boto3 session for that account/region
- Calls `fetch_security_hub_findings()` (from 2.3) to retrieve all active findings for that region (with pagination)
- For each finding: maps Security Hub JSON into the normalized fields and raw_json, then upserts into the `findings` table (insert new, update existing by finding_id + account_id + region)
- Runs inside a single database transaction per job (or per batch); commits on success, rolls back on unrecoverable errors
- Logs a summary (counts of processed, inserted, updated, skipped) and any per-finding errors for debugging
- Ensures the job is idempotent: re-running the same job does not create duplicates and updates existing rows with latest Security Hub data

**Why this matters:** This step completes the ingest pipeline. Reliable, idempotent storage with correct upserts is required so that Security Hub updates (e.g., status changes, new observations) are reflected in Postgres, and so that retries or duplicate SQS messages do not corrupt data.

**Deliverable:** `worker/jobs/ingest_findings.py` with `execute_ingest_job()` (or equivalent entrypoint called by the worker loop from 2.2)

**Job handler location and entrypoint:**
- File: `worker/jobs/ingest_findings.py`
- Entrypoint: a function such as `execute_ingest_job(job: dict) -> None` invoked by the worker when `job_type == "ingest_findings"`

**Function signature:**
```python
def execute_ingest_job(job: dict) -> None:
    """
    Processes an ingestion job: fetches Security Hub findings and stores in Postgres.

    Args:
        job: Job payload from SQS message, e.g.:
            {
                "tenant_id": "uuid",
                "account_id": "123456789012",
                "region": "us-east-1",
                "job_type": "ingest_findings",
                "created_at": "2026-01-29T10:00:00Z"
            }

    Raises:
        JobError: On unrecoverable failure (e.g. account not found, assume role failed);
                  worker should not delete the message so it can retry or go to DLQ.
    """
```

**Pipeline steps (detailed):**
1. **Validate and load account:** Query `aws_accounts` by `job["tenant_id"]` and `job["account_id"]`. If not found, raise; do not retry indefinitely.
2. **Assume role:** Call your STS assume-role helper with `role_read_arn` and `external_id` for that account. On failure, raise (permission or trust issue).
3. **Fetch findings:** Call `fetch_security_hub_findings(session, job["region"], job["account_id"])` and collect all pages into a list (or stream in batches if you process in chunks).
4. **Open DB transaction:** Start a transaction (or use a single session with commit at the end).
5. **Normalize and upsert each finding:** For each Security Hub finding dict, map to your model (see field mapping below). Upsert by `(finding_id, account_id, region)`: insert if no row exists, otherwise update the updatable columns.
6. **Commit:** Commit the transaction after all findings in this job (or batch) are processed.
7. **Log summary:** Log counts (e.g. processed, inserted, updated) and any non-fatal errors (e.g. skipped due to constraint).

**Field mapping (Security Hub JSON → findings table):**

| Security Hub field (path) | Column | Notes |
|---------------------------|--------|--------|
| `Id` | `finding_id` | Required; part of unique key |
| `Severity.Label` | `severity_label` | Map to enum (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL) |
| `Severity.Label` | `severity_normalized` | CRITICAL=100, HIGH=75, MEDIUM=50, LOW=25, INFORMATIONAL=0 |
| `Title` | `title` | Required |
| `Description` | `description` | Can be long text |
| `Resources[0].Id` | `resource_id` | Primary resource; may be ARN or ID |
| `Resources[0].Type` | `resource_type` | e.g. AwsS3Bucket, AwsEc2Instance |
| `ProductFields.ControlId` or equivalent | `control_id` | e.g. S3.1, EC2.2 |
| `ProductFields.StandardsControlArn` / standard name | `standard_name` | e.g. AWS Foundational Security Best Practices |
| `Workflow.Status` | `status` | NEW, NOTIFIED, RESOLVED, SUPPRESSED |
| `FirstObservedAt` | `first_observed_at` | Parse ISO8601; store with timezone |
| `LastObservedAt` | `last_observed_at` | Parse ISO8601; store with timezone |
| `UpdatedAt` | `updated_at` | Security Hub last update time |
| (entire finding dict) | `raw_json` | Store as JSONB |
| (from job) | `tenant_id`, `account_id`, `region` | From job payload; not from finding JSON |
| (generated) | `id`, `created_at`, `updated_at_db` | UUID and DB timestamps; set on insert, update `updated_at_db` on update |

**Upsert semantics:**
- **Unique key:** `(finding_id, account_id, region)` (must match the unique constraint on the findings table).
- **On insert:** Set all columns from the mapping above; generate `id` (UUID) and set `created_at` / `updated_at_db` to now.
- **On update:** Update `last_observed_at`, `updated_at` (Security Hub), `status`, `severity_label`, `severity_normalized`, `title`, `description`, `resource_id`, `resource_type`, `control_id`, `standard_name`, `raw_json`, and `updated_at_db`. Do not change `id`, `tenant_id`, `account_id`, `region`, `finding_id`, or `first_observed_at` (Security Hub lifecycle).

**Upsert options:**

**Option A – Query then insert/update (simple, good for moderate volume):**
```python
for finding_data in findings:
    existing = session.query(Finding).filter_by(
        finding_id=finding_data["Id"],
        account_id=account_id,
        region=region,
        tenant_id=tenant_id,
    ).first()

    if existing:
        existing.last_observed_at = parse_iso(finding_data.get("LastObservedAt"))
        existing.updated_at = parse_iso(finding_data.get("UpdatedAt"))
        existing.status = map_status(finding_data.get("Workflow", {}).get("Status"))
        existing.severity_label = map_severity_label(finding_data.get("Severity", {}).get("Label"))
        existing.severity_normalized = map_severity_normalized(existing.severity_label)
        existing.title = finding_data.get("Title") or existing.title
        existing.description = finding_data.get("Description") or existing.description
        existing.resource_id = extract_resource_id(finding_data)
        existing.resource_type = extract_resource_type(finding_data)
        existing.control_id = extract_control_id(finding_data)
        existing.standard_name = extract_standard_name(finding_data)
        existing.raw_json = finding_data
        existing.updated_at_db = func.now()
    else:
        new_finding = build_finding_from_security_hub(finding_data, tenant_id, account_id, region)
        session.add(new_finding)
```

**Option B – PostgreSQL `ON CONFLICT` (recommended for large batches):**
- Build a list of rows (or use a temporary table / `VALUES`); then run a single `INSERT ... ON CONFLICT (finding_id, account_id, region) DO UPDATE SET ...`.
- Update only the columns that change on conflict (e.g. `last_observed_at`, `updated_at`, `status`, normalized fields, `raw_json`, `updated_at_db`).
- Reduces round-trips and avoids race conditions when multiple workers process the same account/region.

**Transaction and batching:**
- Process findings in a single transaction per job so that either all findings for that job are persisted or none are (all-or-nothing for that run).
- If the list is very large (e.g. > 5000), process in chunks (e.g. 500–1000 per transaction), commit each chunk, and continue; log progress so that partial progress is visible and you can resume or retry from the next chunk if needed.
- On unrecoverable error (e.g. DB connection lost, constraint that should never happen), roll back the current transaction and re-raise so the worker can retry or send to DLQ.

**Key design decisions:**
- **Idempotency:** Same job run twice produces the same final state; duplicates are avoided by the unique key and upsert.
- **Tenant and account context:** Always set `tenant_id` and `account_id` from the job, never from the finding JSON, to preserve multi-tenant isolation.
- **Raw JSON:** Always store the full finding in `raw_json` so future schema or product changes can use it without re-ingesting.
- **Timestamps:** Keep Security Hub timestamps (`first_observed_at`, `last_observed_at`, `updated_at`) separate from DB timestamps (`created_at`, `updated_at_db`) for auditing and incremental sync.

**Error handling:**
- **Account not found:** Raise; do not retry (bad payload or stale message).
- **Assume role failure:** Raise; worker retries, then DLQ; consider marking account as invalid in API.
- **Security Hub fetch failure:** Already handled in 2.3; propagate retries; if ultimately failed, raise so message is not deleted.
- **Database connection error:** Retry with backoff; after N failures, raise and let message return to queue or go to DLQ.
- **Unique constraint violation:** If using Option A, possible under concurrent workers; catch integrity error, log, skip that finding or retry the single row; do not roll back the whole job if policy is “best effort per finding.”
- **Partial batch failure:** Optionally log failed finding IDs and continue; commit successful ones. Prefer all-or-nothing per transaction unless you explicitly design for partial commit.

**Performance considerations:**
- Batch size: 100–500 findings per transaction is a reasonable default; tune based on memory and DB load.
- Prefer `ON CONFLICT` upsert (Option B) for high volume to minimize round-trips and lock time.
- Use connection pooling in the worker; avoid opening a new connection per job if possible.
- If the same account/region is processed frequently, indexes on `(tenant_id, account_id, region)` and `(finding_id, account_id, region)` (from 2.4) keep upserts fast.

**Testing considerations:**
- Unit tests: mock STS and Security Hub; assert correct field mapping and that upsert updates existing rows and inserts new ones.
- Integration test: run job against a test account with a few findings; re-run and assert no duplicates and updated fields (e.g. status, last_observed_at) after changing mock data.
- Test idempotency: run the same job twice and compare row counts and checksums for key columns.

#### 2.6 Create API endpoint to trigger ingestion

**Purpose:** Provide an HTTP entry point for manually or programmatically triggering Security Hub ingestion jobs. The API validates tenant-scoped access, enqueues one SQS message per account-region pair, and returns a structured response. This enables "Refresh Findings" in the UI, scheduled ingestion via cron or EventBridge, and re-ingestion after account validation.

**Endpoint:** `POST /api/aws/accounts/{account_id}/ingest`

**Optional request body:**
```json
{
  "regions": ["us-east-1", "us-west-2"]
}
```
- If omitted: use the account's stored `regions` list from `aws_accounts`.
- If provided: restrict ingestion to the given regions (must be a subset of the account's configured regions). Useful for "ingest this region only" or retry of a single region.

**What the endpoint does:**
1. **Resolve tenant:** Get current tenant from auth context (JWT, API key, or session). Reject request if unauthenticated.
2. **Look up account:** Query `aws_accounts` by `account_id` and `tenant_id`. Return `404` if account not found or account belongs to another tenant.
3. **Optional validation check:** Optionally verify account `status` is `validated` before queuing. If `pending` or `error`, return `409` with a message that the user should validate the account first (or allow anyway and let the worker fail; document the chosen behavior).
4. **Determine regions:** Use request body `regions` if provided and valid; otherwise use `account.regions`. If empty, return `400` with message "No regions configured for this account."
5. **Enqueue jobs:** For each region:
   - Build job payload: `{ "tenant_id": "<uuid>", "account_id": "<12-digit>", "region": "<region>", "job_type": "ingest_findings", "created_at": "<ISO8601>" }`.
   - Send message to `security-autopilot-ingest-queue` (queue URL from config/environment).
   - Collect each `MessageId` returned by SQS (and optionally `MD5OfBody`) for the response.
6. **Respond:** Return `202 Accepted` with JSON body containing `account_id`, `jobs_queued`, `regions`, and optionally `message_ids` for debugging or idempotency tracking.

**Response (success, 202 Accepted):**
```json
{
  "account_id": "123456789012",
  "jobs_queued": 2,
  "regions": ["us-east-1", "us-west-2"],
  "message_ids": ["abc-123", "def-456"],
  "message": "Ingestion jobs queued successfully"
}
```

**Response (error, 404):**
```json
{
  "error": "Account not found",
  "detail": "No AWS account found with the given ID for this tenant."
}
```

**Response (error, 400):**
```json
{
  "error": "Bad request",
  "detail": "No regions configured for this account. Add regions in account settings."
}
```

**Response (error, 409 — if you enforce validated status):**
```json
{
  "error": "Account not validated",
  "detail": "Validate the AWS account connection before triggering ingestion."
}
```

**Response (error, 503 — queue unavailable):**
```json
{
  "error": "Ingestion service unavailable",
  "detail": "Could not enqueue ingestion jobs. Please try again later."
}
```

**Key components:**
- **Router:** Add `POST /api/aws/accounts/{account_id}/ingest` in `backend/routers/aws_accounts.py` (or a dedicated `ingest.py` router mounted under `/api/aws/accounts`).
- **SQS client:** Use boto3 SQS client (same AWS account as API). Queue URL from `config` (e.g. `INGEST_QUEUE_URL` env var).
- **Auth dependency:** Reuse existing auth middleware/dependency to resolve current user and `tenant_id`.
- **Account lookup:** Query `aws_accounts` filtered by `tenant_id` and `account_id`; ensure row-level tenant isolation.

**Error handling:**
- **Account not found or wrong tenant:** Return `404`; do not enqueue.
- **No regions configured:** Return `400` with clear message.
- **Account not validated (if enforced):** Return `409`; suggest user validates first.
- **SQS `SendMessage` failure (throttling, queue missing, access denied):** Log error, return `503` with generic message; do not partially enqueue (all-or-nothing per request). Optionally implement retry with backoff for transient SQS errors before failing.
- **Invalid `regions` in body:** If provided regions are not a subset of account regions, return `400` with validation detail.

**Why this matters:** This endpoint is the primary way to trigger ingestion on demand. It must enforce tenant isolation, avoid duplicate or partial enqueues on failure, and give clear feedback for invalid or misconfigured accounts. Later, EventBridge scheduled rules or internal cron can call this endpoint to automate periodic ingestion.

**Deliverable:** `backend/routers/aws_accounts.py` (or equivalent) with `POST /api/aws/accounts/{account_id}/ingest` implemented, plus config for `INGEST_QUEUE_URL`. Document optional request body and error responses in OpenAPI.

**Use cases:**
- **Manual "Refresh Findings" button in UI:** Frontend calls this endpoint after user clicks refresh for a specific account.
- **Scheduled ingestion:** Cron job or EventBridge rule invokes the endpoint (with auth) for each tenant/account to run daily or hourly ingestion.
- **Re-ingestion after validation:** After user fixes role trust or permissions and re-validates, support or UI triggers ingest for that account.
- **Single-region retry:** Pass `regions: ["us-east-1"]` to retry only one region without re-ingesting all others.

**Key design decisions:**
- **All-or-nothing enqueue:** Either all regional messages are sent or none; on first SQS failure, return `503` without enqueuing the rest. Prevents partially triggered ingestion and simplifies retry semantics.
- **Optional `regions` override:** Supports targeted refresh and single-region retry without changing stored account config.
- **202 Accepted:** Ingestion is asynchronous; returning `202` makes it explicit that work is queued, not completed.
- **Include `message_ids` in response:** Aids debugging, support, and optional idempotency (e.g. client stores last `message_ids` to detect duplicate triggers).
- **Tenant isolation:** Always derive `tenant_id` from auth and scope account lookup to that tenant; never trust `account_id` alone.

**Testing considerations:**
- Unit tests: Mock auth (tenant), DB (account lookup), and SQS; assert correct payload per region, correct `202` and JSON shape, and that no messages are sent when account missing or validation fails.
- Integration tests: Use real or test-local SQS; create account, call endpoint, assert messages appear in queue with correct `tenant_id`, `account_id`, `region`, `job_type`.
- Test error paths: missing account (`404`), empty regions (`400`), invalid regions (`400`), and mocked SQS failure (`503`).
- Test optional body: with and without `regions`; verify stored vs. override behavior.

**Implemented:** Unit tests in `tests/test_ingest_trigger.py` (pytest). Run: `PYTHONPATH=. pytest tests/test_ingest_trigger.py -v`. Covers 503 (queue not configured, SQS failure), 400 (invalid `tenant_id`, no regions, empty/invalid `regions` override), 404 (tenant/account not found), 409 (account not validated), 202 (success with and without `regions` override).

**Reuse from codebase:**
- **`get_tenant`** (`backend.routers.aws_accounts`): tenant lookup; used by register, validate, ingest.
- **`get_account_for_tenant`** (`backend.routers.aws_accounts`): account lookup by `tenant_id` + `account_id`; used by validate and ingest.
- **`backend.utils.sqs`**: `parse_queue_region` (API + worker), `INGEST_JOB_TYPE`, `build_ingest_job_payload` (API); worker uses `parse_queue_region` and `INGEST_JOB_TYPE` in handler registry.
- **Config:** `settings.SQS_INGEST_QUEUE_URL`, `settings.has_ingest_queue`, `settings.AWS_REGION`.
- **Worker contract:** Job payload shape from `build_ingest_job_payload` matches worker `REQUIRED_JOB_FIELDS` and `execute_ingest_job` expectations.

#### 2.7 Multi-region ingestion

**Purpose:** Document and ensure that ingestion supports multiple regions per account. The pipeline is already per-region (one SQS message per account–region); multi-region means the account can have multiple regions configured and ingest runs for all of them.

**What it does:**
- **Account regions:** `aws_accounts.regions` is a list (e.g. `["us-east-1", "us-west-2"]`). When the user configures multiple regions, the ingest trigger (POST /api/aws/accounts/{account_id}/ingest) sends one message per (account_id, region) for every region in the list.
- **Worker:** Each job payload includes a single `region`; the worker fetches Security Hub findings for that region only. No change to worker logic; multi-region is achieved by enqueuing one job per region.
- **ReadRole:** The customer's ReadRole must have Security Hub (and any other) read permissions in **all** regions they configure. Document in the ReadRole template or docs that Security Hub must be enabled in each region and that the role's resource policy (if any) or regional endpoints apply to all configured regions.
- **Definition:** Multi-region is supported when `regions` has more than one entry; no separate "multi-region mode" is required.

**Deliverable:** Document in implementation plan and/or ingest trigger code that multi-region is the default behavior when account has multiple regions; optionally add a test that ingest for an account with N regions enqueues N messages.

**Why this matters:** Growth/Scale tiers (5–20 accounts) typically span multiple regions; supporting multi-region from the ingestion design avoids rework later.

**Implementation (verified):**
- `_enqueue_ingest_jobs` docstring explicitly states multi-region (one message per region). `tests/test_ingest_trigger.py`: `test_ingest_202_success_no_body` asserts regions list passed to enqueue; `test_enqueue_ingest_jobs_sends_one_message_per_region` asserts N regions → N SQS send_message calls with correct payload per region.

#### Step 2 Definition of Done

✅ SQS queues created and configured with DLQ  
✅ Worker service polls queue and routes jobs correctly  
✅ Security Hub findings fetcher handles pagination and rate limiting  
✅ Findings database model created with proper indexes  
✅ Ingestion job stores findings in Postgres with upsert logic  
✅ API endpoint can trigger ingestion jobs (one message per account–region; multi-region supported — see 2.7)  
✅ Worker handles errors gracefully (retries, DLQ)  
✅ Multi-tenant isolation enforced (findings scoped to tenant_id)  
✅ Large accounts (1000+ findings) process successfully  
✅ Findings update correctly when Security Hub updates them

#### Step 2 — Security Hub enablement (deferred)

**Security Hub is not yet enabled** in the test/customer AWS account(s). Enable it **after** Step 2 is fully complete (all sub-steps done, API + worker running, ingest trigger verified).

- Until then: ingestion jobs may run but `findings` will remain empty, or the worker may log Security-Hub–not-enabled errors; this is expected.
- **When ready:** Enable Security Hub (and optionally standards) in each connected account, then trigger ingestion again to populate findings.

### Step 2B: IAM Access Analyzer and Inspector (Optional Data Sources)

This step adds optional ingestion from IAM Access Analyzer and Amazon Inspector alongside Security Hub. Security Hub remains the primary data source; these sources provide additional signals (external access findings, vulnerability findings) that can feed into the action engine or appear in the findings list.

#### 2B.1 IAM Access Analyzer ingestion

**Purpose:** Ingest IAM Access Analyzer findings (e.g. external access, unused access) so they appear in the findings list and can contribute to actions.

**What it does:**
- **Permissions:** ReadRole (or a dedicated permission set) needs `access-analyzer:ListAnalyzers`, `access-analyzer:ListFindings`, `access-analyzer:GetFinding`. Document in ReadRole template or a separate "Access Analyzer optional" policy.
- **Ingest job:** Job type `ingest_access_analyzer`. Worker assumes role, calls Access Analyzer API (list analyzers, list findings per analyzer), normalizes to finding shape, upserts with `source='access_analyzer'`.
- **Storage:** `findings` table extended with `source` column (default `security_hub`); unique constraint `(finding_id, account_id, region, source)`. All findings in one table; GET findings API supports filter `source=security_hub|access_analyzer`.
- **Action engine:** Access Analyzer findings appear in findings list; action engine can include them (compute_actions runs after ingest); mapping to specific action types can be added later (e.g. "review finding").

**Deliverable:** Worker job for Access Analyzer ingestion; DB schema (extended findings or new table); optional ReadRole policy snippet; document in plan how to enable per tenant (e.g. feature flag or account setting).

**Implementation (verified):**
- Migration `0010_findings_source_column`: added `findings.source` (default `security_hub`), unique constraint `uq_findings_finding_id_account_region_source`, index `ix_findings_tenant_source`. Model `Finding` updated with `source`; ingest_findings sets `source=security_hub`, ingest_access_analyzer sets `source=access_analyzer`.
- `worker/services/access_analyzer.py`: `list_analyzers`, `list_findings_page`, `fetch_all_access_analyzer_findings`, `normalize_aa_finding` (FindingSummary → our shape). `worker/jobs/ingest_access_analyzer.py`: `execute_ingest_access_analyzer_job` (assume role, fetch, upsert, optional compute_actions enqueue).
- SQS: `INGEST_ACCESS_ANALYZER_JOB_TYPE`, `build_ingest_access_analyzer_job_payload` in `backend/utils/sqs.py`; worker registry in `worker/jobs/__init__.py`. API: `POST /api/aws/accounts/{account_id}/ingest-access-analyzer` (same regions logic as ingest), `_enqueue_ingest_access_analyzer_jobs`. ReadRole template: added Access Analyzer statement (ListAnalyzers, ListFindings, GetFinding). GET findings: `FindingResponse.source`, optional query param `source=security_hub,access_analyzer`. Tests: `test_build_ingest_access_analyzer_job_payload` in `test_sqs_utils.py`.

#### 2B.2 Amazon Inspector ingestion (optional)

**Purpose:** Ingest Inspector vulnerability findings (e.g. CVE, package findings) so they appear in the findings list and can contribute to actions (e.g. "Update package X" or "Apply patch").

**What it does:**
- **Permissions:** ReadRole needs Inspector v2 read permissions: `inspector2:ListFindings`. (Inspector2 has no GetFinding; list_findings returns full finding objects.) Document in ReadRole template.
- **Ingest job:** Job type `ingest_inspector`. Worker assumes role, calls Inspector v2 API per region (list_findings with filterCriteria.awsAccountId), normalizes (findingArn→finding_id, severity, type, description, resources, firstObservedAt/lastObservedAt, status ACTIVE→NEW/CLOSED→RESOLVED).
- **Storage:** Same pattern as 2B.1—`findings.source = 'inspector'`; unique (finding_id, account_id, region, source). Severity UNTRIAGED supported in Finding model (maps to 25).
- **Action engine:** Inspector findings appear in findings list; compute_actions runs after ingest; mapping to patch/update action types can be added later.

**Deliverable:** Worker job for Inspector ingestion; DB schema; optional ReadRole policy; document how to enable per tenant.

**Implementation (verified):**
- `worker/services/inspector.py`: `list_findings_page` (filterCriteria.awsAccountId, pagination), `fetch_all_inspector_findings`, `normalize_inspector_finding` (findingArn→finding_id, severity CRITICAL/HIGH/MEDIUM/LOW/INFORMATIONAL/UNTRIAGED, type→title, resources[0]→resource_id/type, status ACTIVE→NEW/CLOSED→RESOLVED). Retries and rate limiting. `backend/models/finding.py`: added UNTRIAGED to _severity_normalized (25).
- `worker/jobs/ingest_inspector.py`: `execute_ingest_inspector_job` (assume role, fetch, upsert source=inspector, optional compute_actions enqueue). SQS: `INGEST_INSPECTOR_JOB_TYPE`, `build_ingest_inspector_job_payload`; worker registry; API: `POST /api/aws/accounts/{account_id}/ingest-inspector`, `_enqueue_ingest_inspector_jobs`. ReadRole template: `inspector2:ListFindings`. GET findings: source filter already supports `inspector`. Tests: `tests/test_inspector.py` (normalize_inspector_finding package/untriaged/closed/long_arn), `test_build_ingest_inspector_job_payload` in test_sqs_utils.

#### 2B.3 Action engine and UI

**Purpose:** Ensure Access Analyzer and Inspector findings feed into the action engine and appear in the UI without breaking Security Hub–centric flows.

**What it does:**
- Action engine considers `source` (or joined tables) when grouping/deduping; Security Hub remains primary; optional filters in UI for "Source: Security Hub | Access Analyzer | Inspector".
- Findings list and Top Risks can show all sources; optionally allow "Security Hub only" for customers who have not enabled optional sources.

**Deliverable:** Action engine and GET findings API support source filter; UI (optional) shows source badge or filter.

#### 2B.4 Frontend (optional): Source filter and badge

**Purpose:** Let users filter findings (and optionally actions) by source (Security Hub, Access Analyzer, Inspector) and see which source each finding came from.

**What it does:**
- **Findings list** (/findings): optional filter control (dropdown or tabs) "Source: All | Security Hub | Access Analyzer | Inspector"; pass `source` query param to GET /api/findings. Optional: show a small source badge (e.g. "SH", "AA", "Insp") or label on each finding card/row.
- **Findings detail** (/findings/[id]): optional source badge or field if the API returns source.
- **Actions list/detail:** Optional source display if actions are tagged or derived from findings with source; only if backend exposes it.

**Deliverable:** Optional source filter on findings list; optional source badge on finding cards/detail. Improves clarity when multiple finding sources are enabled (2B.1, 2B.2).

**Status:** Backend (2B.1 source column, findings API source filter) done.

**Implementation (verified):** frontend/src/lib/api.ts: Finding.source, FindingsFilters.source, getFindings passes source param. frontend/src/lib/source.ts: getSourceLabel, getSourceShortLabel, SOURCE_FILTER_VALUES. frontend/src/app/findings/SourceTabs.tsx: Source filter tabs (All sources, Security Hub, Access Analyzer, Inspector). Findings page: SourceTabs, source state, active filter badge, clear all. FindingCard: source badge (short label + tooltip). Finding detail page: source badge in hero, Source field in Compliance card. Top Risks page: SourceTabs filter, source badge on each card.

**Trigger ingest per source (Accounts page):** frontend/src/lib/api.ts: triggerIngestAccessAnalyzer, triggerIngestInspector. frontend/src/app/accounts/AccountIngestActions.tsx: source dropdown (Security Hub | Access Analyzer | Inspector), "Refresh findings" (selected source), "Refresh all sources" (all three in parallel). AccountCard and AccountRowActions use AccountIngestActions (compact for table row). Accounts page header copy mentions all three sources.

#### Step 2B Definition of Done

✅ Optional IAM Access Analyzer ingestion: job, permissions, storage, and (optional) action mapping documented or implemented  
✅ Optional Amazon Inspector ingestion: job, permissions, storage, and (optional) action mapping documented or implemented  
✅ Findings list and action engine can include optional sources; tenant can enable/disable per account or globally  
✅ ReadRole (or optional policy) document includes Access Analyzer and Inspector permissions when optional sources are enabled

### Step 3: UI Pages (Accounts → Findings → Top Risks)

This step delivers the Phase 1 frontend: a Next.js app with an app shell, navigation, and three main flows—AWS account onboarding, findings list with filters, and a Top Risks dashboard. Each page is implemented in its own sub-step so you can build and test incrementally.

**Prerequisites:** Backend must expose: `GET/POST /api/aws/accounts`, `POST /api/aws/accounts/{account_id}/validate`, `POST /api/aws/accounts/{account_id}/ingest` (Steps 1–2). The Findings and Top Risks pages require a **GET findings API** (list with filters and pagination); add this endpoint in 3.1 or before 3.4 if not yet present.

---

#### 3.0 Design system (locked base theme – dark-first)

**Full palette and rules:** See **docs/design-system.md** (black `#000000`, primary blue `#0A71FF`, white text, muted `#B3B3B3`; button system; what not to do).

**Purpose:** Define a single color system, Tailwind design tokens, and component rules so every dashboard page looks and behaves consistently (“premium” feel without visual noise).

**Color system (use everywhere):**

| Role | Hex | Name |
|------|-----|------|
| App background | `#070B10` | Abyss Black |
| Surfaces / cards | `#101720` | Deep Graphite |
| Borders / dividers | `#1F2A35` | Steel Shadow |
| Primary text | `#C7D0D8` | Ion Silver |
| Secondary text | `#8F9BA6` | Muted Slate |
| Primary accent | `#5B87AD` | Cryo Blue |
| Accent hover / focus | `#7FA6C6` | Soft Glow Blue |

**Rules for “premium”:**
- Use Cryo Blue sparingly: only for primary actions, focus rings, selected states, and key risk indicators.
- Keep gradients subtle: mostly radial glow and border sheen, not loud multi-color gradients.

**CSS variables (in global CSS, e.g. `app/globals.css`):**
```css
:root {
  --bg: #070B10;
  --surface: #101720;
  --border: #1F2A35;

  --text: #C7D0D8;
  --text-muted: #8F9BA6;

  --accent: #5B87AD;
  --accent-hover: #7FA6C6;

  /* states */
  --focus-ring: #7FA6C6;
  --danger: #8F9BA6; /* intentionally restrained (avoid neon red) */
}
```

**Tailwind config mapping (`tailwind.config.js`):**
```js
// theme.extend
colors: {
  bg: "var(--bg)",
  surface: "var(--surface)",
  border: "var(--border)",
  text: "var(--text)",
  muted: "var(--text-muted)",
  accent: "var(--accent)",
  "accent-hover": "var(--accent-hover)",
  ring: "var(--focus-ring)",
  danger: "var(--danger)",
},
boxShadow: {
  premium: "0 12px 40px rgba(0,0,0,0.45)", /* subtle premium lift; use sparingly */
},
borderRadius: {
  xl2: "1rem",
},
```

**Component state rules (consistent across all pages):**
- **Primary button (Stateful Button):** `bg-accent` `text-bg` `hover:bg-accent-hover` `focus:ring-2` `focus:ring-ring`
- **Card:** `bg-surface` `border` `border-border` `shadow-premium` (optional)
- **Hover Border Gradient wrapper:** gradient anchored to accent only (no rainbow)
- **Inputs:** `bg-bg` `border-border` `text-text` `placeholder:text-muted` `focus:ring-ring`

**UI library:** Use **Aceternity UI** (aceternity.com) as the primary component source; sub-steps below reference specific Aceternity components by name.

**Deliverables:** Global CSS with variables; `tailwind.config.js` with the token mapping above; documented in this plan for 3.1–3.6 implementation.

---

#### 3.1 Set up Next.js project and GET findings API

**Purpose:** Create the frontend app skeleton and the backend endpoint for listing findings so the UI can display data from Postgres.

**What to do:**

**A) Next.js project**
- Create a new Next.js app (App Router recommended) in a `frontend/` directory at repo root.
- Install dependencies: React, Next.js, Tailwind CSS, a data-fetching/client library (e.g. `fetch` or `axios`), and **Aceternity UI** (or equivalent component set) for modals, buttons, tooltips, loaders, etc.
- Configure environment: `NEXT_PUBLIC_API_URL` pointing at the FastAPI backend (e.g. `http://localhost:8000` for local dev).
- Apply the **design system (3.0):** add CSS variables to global CSS; extend `tailwind.config.js` with `colors`, `boxShadow.premium`, and `borderRadius.xl2` as specified in 3.0.
- Add a minimal API client helper that sends requests to `NEXT_PUBLIC_API_URL`, attaches auth (e.g. Bearer token or API key) when available, and handles non-2xx responses.

**B) GET findings API (backend)**
- **Endpoint:** `GET /api/findings` (or `GET /api/tenants/current/findings` if you prefer tenant in path).
- **Query parameters:** `account_id` (optional), `region` (optional), `severity` (optional, e.g. CRITICAL, HIGH), `status` (optional, e.g. NEW, RESOLVED), `limit` (default 50, max 200), `offset` (for pagination). For **Top Risks time filter** (Step 3.6): add optional `first_observed_since` and/or `last_observed_since` (ISO8601) or `updated_since` so "This week / 30 days / All time" can filter by finding timestamps; if not implemented in MVP, the Top Risks UI should omit time tabs and label as "Critical & high (open)" until backend supports it.
- **Response:** JSON with `items` (array of finding objects with `id`, `finding_id`, `account_id`, `region`, `severity_label`, `status`, `title`, `control_id`, `resource_id`, `updated_at`, etc.) and `total` (total count for the current filters).
- **Auth:** Resolve tenant from auth context; filter all queries by `tenant_id`. Return 401 if unauthenticated, 403 if tenant missing.

**Why this matters:** The app shell and all pages depend on a single frontend app and a consistent API base. The findings list endpoint is required for the Findings page and for Top Risks (which can use the same API with severity/sort).

**Deliverables:**
- `frontend/` with Next.js app, env config, and API client helper.
- `backend/routers/findings.py` (or equivalent) with `GET /api/findings` implemented and mounted in `main.py`.
- OpenAPI docs updated for the new endpoint.

**Key components (frontend):**
- `frontend/.env.local` with `NEXT_PUBLIC_API_URL`.
- `frontend/app/globals.css` (or equivalent) with design tokens from 3.0 (`:root` variables).
- `frontend/tailwind.config.js` with design token mapping from 3.0.
- `frontend/lib/api.ts` (or `api.js`) with `getFindings(params)`, `getAccounts()`, etc., and shared `request(url, options)`.
- Next.js config if you need rewrites/proxy to the backend in dev.

**Key components (backend):**
- Router that parses query params, resolves tenant from auth, runs filtered query on `findings` table, returns `{ items, total }`.
- Pagination via `limit`/`offset`; indexes on `(tenant_id, account_id, region, severity_label, status)` for performance.

**Error handling:**
- Frontend: network errors and 4xx/5xx mapped to user-friendly messages; 401 redirect to login or show “Session expired.”
- Backend: invalid query params → 400; unauthenticated → 401; no tenant → 403.

**Testing considerations:**
- Unit test backend endpoint with mocked auth and DB (different filters and pagination).
- Manually verify frontend dev server starts and API client can call backend (with or without auth).

---

#### 3.2 App shell and layout (navigation, auth wrapper)

**Purpose:** Provide a consistent layout and navigation so users can move between Accounts, Findings, and Top Risks without rebuilding the chrome on every page. Use the design system (3.0) and Aceternity UI for a premium, consistent shell.

**Global layout:**
- **Sidebar:** Use Aceternity **Sidebar** (expandable). Sidebar bg: `#000000`; surface: `#0B0B0B`; active nav: accent `#0A71FF`, text `#FFFFFF`; inactive: `#B3B3B3`, hover `#FFFFFF`. See **docs/design-system.md** for full palette. **Identity display:** When authenticated, show actual **tenant name** and **current user** (e.g. email or name) from `GET /api/auth/me` (Step 4.2); replace any hardcoded "Tenant" / "tenant@example.com". When not authenticated (dev flow), show placeholder or "Not signed in."
- **Top bar (inside app):** Background `#000000`. **Global search:** Either hook the search input to a findings search API (e.g. by title or finding ID) in MVP, or remove the TopBar search control until the backend supports search; do not leave a non-functional search box.
- **Navigation:** Sidebar left rail: **Accounts**, **Findings**, **Top Risks**, **Settings** (Settings can be placeholder for Phase 1).
- **Top app bar:** Aceternity **Floating Navbar** (compact, hides on scroll). Placement: top of viewport. Contains: Workspace switch, global search (see above), profile. **Profile:** When authenticated, show user avatar/initials and email or name from auth context. Colors: bg `#000000`; text `#FFFFFF`; hover/focus `#0A71FF`; active accents `#0A71FF`.

**Routes:**
- `/` redirects to a default page (e.g. `/accounts` or `/findings`).
- `/accounts` → Accounts page (Step 3.3).
- `/findings` → Findings list (Step 3.4).
- `/findings/[id]` → Finding detail (Step 3.5).
- `/top-risks` → Top Risks dashboard (Step 3.6).

**Micro-interactions (standardize across dashboard):**
- **Animated Tooltip** on icon-only actions (e.g. validate, ingest, copy ARN).
- **Animated Modal** for confirmations and progress overlays (e.g. validation/ingest).
- **Stateful Button** for actions that transition: idle → loading → success.
- **Multi Step Loader** for longer operations (ingest, validate).

**Auth:** If auth is in scope for Phase 1, wrap protected routes in an auth wrapper; if missing session/token, redirect to login or “Sign in”. If deferred, build shell and routes; add wrapper later.

**Why this matters:** A single shell avoids duplicated nav and layout logic and gives a clear mental model (Accounts → Findings → Top Risks). Consistent micro-interactions make the app feel polished.

**Deliverables:**
- Root layout and app shell with Aceternity Sidebar + Floating Navbar (or equivalent) using 3.0 colors.
- Route structure as above; optional auth wrapper and placeholder login.
- Shared use of Animated Tooltip, Animated Modal, Stateful Button, Multi Step Loader where specified in 3.3–3.6.

**Key components:**
- Layout: `AppShell` with Sidebar (left) + top bar + `<main>{children}</main>`.
- Nav links: `/accounts`, `/findings`, `/top-risks`, `/settings` (or omit Settings until needed).
- Optional: `AuthProvider` / `useAuth` and a wrapper that redirects when unauthenticated.

---

#### 3.3 Accounts page

**Purpose:** Let users see connected AWS accounts, add a new account (connect flow), re-validate an account, and trigger ingestion (“Refresh findings”) for an account.

**Route:** `/accounts`

**What to do:** Implement list, connect modal, validate, and ingest as below. Reuse API client from 3.1 for `getAccounts()`, `registerAccount()`, `validateAccount()`, `triggerIngest()`.

**A) Connect AWS account (POST /api/aws/accounts)**
- **Primary components:** **Animated Modal** for “Connect AWS account”; **Signup Form** (Aceternity) as base layout for labels + inputs; **Placeholders And Vanish Input** for the most sensitive/high-friction field (Role ARN or External ID); **Stateful Button** for “Connect” (idle → connecting → connected).
- **Placement:** Top-right primary CTA “Connect AWS account” opens modal. Modal body: form fields + short “what we’ll validate” note.
- **Color mapping:** Modal surface `#0B0B0B`, border `#1A1A1A`; inputs bg `#000000`, text `#FFFFFF`, placeholder `#B3B3B3`, focus ring `#0A71FF`; primary action bg `#0A71FF`, hover `#085ACC`, text `#FFFFFF`. See **docs/design-system.md**.

**B) Accounts list (GET /api/aws/accounts)**
- **Primary components:** **Hover Border Gradient** (Aceternity) wrapped around each account row/card for premium hover; **Animated Tooltip** on compact row actions (Validate, Refresh findings).
- **Placement:** Main content = list of account cards (avoid dense tables). Each card: name, account id, last validated, last ingest, status pill, actions.

**C) Re-validate per account (POST /api/aws/accounts/{account_id}/validate)**
- **Primary components:** Row action **Stateful Button** “Validate” (or icon + tooltip). On click: **Animated Modal** with **Multi Step Loader** steps: “Assuming role (STS)” → “Verifying permissions” → “Checking required services” → “Account marked valid”.
- **Placement:** Inside each account card, right-aligned actions.

**D) Trigger ingestion (POST /api/aws/accounts/{account_id}/ingest)**
- **Primary components:** Row action **Stateful Button** “Refresh findings”. Progress: **Multi Step Loader** in **Animated Modal** (or slide-over).
- **Placement:** Next to Validate action in each account card.

**Why this matters:** This is the main onboarding and maintenance surface for AWS accounts; clear actions and error messages reduce support burden.

**Deliverables:**
- `app/accounts/page.tsx` implementing list (cards), connect modal, validate, ingest with the Aceternity components above.
- API client methods: `getAccounts()`, `registerAccount()`, `validateAccount()`, `triggerIngest()`.

**Error handling:**
- Display API error messages (e.g. “Failed to assume role”, “Account not found”) inline or in a toast/alert.
- If `GET /api/aws/accounts` fails (e.g. 401), show a generic error and optionally prompt to sign in.

**UX notes:**
- Optional: short copy or link next to “Connect AWS account” explaining CloudFormation and ExternalId (reference Step 1.1).

---

#### 3.4 Findings list page

**Purpose:** Show a paginated, filterable list of Security Hub findings so users can see what’s in scope, narrow by account/region/severity/status, and open a single finding for detail.

**Route:** `/findings`

**What to do:** Call `GET /api/findings` with query params from filters and pagination; display as cards (not a raw table). Provide filters, pagination, and links to `/findings/[id]`. Use design system (3.0) and Aceternity components below.

**A) Filter + severity switching**
- **Primary components:** **Animated Tabs** (Aceternity) for severity: All / Critical / High / Medium / Low. Optional: **Placeholders And Vanish Input** for “Search findings…” (high-end, lightweight).
- **Placement:** Top of page: tabs row (left), search (right), advanced filters below as chips (account, region, status).

**B) Findings results list (cards, not raw table)**
- **Primary components:** Each finding as a card wrapped with **Hover Border Gradient** (Aceternity). For the top 3 most severe in the current filter, apply **Card Spotlight** (subtle) to differentiate “premium prioritization.” **Animated Tooltip** for quick actions: “Copy resource”, “Open detail”.
- **Placement:** Main column: stack of cards. Each card: title, resource, account, region, severity indicator, updated_at. Row click or “View” → `/findings/[id]` (use finding internal `id`). Optional “Refresh” button.

**C) Empty / loading states**
- **Primary components:** Loading: **Loader** or **Loaders set** (Aceternity); keep minimal. Empty: plain card (no gimmicks); keep it calm (“No findings match your filters” or “No findings yet”).

**Why this matters:** This is the primary view for “what’s wrong” in the customer’s accounts; filters and pagination keep it usable with hundreds or thousands of findings.

**Deliverables:**
- `app/findings/page.tsx` with cards, Animated Tabs, filters, pagination, links to detail.
- API client method that builds `GET /api/findings?...` from current filter and pagination state.

**Error handling:**
- On fetch failure, show “Failed to load findings” and retry or “Refresh” action.
- Empty state: when `items.length === 0`, show “No findings match your filters” (or “No findings yet” if no filters).

---

#### 3.5 Finding detail page

**Purpose:** Show a single finding’s full metadata and, for power users or support, the raw Security Hub JSON. Use design system (3.0) and Aceternity components; keep motion subtle so the page feels “expensive” but not noisy.

**Route:** `/findings/[id]`

**What to do:** Call `GET /api/findings/{id}` (backend tenant-scoped, 404 if not found). Display key fields and optional raw JSON. Link back to `/findings` (optionally preserve query for filters).

**A) Header / summary**
- **Primary components:** Summary card with **Card Spotlight** (very low intensity) for the “Hero risk summary” section only. **Animated Tooltip** on copy icons (Finding ID, Resource ARN).
- **Placement:** Top: Title + chips (account/region/service) + severity. Right side: primary action “Mark as triaged” (if available later) as **Stateful Button**.

**B) Body sections (clean, readable)**
- **Primary components:** Use Aceternity **Cards** patterns for: Evidence, Impact, Recommendation, References. For long evidence/code: **Code Block** component.
- **Placement:** Stacked section cards; keep line length short. Optionally collapsible “Raw JSON” with `<pre>` or syntax-highlighted JSON.

**C) Inline motion**
- Add micro motion only on: expanding evidence, copying, tab switching. Avoid constant animated backgrounds on detail pages.

**Why this matters:** Users and support need full context and evidence; raw JSON helps with integration and debugging.

**Deliverables:**
- `app/findings/[id]/page.tsx` with header, section cards, Code Block, back link.
- Backend: `GET /api/findings/{id}` returning a single finding (tenant-scoped).

**Error handling:**
- 404: “Finding not found” and link back to list.

---

#### 3.6 Top Risks dashboard page

**Purpose:** Surfaces the highest-severity or highest-priority findings so users can focus on what to fix first. Use the same findings API with filters; present as a Bento-style overview with drill-down. Use design system (3.0) and Aceternity components.

**Route:** `/top-risks`

**What to do:** Use `GET /api/findings` with params that emphasize risk (e.g. `severity=CRITICAL,HIGH`, `status=NEW,NOTIFIED`, limit 20–50), or a dedicated `GET /api/findings/top-risks` if implemented. Each item links to `/findings/[id]`. **"Refresh findings" behavior:** Choose one: (A) Trigger ingest from this page — e.g. call POST ingest for all validated accounts (or a single "Refresh all" button that queues jobs for each account), or (B) Link to `/accounts` with copy "Go to Accounts to refresh findings" so the user triggers ingest per account there. Document the chosen behavior in the UI.

**A) Top risks overview (high-level)**
- **Primary components:** **Bento Grid** (Aceternity) for the “Top Risks” tiles. Apply **Card Spotlight** only to the #1 risk tile. **Animated Tabs** above the grid for “This week / 30 days / All time” (or “By account / By service”). **Time filter requirement:** These tabs must drive the API call: use optional `first_observed_since` / `last_observed_since` or `updated_since` on `GET /api/findings` (see Step 3.1). If the backend does not yet support time-range filtering, remove the time tabs and label the view as "Critical & high (open)" until supported.
- **Placement:** Above the fold: Bento grid of top 6 risks. Below: a Findings list filtered to match the selected top risk (or same data in list form).

**B) Drill-down interactions**
- Clicking a Bento tile routes to Findings list with filters applied (no modal). Keep the experience fast: route + preserve tab state.

**Why this matters:** Phase 1 definition of done includes “basic scoring and Top risks view”; this page fulfills that and gives a quick landing view for security posture.

**Deliverables:**
- `app/top-risks/page.tsx` with Bento Grid, Card Spotlight on #1, Animated Tabs, and links to `/findings/[id]` (or filtered Findings list).
- Same API client as Findings list; optional `getTopRisks()` with fixed or configurable params.

**Error handling:**
- Same as Findings list (failure message, empty state when no high-severity findings).

---

#### Step 3 Definition of Done

✅ Design system (3.0) applied: CSS variables, Tailwind tokens, component state rules; Aceternity UI as component source  
✅ Next.js app runs locally and talks to FastAPI via `NEXT_PUBLIC_API_URL`  
✅ GET findings API implemented and documented (list + optional get-by-id)  
✅ App shell: Sidebar + Floating Navbar, nav Accounts / Findings / Top Risks / Settings; micro-interactions (Tooltip, Modal, Stateful Button, Multi Step Loader)  
✅ Accounts page: list (cards + Hover Border Gradient), connect modal (Placeholders And Vanish Input, Stateful Button), validate + ingest with Multi Step Loader  
✅ Findings list page: Animated Tabs (severity), cards with Card Spotlight on top 3 severe, filters, pagination, link to detail  
✅ Finding detail page: Card Spotlight hero summary, section cards, Code Block, raw JSON; minimal motion  
✅ Top Risks page: Bento Grid, Card Spotlight on #1, Animated Tabs, drill-down to Findings with filters  
✅ All pages use Cold Intelligence Dark Mode colors and respect auth (or placeholder); clear errors when API fails

### Step 4: Auth, Sign Up, Login, Onboarding, and User Management

Add authentication (sign up, login with JWT), a short onboarding tutorial, and user management (invite by email). Use **optional auth** so existing API callers and frontend keep working: keep `tenant_id` in query/body; when a Bearer token is present, resolve tenant from JWT and ignore request `tenant_id`; when no token, use `tenant_id` from the request. No breaking changes to existing endpoints or tests.

---

#### 4.1 User model and invites table (migration)

**Purpose:** Support passwords, roles, and onboarding state on User; support invite-by-email with a token.

**What to do:**
- Add to **User**: `password_hash` (nullable), `role` (enum: admin, member; default member), `onboarding_completed_at` (timestamp, nullable).
- New table **user_invites**: `id`, `tenant_id`, `email`, `token` (UUID), `expires_at`, `created_by_user_id`, `created_at`. Unique on `(tenant_id, email)` for pending invite.

**Deliverable:** Alembic migration. Existing User rows get nullable/default values.

---

#### 4.2 Auth module and endpoints

**Purpose:** Let users sign up (create tenant + first user), log in, and get current user from JWT.

**What to do:**
- Add [backend/auth.py](backend/auth.py): password hashing (passlib/bcrypt), JWT encode/decode (secret from config). Dependencies: **`get_optional_user`** (returns user or None; no 401 if no token), **`get_current_user`** (returns user or 401) for auth-only routes.
- **POST /api/auth/signup:** body `company_name`, `email`, `name`, `password`. Create tenant + user (role=admin), return JWT + user/tenant.
- **POST /api/auth/login:** body `email`, `password`. Verify password, return JWT + user/tenant.
- **GET /api/auth/me:** require auth; return current user + tenant from JWT. **Response shape (explicit):** `user`: `{ id, email, name, role, onboarding_completed_at }`; `tenant`: `{ id, name, external_id }` so the frontend can show tenant name in Sidebar/TopBar and External ID in onboarding/Settings without a separate tenant endpoint.

**Deliverable:** Auth router mounted under `/api`; config: `JWT_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES`.

---

#### 4.3 Optional auth on existing routers

**Purpose:** Resolve tenant from JWT when token present, else from request; keep API contract unchanged.

**What to do:**
- In [backend/routers/aws_accounts.py](backend/routers/aws_accounts.py) and [backend/routers/findings.py](backend/routers/findings.py): use `get_optional_user`. If user returned → use `user.tenant_id` only (ignore request `tenant_id`). If None → require and use `tenant_id` from query/body. Do not remove `tenant_id` from request schemas.

**Deliverable:** Same endpoints; existing callers and tests unchanged.

---

#### 4.4 Users and invite API + email

**Purpose:** List users in tenant, invite by email (link to set password), accept invite.

**What to do:**
- **GET /api/users:** require auth; return users for current user’s tenant (id, email, name, role, created_at).
- **POST /api/users/invite:** body `email`; require auth + role=admin. Create invite row (token, expiry e.g. 7 days), send email with link `{FRONTEND_URL}/accept-invite?token={token}`. Use [backend/services/email.py](backend/services/email.py) (SES or SMTP); config: `FRONTEND_URL`, `EMAIL_FROM`.
- **GET /api/users/accept-invite?token=:** validate token; return `email`, `tenant_name`, `inviter_name` for UI.
- **POST /api/users/accept-invite:** body `token`, `password`. Validate token; create/update user (set password_hash, role=member), delete invite; return JWT so frontend can log user in.
- **PATCH /api/users/me:** body `onboarding_completed: true`; require auth; set `user.onboarding_completed_at = now()`.
- **User/access revocation:** **DELETE /api/users/{id}** (or **PATCH /api/users/{id}** with `disabled: true`): require auth + role=admin; scope to current tenant. Optionally expire invite tokens on use and support token invalidation (e.g. short-lived tokens or blocklist on logout). Document revocation behavior so admins can remove or disable users.

**Deliverable:** Users router; email service and invite template.

---

#### 4.5 Frontend: auth context, login, signup, accept-invite

**Purpose:** Users can sign up, log in, and accept invites; API client sends token when logged in.

**What to do:**
- Auth context (e.g. [frontend/src/contexts/AuthContext.tsx](frontend/src/contexts/AuthContext.tsx)): store token (e.g. localStorage), user, tenant; expose login, logout, and token for API client. On load, validate token (e.g. GET /api/auth/me).
- API client: when token exists, send `Authorization: Bearer <token>` and omit `tenant_id`; when no token, send `tenant_id` as today. Keep `tenantId` optional in function signatures so existing pages keep working.
- **Route /login:** form email, password → POST /api/auth/login → store token, redirect to onboarding or dashboard.
- **Route /signup:** form company name, name, email, password → POST /api/auth/signup → store token, redirect to onboarding.
- **Route /accept-invite:** query `?token=`. GET accept-invite for display; form password → POST accept-invite → store JWT, redirect to dashboard.
- Root `/`: if authenticated redirect to dashboard (or onboarding if not completed); if not, redirect to login or allow dev flow with tenant_id.

**Deliverable:** AuthContext; login, signup, accept-invite pages; API client updated to send token when present.

---

#### 4.6 Onboarding tutorial (multi-step)

**Purpose:** Short tutorial after signup: show External ID, connect first AWS account, trigger ingest, mark done.

**What to do:**
- **Route /onboarding:** steps: (1) Welcome, (2) Show tenant External ID + link to CloudFormation, (3) Connect AWS account (reuse ConnectAccountModal), (4) Trigger ingestion for that account, (5) Done — button calls PATCH /api/users/me with `onboarding_completed: true`, then redirect to `/accounts` or `/findings`.
- Show onboarding when user is logged in and `onboarding_completed_at` is null.
- **Invited users:** When a user accepts an invite (tenant already exists), choose one: (A) Show the same onboarding wizard if the tenant has no connected AWS accounts (so they can connect the first account), or (B) Skip to dashboard and show a short "Get started" prompt (e.g. "Connect your first AWS account") if no accounts exist. If the tenant already has accounts, skip onboarding and go to dashboard.

**Deliverable:** [frontend/src/app/onboarding/page.tsx](frontend/src/app/onboarding/page.tsx) with step indicator and existing design system; reuse connect + ingest from Accounts.

---

#### 4.7 User management UI (Settings > Team) and Settings > Account/Organization

**Purpose:** Admins can list tenant users and invite by email; all users can see tenant/org info and (later) profile.

**What to do:**
- **Settings > Team:** List users (email, name, role). Button “Invite user” (admin only): modal with email → POST /api/users/invite. Success: “Invitation sent to {email}.” Optionally: per-user “Remove” or “Disable” (calls DELETE or PATCH from 4.4 revocation).
- **Settings > Account / Organization:** Display read-only tenant/org context for the current user: **tenant name**, optional **Organization ID** (tenant `id`), and **External ID** (from GET /api/auth/me `tenant.external_id`) so users can reference it for CloudFormation or support. Later: profile (name, change password), and optionally “Switch organization” when multi-tenant per user is supported.

**Deliverable:** Team list and invite modal in Settings; guard invite button by `user.role === 'admin'`. Settings > Account/Organization section showing tenant name, Organization ID, and External ID (from auth/me).

---

#### Step 4 Definition of Done

✅ Migration: User has password_hash, role, onboarding_completed_at; user_invites table exists  
✅ Auth module: get_optional_user, get_current_user; JWT sign/verify; signup, login, me endpoints; GET /api/auth/me returns user + tenant (id, name, external_id) for Sidebar/Settings  
✅ Existing routers (accounts, findings) resolve tenant from token when present, else from request; tenant_id remains in API  
✅ Users router: list, invite, accept-invite (get + set password); user revocation (DELETE or PATCH disable); email service sends invite link  
✅ PATCH /api/users/me sets onboarding_completed_at  
✅ Frontend: AuthContext, login/signup/accept-invite pages; API client sends Bearer when token present  
✅ Onboarding wizard (5 steps); complete endpoint called at end; invited users: same wizard if no accounts, else skip to dashboard with "Get started" prompt  
✅ Settings > Team: list users, invite (admin only); optional remove/disable per user  
✅ Settings > Account/Organization: tenant name, Organization ID, External ID (from auth/me)  
✅ Existing tests and dev flow (tenant_id, no token) still work

### Step 5: Action Grouping + Dedupe

This step adds the action layer that groups and deduplicates Security Hub findings into a smaller set of actionable items. Users see 10–30 "Actions" instead of hundreds of noisy findings. The action engine groups by resource + control, dedupes across regions/accounts where possible, and computes a priority score. This fulfills Phase 2: "user sees 10–30 Actions instead of 500 noisy findings."

---

#### 5.1 Create actions model (migration)

**Purpose:** Define the database schema for actions—the aggregated, deduplicated units of work derived from findings. Each action represents "fix this resource for this control" (optionally scoped to account/region when dedupe is not possible).

**What it does:**
- Creates an `actions` table that stores one row per distinct actionable item
- Each action has a type, target (resource or control), scope (account, region), priority score, and status
- Supports linking to multiple findings via `action_findings` (5.2)
- Enforces multi-tenant isolation through `tenant_id` foreign key
- Indexes support common query patterns (tenant + status, tenant + priority)

**Table: actions**

**Columns:**

**Primary key and tenant isolation:**
- `id` (UUID, primary key) - Unique identifier for each action
- `tenant_id` (UUID, foreign key to tenants, NOT NULL) - Multi-tenant isolation

**Action identification:**
- `action_type` (string(64), NOT NULL) - Type of remediation. MVP in-scope (7): "s3_block_public_access", "enable_security_hub", "enable_guardduty", "s3_bucket_block_public_access", "s3_bucket_encryption", "sg_restrict_public_ports", "cloudtrail_enabled"; fallback: "pr_only"
- `target_id` (string(512), NOT NULL) - Normalized target identifier for dedupe (e.g., resource ARN, control ID, or composite key like `account_id|region|control_id` for account-level fixes)
- `account_id` (string(12), NOT NULL) - AWS account ID
- `region` (string(32), nullable) - AWS region; NULL for account-level actions (e.g., S3 Block Public Access)

**Priority and status:**
- `priority` (integer, 0–100, NOT NULL) - Computed priority score (severity + exploitability + exposure; higher = more urgent)
- `status` (enum: open, in_progress, resolved, suppressed, NOT NULL) - Workflow status

**Metadata:**
- `title` (string(500), NOT NULL) - Human-readable title (e.g., "Enable S3 Block Public Access in account 123456789012")
- `description` (text, nullable) - Optional summary of the action
- `control_id` (string(64), nullable) - Primary Security Hub control ID if applicable
- `resource_id` (string(2048), nullable) - Primary resource ARN or ID if applicable
- `resource_type` (string(128), nullable) - Resource type (e.g., AwsS3Bucket, AwsAccount)
- `created_at` (timestamp with timezone, NOT NULL)
- `updated_at` (timestamp with timezone, NOT NULL)

**Indexes:**
- `idx_actions_tenant_status` on `(tenant_id, status)` - Fast "open actions" queries
- `idx_actions_tenant_priority` on `(tenant_id, priority DESC)` - Top-priority actions
- `idx_actions_tenant_account_region` on `(tenant_id, account_id, region)` - Scope filtering
- `uq_actions_tenant_target` on `(tenant_id, action_type, target_id, account_id, COALESCE(region, ''))` - Dedupe: one action per distinct target per tenant

**Why this matters:** Actions are the primary unit of work for the UI and remediation workflow. Without a proper schema, grouping and dedupe logic will be brittle.

**Deliverable:** Alembic migration; SQLAlchemy model in `backend/models/action.py`

---

#### 5.2 Create action_findings mapping table

**Purpose:** Many-to-many relationship between actions and findings. One action can group multiple findings (e.g., same S3 bucket with multiple control failures across regions); one finding can map to one action. This supports drill-down from action to underlying findings and evidence.

**What it does:**
- Creates `action_findings` association table: `action_id`, `finding_id`, `created_at`
- Foreign keys to `actions.id` and `findings.id` (both CASCADE on delete)
- Unique constraint on `(action_id, finding_id)` to avoid duplicate links
- Index on `action_id` for "findings for this action" queries; index on `finding_id` for "action for this finding" queries

**Table: action_findings**

**Columns:**
- `action_id` (UUID, foreign key to actions.id, ON DELETE CASCADE, NOT NULL)
- `finding_id` (UUID, foreign key to findings.id, ON DELETE CASCADE, NOT NULL)
- `created_at` (timestamp with timezone, NOT NULL, default=now())

**Constraints:**
- Primary key: `(action_id, finding_id)`
- Unique: `(action_id, finding_id)`

**Indexes:**
- `idx_action_findings_action` on `(action_id)` - List findings for an action
- `idx_action_findings_finding` on `(finding_id)` - Find action(s) for a finding

**Why this matters:** Evidence packs and UI drill-down require traceability from action back to source findings. The mapping also enables "how many findings does this action represent?" metrics.

**Deliverable:** Alembic migration adding `action_findings`; SQLAlchemy relationship on `Action` and `Finding` models

---

#### 5.3 Implement action engine (grouping + dedupe logic)

**Purpose:** Core logic that reads findings from Postgres, groups them by resource + control (or account + control for account-level fixes), dedupes across regions/accounts where safe, computes priority scores, and writes actions + action_findings. This runs inside a worker job (5.4).

**What it does:**
- **Grouping keys:** Group findings by composite key. Examples:
  - Resource-level: `(tenant_id, account_id, region, resource_id, control_id)` — same bucket, same control, same region
  - Account-level: `(tenant_id, account_id, control_id)` — e.g., S3 Block Public Access (no region)
  - Cross-region dedupe (optional): For some controls (e.g., IAM role), same `resource_id` across regions may be one action: `(tenant_id, account_id, resource_id, control_id)` with `region = NULL` or "multi"
- **Dedupe rules:** Document which controls support cross-region dedupe (e.g., IAM roles are global; S3 buckets are per-region). For MVP, keep dedupe conservative: same account + region + resource + control = one action.
- **Priority score:** `priority = severity_normalized (0–100) + exploitability_bonus (0–10) + exposure_bonus (0–10)`, capped at 100. Exploitability: +5 if finding mentions "public" or "unrestricted"; exposure: +5 if resource is internet-facing (from finding metadata if available). Simple heuristics are enough for MVP.
- **Idempotency:** Re-run produces same actions for same findings. Use upsert on `(tenant_id, action_type, target_id, account_id, region)`; update priority, status, and refresh action_findings links.
- **Status propagation:** When all linked findings are RESOLVED in Security Hub, optionally mark action as `resolved`. When new findings match an existing action, add to action_findings and refresh `updated_at`.

**Function signature:**
```python
def compute_actions_for_tenant(
    tenant_id: uuid.UUID,
    account_id: str | None = None,
    region: str | None = None,
) -> dict:
    """
    Computes actions from findings for a tenant (optionally scoped to account/region).
    Groups, dedupes, scores, upserts actions and action_findings.

    Returns:
        dict with counts: actions_created, actions_updated, action_findings_linked
    """
```

**Grouping algorithm (outline):**
1. Query findings for tenant (and optional account_id, region) where status IN (NEW, NOTIFIED)
2. For each finding, compute grouping key (resource_id, control_id, account_id, region)
3. Group findings by key; each group becomes one action
4. For each group: build target_id (e.g., `f"{account_id}|{region}|{resource_id}|{control_id}"`), compute priority, upsert action
5. Replace action_findings for each action with current group members
6. Optionally: mark actions as resolved when no open findings remain

**Why this matters:** The action engine is the core of Phase 2. Without correct grouping and dedupe, users will still see hundreds of items instead of a manageable list.

**Deliverable:** `backend/services/action_engine.py` (or `worker/services/action_engine.py`) with `compute_actions_for_tenant()` and grouping/dedupe helpers

---

#### 5.4 SQS job and trigger to compute actions

**Purpose:** Run the action engine asynchronously after ingestion completes, or on a schedule. SQS decouples compute from API; same pattern as ingest (Step 2).

**What it does:**
- **New queue (optional):** `security-autopilot-actions-queue` for `compute_actions` job type. Alternatively, reuse ingest queue with `job_type: compute_actions` and a separate handler.
- **Message format:**
  ```json
  {
    "tenant_id": "uuid",
    "account_id": "123456789012",
    "region": "us-east-1",
    "job_type": "compute_actions",
    "created_at": "2026-01-29T10:00:00Z"
  }
  ```
  Omit `account_id`/`region` to compute for entire tenant.
- **Worker handler:** On `job_type == "compute_actions"`, call `compute_actions_for_tenant(tenant_id, account_id, region)`.
- **Trigger options:**
  - **A) Chained after ingest:** When ingest job completes successfully, enqueue a `compute_actions` job for same tenant/account/region (or tenant-wide).
  - **B) API endpoint:** `POST /api/actions/compute` — require auth; enqueue job for current tenant; return 202 Accepted.
  - **C) Scheduled:** EventBridge/cron invokes API or sends SQS message for all tenants periodically (e.g., daily).

**Endpoint (if B):** `POST /api/actions/compute`

**Request body (optional):**
```json
{
  "account_id": "123456789012",
  "region": "us-east-1"
}
```
If omitted: compute for entire tenant.

**Response (202 Accepted):**
```json
{
  "message": "Action computation job queued",
  "tenant_id": "uuid",
  "scope": { "account_id": "123456789012", "region": "us-east-1" }
}
```

**Error handling:**
- Tenant not found → 404
- SQS failure → 503
- Invalid account_id/region (not in tenant's accounts) → 400

**Why this matters:** Actions must stay in sync with findings. Running after ingest ensures new findings quickly become actions; scheduled run catches external Security Hub updates.

**Deliverable:** Worker job handler for `compute_actions`; **Required for MVP:** `POST /api/actions/compute`; optional chain from ingest job completion

---

#### 5.5 Actions API endpoints

**Purpose:** Let the frontend list actions, filter by status/account/priority, and fetch a single action with its linked findings.

**Endpoints:**

**GET /api/actions**
- **Query params:** `account_id` (optional), `region` (optional), `status` (optional, e.g., open, resolved), `limit` (default 50, max 200), `offset`
- **Response:** `{ "items": [...], "total": N }` — each item includes `id`, `action_type`, `target_id`, `account_id`, `region`, `priority`, `status`, `title`, `control_id`, `resource_id`, `updated_at`, `finding_count` (number of linked findings)
- **Auth:** Resolve tenant from JWT; filter by `tenant_id`

**GET /api/actions/{id}**
- **Response:** Full action object plus `findings` array (id, finding_id, severity_label, title, resource_id, account_id, region, updated_at)
- **Auth:** Tenant-scoped; 404 if not found

**PATCH /api/actions/{id}** (optional for Step 5)
- **Body:** `{ "status": "in_progress" | "resolved" | "suppressed" }`
- **Use case:** User marks action as "in progress" or "resolved" manually; later, exception workflow (Step 6) may also update status

**Why this matters:** The Actions list and detail pages need these endpoints. Pagination and filters keep the UI usable with many actions.

**Deliverable:** `backend/routers/actions.py` with GET list, GET by id; optional PATCH for status

---

#### 5.6 Frontend: Actions list and detail pages

**Purpose:** Users see a prioritized list of actions (instead of raw findings) and can drill into each action to view linked findings. Uses design system 3.0 and Aceternity components.

**Route:** `/actions` (list), `/actions/[id]` (detail)

**What to do:**

**A) Actions list page (`/actions`)**
- **Primary components:** **Animated Tabs** for status: All / Open / In progress / Resolved. **Hover Border Gradient** on each action card. **Card Spotlight** on top 3 by priority. **Animated Tooltip** on row actions (View, Copy resource).
- **Placement:** Top: tabs + filters (account, region). Main: stack of action cards. Each card: title, account, region, priority badge, finding count, control_id, updated_at. Click → `/actions/[id]`.
- **API:** `GET /api/actions` with params from filters and tabs.
- **Empty state:** "No actions match your filters" or "Run ingestion and action computation to see actions."

**B) Action detail page (`/actions/[id]`)**
- **Primary components:** **Card Spotlight** on hero summary (action title, priority, status). Section cards for: Description, Linked findings (list with links to `/findings/[id]`), Metadata (control_id, resource_id, account, region).
- **Placement:** Top: title + status + priority. Below: description, then table/list of linked findings with severity, title, link to finding detail.
- **API:** `GET /api/actions/{id}` for full action + findings.
- **Required for MVP:** "Recompute actions" button → `POST /api/actions/compute` (Stateful Button + Multi Step Loader) for manual refresh. Users must be able to refresh action status after applying fixes (direct fix or PR bundle). Place on actions list and/or action detail page. Part of remediation flow (Step 9.7: Next steps UI points user to Recompute after run success).

**C) Navigation**
- Add **Actions** to Sidebar (between Findings and Top Risks, or after Top Risks). Route: `/actions`.

**Why this matters:** Phase 2 definition of done is "user sees 10–30 Actions instead of 500 noisy findings." The Actions list is the primary view for remediation workflow.

**Deliverable:** `app/actions/page.tsx`, `app/actions/[id]/page.tsx`; Sidebar link to `/actions`; API client methods `getActions()`, `getAction(id)`

**Error handling:** Same as Findings (failure message, empty state, 404 on detail)

---

#### Step 5 Definition of Done

✅ Actions model and migration created with proper indexes and unique constraint for dedupe  
✅ action_findings mapping table and relationships implemented  
✅ Action engine: groups by resource + control, dedupes, computes priority, upserts actions and links  
✅ Worker job for compute_actions (SQS); POST /api/actions/compute (required for MVP)  
✅ GET /api/actions (list with filters) and GET /api/actions/{id} (with findings)  
✅ Frontend: Actions list page (tabs, cards, filters, Recompute actions button) and Actions detail page (linked findings, Recompute actions button)  
✅ Sidebar includes Actions; design system 3.0 and Aceternity components applied  
✅ User can see 10–30 actions instead of hundreds of raw findings when data is present

---

### Step 6: Exceptions + Expiry

This step adds first-class exceptions (suppressions) with reason, approver, and expiry. Users can approve an exception for a finding or action to reduce noise; expired exceptions are detected so items return to the open view. Exceptions are part of the evidence pack and audit trail. This fulfills Phase 2: "exceptions workflow (approve + expiry)" and keeps the Actions list focused on items that still need attention.

---

#### 6.1 Create exceptions model (migration)

**Purpose:** Define the database schema for exceptions—records that suppress a finding or action from the active workflow for a defined period, with an audit trail (reason, approver, optional ticket link).

**What it does:**
- Creates an `exceptions` table that stores one row per suppressed finding or action
- Each exception has a scope (which finding or action), reason, approver, expiry date, and optional ticket link
- Enforces multi-tenant isolation through `tenant_id` foreign key
- At most one active exception per (entity_type, entity_id) per tenant; creating a new exception for the same target can update the existing row or replace it (business rule: one active exception per finding/action)
- Indexes support "list exceptions for tenant," "find exception for this finding/action," and "exceptions expiring soon" queries

**Table: exceptions**

**Columns:**

**Primary key and tenant isolation:**
- `id` (UUID, primary key)
- `tenant_id` (UUID, foreign key to tenants, NOT NULL)

**Scope (what is excepted):**
- `entity_type` (enum: finding, action, NOT NULL) - Whether this exception applies to a finding or an action
- `entity_id` (UUID, NOT NULL) - `findings.id` or `actions.id`; no FK to allow soft reference if entity is later deleted (or use FK with SET NULL on delete and nullable entity_id for audit)

**Approval and reason:**
- `reason` (text, NOT NULL) - Why the exception was approved (e.g., "False positive; scanner misconfig", "Accepted risk until Q3")
- `approved_by_user_id` (UUID, foreign key to users, NOT NULL) - Who approved the exception
- `ticket_link` (string(500), nullable) - Optional link to Jira, ServiceNow, etc.

**Expiry:**
- `expires_at` (timestamp with timezone, NOT NULL) - After this time the exception no longer applies; the finding/action returns to open/suppressed-by-expiry handling per 6.3

**Metadata:**
- `created_at` (timestamp with timezone, NOT NULL)
- `updated_at` (timestamp with timezone, NOT NULL)

**Constraints:**
- Unique on `(tenant_id, entity_type, entity_id)` so only one active exception per finding or action per tenant (optional: allow multiple with different date ranges; for MVP one per entity is simpler)

**Indexes:**
- `idx_exceptions_tenant` on `(tenant_id)` - List all exceptions for tenant
- `idx_exceptions_entity` on `(tenant_id, entity_type, entity_id)` - Look up exception for a given finding/action (covers unique constraint)
- `idx_exceptions_expires_at` on `(tenant_id, expires_at)` - Expiry job: find exceptions where `expires_at <= now()`

**Why this matters:** Exceptions reduce noise and are part of the evidence pack. A clear schema with expiry and approver supports compliance and "why was this suppressed?" audits.

**Deliverable:** Alembic migration; SQLAlchemy model in `backend/models/exception.py`

---

#### 6.2 Exception API endpoints

**Purpose:** Let the frontend create, list, and revoke exceptions; and let the backend (and Actions/Findings APIs) resolve whether a finding or action is currently excepted and whether the exception is expired.

**Endpoints:**

**POST /api/exceptions**
- **Body:** `{ "entity_type": "finding" | "action", "entity_id": "uuid", "reason": "string", "expires_at": "ISO8601", "ticket_link": "optional string" }`
- **What it does:** Resolve tenant from JWT; resolve `approved_by_user_id` from current user. Validate that `entity_id` exists and belongs to tenant (finding or action per `entity_type`). If an exception already exists for this (entity_type, entity_id), either update it (same row) or return 409 with message "An exception already exists for this item; revoke or update it." Create exception row. If entity_type is action, optionally update action status to `suppressed` (see 6.3).
- **Response (201):** `{ "id": "uuid", "entity_type": "...", "entity_id": "...", "reason": "...", "expires_at": "...", "approved_by_user_id": "...", "ticket_link": "...", "created_at": "..." }`
- **Auth:** Tenant-scoped; require authenticated user
- **Error handling:** Entity not found → 404; duplicate exception → 409 or 200 with update; invalid expires_at (past) → 400

**GET /api/exceptions**
- **Query params:** `entity_type` (optional), `entity_id` (optional), `active_only` (optional, default true — only non-expired), `limit` (default 50), `offset`
- **Response:** `{ "items": [...], "total": N }` — each item includes id, entity_type, entity_id, reason, expires_at, approved_by (user email or id), ticket_link, created_at; if `active_only=true` filter where `expires_at > now()`
- **Auth:** Tenant-scoped

**GET /api/exceptions/{id}**
- **Response:** Full exception object including approver details
- **Auth:** Tenant-scoped; 404 if not found

**DELETE /api/exceptions/{id}** (revoke)
- **What it does:** Delete exception (or soft-delete if you add deleted_at). If entity was an action with status `suppressed`, optionally set action status back to `open` (or leave for action engine / expiry job to reconcile).
- **Response:** 204 No Content
- **Auth:** Tenant-scoped; 404 if not found

**Helper for other APIs:** When returning findings or actions, include a field such as `exception_id` (nullable) and `exception_expires_at` (nullable) so the UI can show "Suppressed until &lt;date&gt;" or "Exception expired." Alternatively, resolve in frontend with GET /api/exceptions?entity_type=action&entity_id=&lt;id&gt;.

**Why this matters:** The UI needs to create exceptions from a finding or action detail page, list them (e.g. Settings > Exceptions or a tab on Actions), and revoke or let them expire. APIs must expose exception state so lists can filter or badge "Suppressed."

**Deliverable:** `backend/routers/exceptions.py` with POST, GET list, GET by id, DELETE; mount under `/api/exceptions`. Optional: include `exception_id` / `exception_expires_at` in GET /api/actions and GET /api/findings response items.

---

#### 6.3 Expiry checking logic

**Purpose:** When an exception's `expires_at` has passed, the system should treat the finding/action as no longer suppressed so it reappears in open lists and, for actions, status can revert from `suppressed` to `open`.

**What it does:**

**Option A — On read:** When listing or fetching actions (and optionally findings), filter or annotate using current time: if `expires_at <= now()`, do not consider the exception active. Actions with status `suppressed` but whose exception has expired can be returned with a computed "effective" state (e.g. `exception_expired: true`) so UI shows "Exception expired; action is open again." No background job; logic is in query or in API layer.

**Option B — Background job:** A scheduled worker job (e.g. daily or hourly) runs: select exceptions where `expires_at <= now()`. For each, if `entity_type == action`, update the corresponding action's status from `suppressed` to `open` (if you store status on action). Optionally send a notification (e.g. "Exception for action X has expired"). Do not delete the exception row (keep for audit); optionally add a column `expired_at` or leave as-is and "active" is defined by `expires_at > now()` in queries.

**Recommendation:** Use **on-read** for MVP so "exception expired" is reflected immediately when user opens the list; optionally add a small nightly job that sets `actions.status` from `suppressed` to `open` for expired exceptions so list filters (e.g. status=open) stay consistent without extra JOIN logic.

**Where to implement:**
- **Actions API (GET list / GET by id):** When returning an action, look up exception by (tenant_id, entity_type=action, entity_id=action.id). If found and `expires_at > now()`, include `exception_id`, `exception_expires_at`, and set or keep `status` as suppressed. If found and `expires_at <= now()`, include `exception_expired: true` and treat status as open for filtering/display.
- **Findings API (GET list / GET by id):** Same idea: resolve exception for (tenant_id, entity_type=finding, entity_id=finding.id); expose exception info or "suppressed until" only when not expired.

**Why this matters:** Expiry is a core part of the exceptions workflow. Users expect suppressed items to reappear after the exception period; the system must not show stale "suppressed" state after expiry.

**Deliverable:** Helper in backend (e.g. `services/exception_service.py`) such as `get_active_exception(tenant_id, entity_type, entity_id)` returning None or exception row; use in actions and findings APIs to attach exception/expiry fields. Optional: worker job that sets `actions.status = open` where exception expired.

---

#### 6.4 Frontend: Exceptions UI (design system 3.0 + Aceternity)

**Purpose:** Users can create an exception from a finding or action, view exception details, see "Suppressed until &lt;date&gt;" in lists, and revoke exceptions. Uses Cold Intelligence Dark Mode, Stateful Button, Animated Modal, and tooltips.

**What to do:**

**A) Create exception flow**
- **From Finding detail (`/findings/[id]`):** Add a "Create exception" or "Suppress" button. On click, open **Animated Modal** with form: Reason (required textarea), Expires at (required date/datetime picker), Ticket link (optional). Submit → `POST /api/exceptions` with `entity_type: "finding", entity_id: finding.id`. On success, close modal and refresh finding (show "Suppressed until &lt;date&gt;" and optionally hide or grey out "Create exception").
- **From Action detail (`/actions/[id]`):** Same pattern: "Create exception" / "Suppress" → Modal with reason, expires_at, ticket_link → `POST /api/exceptions` with `entity_type: "action", entity_id: action.id`. On success, show action as suppressed and optional "Revoke exception" link.

**B) Exceptions list page (optional but recommended)**
- **Route:** `/settings/exceptions` or `/exceptions`. List all exceptions (active only by default) with filters: entity type (finding/action), optional search by reason. **Animated Tabs** for Active / Expired if you support showing expired for audit. Table or cards: entity type, entity_id (with link to finding or action), reason, approved by, expires at, ticket link, actions (Revoke = DELETE /api/exceptions/{id}). Use **Hover Border Gradient** on rows/cards; **Animated Tooltip** on "Revoke" and expiry date.

**C) Actions and Findings lists**
- **Actions list:** For each action card/row, if API returns `exception_id` and `exception_expires_at`, show a badge "Suppressed until &lt;date&gt;" (or "Exception expired" if `exception_expired: true`). Tooltip on badge: reason and approver if available. Filter tab or filter option: "Open" (exclude suppressed), "Suppressed," "All."
- **Findings list:** Same idea: badge "Suppressed until &lt;date&gt;" when finding has an active exception; link to revoke or view exception.

**D) Revoke exception**
- From exception list or from finding/action detail: "Revoke exception" → confirm in small modal → `DELETE /api/exceptions/{id}` → refresh. Use **Stateful Button** for submit; **Animated Modal** for confirmation.

**E) Design system and components**
- **Cold Intelligence Dark Mode:** Surfaces, borders, text, accent per 3.0.
- **Stateful Button** for "Create exception," "Revoke," "Save."
- **Animated Modal** for create-exception form and revoke confirmation.
- **Animated Tooltip** on badges and buttons (e.g. "Suppressed until …" tooltip shows reason).
- **Card Spotlight** or **Hover Border Gradient** on exception list cards/rows.

**Why this matters:** Phase 2 definition of done includes "exceptions workflow (approve + expiry)." Users must be able to suppress items with a reason and expiry and see when exceptions expire or revoke them.

**Deliverable:** Create-exception modal (reusable) used from `/findings/[id]` and `/actions/[id]`; optional `/exceptions` or `/settings/exceptions` list page; exception badges and revoke flow; API client methods `createException()`, `getExceptions()`, `getException(id)`, `revokeException(id)`. Apply design system 3.0 and Aceternity components as above.

**Error handling:** 409 (duplicate exception) → show message "An exception already exists for this item; update or revoke it." 400 (e.g. past expiry) → show field errors. 404 → refresh and show "Item not found."

---

#### Step 6 Definition of Done

✅ Exceptions model and migration created with proper indexes and unique constraint per (tenant, entity_type, entity_id)  
✅ Exception API: POST (create), GET list, GET by id, DELETE (revoke); tenant-scoped and auth enforced  
✅ Actions and findings APIs expose exception state (exception_id, exception_expires_at or exception_expired) where applicable  
✅ Expiry logic: on-read or job so that expired exceptions no longer suppress items; actions/findings show as open or "Exception expired"  
✅ Frontend: Create exception from finding and action detail (modal with reason, expires_at, ticket_link); revoke from detail or exceptions list  
✅ Optional exceptions list page; Actions/Findings lists show "Suppressed until" badge and filter options  
✅ Design system 3.0 and Aceternity (Stateful Button, Animated Modal, tooltips) applied to exception UI  
✅ User can suppress a finding or action with reason and expiry and see it reappear when expired or revoke it

### Step 7: Remediation Runs Model + PR Bundle Generation Scaffold

This step adds the remediation run model and audit trail, remediation run tracking (API + worker integration), and a **scaffold** for the PR bundle generator (Terraform/CloudFormation text + steps). No full IaC generation yet—only the data model, APIs, worker hook, and a stub generator that returns a placeholder structure. This fulfills Phase 3 foundation: "remediation run model + audit logs" and "PR bundle generator (Terraform/CFN text + steps)" as a scaffold so Step 8 (direct fixes) and later PR-only flows can record every run and attach artifacts.

---

#### 7.1 Create remediation_runs model (migration)

**Purpose:** Define the database schema for remediation runs—one row per remediation attempt (PR-only or direct fix). Each run records who started it, which action it targeted, mode, status, outcome, logs, and optional artifacts (e.g. PR bundle file references or inline JSON). This table is the primary audit trail for "what was remediated, when, and what happened."

**What it does:**
- Creates a `remediation_runs` table that stores one row per run
- Links to tenant, action (and optionally approval/user)
- Records mode (pr_only vs direct_fix), status (pending, running, success, failed, cancelled), outcome summary, and log content
- Stores artifact references (e.g. S3 keys for generated Terraform/CFN bundles or inline JSON for scaffold)
- Enforces multi-tenant isolation via `tenant_id`
- Indexes support "runs for this action," "runs for tenant," and "recent runs" queries

**Table: remediation_runs**

**Columns:**

**Primary key and tenant isolation:**
- `id` (UUID, primary key)
- `tenant_id` (UUID, foreign key to tenants, NOT NULL)

**Scope (what was remediated):**
- `action_id` (UUID, foreign key to actions.id, NOT NULL) - The action this run remediates
- `mode` (enum: pr_only, direct_fix, NOT NULL) - Whether this run produced a PR bundle only or applied a direct fix

**Status and outcome:**
- `status` (enum: pending, running, success, failed, cancelled, NOT NULL) - Current state of the run
- `outcome` (string(500), nullable) - Short human-readable outcome (e.g. "S3 Block Public Access enabled", "PR bundle generated", "Pre-check failed: bucket in use")
- `logs` (text, nullable) - Full log output or structured JSON (worker appends here or stores in S3 and keeps reference)
- `artifacts` (JSONB, nullable) - Structured artifact metadata: e.g. `{ "pr_bundle": { "format": "terraform", "files": [{ "path": "...", "s3_key": "..." }], "steps": ["Step 1: ...", "Step 2: ..."] } }` or inline stub for scaffold

**Audit and timing:**
- `approved_by_user_id` (UUID, foreign key to users, nullable) - Who approved the run (required for direct_fix; optional for pr_only)
- `started_at` (timestamp with timezone, nullable) - When the worker actually started the run
- `completed_at` (timestamp with timezone, nullable) - When the run finished (success or failed)
- `created_at` (timestamp with timezone, NOT NULL)
- `updated_at` (timestamp with timezone, NOT NULL)

**Indexes:**
- `idx_remediation_runs_tenant` on `(tenant_id)` - List all runs for tenant
- `idx_remediation_runs_action` on `(action_id)` - Runs for a given action
- `idx_remediation_runs_tenant_created` on `(tenant_id, created_at DESC)` - Recent runs for tenant
- `idx_remediation_runs_status` on `(tenant_id, status)` - Filter by pending/running/success/failed

**Why this matters:** Phase 3 requires "every remediation run writes a full audit trail." This table is that audit trail. Without it, you cannot show users "before/after checks + logs" or attach PR bundle outputs to a run.

**Deliverable:** Alembic migration; SQLAlchemy model in `backend/models/remediation_run.py`

---

#### 7.2 Remediation runs API endpoints

**Purpose:** Let the frontend start a remediation run (or enqueue one), list runs for an action or tenant, and fetch a single run with logs and artifacts. Approval workflow for direct_fix is covered in Step 8; here we only expose the run resource.

**Endpoints:**

**POST /api/remediation-runs**
- **Body:** `{ "action_id": "uuid", "mode": "pr_only" | "direct_fix" }`
- **What it does:** Resolve tenant from JWT. Validate that `action_id` exists and belongs to tenant. For `direct_fix`, optionally require an approval token or pre-check (Step 8); for this step, creating a run in `pending` status is enough. Create `remediation_runs` row with `status = pending`. Enqueue worker job (see 7.3) with `run_id`, `action_id`, `mode`. Return created run.
- **Response (201):** `{ "id": "uuid", "action_id": "...", "mode": "...", "status": "pending", "created_at": "...", "updated_at": "..." }`
- **Auth:** Tenant-scoped; require authenticated user
- **Error handling:** Action not found → 404; invalid mode → 400; duplicate pending run for same action (optional) → 409

**GET /api/remediation-runs**
- **Query params:** `action_id` (optional), `status` (optional), `mode` (optional), `limit` (default 50, max 200), `offset`
- **Response:** `{ "items": [...], "total": N }` — each item includes id, action_id, mode, status, outcome, started_at, completed_at, created_at; optionally summary of artifacts (e.g. "PR bundle: 2 files")
- **Auth:** Tenant-scoped

**GET /api/remediation-runs/{id}**
- **Response:** Full run object: id, action_id, mode, status, outcome, logs, artifacts, approved_by_user_id, started_at, completed_at, created_at, updated_at. Include action summary (title, account_id, region) for display.
- **Auth:** Tenant-scoped; 404 if not found

**Why this matters:** The UI needs to trigger a run (e.g. "Generate PR bundle" or "Run fix" after approval), show run history per action, and display logs/artifacts for a given run.

**Deliverable:** `backend/routers/remediation_runs.py` with POST, GET list, GET by id; mount under `/api/remediation-runs`

---

#### 7.3 Remediation run tracking (worker integration)

**Purpose:** When a remediation run is created, the worker picks up the job, updates the run row (pending → running → success/failed), appends or stores logs, and (for pr_only) can call the PR bundle scaffold and store result in `artifacts`. This step implements the job shape and status transitions; actual fix logic is in Step 8.

**What it does:**
- **New queue or job type:** Use an SQS queue (e.g. `security-autopilot-remediation-queue`) or reuse a generic worker queue with `job_type: remediation_run`.
- **Message format:**
  ```json
  {
    "job_type": "remediation_run",
    "run_id": "uuid",
    "tenant_id": "uuid",
    "action_id": "uuid",
    "mode": "pr_only",
    "created_at": "2026-02-02T10:00:00Z"
  }
  ```
- **Worker handler:**
  1. Load `remediation_runs` row by `run_id`; verify tenant and status is `pending`.
  2. Set `status = running`, `started_at = now()`, save.
  3. If `mode == "pr_only"`: call PR bundle scaffold (7.4); write result to `artifacts`; set `outcome` to e.g. "PR bundle generated (scaffold)"; set `status = success`, `completed_at = now()`.
  4. If `mode == "direct_fix"`: for this step, do not implement real fix; set `outcome = "Direct fix not implemented (scaffold)"`, `status = failed` or leave for Step 8 to implement.
  5. Append or store logs (e.g. a few lines of "Run started", "PR bundle scaffold called", "Run completed") in `logs` or in S3 and store key in `artifacts`.
  6. Save row.
- **Idempotency:** If the same run_id is processed twice (e.g. retry), check status; if already `success` or `failed`, skip or no-op so we do not overwrite the audit record.

**Why this matters:** Remediation runs must be tracked end-to-end. The worker is the single place that updates run status and writes logs/artifacts, so the API and UI always read from `remediation_runs`.

**Deliverable:** Worker job handler for `remediation_run`; enqueue from POST /api/remediation-runs after creating the row

---

#### 7.4 PR bundle generator scaffold

**Purpose:** Provide a stub implementation that returns a fixed structure (placeholder files + steps) so the rest of the pipeline (worker, API, UI) can assume "generate PR bundle" returns a consistent shape. **Real IaC generation per action type is implemented in Step 9.** Until Step 9 is done, this scaffold returns placeholder content.

**What it does:**
- **Function signature:**
  ```python
  def generate_pr_bundle(
      action_id: uuid.UUID,
      format: str = "terraform",  # or "cloudformation"
  ) -> dict:
      """
      Returns a PR bundle structure for the given action.
      Scaffold (Step 7): returns placeholder content.
      Real implementation (Step 9): loads action, generates applyable IaC per action_type.
      """
      # Returns e.g.:
      # {
      #   "format": "terraform",
      #   "files": [ { "path": "main.tf", "content": "# Placeholder for action {action_id}" } ],
      #   "steps": [ "Step 1: Review the generated files.", "Step 2: Apply in your pipeline." ]
      # }
  ```
- **Inputs:** `action_id` (to load action type, target_id, account_id, region for Step 9); `format` (terraform | cloudformation).
- **Output:** Dict with `format`, `files` (list of `{ "path": str, "content": str }`), and `steps` (list of strings). Scaffold returns one placeholder file and 2–3 generic steps. Step 9 replaces this with real IaC.
- **Where it plugs in:** Worker (7.3) calls this when `mode == "pr_only"`; result is stored in `remediation_runs.artifacts` under a key like `pr_bundle`. Optionally, for larger output, write files to S3 and store only paths/keys in `artifacts`.

**Why this matters:** Phase 3 deliverable is "PR bundle generator (Terraform/CFN text + steps)." A scaffold unblocks API and UI work and defines the contract. Step 9 implements real IaC generation.

**Deliverable:** `backend/services/pr_bundle.py` (or `worker/services/pr_bundle.py`) with `generate_pr_bundle(action_id, format)` returning stub structure; worker stores result in run artifacts. **Replace scaffold with real implementation in Step 9.**

---

#### 7.5 Audit logging

**Purpose:** Ensure every remediation run is an immutable audit record: who (approved_by_user_id), when (started_at, completed_at), what (action_id, mode), and outcome (status, outcome, logs, artifacts). No overwriting of final outcome after completion.

**What it does:**
- **Primary audit record:** The `remediation_runs` table is the source of truth. Once `status` is `success` or `failed`, do not allow updates to `outcome`, `logs`, or `artifacts` (or only allow append for logs if you support streaming). This gives an append-only audit feel.
- **Optional enhancements:** (1) Write a one-line summary event to a dedicated `audit_log` table (tenant_id, event_type, entity_type, entity_id, user_id, timestamp, summary) for compliance dashboards. (2) Send a short metric or log line to CloudWatch (e.g. "RemediationRun completed run_id=... action_id=... status=success") for operational visibility.
- **Documentation:** In code or docs, state that remediation_runs is the remediation audit trail and that completed runs are immutable.

**Why this matters:** Remediation safety rules (Section D) require "Full audit log for every run." This step makes that explicit and prevents accidental overwrites.

**Deliverable:** Document audit semantics; optionally add `audit_log` table and/or CloudWatch log line in worker when run completes; enforce no outcome/log/artifact updates after status is success/failed (application rule or DB trigger)

---

#### Step 7 Definition of Done

✅ remediation_runs model and migration created with proper columns and indexes (tenant_id, action_id, mode, status, outcome, logs, artifacts, approved_by_user_id, started_at, completed_at)  
✅ Remediation runs API: POST (create + enqueue), GET list (filter by action_id, status, mode), GET by id (full run with logs and artifacts); tenant-scoped and auth enforced  
✅ Worker job for remediation_run: updates status pending → running → success/failed, writes outcome and logs, calls PR bundle scaffold for pr_only and stores result in artifacts  
✅ PR bundle scaffold: generate_pr_bundle(action_id, format) returns stub structure (files + steps); worker stores in run artifacts. **Step 9 replaces scaffold with real IaC.**  
✅ Audit: remediation_runs is the audit record; completed runs are immutable for outcome/logs/artifacts; optional audit_log or CloudWatch summary  
✅ User can create a remediation run (pr_only or direct_fix), see it in list and detail, and see scaffold PR bundle output and run logs

---

### Step 8: 7 Real Action Types (3 Direct Fix + 4 PR Bundle; WriteRole required)

This step implements **7 real action types** from Phase 3. **Three** have direct fix (S3 Block Public Access account-level, Security Hub enablement, GuardDuty enablement); **four** are PR bundle only (S3 bucket block, S3 bucket encryption, SG restrict public ports, CloudTrail enabled—see Step 9.8 table). Each direct fix requires an approval workflow, pre-check and post-check validation, and a **required** WriteRole in the customer AWS account. Account connection requires both ReadRole and WriteRole; both are validated at registration. This fulfills Phase 3: "7 real remediations" with full audit trail and safety rules per Section D.

---

#### 8.1 WriteRole CloudFormation template and account support (required)

**Purpose:** Provide the **required** CloudFormation template that customers deploy in their AWS account to create a WriteRole with minimal, scoped permissions for the **three** safe direct fixes only. The four additional action types (S3 bucket block, S3 bucket encryption, SG restrict, CloudTrail) are PR bundle only at MVP—no WriteRole permissions required for them. The SaaS requires WriteRole at account connection; both ReadRole and WriteRole are validated (STS assume) during registration.

**What it does:**
- Creates a CloudFormation template that defines an IAM Role with write permissions scoped to the three direct fixes only
- Trusts your SaaS AWS account with ExternalId (same pattern as ReadRole)
- Permissions include:
  - **S3 Block Public Access:** `s3:GetAccountPublicAccessBlock`, `s3:PutAccountPublicAccessBlock` (S3 Control API; note: some docs reference `s3control:PutPublicAccessBlock`—verify boto3 S3Control client)
  - **Security Hub:** `securityhub:EnableSecurityHub`, `securityhub:GetEnabledStandards` (enable and verify)
  - **GuardDuty:** `guardduty:CreateDetector`, `guardduty:GetDetector`, `guardduty:ListDetectors` (enable and verify)
- `aws_accounts` table has `role_write_arn` (required at registration); API requires `role_write_arn` on POST /aws/accounts; PATCH allows updating or correcting the WriteRole ARN
- At registration, backend validates both ReadRole and WriteRole (assume each and verify account_id via get_caller_identity)
- When starting a direct fix, worker uses the stored WriteRole; if missing (e.g. legacy account), fail with outcome "WriteRole not configured"

**Key components of template:**
- IAM Role with trust policy (SaaS account ID + ExternalId)
- IAM policy with least-privilege actions above; use resource `*` only where required (account-level APIs)
- Output: `WriteRoleArn` for customer to paste into SaaS Connect AWS screen (required)

**Why this matters:** WriteRole is required for account connection and for direct fixes. Customers deploy both Read Role and Write Role stacks (same SaaS Account ID and External ID), then paste both ARNs. This ensures every connected account can use direct fixes and keeps the security model consistent.

**Deliverable:** `infrastructure/cloudformation/write-role-template.yaml`; API requires `role_write_arn` on account registration (POST); PATCH to update/correct WriteRole ARN; UI requires both Read Role ARN and Write Role ARN in Connect AWS flow; documentation for "Connect AWS" (both roles required).

---

#### 8.2 Direct fix executor service (pre-check, apply, post-check)

**Purpose:** Implement a reusable direct-fix executor that runs pre-check, applies the fix, runs post-check, and returns structured outcome. **Only three** action types have direct fix at MVP (S3 account-level, Security Hub, GuardDuty); the other four (S3 bucket block, S3 bucket encryption, SG restrict, CloudTrail) are PR bundle only—no direct fix handler. The executor calls the appropriate handler based on `action_type`. All runs are idempotent and safe to re-run.

**What it does:**
- **Executor interface:**
  ```python
  def run_direct_fix(
      run_id: uuid.UUID,
      action_id: uuid.UUID,
      account_id: str,
      region: str | None,
      action_type: str,
      role_write_arn: str,
      tenant_id: uuid.UUID,
  ) -> DirectFixResult:
      """
      Assumes WriteRole, runs pre-check, applies fix, runs post-check.
      Returns: outcome (str), success (bool), logs (list[str])
      """
  ```
- **Pre-check:** Before applying, verify current state. If already compliant, return success with outcome "Already compliant; no change needed" (idempotent). If pre-check fails (e.g., org policy blocking S3 settings), return failure with clear message.
- **Post-check:** After apply, verify the fix took effect. If post-check fails, log the failure; consider run as failed and do not mark finding as resolved.
- **Logging:** Append each step (pre-check, apply, post-check) to run logs; store in `remediation_runs.logs` or `artifacts`.

**Fix 1 — S3 Block Public Access (action_type: `s3_block_public_access`):**
- **Scope:** Account-level; `region` is NULL for this action.
- **Pre-check:** Call `s3control.get_public_access_block(AccountId=account_id)`. If all four settings are true (`BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets`), return "Already compliant."
- **Apply:** Call `s3control.put_public_access_block(AccountId=account_id, PublicAccessBlockConfiguration={...})` with all four booleans `True`. Use `AccountId` from action's `account_id`.
- **Post-check:** Call `get_public_access_block` again; verify all four are True.
- **Control IDs:** Typically S3.1 (CIS) or AWS config rule `s3-account-level-public-access-blocks-periodic`. Map in action_engine `_CONTROL_TO_ACTION_TYPE` if not already.

**Fix 2 — Security Hub enablement (action_type: `enable_security_hub`):**
- **Scope:** Per region; `region` is required.
- **Pre-check:** Call `securityhub.get_enabled_standards()` or `securityhub.describe_hub()` (or equivalent). If Security Hub is already enabled, return "Already compliant."
- **Apply:** Call `securityhub.enable_security_hub(EnableDefaultStandards=True)` (or per product requirements). Region from action.
- **Post-check:** Verify Security Hub is enabled in the region.
- **Control IDs:** Map findings related to "Security Hub should be enabled" to this action_type.

**Fix 3 — GuardDuty enablement (action_type: `enable_guardduty`):**
- **Scope:** Per region; `region` is required.
- **Pre-check:** Call `guardduty.list_detectors()`. If a detector exists and is enabled, return "Already compliant."
- **Apply:** Call `guardduty.create_detector(Enable=True)`. One detector per account per region.
- **Post-check:** Call `guardduty.get_detector(DetectorId=...)`; verify status is enabled.
- **Control IDs:** Map findings related to "GuardDuty should be enabled" to this action_type.

**Why this matters:** Section D requires "Pre-check and post-check for each remediation" and "Idempotent remediations (safe to re-run)." A structured executor ensures consistency and auditability.

**Deliverable:** `worker/services/direct_fix.py` (or `backend/services/direct_fix.py` if run in API; recommend worker) with `run_direct_fix()` and three handlers: `_fix_s3_block_public_access`, `_fix_enable_security_hub`, `_fix_enable_guardduty`. Update `action_engine._CONTROL_TO_ACTION_TYPE` to map **all 7** in-scope control IDs to their action types (see Step 9.8 table); the four PR-bundle-only types are not passed to the direct fix executor. Add unit tests with mocked boto3 clients.

---

#### 8.3 Worker integration for direct_fix mode

**Purpose:** When a remediation run is created with `mode=direct_fix`, the worker (from Step 7.3) must call the direct fix executor instead of returning "Direct fix not implemented (scaffold)." It assumes the WriteRole, runs the fix, and updates the remediation_runs row with outcome, logs, and status.

**What it does:**
- **Load action:** From `action_id`, load action (action_type, account_id, region, target_id). Validate tenant.
- **Load account:** From `aws_accounts`, get `role_write_arn` for the account. If NULL, set `status=failed`, `outcome="WriteRole not configured for this account"`, append to logs, save, return.
- **Assume WriteRole:** Use STS AssumeRole with `role_write_arn` and external_id (from tenant or account). Obtain boto3 session for the customer account (and region for Security Hub/GuardDuty).
- **Call executor:** Invoke `run_direct_fix(...)` with run_id, action_id, account_id, region, action_type, role_write_arn, tenant_id. Pass the assumed session or account credentials.
- **Update run:** Set `outcome`, `logs`, `status` (success/failed), `completed_at` from executor result. Append logs to `remediation_runs.logs`. Store any structured post-check output in `artifacts` if useful.
- **Idempotency:** If run status is already success/failed, skip (per 7.3). Do not overwrite completed runs.
- **Approval:** Before enqueueing, the API (8.4) must record `approved_by_user_id`. Worker does not re-validate approval; it trusts that a run in `pending` was approved.

**Why this matters:** Step 7 defined the run model and worker hook; Step 8 completes the loop by executing real fixes when WriteRole is present and the user has approved.

**Deliverable:** Update worker job handler for `remediation_run` when `mode=direct_fix`: integrate `run_direct_fix`; add STS AssumeRole for WriteRole; handle WriteRole-missing and executor failures with clear outcomes.

---

#### 8.4 Approval workflow (backend)

**Purpose:** Before a direct fix run is enqueued, require explicit user approval. Record who approved and when. The remediation_runs table has `approved_by_user_id`; the API enforces that direct_fix runs cannot be created without approval.

**What it does:**
- **POST /api/remediation-runs** (from Step 7.2): When body includes `mode: "direct_fix"`, require an additional field: `approval_token` or `approved_by_user_id`. For MVP, resolve `approved_by_user_id` from the current JWT user (the requester is the approver). Optionally require a separate "approve" step: e.g. POST /api/remediation-runs with `mode=direct_fix` and `action_id` creates a run in `pending_approval`; a second call or separate endpoint confirms approval and moves to `pending` then enqueues. Simpler approach: single POST with `mode=direct_fix` implies the caller approves; set `approved_by_user_id` to current user, then create run and enqueue.
- **Audit:** `approved_by_user_id` and `created_at` are stored on remediation_runs. No overwrite after run completes.
- **Optional enhancement:** Separate `POST /api/actions/{id}/approve-remediation` that returns an approval token; POST remediation-runs with that token. For MVP, approval = authenticated user creating the run is sufficient.
- **Dry-run / preview:** Section D requires "Dry-run / preview output shown to user." Before approval, the UI can call a **pre-check-only** endpoint: e.g. `GET /api/actions/{id}/remediation-preview?mode=direct_fix` or `POST /api/remediation-runs/preview` with action_id. Backend runs pre-check only (no apply), returns `{ "compliant": bool, "message": str, "will_apply": bool }`. This gives users a "what will happen" before they approve.

**Why this matters:** "Approval required for any write action" is a non-negotiable safety rule. Storing approver and time supports compliance and audit.

**Deliverable:** Ensure POST /api/remediation-runs sets `approved_by_user_id` from current user for direct_fix; document approval semantics. Optional: `GET /api/actions/{id}/remediation-preview?mode=direct_fix` that runs pre-check only and returns preview.

---

#### 8.5 Frontend: Approval workflow UI (design system 3.0 + Aceternity)

**Purpose:** Users can trigger a direct fix from an action detail page, see a preview (pre-check result), confirm in a modal, and watch run progress. Uses Cold Intelligence Dark Mode, Animated Modal for confirmations, Stateful Button for submit/cancel, and Multi Step Loader (or similar) for run progress.

**What to do:**

**A) Action detail page — "Run fix" / "Apply direct fix"**
- On `/actions/[id]`, show a "Run fix" or "Apply direct fix" button **only** when the action's `action_type` is one of the three direct-fix types: `s3_block_public_access`, `enable_security_hub`, `enable_guardduty`. For the other four action types (s3_bucket_block_public_access, s3_bucket_encryption, sg_restrict_public_ports, cloudtrail_enabled), show only "Generate PR bundle." If account has no WriteRole, show Run fix button as disabled with tooltip "WriteRole not configured; add WriteRole in account settings or use Generate PR bundle."
- On click: Call `GET /api/actions/{id}/remediation-preview?mode=direct_fix` (if implemented). Display result in a small summary: "Current state: [compliant / not compliant]. This will [enable S3 Block Public Access / enable Security Hub / enable GuardDuty]."

**B) Approval modal**
- Open **Animated Modal** with: action title, account/region, fix description, pre-check result (if available), and two buttons: "Cancel" and "Approve & run."
- "Approve & run" uses **Stateful Button** (loading state during API call). On click: `POST /api/remediation-runs` with `{ "action_id": "<id>", "mode": "direct_fix" }`. On success (201), close modal and navigate to run detail or show success toast + refresh.

**C) Run progress (Multi Step Loader)**
- After creating a run, show run detail (`/remediation-runs/[id]` or inline expand). Use **Multi Step Loader** or progress indicator: Pending → Running → Success/Failed. Poll `GET /api/remediation-runs/{id}` every 2–3 seconds while status is `pending` or `running`; stop when `success` or `failed`.
- Display: status, outcome, logs (streaming or full when complete), timestamps. If failed, show error message and logs clearly.
- **On success:** Show "Next steps" (Step 9.7) — detailed guidance: for PR-only, (1) review/download generated files via "Download bundle," (2) apply in AWS (pipeline, merge PR, or manual), (3) return to the action and click **Recompute actions** (or trigger ingest) to verify; for direct fix, return to the action and click **Recompute actions**. Recompute is available on the actions list and action detail page (Step 5).

**D) PR-only remains available**
- "Generate PR bundle" button still triggers `mode=pr_only` (no WriteRole needed). Same modal pattern for confirmation if desired, or single click to create run.

**E) Design system and components**
- **Cold Intelligence Dark Mode:** Surfaces, borders, text, accent per 3.0.
- **Stateful Button** for "Approve & run," "Cancel," "Generate PR bundle."
- **Animated Modal** for approval confirmation and optional preview.
- **Multi Step Loader** for run progress (Pending → Running → Done).
- **Animated Tooltip** on disabled "Run fix" when WriteRole missing.

**Why this matters:** Phase 3 definition of done: "user can approve a safe fix and see before/after checks + logs." The UI must make approval explicit and progress visible.

**Deliverable:** Action detail page with "Run fix" (conditional on action_type and WriteRole) and "Generate PR bundle"; approval modal with pre-check summary; run progress view with polling; API client methods for preview, create run, get run. Apply design system 3.0 and Aceternity components as above.

**Error handling:** 400 (e.g. action not fixable) → show message. 404 (action/account not found) → refresh. WriteRole missing → disable button with tooltip. Run failed → show outcome and logs in run detail.

---

#### Step 8 Definition of Done

✅ WriteRole CloudFormation template created with scoped permissions for the three direct fixes (S3, Security Hub, GuardDuty); optional role_write_arn support in account API and UI  
✅ Direct fix executor: pre-check, apply, post-check for s3_block_public_access, enable_security_hub, enable_guardduty (three types only); other four action types are PR bundle only; idempotent and safe to re-run  
✅ Worker integrates direct fix: assumes WriteRole, calls executor, updates remediation_runs with outcome and logs; skips if WriteRole not configured  
✅ Approval workflow: direct_fix runs require approved_by_user_id (from current user); optional remediation-preview endpoint for pre-check only  
✅ Frontend: "Run fix" and "Generate PR bundle" on action detail; approval modal with preview; run progress with Multi Step Loader; WriteRole-missing handled with disabled button and tooltip  
✅ Design system 3.0 and Aceternity (Animated Modal, Stateful Button, Multi Step Loader, tooltips) applied to approval and run UI  
✅ User can approve a safe direct fix, see pre-check and run progress, and view outcome and logs when complete

---

### Step 9: Real PR Bundle IaC Generation per Action Type

**Purpose:** Replace the scaffold in Step 7.4 with real, applyable Terraform and CloudFormation output per action type. The PR bundle must produce IaC that users can apply in their pipeline or merge as a PR to remediate findings. This step closes the MVP gap: "PR bundle generated (scaffold)" becomes "PR bundle with real IaC."

---

#### 9.1 PR bundle service: load action and dispatch by action_type

**Purpose:** The `generate_pr_bundle` function must load the action from the database (action_type, account_id, region, target_id, control_id) and dispatch to action-type-specific generators. Unsupported action types fall back to a "pr_only" placeholder with guidance.

**What it does:**
- **Load action:** Query actions table by `action_id`; resolve `action_type`, `account_id`, `region`, `target_id`, `control_id`, `title`. If action not found, return error or generic placeholder.
- **Dispatch:** Based on `action_type`:
  - `s3_block_public_access` → Terraform/CFN for S3 account-level public access block (9.2)
  - `enable_security_hub` → Terraform/CFN for Security Hub enablement (9.3)
  - `enable_guardduty` → Terraform/CFN for GuardDuty enablement (9.4)
  - `s3_bucket_block_public_access` → Terraform/CFN for per-bucket S3 block public access (9.9)
  - `s3_bucket_encryption` → Terraform/CFN for S3 bucket encryption (9.10)
  - `sg_restrict_public_ports` → Terraform/CFN for SG restrict public ports 22/3389 (9.11)
  - `cloudtrail_enabled` → Terraform/CFN for CloudTrail enabled (9.12)
  - `pr_only` or unmapped → Return a guidance placeholder: "This action type does not yet have IaC generation. Apply the fix manually in AWS Console or use direct fix if supported."
- **Dependency:** Worker already loads the run (with `action` relationship via `selectinload`). Worker passes `run.action` to `generate_pr_bundle`; pr_bundle service receives action object (no DB access needed in pr_bundle).

**Deliverable:** Refactor `generate_pr_bundle(action_id, format)` to `generate_pr_bundle(action, format)` where `action` has `action_type`, `account_id`, `region`, `target_id`, `title`, `control_id`. Worker passes `run.action` (ensure run is loaded with `selectinload(RemediationRun.action)`). **Dispatch list extended to all 7 types with subsection refs (9.2–9.5, 9.9–9.12).** Add generators for **all 7** action types (`_generate_for_s3`, `_generate_for_security_hub`, `_generate_for_guardduty`, `_generate_for_s3_bucket_block_public_access`, `_generate_for_s3_bucket_encryption`, `_generate_for_sg_restrict_public_ports`, `_generate_for_cloudtrail_enabled`) and a fallback for unknown types. **Deliverable: all 7 generators.**

---

#### 9.2 Terraform: S3 Block Public Access (action_type: s3_block_public_access)

**Purpose:** Generate Terraform that enables account-level S3 Block Public Access. Mirrors the direct fix logic in Step 8.2.

**What it does:**
- **Scope:** Account-level; `region` is not used for the resource (S3 Control API is account-level).
- **Resource:** `aws_s3_account_public_access_block` (HashiCorp AWS provider).
- **File:** `s3_block_public_access.tf` or `main.tf` (if single-file bundle).

**Terraform content (exact structure):**
```hcl
# S3 Block Public Access (account-level) - Action: {action_id}
# Remediation for: {action_title}
# Account: {account_id}
# Control: {control_id}

resource "aws_s3_account_public_access_block" "security_autopilot" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

- **Provider:** Must use `aws` provider; account/region from user's Terraform backend. Add a `providers.tf` or comment if needed: "Configure AWS provider with credentials for account {account_id}."
- **Steps (for `steps` array):**
  1. "Ensure AWS provider is configured for account {account_id}."
  2. "Run `terraform init` and `terraform plan` to preview changes."
  3. "Run `terraform apply` to enable S3 Block Public Access."
  4. "Return to the action and click **Recompute actions** or trigger ingest to verify the finding is resolved."

---

#### 9.3 Terraform: Security Hub enablement (action_type: enable_security_hub)

**Purpose:** Generate Terraform that enables Security Hub in the specified region.

**What it does:**
- **Scope:** Per region; `region` is required. Use `provider "aws" { region = "{region}" }` or equivalent.
- **Resource:** `aws_securityhub_account` (HashiCorp AWS provider). Optionally `aws_securityhub_standards_subscription` for FSBP/CIS if desired; MVP can start with account only.

**Terraform content:**
```hcl
# Security Hub enablement - Action: {action_id}
# Remediation for: {action_title}
# Account: {account_id} | Region: {region}
# Control: {control_id}

resource "aws_securityhub_account" "security_autopilot" {}
```

- **Provider:** Region must be `{region}`. Add provider block or `terraform { required_providers { aws = { ... } } }` and ensure region is set.
- **Steps:**
  1. "Configure AWS provider for account {account_id} and region {region}."
  2. "Run `terraform init` and `terraform plan`."
  3. "Run `terraform apply` to enable Security Hub."
  4. "Return to the action and click **Recompute actions** or trigger ingest to verify."

---

#### 9.4 Terraform: GuardDuty enablement (action_type: enable_guardduty)

**Purpose:** Generate Terraform that enables GuardDuty in the specified region.

**What it does:**
- **Scope:** Per region; `region` is required.
- **Resource:** `aws_guardduty_detector` with `enable = true`.

**Terraform content:**
```hcl
# GuardDuty enablement - Action: {action_id}
# Remediation for: {action_title}
# Account: {account_id} | Region: {region}
# Control: {control_id}

resource "aws_guardduty_detector" "security_autopilot" {
  enable = true
}
```

- **Steps:** Same pattern as Security Hub (configure provider, init, plan, apply, Recompute).

---

#### 9.5 CloudFormation: All seven action types

**Purpose:** For users who prefer CloudFormation, generate equivalent templates for **all 7** in-scope action types. Step 9.5 is explicitly named "All seven action types" and CloudFormation is described (and implemented) for every type, including those defined in 9.9–9.12.

**What it does (CloudFormation for all 7):**
- **s3_block_public_access (9.2):** Account-level S3 block; CloudFormation has no native account-level resource. Template uses valid YAML with placeholder resource and Description/Metadata instructing use of Terraform or AWS CLI (`aws s3control put-public-access-block`). File: `s3_block_public_access.yaml`.
- **enable_security_hub (9.3):** `AWS::SecurityHub::Hub`; per region. File: `enable_security_hub.yaml`.
- **enable_guardduty (9.4):** `AWS::GuardDuty::Detector` with `Enable: true`; per region. File: `enable_guardduty.yaml`.
- **s3_bucket_block_public_access (9.9):** `AWS::S3::Bucket` with `PublicAccessBlockConfiguration` (BlockPublicAcls, BlockPublicPolicy, IgnorePublicAcls, RestrictPublicBuckets). Parameter: BucketName (target_id). File: `s3_bucket_block_public_access.yaml`. For existing buckets, Terraform preferred.
- **s3_bucket_encryption (9.10):** `AWS::S3::Bucket` with `BucketEncryption` / `ServerSideEncryptionConfiguration` (AES256). Parameter: BucketName. File: `s3_bucket_encryption.yaml`.
- **sg_restrict_public_ports (9.11):** `AWS::EC2::SecurityGroupIngress` for SSH (22) and RDP (3389) with parameterized CIDR (e.g. 10.0.0.0/8). Parameters: SecurityGroupId, AllowedCidr. File: `sg_restrict_public_ports.yaml`. User must remove existing 0.0.0.0/0 rules first.
- **cloudtrail_enabled (9.12):** `AWS::CloudTrail::Trail` with `IsMultiRegionTrail: true`, `IncludeGlobalServiceEvents: true`. Parameter: TrailBucketName (S3 bucket for logs). File: `cloudtrail_enabled.yaml`.

All templates are valid YAML and applyable (or documented placeholder where CF has no resource).

**Deliverable:** CloudFormation generators for **all 7** action types (9.2–9.5 for the first three; 9.9–9.12 for the remaining four). Each returns `{ "path": "template.yaml", "content": "..." }`. Implemented in `pr_bundle.py` as `_cloudformation_s3_content`, `_cloudformation_security_hub_content`, `_cloudformation_guardduty_content`, `_cloudformation_s3_bucket_block_content`, `_cloudformation_s3_bucket_encryption_content`, `_cloudformation_sg_restrict_content`, `_cloudformation_cloudtrail_content`.

---

#### 9.6 PR bundle download (API + UI)

**Purpose:** Users need to download the generated files to apply them in their pipeline. Display in UI is not enough for pipeline integration.

**What it does:**
- **Option A — Inline in artifacts:** Files are already in `remediation_runs.artifacts.pr_bundle.files`. Add `GET /api/remediation-runs/{id}/pr-bundle.zip` that returns a zip of all files. Or add a "Download as ZIP" button in the UI that builds the zip client-side from artifacts.
- **Option B — S3 presigned URL:** For large bundles, write files to S3 (e.g. `exports/{tenant_id}/{run_id}/pr-bundle.zip`), store key in artifacts, and expose `GET /api/remediation-runs/{id}/pr-bundle-download-url` returning a presigned URL.
- **MVP:** Client-side zip from artifacts is sufficient: UI has "Download bundle" button that fetches run, extracts `artifacts.pr_bundle.files`, builds a zip blob, and triggers download. No new API required.
- **UI:** On run detail page (and in RemediationRunProgress when status=success and mode=pr_only), show "Download bundle" button. Click → download `pr-bundle-{run_id}.zip` with files at root (e.g. `main.tf`, `s3_block_public_access.tf`).

**Deliverable:** Frontend "Download bundle" button that creates and downloads a zip from `run.artifacts.pr_bundle.files`. Optional: backend `GET /api/remediation-runs/{id}/pr-bundle.zip` for server-side zip if client-side is not desired.

---

#### 9.7 Next steps UI (already implemented; verify and document)

**Purpose:** When a remediation run completes (success), the UI must show "Next steps" so the user knows what to do after the run. This was added in a prior task; ensure it is documented and consistent with Step 9 output.

**What it does:**
- **PR-only success:** Show "Next steps" with detailed guidance:
  1. **Review and download the generated files:** Use the **"Download bundle"** button on this run detail page (or in your pipeline) to get a zip of the IaC files (e.g. Terraform `.tf` or CloudFormation `.yaml`). Open the files locally and review resources, variables, and target IDs (e.g. bucket name, security group ID) to ensure they match your environment before applying.
  2. **Apply the changes in AWS:** Choose one: **Pipeline** (see steps below for Terraform or CloudFormation), **Merge PR** — if you opened a PR from the bundle, review, merge, and let the pipeline apply using the same steps, or **Manual** — run `terraform init`, `terraform plan`, and `terraform apply` (or CloudFormation validate/deploy) in the account and region for this action.
  3. **Verify the finding is resolved:** Return to the action (link) and click **Recompute actions** (or trigger a fresh ingest) so action status refreshes and you can confirm the finding is no longer open.
- **How to apply with a pipeline (Terraform)** — written for first-time users:
  1. **What Terraform is:** A tool that creates or updates cloud resources from `.tf` files.
  2. Download the bundle and unzip it; you should see `.tf` files (e.g. `main.tf`, `providers.tf`).
  3. Install Terraform on the machine that runs your pipeline (e.g. [install guide](https://developer.hashicorp.com/terraform/install)).
  4. Put the unzipped files into your infrastructure Git repo — e.g. create a new branch, add the files, commit and push.
  5. In your CI/CD pipeline (GitHub Actions, GitLab CI, AWS CodePipeline, etc.), configure the job to use the **same AWS account and region** as this action (set credentials and `AWS_REGION` or `TF_VAR_region`).
  6. In the pipeline, run in order: `terraform init` (downloads providers), `terraform plan` (shows what will change), then `terraform apply -auto-approve` (applies changes). Optionally add a manual approval step between plan and apply.
  7. Trigger the pipeline (push or merge) so it runs in that account and region.
- **How to apply with a pipeline (CloudFormation)** — written for first-time users:
  1. **What CloudFormation is:** An AWS service that creates or updates resources from a YAML or JSON template.
  2. Download the bundle and unzip it; you should see `.yaml` template(s) (e.g. `s3_bucket_block_public_access.yaml`).
  3. Install the AWS CLI on the machine that runs your pipeline (e.g. [install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)). Configure credentials for the **account and region** for this action.
  4. Put the template(s) into your infrastructure repo (or upload to S3 and use `--template-url`).
  5. In your CI/CD pipeline, set AWS credentials and region for this action, then run: `aws cloudformation validate-template --template-body file://<template>.yaml` to check syntax.
  6. Then run `aws cloudformation create-stack` (new stack) or `update-stack` (existing stack) with `--template-body file://<template>.yaml` and `--parameters ParameterKey=BucketName,ParameterValue=...` (or other parameters the template needs). Use pipeline secrets or a parameters file for values.
  7. Trigger the pipeline (push or merge) so it runs in that account and region.
- **How to apply via Merge PR** — written for first-time users:
  1. **What a PR is:** A Pull Request (or Merge Request) proposes changes for review before merging into your main branch.
  2. Download the bundle and unzip it; create a new branch in your infrastructure repo (e.g. `git checkout -b fix-remediation`).
  3. Copy the unzipped files into the repo folder, then `git add .` and `git commit -m "Apply remediation from AWS Security Autopilot"`.
  4. Push the branch (e.g. `git push -u origin fix-remediation`).
  5. In GitHub, GitLab, or Bitbucket, open a new Pull Request / Merge Request from this branch to your main (or default) branch. In the description, note that this applies the remediation for this action.
  6. After review and approval, merge the PR. The branch you merge into should already have a pipeline that runs Terraform or CloudFormation (see Pipeline tabs). If you don't have a pipeline yet, set one up using the Pipeline (Terraform) or Pipeline (CloudFormation) steps, then merge so the pipeline runs. Ensure the pipeline uses the **same AWS account and region** as this action.
- **How to apply manually** — written for first-time users:
  1. **Terraform:** Install Terraform ([install guide](https://developer.hashicorp.com/terraform/install)). Download and unzip the bundle. Open a terminal in the folder with the `.tf` files. Set AWS credentials and region (`export AWS_PROFILE=...`, `export AWS_REGION=...`, or `aws configure`). Run `terraform init`, then `terraform plan`, then `terraform apply` (type `yes` when prompted, or use `-auto-approve`).
  2. **CloudFormation:** Install the AWS CLI and configure credentials for this action's account and region ([quickstart](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html)). Download and unzip the bundle. Run `aws cloudformation validate-template --template-body file://<template>.yaml`, then `aws cloudformation create-stack --stack-name <name> --template-body file://<template>.yaml --parameters ParameterKey=...,ParameterValue=...` (fill parameters from the template). For an existing stack use `update-stack`. Alternatively, in the AWS Console: **CloudFormation → Stacks → Create stack**, upload the template, and enter the required parameters.
- **Direct fix success:** Show "Next steps" with: Return to the action (link) and click **Recompute actions** (or trigger ingest) to refresh action status and verify the finding is resolved.
- **Recompute actions:** The actions page must have a "Recompute actions" button (or equivalent) that calls `POST /api/actions/compute` (or ingest) so the user can refresh action status after applying fixes. Step 5 defines this as **required for MVP**; ensure it exists on the actions list and/or action detail page.

**Deliverable:** Document in Step 9; ensure Step 5 and Step 8.5 reference "Recompute actions" as part of the flow. No code change if already implemented.

**Step 9.7 Implementation (verified):**
- **Next steps:** Implemented in `frontend/src/components/RemediationRunProgress.tsx`. When `run.status === 'success'` and `!compact`, a "Next steps" section is shown:
  - **PR-only:** Ordered list with detailed copy: (1) Review and download — use "Download bundle" on this page or in pipeline to get the zip; open files and review resources, variables, and target IDs before applying. (2) Apply in AWS — **Aceternity-style Tabs** (one tab per method): **Pipeline (Terraform)**, **Pipeline (CloudFormation)**, **Merge PR**, **Manual**; each tab shows **first-time-user** step-by-step instructions (what the tool is, install links, repo/pipeline setup, commands in order, account/region). (3) Verify — return to the action (link) and click **Recompute actions** or trigger ingest to refresh status and confirm the finding is resolved.
  - **Direct fix:** Single paragraph: Return to the action (link) and click **Recompute actions** or trigger ingest to refresh action status and verify the finding is resolved.
- **Recompute actions:** Implemented in Step 5 and used in the remediation flow.
  - **Actions list:** `frontend/src/app/actions/page.tsx` — "Recompute actions" button calls `POST /api/actions/compute` via `triggerComputeActions()`, then refetches list after 2s.
  - **Action detail:** `frontend/src/app/actions/[id]/page.tsx` — "Recompute actions" button same behavior; user returns here from run detail via Next steps link.
- **Flow:** Run detail (`/remediation-runs/[id]`) and inline RemediationRunProgress (e.g. in modal) both show Next steps with link to the action; user clicks "Recompute actions" on list or detail to refresh action status after applying fixes.

---

#### 9.8 In-scope controls: control_id mapping and PR bundle coverage

**Purpose:** Ensure every in-scope Security Hub control gets real IaC (no `pr_only` / README.tf fallback). In-scope = **7 real action types** the product commits to supporting with automatic PR bundle generation (and direct fix where applicable).

**MVP in-scope action types (7):**

| action_type | control_id(s) | Direct fix | PR bundle | Subsection |
|-------------|---------------|------------|-----------|------------|
| s3_block_public_access | S3.1 | Y | Y | 9.2, 9.5 |
| enable_security_hub | SecurityHub.1 | Y | Y | 9.3, 9.5 |
| enable_guardduty | GuardDuty.1 | Y | Y | 9.4, 9.5 |
| s3_bucket_block_public_access | S3.2 | N | Y | 9.9, 9.5 |
| s3_bucket_encryption | S3.4 | N | Y | 9.10, 9.5 |
| sg_restrict_public_ports | EC2.18 (or FSBP equivalent) | N | Y | 9.11, 9.5 |
| cloudtrail_enabled | CloudTrail.1 | N | Y | 9.12, 9.5 |
| pr_only | (unmapped / out-of-scope) | N | guidance only | 9.1 fallback |

**What it does:**
- **Define in-scope control list:** The table above is the MVP in-scope list. Implemented in `backend/services/control_scope.py`: `IN_SCOPE_CONTROLS` (typed list), `CONTROL_TO_ACTION_TYPE` (canonical mapping), `IN_SCOPE_CONTROL_IDS`, `action_type_from_control()`. Each in-scope control maps to one `action_type`.
- **Control_id → action_type mapping:** `backend/services/action_engine.py` imports `CONTROL_TO_ACTION_TYPE` and `action_type_from_control` from `control_scope`; the mapping is the single source of truth in control_scope. Every control_id in the table maps to its action_type.
- **PR bundle generators:** For each of the 7 action types, a generator exists in `backend/services/pr_bundle.py` and is registered in the dispatch (9.1). Resource-level actions (S3 bucket, SG) use `action.target_id` / `resource_id` to produce IaC for that resource. Tests in `tests/test_control_scope.py` assert every in-scope action_type is in `pr_bundle.SUPPORTED_ACTION_TYPES`.
- **Process for new controls:** When adding a new in-scope control: (1) add control_id and row to `control_scope.IN_SCOPE_CONTROLS` and ensure `CONTROL_TO_ACTION_TYPE` includes it; (2) if action_type is new, implement generator in pr_bundle (9.9-style); if existing, no code change.

**Deliverable:** In-scope control list in `backend/services/control_scope.py` (table above); `CONTROL_TO_ACTION_TYPE` used by action_engine for all 7 types; generators for all 7 (9.2–9.5, 9.9–9.12) in pr_bundle. Unsupported (out-of-scope) controls continue to receive guidance placeholder. Tests: `tests/test_control_scope.py` (Step 9.8).

---

#### 9.9 Terraform + CloudFormation: S3 bucket-level block public access (action_type: s3_bucket_block_public_access, control_id: S3.2)

**Purpose:** Generate Terraform/CloudFormation for per-bucket S3 block public access (e.g. finding "S3 general purpose buckets should block public read access"). One bucket per action; use `target_id` or `resource_id` to identify the bucket.

**What it does:**
- **Scope:** Per bucket; `region` and `resource_id` (bucket name/ARN) from action. Security Hub control **S3.2** maps to `s3_bucket_block_public_access` in control_scope (9.8); action_engine uses that mapping.
- **Terraform:** `aws_s3_bucket_public_access_block` (HashiCorp AWS provider) for the bucket identified by action (target_id). `block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets` = true. File: `s3_bucket_block_public_access.tf` + `providers.tf`.
- **CloudFormation:** `AWS::S3::Bucket` with `PublicAccessBlockConfiguration` (BlockPublicAcls, BlockPublicPolicy, IgnorePublicAcls, RestrictPublicBuckets). Parameter: BucketName (target_id). File: `s3_bucket_block_public_access.yaml`. For existing buckets, Terraform preferred.
- **Steps:** Configure provider for account and region; set bucket name (target_id); init/plan/apply (Terraform) or validate/deploy (CloudFormation); Recompute actions to verify.

**Deliverable:** `s3_bucket_block_public_access` in control_scope (9.8) with control_id S3.2; `_generate_for_s3_bucket_block_public_access` in pr_bundle (Terraform + CloudFormation); Terraform uses aws_s3_bucket_public_access_block; CloudFormation valid YAML and applyable.

**Step 9.9 Implementation (verified):**
- **control_scope (9.8):** S3.2 → s3_bucket_block_public_access; pr_bundle True; direct_fix False.
- **pr_bundle:** `_generate_for_s3_bucket_block_public_access`; Terraform `aws_s3_bucket_public_access_block` with block_public_acls, block_public_policy, ignore_public_acls, restrict_public_buckets; CloudFormation `AWS::S3::Bucket` with PublicAccessBlockConfiguration.
- **Tests:** test_pr_bundle_dispatch_s3_bucket_block_terraform_step_9_9; test_pr_bundle_s3_bucket_block_terraform_step_9_9_exact_structure; test_pr_bundle_s3_bucket_block_cloudformation_step_9_9.

---

#### 9.10 Terraform + CloudFormation: S3 bucket encryption (action_type: s3_bucket_encryption, control_id: S3.4)

**Purpose:** Generate Terraform/CloudFormation for S3 bucket default encryption (e.g. finding "S3 general purpose buckets should have default encryption enabled"). One bucket per action; use `target_id` or `resource_id` to identify the bucket.

**What it does:**
- **Scope:** Per bucket; `region` and `resource_id` (bucket name/ARN) from action. Security Hub control **S3.4** maps to `s3_bucket_encryption` in control_scope (9.8); action_engine uses that mapping.
- **Terraform:** `aws_s3_bucket_server_side_encryption_configuration` (HashiCorp AWS provider) for the bucket; `apply_server_side_encryption_by_default` with `sse_algorithm = "AES256"`; `bucket_key_enabled = true`. File: `s3_bucket_encryption.tf` + `providers.tf`.
- **CloudFormation:** `AWS::S3::Bucket` with `BucketEncryption` / `ServerSideEncryptionConfiguration` (AES256, BucketKeyEnabled). Parameter: BucketName (target_id). File: `s3_bucket_encryption.yaml`.
- **Steps:** Configure provider for account and region; set bucket name (target_id); init/plan/apply (Terraform) or validate/deploy (CloudFormation); Recompute actions to verify.

**Deliverable:** `s3_bucket_encryption` in control_scope (9.8) with control_id S3.4; `_generate_for_s3_bucket_encryption` in pr_bundle (Terraform + CloudFormation); Terraform uses AES256; CloudFormation valid YAML and applyable.

**Step 9.10 Implementation (verified):**
- **control_scope (9.8):** S3.4 → s3_bucket_encryption; pr_bundle True.
- **pr_bundle:** `_generate_for_s3_bucket_encryption`; Terraform `aws_s3_bucket_server_side_encryption_configuration` with AES256 and bucket_key_enabled; CloudFormation `AWS::S3::Bucket` with BucketEncryption / ServerSideEncryptionConfiguration.
- **Tests:** test_pr_bundle_dispatch_s3_bucket_encryption_terraform_step_9_10; test_pr_bundle_s3_bucket_encryption_terraform_exact_structure (Step 9.10); test_pr_bundle_s3_bucket_encryption_cloudformation_step_9_10.

---

#### 9.11 Terraform + CloudFormation: SG restrict public ports (action_type: sg_restrict_public_ports, control_id: EC2.18)

**Purpose:** Generate Terraform/CloudFormation to restrict security group rules that allow 0.0.0.0/0 on ports 22 (SSH) and 3389 (RDP). One SG per action; use `target_id` / `resource_id`. Optional allowlist for permitted CIDRs (document in steps).

**What it does:**
- **Scope:** Per security group; `region` and `resource_id` (SG ID/ARN) from action. Security Hub control **EC2.18** (FSBP: "EC2 security groups should not allow unrestricted SSH/RDP") maps to `sg_restrict_public_ports` in control_scope (9.8); action_engine uses that mapping.
- **Terraform:** `aws_vpc_security_group_ingress_rule` for ports 22 (SSH) and 3389 (RDP) with parameterized CIDR (variables `security_group_id`, `allowed_cidr` default "10.0.0.0/8"). User must remove existing 0.0.0.0/0 rules first. File: `sg_restrict_public_ports.tf` + `providers.tf`.
- **CloudFormation:** `AWS::EC2::SecurityGroupIngress` for SSH (22) and RDP (3389) with parameterized CIDR. Parameters: SecurityGroupId, AllowedCidr (default "10.0.0.0/8"). User must remove existing 0.0.0.0/0 rules first. File: `sg_restrict_public_ports.yaml`.
- **Steps:** Configure provider for account and region; remove existing 0.0.0.0/0 rules for 22/3389 (Console or CLI); set security_group_id and allowed_cidr; init/plan/apply (Terraform) or validate/deploy (CloudFormation); Recompute actions to verify.

**Deliverable:** `sg_restrict_public_ports` in control_scope (9.8) with control_id EC2.18; `_generate_for_sg_restrict_public_ports` in pr_bundle (Terraform + CloudFormation); Terraform uses `aws_vpc_security_group_ingress_rule` with variables; CloudFormation valid YAML and applyable.

**Step 9.11 Implementation (verified):**
- **control_scope (9.8):** EC2.18 → sg_restrict_public_ports; pr_bundle True; direct_fix False (optional later with strict allowlist, Step 8 extension).
- **pr_bundle:** `_generate_for_sg_restrict_public_ports`; Terraform `aws_vpc_security_group_ingress_rule` for SSH (22) and RDP (3389) with variables; CloudFormation `AWS::EC2::SecurityGroupIngress` with parameters.
- **Tests:** test_pr_bundle_dispatch_sg_restrict_terraform_step_9_11; test_pr_bundle_sg_restrict_terraform_exact_structure (Step 9.11); test_pr_bundle_sg_restrict_cloudformation_step_9_11.

---

#### 9.12 Terraform + CloudFormation: CloudTrail enabled (action_type: cloudtrail_enabled, control_id: CloudTrail.1)

**Purpose:** Generate Terraform/CloudFormation so CloudTrail is enabled (e.g. finding "CloudTrail should be enabled"). Account-level or multi-region trail per product requirements.

**What it does:**
- **Scope:** Account-level or per region; `region` from action. Security Hub control **CloudTrail.1** maps to `cloudtrail_enabled` in control_scope (9.8); action_engine uses that mapping.
- **Terraform:** `aws_cloudtrail` (HashiCorp AWS provider) with `is_multi_region_trail = true`, `include_global_service_events = true`, `enable_logging = true`; variable `trail_bucket_name` (S3 bucket for logs). File: `cloudtrail_enabled.tf` + `providers.tf`.
- **CloudFormation:** `AWS::CloudTrail::Trail` with `IsMultiRegionTrail: true`, `IncludeGlobalServiceEvents: true`; parameter `TrailBucketName` (S3 bucket for logs). File: `cloudtrail_enabled.yaml`.
- **Steps:** Configure provider for account and region; create or identify S3 bucket for trail logs; set trail_bucket_name (Terraform) or TrailBucketName (CloudFormation); init/plan/apply (Terraform) or validate/deploy (CloudFormation); Recompute actions to verify.

**Deliverable:** `cloudtrail_enabled` in control_scope (9.8) with control_id CloudTrail.1; `_generate_for_cloudtrail_enabled` in pr_bundle (Terraform + CloudFormation); Terraform uses aws_cloudtrail with multi-region and logging; CloudFormation valid YAML and applyable.

**Step 9.12 Implementation (verified):**
- **control_scope (9.8):** CloudTrail.1 → cloudtrail_enabled; pr_bundle True; direct_fix False.
- **pr_bundle:** `_generate_for_cloudtrail_enabled`; Terraform `aws_cloudtrail` with is_multi_region_trail, s3_bucket_name, enable_logging; CloudFormation `AWS::CloudTrail::Trail` with IsMultiRegionTrail, S3BucketName parameter.
- **Tests:** test_pr_bundle_dispatch_cloudtrail_terraform_step_9_12; test_pr_bundle_cloudtrail_terraform_step_9_12_exact_structure; test_pr_bundle_cloudtrail_cloudformation_step_9_12.

---

#### Step 9 Definition of Done

✅ `generate_pr_bundle` loads action and dispatches by action_type; scaffold replaced with real generators  
✅ Terraform generated for **all 7** action types (s3_block_public_access, enable_security_hub, enable_guardduty, s3_bucket_block_public_access, s3_bucket_encryption, sg_restrict_public_ports, cloudtrail_enabled) with correct resources and provider hints  
✅ **Step 9.5 "All seven action types":** CloudFormation described and implemented for all 7 (9.2–9.5 for first three; 9.9–9.12 for remaining four); valid, applyable YAML  
✅ Unsupported action types return guidance placeholder (not generic "Real IaC TBD")  
✅ PR bundle files include action metadata (title, account_id, region, control_id) in comments  
✅ "Download bundle" button in UI creates and downloads zip of generated files  
✅ "Next steps" and "Recompute actions" are documented and available in the remediation flow  
✅ User can generate a PR bundle, download it, apply in Terraform/CloudFormation, and verify via Recompute  
✅ In-scope control list (7 action types) documented in 9.8 table; control_id → action_type mapping extended for all 7 in action_engine  
✅ All 7 in-scope action types have PR bundle generators (9.2–9.5, 9.9–9.12) so in-scope findings get real IaC, not README.tf

---

### Step 10: Evidence Export v1 (CSV/JSON zip to S3)

This step adds the evidence pack export for compliance and audit. Users can trigger an export that bundles findings, actions, remediation run history, and exceptions into a zip (CSV + JSON), uploads it to S3, and provides a download link. This fulfills Phase 4: "evidence pack export to S3" and the MVP promise of "audit-ready evidence" and "exception governance" for SOC 2 / ISO readiness.

---

#### 10.1 Create exports model (migration)

**Purpose:** Define the database schema for export jobs—one row per evidence pack export request. Each row tracks who requested it, status (pending → running → success/failed), and where the result lives (S3 key or download URL). This table enables the API to enqueue an export, return an export id, and let the frontend poll for status and download.

**What it does:**
- Creates an `exports` table (or `evidence_exports` to avoid reserved word) that stores one row per export job
- Links to tenant and optionally the user who requested the export
- Records status (pending, running, success, failed), timestamps (created_at, completed_at), and result location (s3_key or download_url)
- Enforces multi-tenant isolation via `tenant_id`
- Indexes support "list exports for tenant" and "get export by id" queries

**Table: evidence_exports** (or `exports` if preferred; some ORMs allow reserved words)

**Columns:**

**Primary key and tenant isolation:**
- `id` (UUID, primary key)
- `tenant_id` (UUID, foreign key to tenants, NOT NULL)

**Status and outcome:**
- `status` (enum: pending, running, success, failed, NOT NULL) - Current state of the export job
- `requested_by_user_id` (UUID, foreign key to users, nullable) - Who triggered the export (from JWT)
- `started_at` (timestamp with timezone, nullable) - When the worker started processing
- `completed_at` (timestamp with timezone, nullable) - When the job finished (success or failed)
- `error_message` (string(1000), nullable) - If failed, short reason (e.g. "S3 upload failed")

**Result (when success):**
- `s3_bucket` (string(255), nullable) - Bucket name (from config; stored for audit)
- `s3_key` (string(512), nullable) - Object key (e.g. `exports/{tenant_id}/{export_id}/evidence-pack.zip`)
- `file_size_bytes` (bigint, nullable) - Size of the zip for display
- `expires_at` (timestamp with timezone, nullable) - When a presigned URL (if stored) expires; or generate on demand

**Metadata:**
- `created_at` (timestamp with timezone, NOT NULL)
- `updated_at` (timestamp with timezone, NOT NULL)

**Indexes:**
- `idx_evidence_exports_tenant` on `(tenant_id)` - List exports for tenant
- `idx_evidence_exports_tenant_created` on `(tenant_id, created_at DESC)` - Recent exports
- `idx_evidence_exports_status` on `(tenant_id, status)` - Filter by pending/running/success/failed

**Why this matters:** The frontend needs a stable export id to poll status and show a download link. Without a table, you cannot track multiple export requests per tenant or retry cleanly.

**Deliverable:** Alembic migration; SQLAlchemy model in `backend/models/evidence_export.py` (or `export.py`). Use a table name that is not the SQL reserved word `EXPORT` if the DB or ORM complains; `evidence_exports` is safe.

---

#### 10.2 Export content specification (what goes in the pack)

**Purpose:** Define exactly which data is included in the evidence pack and in what format (CSV and/or JSON per entity type). Auditors and compliance workflows need findings, actions, remediation history, and exceptions with timestamps and approvals.

**What it does:**

**Files in the zip bundle (v1):**

1. **manifest.json** (required)
   - `export_id`, `tenant_id`, `export_created_at` (ISO8601), `requested_by` (user email or id)
   - `files`: list of `{ "name": "findings.csv", "rows": N, "description": "..." }`
   - Optional: `control_scope`: note that control_id in findings/actions maps to Security Hub / CIS controls for auditor reference

2. **findings.csv** (and optionally findings.json)
   - Columns: id, finding_id, account_id, region, severity, status, control_id, title, resource_id, resource_type, first_observed_at, updated_at, created_at (or subset; include at least severity, control_id, title, resource_id, status, updated_at for audit)
   - One row per finding for the tenant; filter by tenant_id
   - Optional: include raw_json path or a separate findings_raw.json for full Security Hub payload

3. **actions.csv** (and optionally actions.json)
   - Columns: id, action_type, target_id, account_id, region, priority, status, title, control_id, resource_id, created_at, updated_at, finding_count (or subset)
   - One row per action for the tenant

4. **remediation_runs.csv** (and optionally remediation_runs.json)
   - Columns: id, action_id, mode, status, outcome, approved_by_user_id, started_at, completed_at, created_at (or subset; include mode, status, outcome, completed_at for audit)
   - One row per remediation run for the tenant

5. **exceptions.csv** (and optionally exceptions.json)
   - Columns: id, entity_type, entity_id, reason, approved_by_user_id, expires_at, ticket_link, created_at (or subset; include reason, approved_by, expires_at for audit)
   - One row per exception (active and expired) for the tenant

**Format rules:**
- CSV: header row; escape commas and newlines in fields; use a consistent encoding (UTF-8)
- JSON: array of objects; same field names as CSV columns for consistency
- For MVP, CSV-only is acceptable if JSON is deferred; plan suggests "CSV/JSON + zipped" so at least one of each entity type (CSV preferred for spreadsheets, JSON for tooling)

**Control/framework mapping (v1):**
- In manifest or a short README.txt in the zip, state that `control_id` in findings and actions corresponds to Security Hub control IDs (e.g. CIS AWS Foundations Benchmark, FSBP). No need for a full SOC 2 control matrix in v1; a one-line note suffices for "auditor-ready" clarity.

**Why this matters:** Evidence pack content is the core of the compliance deliverable. A clear spec ensures the worker generates consistent, complete bundles and auditors know what each file contains.

**Deliverable:** Document in implementation plan and/or `backend/services/evidence_export.py` docstring: list of files, column names per entity, manifest schema. Implement in 10.3.

---

#### 10.3 Export worker (generate + zip + S3 upload)

**Purpose:** When an export job is enqueued, the worker loads tenant data (findings, actions, remediation_runs, exceptions), generates the CSV/JSON files per 10.2, zips them, uploads to S3, and updates the export row with status and S3 key.

**What it does:**
- **Job type:** `generate_export` (or `evidence_export`). Use existing SQS pattern (e.g. ingest queue with job_type or a dedicated exports queue).
- **Message format:**
  ```json
  {
    "job_type": "generate_export",
    "export_id": "uuid",
    "tenant_id": "uuid",
    "created_at": "2026-02-02T10:00:00Z"
  }
  ```
- **Worker handler:**
  1. Load `evidence_exports` row by `export_id`; verify tenant and status is `pending`. If not pending, skip (idempotency).
  2. Set `status = running`, `started_at = now()`, save.
  3. Query DB for tenant: findings (all), actions (all), remediation_runs (all), exceptions (all). Use tenant_id; no pagination for MVP (if tenant has very large data, add limits or chunking later).
  4. Generate in-memory files per 10.2: manifest.json, findings.csv, actions.csv, remediation_runs.csv, exceptions.csv (and optional .json variants). Build zip in memory (e.g. Python `zipfile.ZipFile` with `BytesIO`).
  5. Upload zip to S3: bucket from config (`S3_EXPORT_BUCKET`); key = `exports/{tenant_id}/{export_id}/evidence-pack.zip` (tenant-scoped path). Use boto3 `put_object` or upload_fileobj; set Content-Type `application/zip`.
  6. Update export row: `status = success`, `completed_at = now()`, `s3_bucket`, `s3_key`, `file_size_bytes` (from zip size). Clear any previous error_message.
  7. On exception: set `status = failed`, `error_message = str(e)[:1000]`, `completed_at = now()`, save.
- **Idempotency:** If status is already success/failed, do not overwrite. If the same export_id is processed twice (retry), no-op once completed.

**Why this matters:** The worker is the single place that produces the evidence pack. Decoupling from the API keeps export generation async and avoids timeouts for large tenants.

**Deliverable:** Worker job handler for `generate_export` in `worker/jobs/` (e.g. `evidence_export.py` or under existing ingest/worker module); service layer `backend/services/evidence_export.py` (or `worker/services/evidence_export.py`) with `generate_evidence_pack(tenant_id, export_id)` that performs queries, file generation, zip, and S3 upload. Use config `S3_EXPORT_BUCKET`; if empty, fail export with clear error "S3 export bucket not configured."

---

#### 10.4 Export API endpoints

**Purpose:** Let the frontend request an evidence export (enqueue job) and poll for status and download URL.

**Endpoints:**

**POST /api/exports** (or POST /api/evidence-exports)
- **Body:** Empty or `{}` (optional: `format` or `scope` for future use).
- **What it does:** Resolve tenant from JWT. Require authenticated user. Create `evidence_exports` row with `status = pending`, `requested_by_user_id = current user`. Enqueue `generate_export` job with export_id, tenant_id. Return created export with id and status.
- **Response (202 Accepted):** `{ "id": "uuid", "status": "pending", "created_at": "...", "message": "Export job queued" }`
- **Auth:** Tenant-scoped; require authenticated user
- **Error handling:** SQS send failure → 503; S3_EXPORT_BUCKET not set → 503 or 400 with message "Evidence export not configured"

**GET /api/exports/{id}** (or GET /api/evidence-exports/{id})
- **What it does:** Resolve tenant from JWT or query. Load export by id and tenant_id. Return status, created_at, started_at, completed_at, error_message (if failed), and when status is success: download_url (presigned URL) or s3_bucket + s3_key with instruction to use a separate download endpoint).
- **Response (200):** `{ "id": "uuid", "status": "pending" | "running" | "success" | "failed", "created_at": "...", "started_at": "...", "completed_at": "...", "error_message": null | "...", "download_url": null | "https://...", "file_size_bytes": null | N }`
- **Presigned URL:** Generate on demand for GET when status=success: `s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=3600)`. Expiry 1 hour is typical; document in API response or manifest.
- **Auth:** Tenant-scoped; 404 if not found or wrong tenant

**GET /api/exports** (optional)
- **Query params:** limit (default 20), offset, status (optional filter)
- **Response:** `{ "items": [ { "id", "status", "created_at", "completed_at" } ], "total": N }` — list of exports for the tenant (most recent first)
- **Use case:** User can see past exports and re-download if you store S3 key and regenerate presigned URL on GET by id

**Why this matters:** The UI needs a simple flow: click "Export evidence pack" → POST → get id → poll GET until status is success or failed → show download link or error.

**Deliverable:** `backend/routers/exports.py` (or `evidence_exports.py`) with POST (create + enqueue), GET by id (with presigned URL when success); optional GET list. Mount under `/api/exports` or `/api/evidence-exports`. Use existing SQS utility to build and send `generate_export` message.

---

#### 10.5 S3 configuration and tenant isolation

**Purpose:** Ensure evidence packs are stored in a tenant-scoped path and only the owning tenant can access their exports. Use the existing config for the export bucket.

**What it does:**
- **Bucket:** From application config `S3_EXPORT_BUCKET`. If not set, export feature is disabled (POST returns 503 or 400 with clear message).
- **Key pattern:** `exports/{tenant_id}/{export_id}/evidence-pack.zip` so each export has a unique key and tenant data is isolated by path.
- **Permissions:** Worker (or API) uses an IAM role that can `s3:PutObject` and `s3:GetObject` on the bucket (or a prefix). No customer AWS credentials; this is the SaaS bucket.
- **Presigned URL:** Generated by the API or worker using the same bucket/key; only returned in GET /api/exports/{id} when the export belongs to the requesting tenant. Presigned URL grants temporary read-only access; expiry 3600 seconds (1 hour) is typical.
- **Optional:** Lifecycle rule on the bucket to expire or transition old exports (e.g. delete after 90 days) to manage storage cost; document for ops.

**Why this matters:** Tenant isolation and secure download links are required for multi-tenant SaaS. Presigned URLs avoid exposing bucket credentials to the frontend.

**Deliverable:** Document key pattern and config requirement in implementation plan; use `S3_EXPORT_BUCKET` in worker and API; generate presigned URL in GET by id when status=success.

**Implementation (verified):**
- **Single source of truth:** `backend/services/evidence_export_s3.py` defines key pattern (`build_export_s3_key(tenant_id, export_id)` → `exports/{tenant_id}/{export_id}/evidence-pack.zip`), `PRESIGNED_URL_EXPIRES_IN` (3600), and documents bucket config, tenant isolation, IAM, and optional lifecycle for ops.
- **Worker:** `backend/services/evidence_export.py` uses `build_export_s3_key` for upload key; bucket from `S3_EXPORT_BUCKET` (raises if empty).
- **API:** `backend/routers/exports.py` uses `PRESIGNED_URL_EXPIRES_IN` when generating presigned URL in GET /api/exports/{id}; returns download_url only when export belongs to requesting tenant (load by export_id and tenant_id).
- **Config:** `backend/config.py` `S3_EXPORT_BUCKET` description updated to reference Step 10.5 and key pattern for tenant isolation.
- **Ops (optional):** Lifecycle rule on bucket (e.g. delete objects under `exports/` after 90 days) documented in `evidence_export_s3.py` module docstring.

---

#### 10.6 Frontend: Evidence export UI

**Purpose:** Users can trigger an evidence pack export from the app and download the zip when ready. Uses design system 3.0 and Aceternity components consistent with the rest of the app.

**What to do:**

**A) Trigger and progress**
- **Placement:** Settings page (e.g. under a "Compliance" or "Evidence pack" section) or Top Risks page (e.g. header or sidebar). Implementation plan suggests "Settings or Top Risks page."
- **Button:** "Export evidence pack" (Stateful Button). On click, call `POST /api/exports` (or equivalent). Disable button while request in flight; show loading state.
- **After POST:** Receive export id. Show progress state: "Preparing evidence pack..." with Multi Step Loader or spinner. Poll `GET /api/exports/{id}` every 2–3 seconds until `status` is `success` or `failed` (cap polling at e.g. 5 minutes; then show "Export is taking longer than expected" and link to try again or contact support).

**B) Download and completion**
- When `status === "success"`: Show "Your evidence pack is ready" and a primary button/link "Download evidence pack" that opens `download_url` in a new tab or triggers download (same-origin or presigned URL). Optionally show file_size_bytes ("ZIP, ~2.4 MB").
- When `status === "failed"`: Show error_message in a danger/inline alert ("Export failed: …"). Offer "Try again" (new POST).

**C) Optional: confirmation modal**
- Before POST, show Animated Modal: "This will generate a zip file containing your findings, actions, remediation history, and exceptions for compliance and audit. Continue?" with Cancel and "Export" buttons. For MVP, optional; a single button without modal is acceptable.

**D) Design system**
- Cold Intelligence Dark Mode: surfaces, borders, text, accent per 3.0.
- Stateful Button for "Export evidence pack" and "Download evidence pack."
- Multi Step Loader or skeleton for "Preparing evidence pack..."
- Animated Modal only if confirmation or error detail modal is used.

**Error handling:** POST 503 (queue or S3 not configured) → show "Evidence export is not available. Please try again later or contact support." 401/403 → redirect to login or show "Unauthorized." GET 404 → show "Export not found."

**Why this matters:** Phase 4 definition of done includes "evidence pack export to S3" and "downloadable bundle." Users must be able to request and download the pack without leaving the app.

**Deliverable:** Settings page (or Top Risks) section with "Export evidence pack" button; API client methods `createExport()`, `getExport(id)`; polling loop or hook until success/failed; download link when success. Reuse design system 3.0 and Aceternity (Stateful Button, Multi Step Loader, Animated Modal if used).

---

#### Step 10 Definition of Done

✅ evidence_exports (or exports) model and migration created with proper columns and indexes (tenant_id, status, s3_key, completed_at, etc.)  
✅ Export content spec: manifest.json + findings, actions, remediation_runs, exceptions (CSV; optional JSON); manifest includes file list and optional control_id note  
✅ Worker job for generate_export: loads tenant data, generates files, zips, uploads to S3 (tenant-scoped key), updates export row (status, s3_key, file_size_bytes); idempotent  
✅ Export API: POST /api/exports (create row + enqueue job, return 202 with export id); GET /api/exports/{id} (status + presigned download_url when success); optional GET list  
✅ S3: use S3_EXPORT_BUCKET config; tenant-scoped key pattern; presigned URL for download with sensible expiry  
✅ Frontend: "Export evidence pack" button (Settings or Top Risks); progress (polling + Multi Step Loader); download link when success; error message when failed  
✅ User can trigger an evidence export and download the zip containing findings, actions, remediation runs, and exceptions for audit/compliance

---

### Step 11: Weekly Digest (Email and/or Slack)

This step adds a scheduled weekly digest so users receive a summary of open actions, new/updated findings, and exceptions expiring soon. It fulfills Phase 2: "weekly digest (email or Slack)" and supports the business plan cadence of "minimal weekly effort" and the KPI "digest opens."

#### 11.1 Scheduled job

**Purpose:** Run a weekly job (e.g. via EventBridge cron or worker cron) that, for each tenant, builds a digest payload and sends it by email and/or Slack.

**What it does:**
- **Schedule:** One cron rule (e.g. every Monday 09:00 UTC) or a worker that wakes on schedule and iterates over tenants (or tenants with digest enabled).
- **Payload per tenant:** Query open action count, new/updated findings in the last 7 days, exceptions expiring in the next 14 days, optional top 5–10 actions by priority. Keep payload small (counts + links).
- **Idempotency:** Use a "digest sent at" timestamp or job id per tenant per week so duplicate runs do not send twice.

**Deliverable:** Worker job or Lambda triggered by EventBridge; payload builder (query findings, actions, exceptions); config for schedule (e.g. CRON_EXPRESSION).

**Implementation (verified):** Migration `0011_tenants_last_digest_sent_at`; `WEEKLY_DIGEST_JOB_TYPE` and `build_weekly_digest_job_payload` in backend/utils/sqs.py; worker/jobs/weekly_digest.py (build_digest_payload, execute_weekly_digest_job with 7-day idempotency, last_digest_sent_at update); POST /api/internal/weekly-digest protected by X-Digest-Cron-Secret (DIGEST_CRON_SECRET); worker validation for weekly_digest job shape. EventBridge/cron calls the internal endpoint; API enqueues one job per tenant; worker consumes and builds payload (email/Slack in 11.3/11.4).

#### 11.2 Digest content

**Purpose:** Define exactly what appears in the email and Slack message.

**What it does:**
- **Email:** Subject line (e.g. "AWS Security Autopilot – Weekly digest for {tenant_name}"); body: open action count, new findings count, exceptions expiring soon; "View in app" link (FRONTEND_URL with tenant context or login).
- **Slack:** Same summary in short blocks; link to app. Optional: "Unsubscribe" or "Pause digest" link that hits an API to update tenant preference.
- **Optional:** Top 5–10 actions (title, severity, link); exceptions expiring in next 14 days (entity, expiry date, link).

**Deliverable:** Document in plan and/or template files: subject, body template, Slack block layout; implement in 11.3/11.4.

**Implementation (verified):** `backend/services/digest_content.py`: `build_email_subject`, `build_email_body_plain`, `build_email_body_html`, `build_slack_blocks`; URL helpers `get_view_in_app_url` (default `/top-risks`), `get_action_url`, `get_exceptions_url`. Email: subject `{app_name} – Weekly digest for {tenant_name}`; plain and HTML body with summary counts, optional top 5 actions (with links), optional expiring exceptions list, "View in app" CTA. HTML uses inline styles (dark theme). Slack: Block Kit header, summary section, optional top actions and expiring exceptions sections, divider, "View in app" button, context footer. Worker `build_digest_payload` extended with `expiring_exceptions` list (entity_type, entity_id, expires_at_iso, label) for content rendering. 11.3/11.4 will call these builders when sending.

#### 11.3 Email delivery

**Purpose:** Send the digest by email using the existing email stack.

**What it does:**
- Reuse `backend/services/email.py` (SES or SMTP). Add a function `send_weekly_digest(tenant_id, to_emails, payload)` that renders the body from 11.2 and sends to tenant users (e.g. all users with role admin, or a dedicated "digest_recipients" list per tenant).
- **Config:** `FRONTEND_URL`, `EMAIL_FROM`; optional `DIGEST_ENABLED` to turn off in dev.
- **Preferences:** Optional: store per-user or per-tenant "digest_enabled" and "digest_recipients"; only send if enabled.

**Deliverable:** Email sending function; template (HTML or plain text); optional preferences table and API (GET/PATCH "digest settings").

**Implementation (verified):** Migration 0012: tenants.digest_enabled (boolean, default true), tenants.digest_recipients (text, nullable). Config DIGEST_ENABLED (default True). email_service.send_weekly_digest(tenant_name, to_emails, payload) uses digest_content for subject/plain/HTML and _send_smtp per recipient; returns (sent, failed). Worker: _get_digest_recipients(tenant, session) uses digest_recipients if set else admin users; after building payload, if DIGEST_ENABLED and tenant.digest_enabled, sends digest. GET/PATCH /api/users/me/digest-settings (auth; PATCH admin only) for digest_enabled and digest_recipients.

#### 11.4 Slack delivery (optional)

**Purpose:** Send the same digest to a Slack channel via webhook.

**What it does:**
- Store per-tenant Slack webhook URL (e.g. `tenant_settings.slack_webhook_url` or `integrations` table). Optional: store per-tenant "slack_digest_enabled."
- When sending digest, if webhook URL present and Slack enabled, POST to Slack webhook with the summary (blocks or simple text + link). Use Slack's message format (e.g. Block Kit) for readability.
- **Security:** Webhook URL is secret; store encrypted or in Secrets Manager if desired; do not log full URL.

**Deliverable:** Slack webhook send function; tenant setting for webhook URL and enable/disable; optional Settings UI: "Connect Slack" (paste webhook) and "Send weekly digest to Slack" toggle.

**Implementation (verified):** Migration 0013: tenants.slack_webhook_url (text, nullable), tenants.slack_digest_enabled (boolean, default false). backend/services/slack_digest.py: send_slack_digest POSTs Block Kit blocks (from digest_content) to webhook; _mask_webhook_url for logs (never full URL). Worker: after email, if webhook set and slack_digest_enabled, call send_slack_digest. GET/PATCH /api/users/me/slack-settings (auth; PATCH admin only): GET returns slack_webhook_configured and slack_digest_enabled (URL never exposed); PATCH sets/clears webhook and enable flag.

#### 11.5 Frontend: Digest and Slack settings UI (optional)

**Purpose:** Let admins configure digest (enabled/recipients) and Slack (webhook, enable) from the app so they don’t need to call the API directly.

**What it does:**
- **Settings** page: add a section or tab (e.g. "Digest & Slack" or under Organization) with:
  - **Digest:** GET /api/users/me/digest-settings; show digest_enabled (toggle) and digest_recipients (comma-separated emails); PATCH (admin only) on save. Copy: "Weekly digest" / "Send digest to" / "Recipients (comma-separated; leave empty to use tenant admins)."
  - **Slack:** GET /api/users/me/slack-settings; show slack_webhook_configured (boolean, no URL) and slack_digest_enabled (toggle); PATCH (admin only): form to set/clear webhook URL (masked input or "Configured" when set) and "Send weekly digest to Slack" toggle. Copy: "Slack webhook" / "Send weekly digest to Slack."
- API client: getDigestSettings(), patchDigestSettings(body), getSlackSettings(), patchSlackSettings(body). Auth required; PATCH returns 403 for non-admin.

**Deliverable:** Settings UI for digest and Slack preferences; admins can enable/disable digest, set recipients, and configure Slack webhook + enable Slack digest from the app.

**Implementation (verified):** frontend/src/lib/api.ts: DigestSettingsResponse, DigestSettingsUpdateRequest, SlackSettingsResponse, SlackSettingsUpdateRequest; getDigestSettings(), patchDigestSettings(body), getSlackSettings(), patchSlackSettings(body). frontend/src/app/settings/page.tsx: Settings tab "Notifications" with Digest card (digest_enabled toggle, digest_recipients comma-separated input, Save admin-only; 403 message) and Slack card (slack_webhook_configured → "Configured" badge, Change webhook / Clear webhook for admin; slack_digest_enabled toggle; Save admin-only; 403 message). Fetch on tab active; forms sync from GET response.

#### Step 11 Definition of Done

✅ Scheduled job runs weekly and builds digest payload per tenant (open actions, new findings, expiring exceptions)  
✅ Email digest sent via existing email service; template and link to app  
✅ Optional: Slack digest sent when tenant has webhook configured  
✅ Optional: User or admin can disable digest or set recipients  
✅ User receives weekly digest by email (and optionally Slack) with action summary and link to app

---

### Step 12: Compliance Pack Add-on

This step extends the evidence export (Step 10) with a **compliance pack** that includes exception attestations, control/framework mapping, and an optional auditor summary. It supports the business plan "Compliance pack add-on" (+$500–$1,500/mo) and Phase 4: "compliance pack (exception attestations, control mapping, auditor summary)."

#### 12.1 What the compliance pack includes

**Purpose:** Define the contents of the compliance pack on top of the base evidence pack.

**What it includes:**

1. **Everything in the evidence pack (Step 10):** manifest.json, findings.csv, actions.csv, remediation_runs.csv, exceptions.csv (and optional JSON). No change to 10.2 content.

2. **Exception attestation report:** A dedicated file (e.g. `exception_attestations.csv` or `exception_attestations.pdf`) listing every exception with: approver name/email, approval timestamp, expiry date, reason, ticket link, entity type and id. Enables auditors to see "who approved what, until when" in one place.

3. **Control/framework mapping:** A file (e.g. `control_mapping.csv` or `control_mapping.json`) that maps your `control_id` (and action types) to framework controls—e.g. SOC 2 (CC6.1, CC7.2), ISO 27001 (A.12.4.1). Columns: control_id, framework_name, framework_control_code, control_title, optional description. Enables auditors to map findings to their audit framework.

4. **Auditor summary (optional):** A short PDF or HTML one-pager: "As of [date], tenant X: Y open findings, Z open actions, N exceptions (M expiring in 30 days), P remediations in last 30 days." One-click view for auditors.

**Deliverable:** Document in plan and in export service: list of compliance-pack-only files; column names for exception_attestations and control_mapping; template or spec for auditor summary.

**Implementation (verified):** backend/services/compliance_pack_spec.py: Compliance-pack-only files: exception_attestations.csv, control_mapping.csv, auditor_summary.html. Exception attestation columns: id, entity_type, entity_id, approver_name, approver_email, approval_timestamp, expires_at, reason, ticket_link. Control mapping columns: control_id, framework_name, framework_control_code, control_title, description. build_exception_attestation_rows(session, tenant_id) joins Exception with approved_by; build_control_mapping_rows() returns v1 static mapping (S3.1, CloudTrail.1, GuardDuty.1, SecurityHub.1 → CIS, SOC 2, ISO 27001); build_auditor_summary_content(...) produces mandatory HTML one-pager with open findings, open actions, total exceptions, expiring in 30d, remediations in last 30d. get_compliance_pack_only_files(), csv_content_from_rows(). Step 12.2 will wire pack_type and zip generation.

#### 12.2 Export type: evidence vs compliance

**Purpose:** Allow the export job to produce either the base evidence pack or the full compliance pack.

**What it does:**
- Add an **export type** (or **pack type**) parameter: `evidence` (Step 10 only) or `compliance` (Step 10 + attestations + control mapping + optional summary).
- API: e.g. `POST /api/exports` body `{ "pack_type": "evidence" | "compliance" }`; default `evidence` for backward compatibility.
- Worker: When `pack_type === "compliance"`, generate the same zip as Step 10 plus exception_attestations file(s), control_mapping file(s), and optional auditor summary PDF/HTML. Reuse same S3 pattern (tenant-scoped key, presigned URL).

**Deliverable:** Export API and worker accept pack_type; compliance pack zip includes all files in 12.1; optional plan gate (e.g. compliance pack only for paid compliance add-on) deferred to billing step.

**Implementation (verified):** evidence_exports.pack_type (migration 0014); CreateExportRequest with pack_type (Literal["evidence", "compliance"]); create_export stores pack_type and passes to build_generate_export_job_payload; ExportDetailResponse and ExportListItem include pack_type. build_generate_export_job_payload(..., pack_type="evidence") includes pack_type in SQS payload. Worker reads pack_type from job (default "evidence"), passes to generate_evidence_pack. evidence_export service: generate_evidence_pack(..., pack_type="evidence"); when pack_type == "compliance", _auditor_metrics(session, tenant_id, as_of) computes open_findings, open_actions, total_exceptions, expiring_30d, remediations_30d; adds exception_attestations.csv, control_mapping.csv, auditor_summary.html to zip via compliance_pack_spec builders. Tests: API pack_type in create/list/detail; worker pack_type passed to generate_evidence_pack; service test compliance zip contains three compliance files.

#### 12.3 Control mapping data

**Purpose:** Populate the control mapping file with a minimal v1 mapping.

**What it does:**
- Maintain a mapping table or config (e.g. CSV/JSON in repo or DB table): control_id (e.g. S3.1, CloudTrail.1) → framework (e.g. SOC 2, ISO 27001) → control code and title. Start with Security Hub control IDs and common frameworks (SOC 2, CIS, ISO 27001). Expand over time.
- Worker reads this mapping and emits control_mapping.csv (or JSON) with one row per control_id and framework combination.

**Deliverable:** Mapping data (file or table); worker logic to generate control_mapping file in compliance pack.

**Implementation (verified):** control_mappings table (migration 0015) with control_id, framework_name, framework_control_code, control_title, description; unique (control_id, framework_name); seed v1 data (S3.1, CloudTrail.1, GuardDuty.1, SecurityHub.1 → CIS, SOC 2, ISO 27001). ControlMapping model. compliance_pack_spec.build_control_mapping_rows(session): reads from DB when session provided; fallback to static CONTROL_MAPPING_V1 when session None or empty. evidence_export calls build_control_mapping_rows(session). API: GET /api/control-mappings (auth, filters, pagination), GET /api/control-mappings/{id}, POST /api/control-mappings (admin only, 409 on duplicate). Tests: compliance pack spec DB/fallback, evidence export service mock, control mappings API auth/list/get/POST 403.

#### Step 12 Definition of Done

✅ Compliance pack includes evidence pack (Step 10) + exception_attestations + control_mapping + optional auditor summary  
✅ Export API and worker support pack_type "evidence" | "compliance"  
✅ User can request "Export compliance pack" and download zip with attestations and control mapping  
✅ Control mapping file documents control_id → framework (e.g. SOC 2, ISO) for auditor reference

#### 12.4 Frontend: Evidence vs compliance export (Step 12.2 UI)

**Purpose:** Expose pack_type (evidence vs compliance) in the web app so users can request a compliance pack from Settings.

**What it does:**
- API client: `ExportDetailResponse` and `ExportListItem` include `pack_type`; `createExport(body?: { pack_type?: 'evidence' | 'compliance' })` sends body to POST /api/exports (default evidence).
- Settings → Evidence export tab: add pack type choice (Evidence pack vs Compliance pack) with short descriptions; "Generate pack" calls createExport with selected pack_type; show pack_type in current export and recent exports (e.g. badge or label).

**Deliverable:** User can choose "Evidence pack" or "Compliance pack" in Settings and download the corresponding zip; list/detail show pack type.

**Implementation (verified):** frontend api.ts: pack_type on ExportDetailResponse/ExportListItem; createExport(body?: { pack_type }). Settings: exportPackType state; radio Evidence pack / Compliance pack; createExport({ pack_type }); button and success text by pack type; recent exports show pack_type.

#### 12.5 Frontend: Control mappings (Step 12.3 UI)

**Purpose:** Expose control mappings in the web app so admins can view and add mappings; all users can view the list.

**What it does:**
- API client: types `ControlMapping`, `ControlMappingListResponse`, `CreateControlMappingRequest`; `listControlMappings(params?)`, `getControlMapping(id)`, `createControlMapping(body)` calling GET/POST /api/control-mappings.
- Settings → new tab "Control mappings": list table (control_id, framework_name, framework_control_code, control_title, description); optional filters (control_id, framework_name); for admin users, "Add mapping" form (same fields) calling createControlMapping; show 409 as "This mapping already exists," 403 as "Only admins can add mappings."

**Deliverable:** Settings has a Control mappings tab; users see the v1 mapping list; admins can add new mappings.

**Implementation (verified):** frontend api.ts: ControlMapping, ControlMappingListResponse, CreateControlMappingRequest; listControlMappings(params?), getControlMapping(id), createControlMapping(body). Settings: tab "Control mappings"; list table with filters (control_id, framework_name); "Add mapping" (admin only) modal; form submit createControlMapping; 409/403 error messages.

---

### Step 13: 48h Baseline Report (Lead Magnet)

This step implements the **48h baseline report** as the Alpha lead magnet from Phase 0/GTM (see J) Alpha → Beta → GA). Prospects connect a **read-only role** only (no WriteRole); your app runs ingestion; within 48 hours they receive a one-off report summarizing findings and top risks. The report supports the GTM motion: "connect read-only → ingest → request report → 48h report → propose onboarding sprint → convert to monthly autopilot." No approval workflow or remediation runs are required for this flow; the report is informational only. Implementation covers: report content and format, async job and storage, API and delivery (including 48h SLA), and UI plus GTM playbook.

---

#### 13.1 Report content and format (sections, fields, layout)

**Purpose:** Define the exact content and format of the 48h baseline report so the generator (13.2) and templates produce a consistent, professional deliverable.

**What the report contains:**

- **Executive summary (page 1):**
  - Total finding count; counts by severity (Critical, High, Medium, Low, Informational); open vs resolved.
  - Optional: breakdown by account and/or region (e.g. "3 accounts, 5 regions").
  - One-paragraph narrative: "This baseline reflects your AWS security posture as of [date]. Top priorities: [N] critical, [N] high. Recommended next steps below."
- **Top risks (section 2):**
  - Top 10–20 findings (or aggregated actions) ordered by severity then priority/exploitability. For each: title, resource_id, control_id, severity, account_id, region, status (open/resolved). Optional: short recommendation line (e.g. "Enable GuardDuty in us-east-1").
  - If the prospect later signs up, optional "View in app" link per finding (URL to your app with tenant context or token).
- **Recommendations (section 3):**
  - Bullet list derived from the scan: e.g. "Enable Security Hub in all configured regions," "Review S3 public access (N buckets with public read)," "Enable GuardDuty in N regions," "Restrict SSH/RDP (N security groups)." Keep to 5–10 bullets; tie to control IDs or action types where useful.
- **Appendix (optional):**
  - Full finding list (paginated or truncated with "first 100") with same fields as top risks; or "Available in app after sign-up."

**Format and layout:**
- **PDF (primary):** Preferred for "report" feel and sharing. Use a template (e.g. WeasyPrint, ReportLab, or headless Chrome/ Puppeteer) with cover page (logo, "Baseline Security Report," tenant name, report date), table of contents optional, sections as above. Font and spacing consistent with your brand.
- **HTML (optional):** Same sections; useful for in-app preview or email inline snippet (e.g. "View report" link).
- **JSON (optional):** For power users or API: same data (summary, top_risks, recommendations) as structured JSON; no layout.

**Key components:**
- Report schema (in code or config): summary (counts, severity breakdown, account/region breakdown), top_risks (list of finding/action objects), recommendations (list of strings or { text, control_id? }).
- Template(s): one per format (PDF template, HTML template). PDF template receives structured data; generator fills and renders.
- Field list for top_risks: title, resource_id, control_id, severity, account_id, region, status; optional recommendation_text, link_to_app.

**Why this matters:** A clear, consistent report increases perceived value and supports the lead-magnet pitch. Defined sections and fields prevent scope creep in the generator and make the 48h SLA achievable.

**Deliverable:** Document in this plan (or `docs/baseline-report-spec.md`): report sections, field list, sample layout; implement in 13.2 (generator fills schema and calls template).

---

#### 13.2 Baseline report job and storage (worker + S3 + DB)

**Purpose:** Generate the report asynchronously via a dedicated worker job, store the artifact in S3, and record metadata in the database so the API can return status and presigned download URL.

**What it does:**

- **Trigger:** When a user requests a baseline report (e.g. `POST /api/baseline-report` from 13.3), the API creates a `baseline_reports` row with `status=pending`, then enqueues a **baseline report job** (new job type: `generate_baseline_report`). Message payload: `report_id` (UUID), `tenant_id`, optional `account_ids` (if omitted, use all accounts for tenant). Do not block the API on report generation; return immediately with report id and status.
- **Worker job handler:**
  - Load report by id; assert tenant_id and status=pending (idempotency: if status is already running/success/failed, skip or return).
  - Set status=running; save.
  - Load tenant's findings (and optionally actions) for the given account_ids (or all). Filter by tenant_id; respect account/region if specified.
  - Compute **summary:** counts by severity, open vs resolved, optional by account/region.
  - Compute **top risks:** sort findings (and optionally actions) by severity (Critical first) then priority; take top 10–20; map to report schema (title, resource_id, control_id, severity, account_id, region, status).
  - Compute **recommendations:** from action types or control IDs (e.g. "Enable Security Hub" if findings exist for that control); dedupe; list of strings.
  - Render report: fill PDF (and/or HTML) template with summary, top_risks, recommendations; generate PDF bytes (or HTML string).
  - Upload to S3: key pattern e.g. `baseline-reports/{tenant_id}/{report_id}/baseline-report.pdf`. Set content-type and metadata (tenant_id, report_id).
  - Update `baseline_reports`: set `status=success`, `s3_key=<key>`, `file_size_bytes=<size>`, `completed_at=now`. On any exception: set `status=failed`, store error message in `outcome` or `logs` column if present; re-raise or log for DLQ.
- **Idempotency:** One report per request (one row per POST). Optional: rate limit (e.g. one report per tenant per 24h) to avoid abuse; return 429 with Retry-After if exceeded.
- **Storage schema (baseline_reports table):**
  - `id` (UUID, PK), `tenant_id` (FK), `status` (enum: pending, running, success, failed), `requested_by_user_id` (FK, nullable), `requested_at` (timestamp), `completed_at` (timestamp, nullable), `s3_key` (string, nullable), `file_size_bytes` (bigint, nullable), `account_ids` (JSON array, optional), `outcome` or `logs` (text, optional, for failure reason). `created_at`, `updated_at`. Tenant-scoped; all queries filter by tenant_id.

**Key components:**
- Alembic migration: create `baseline_reports` table.
- Worker: new job type `generate_baseline_report`; handler in e.g. `worker/jobs/generate_baseline_report.py`; register in worker dispatcher.
- Report generator function: `build_baseline_report_data(tenant_id, account_ids=None) -> dict` (summary, top_risks, recommendations); `render_baseline_report_pdf(data) -> bytes` (or use shared template helper).
- S3: bucket or prefix for baseline-reports; presigned URL generation (e.g. 1-hour expiry) when status=success.

**Why this matters:** Async generation keeps the API fast and avoids timeouts; S3 gives a stable, scalable place for large PDFs; DB row gives audit trail and status for the UI.

**Deliverable:** Alembic migration for `baseline_reports`; worker job `generate_baseline_report` with handler; report data builder and PDF (and/or HTML) renderer; S3 upload and key pattern; presigned URL helper used by API (13.3). Optional: rate limit (e.g. one per tenant per 24h).

---

#### 13.3 API and delivery (request, status, download, 48h SLA, email)

**Purpose:** Expose endpoints so the user can request a baseline report and, when it is ready, retrieve status and a secure download link. Define 48h SLA and optional email notification.

**What it does:**

- **POST /api/baseline-report**
  - Auth required (JWT or session); tenant from auth.
  - Request body (optional): `{ "account_ids": ["123456789012", ...] }` to limit report to specific accounts; if omitted, report includes all accounts for the tenant.
  - Create `baseline_reports` row: tenant_id, status=pending, requested_by_user_id=current user, requested_at=now, account_ids=body or null. Enqueue job `generate_baseline_report` with payload report_id, tenant_id, account_ids.
  - Response: `201 Created` with body e.g. `{ "id": "<report_id>", "status": "pending", "requested_at": "<iso>" }`. Do not wait for job completion.
  - Errors: 429 if rate limit exceeded (e.g. one per tenant per 24h); 400 if account_ids invalid; 401/403 per auth.

- **GET /api/baseline-report/{id}**
  - Auth required; tenant from auth. Load report by id; enforce tenant_id matches current tenant (404 if not found or wrong tenant).
  - Response: `{ "id", "status", "requested_at", "completed_at", "file_size_bytes", "download_url" }`. When status=success, include `download_url`: presigned S3 URL (e.g. 1-hour expiry) for the report PDF (or primary format). When pending/running, omit download_url; when failed, optionally include `outcome` or `message` with error reason.
  - Cache-Control: avoid caching of download_url (it is time-limited).

- **48h SLA:**
  - Product copy: "Your baseline report will be ready within 48 hours." Implementation options: (a) Worker processes the queue continuously; ensure worker capacity and DLQ so jobs complete within 48h under normal load. (b) Optional cron (e.g. every 12h) that processes pending reports if you batch them. (c) Document in plan/playbook: "Report ready within 48 hours; you will receive an email when it's ready (if email enabled)."

- **Email (optional):**
  - When report status transitions to success, trigger "report ready" email to requested_by user (or to tenant admin/users): subject e.g. "Your baseline security report is ready"; body: short message + "Download report" link (presigned URL or link to app that redirects to GET .../baseline-report/{id} and then redirects to download_url). Use existing email sender (e.g. Step 11 weekly digest) if available.

**Key components:**
- Router: e.g. `routers/baseline_report.py` or under `routers/reports.py`; POST and GET; tenant scoping via middleware or dependency.
- Presigned URL: generate in GET handler when status=success using boto3 `generate_presigned_url` for the stored s3_key; expiry 3600 seconds (or configurable).
- Optional: small service `notify_baseline_report_ready(report_id)` called from worker after upload; sends email with download link.

**Why this matters:** Clear API allows the frontend to request and poll (or redirect to download); 48h SLA sets expectations; email increases engagement and conversion.

**Deliverable:** POST and GET `/api/baseline-report` (and `/api/baseline-report/{id}`); tenant isolation; presigned download_url when success; optional email on completion; document 48h SLA and trigger flow in plan or product docs.

**Error handling:** 404 when report not found or wrong tenant. 429 when rate limit exceeded (Retry-After header). 400 when account_ids malformed.

---

#### 13.4 Frontend: Request report and download (design system 3.0)

**Purpose:** Let the user request a baseline report from the app and see status; when ready, show a clear "Download report" action. Use the same design system (e.g. 3.0) and components as the rest of the app for consistency.

**What to do:**

**A) Placement and entry point**
- **Settings or onboarding:** Add a section e.g. "Baseline report" with short copy: "Get a one-off security baseline report (ready within 48 hours)." Button: "Request baseline report." For prospects in Alpha, this can be the main CTA after "Connect AWS account" and first ingest (e.g. show on dashboard or onboarding completion).
- **Optional:** After first ingestion completes, show a banner or modal: "Your data is ready. Request your free baseline report (48h)." Link/button to the same flow.

**B) Request flow**
- On "Request baseline report" click: call `POST /api/baseline-report` (optional body with account_ids if user selected specific accounts). On success (201), show message: "Report requested. We'll notify you when it's ready (within 48 hours)." Display report id and status (pending). Optional: link to "View report status" or redirect to a "Reports" or "Baseline report" detail view.
- If rate limited (429): show "You can request one report per 24 hours. Try again later." with optional Retry-After countdown.

**C) Status and download**
- **Report list or detail:** Page or section listing the user's (tenant's) baseline reports: id, status, requested_at, and when status=success: "Download report" button. Use `GET /api/baseline-report/{id}` to fetch status; when status=success, show button that opens `download_url` in a new tab or triggers download (same-origin redirect or fetch + blob download if needed).
- **Polling (optional):** On report detail view, while status is pending or running, poll GET every 30–60 seconds; when status becomes success, show "Download report" and stop polling; when failed, show error message from response.
- **Email CTA:** If email is sent when report is ready, user can also click "Download report" from the email link (to app or direct presigned URL).

**D) Design system**
- Use same surfaces, typography, and buttons as rest of app (e.g. design system 3.0). Primary button for "Request baseline report" and "Download report"; secondary or link for "View status." Error and loading states consistent with existing patterns.

**E) Accessibility and copy**
- Button labels clear ("Request baseline report," "Download report"); success message reiterates 48h; error messages actionable (e.g. "Try again later" for 429).

**Why this matters:** Friction-free request and obvious download increase conversion from prospect to lead and from lead to onboarding.

**Deliverable:** Frontend: "Request baseline report" button (Settings or onboarding/dashboard); POST on click; success and rate-limit messaging; report list or detail with status and "Download report" when success; optional polling. Apply design system 3.0. Error handling for 400, 429, 404.

---

#### 13.5 GTM playbook and lead-magnet flow (documentation)

**Purpose:** Document the end-to-end lead-magnet flow so sales and marketing can use the 48h baseline report consistently in Alpha (and beyond).

**What it does:**
- **Flow (numbered steps for playbook):**
  1. Prospect signs up (or is invited) and lands in app.
  2. Prospect connects **read-only** AWS account (CloudFormation ReadRole + ExternalId); no WriteRole required for baseline report.
  3. App (or manual trigger) runs ingestion for the connected account(s); findings (and optionally actions) are stored.
  4. Prospect clicks "Request baseline report" (Step 13.4); report job is enqueued.
  5. Within 48 hours, report is generated and stored; prospect receives email (if enabled) with "Your baseline report is ready" and download link.
  6. Prospect downloads PDF; reviews summary, top risks, and recommendations.
  7. Sales/CS follows up: "Here’s your baseline; we recommend an onboarding sprint to address the top risks and then monthly autopilot." Propose paid onboarding or subscription (Beta/GA).

- **Where to document:** Implementation starter (Section "Implementation starter (what to build first)") and J) Alpha → Beta → GA: "Use 48h baseline report as lead magnet: connect → ingest → report → propose onboarding." Optional: one-pager or internal doc `docs/gtm-baseline-report-playbook.md` with the steps above, copy suggestions ("Get your free 48h security baseline"), and qualification criteria (e.g. "Prospect has at least one connected account and has requested at least one report").

**Why this matters:** Aligning engineering (report + API + UI) with GTM ensures the lead magnet is used consistently and converts.

**Deliverable:** Document in implementation plan (this section) and in J) Alpha; optional `docs/gtm-baseline-report-playbook.md` with numbered flow and copy notes.

---

#### Step 13 Definition of Done

✅ Report content and format defined: executive summary, top risks, recommendations; PDF (primary), optional HTML/JSON; template and schema implemented in generator  
✅ `baseline_reports` table created (Alembic); columns: id, tenant_id, status, requested_by_user_id, requested_at, completed_at, s3_key, file_size_bytes, account_ids, outcome/logs  
✅ Worker job `generate_baseline_report`: loads findings (and optionally actions), computes summary and top risks and recommendations, renders PDF (and/or HTML), uploads to S3, updates row; idempotent; errors set status=failed  
✅ POST /api/baseline-report creates row and enqueues job; returns report id and status; optional account_ids; rate limit (e.g. one per tenant per 24h) returns 429  
✅ GET /api/baseline-report/{id} returns status and presigned download_url when success; tenant-scoped; 404 when not found or wrong tenant  
✅ Optional: email sent when report ready with download link  
✅ Frontend: "Request baseline report" button (Settings or onboarding); success and rate-limit messaging; report list/detail with "Download report" when success; design system 3.0  
✅ GTM: 48h baseline report flow documented in plan and J) Alpha; optional playbook doc with numbered steps and copy notes  
✅ User can request baseline report and download it within 48h SLA; flow supports lead-magnet GTM from connect read-only → report → propose onboarding

---

## MVP Remediation Flow — End-to-End (No Gaps)

This section summarizes the complete remediation flow so no step is left ambiguous. MVP is complete when a user can go from finding → action → fix → verification.

### PR-only flow (Generate PR bundle)

1. User opens action detail → clicks "Generate PR bundle".
2. Worker runs `generate_pr_bundle` (Step 9: real IaC per action_type).
3. Run completes → artifacts contain Terraform/CloudFormation files.
4. UI shows "Generated files" section and "Next steps" (review, apply, verify).
5. User clicks "Download bundle" → gets zip of applyable IaC.
6. User applies IaC in pipeline or manually in AWS.
7. User returns to action → clicks "Recompute actions" (or triggers ingest).
8. Action engine recomputes; if finding resolved in Security Hub, action status updates.

### Direct fix flow

1. User opens action detail → clicks "Run fix" (requires WriteRole).
2. Approval modal → user confirms.
3. Worker runs direct fix (pre-check, apply, post-check).
4. Run completes → outcome and logs shown.
5. UI shows "Next steps" (return to action, Recompute to verify).
6. User clicks "Recompute actions" → action status reflects fix.

### Previously missing (now addressed)

| Gap | Where addressed |
|-----|-----------------|
| PR bundle returns placeholder only | Step 9: Real IaC per action type |
| No way to download PR bundle | Step 9.6: Download bundle (zip) |
| User doesn't know next steps | Step 9.7: Next steps UI (RemediationRunProgress) |
| No way to verify fix applied | Step 5, 9.7: Recompute actions button (required) |
| Unsupported action types unclear | Step 9.1: Guidance placeholder for pr_only/unmapped |
