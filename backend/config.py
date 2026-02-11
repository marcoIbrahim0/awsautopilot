"""
Application configuration. All values are read from environment variables.
Locally: use a .env file in the project root (or backend/). In AWS: set env vars
or load from Secrets Manager and inject into the process environment.
Never hardcode secrets in code.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = Field(default="AWS Security Autopilot", description="Application name")
    ENV: str = Field(default="local", description="Environment: local | dev | prod")
    LOG_LEVEL: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")

    # Database
    DATABASE_URL: str = Field(
        ...,
        description="Postgres connection string (e.g. postgresql+asyncpg://user:pass@host:5432/db)",
    )
    DATABASE_URL_SYNC: str | None = Field(
        default=None,
        description="Sync Postgres URL for Alembic (postgresql+psycopg2). If unset, derived from DATABASE_URL.",
    )
    DB_REVISION_GUARD_ENABLED: bool = Field(
        default=True,
        description=(
            "When true, API and worker fail fast at startup if the database revision is not at Alembic head."
        ),
    )

    @property
    def database_url_sync(self) -> str:
        """Sync DB URL for Alembic. Uses DATABASE_URL_SYNC if set, else derives from DATABASE_URL."""
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        u = self.DATABASE_URL
        if "+asyncpg" in u:
            return u.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
        return u

    # AWS
    AWS_REGION: str = Field(default="us-east-1", description="Default AWS region")
    SAAS_AWS_ACCOUNT_ID: str = Field(
        default="",
        description="Your SaaS AWS account ID (12 digits); used in ReadRole trust and validation",
    )
    ROLE_SESSION_NAME: str = Field(
        default="security-autopilot-session",
        description="Session name used when calling STS AssumeRole",
    )
    SQS_INGEST_QUEUE_URL: str = Field(
        default="",
        description="SQS URL for security-autopilot-ingest-queue (API sends, Worker consumes). Set from stack output IngestQueueURL.",
    )
    SQS_INGEST_DLQ_URL: str = Field(
        default="",
        description="SQS URL for security-autopilot-ingest-dlq (dead-letter queue). Set from stack output IngestDLQURL.",
    )
    SQS_EVENTS_FAST_LANE_QUEUE_URL: str = Field(
        default="",
        description="SQS URL for near-real-time control-plane event jobs (events-fast-lane).",
    )
    SQS_EVENTS_FAST_LANE_DLQ_URL: str = Field(
        default="",
        description="SQS URL for dead-letter queue backing events-fast-lane.",
    )
    SQS_INVENTORY_RECONCILE_QUEUE_URL: str = Field(
        default="",
        description="SQS URL for inventory reconciliation jobs.",
    )
    SQS_INVENTORY_RECONCILE_DLQ_URL: str = Field(
        default="",
        description="SQS URL for dead-letter queue backing inventory reconciliation.",
    )
    S3_EXPORT_BUCKET: str = Field(
        default="",
        description="S3 bucket name for evidence pack exports (Step 10.5). If unset, POST /api/exports returns 503. Key pattern: exports/{tenant_id}/{export_id}/evidence-pack.zip for tenant isolation.",
    )
    S3_EXPORT_BUCKET_REGION: str = Field(
        default="",
        description="AWS region of the S3 export bucket (e.g. eu-north-1). If unset, defaults to AWS_REGION. Must match the bucket region for presigned URLs to work.",
    )

    # CloudFormation templates (S3; versioned paths)
    CLOUDFORMATION_READ_ROLE_TEMPLATE_URL: str = Field(
        default="https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.1.yaml",
        description="Full HTTPS URL to the Read Role template. Default: project S3 bucket in eu-north-1. Override for CloudFront or custom domain.",
    )
    CLOUDFORMATION_WRITE_ROLE_TEMPLATE_URL: str = Field(
        default="https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/write-role/v1.4.0.yaml",
        description="Full HTTPS URL to the Write Role template. Default: project S3 bucket in eu-north-1. Override for CloudFront or custom domain.",
    )
    CLOUDFORMATION_CONTROL_PLANE_FORWARDER_TEMPLATE_URL: str = Field(
        default="",
        description=(
            "Full HTTPS URL to the Control Plane Event Forwarder CloudFormation template. "
            "When set, tenant admins can one-click deploy the EventBridge rule + API Destination."
        ),
    )
    CLOUDFORMATION_DEFAULT_REGION: str = Field(
        default="eu-north-1",
        description="Default region for Launch Stack console link (matches template bucket region).",
    )

    # Auth (set in prod; placeholder allowed for local only)
    JWT_SECRET: str = Field(
        default="change-me-in-production-do-not-use-in-prod",
        description="Secret for signing JWT; must be overridden in dev/prod via env or Secrets Manager",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=(60 * 24 * 7) + 60,  # 7 days + 1 hour
        description="JWT access token expiry in minutes",
    )
    SAAS_BUNDLE_EXECUTOR_ENABLED: bool = Field(
        default=False,
        description="Enable SaaS-managed Terraform runner for PR bundles.",
    )
    SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT: int = Field(
        default=6,
        description="Maximum concurrent queued/running SaaS PR bundle executions per tenant. <=0 disables cap.",
    )
    SAAS_BUNDLE_EXECUTOR_FAIL_FAST: bool = Field(
        default=True,
        description="Default fail-fast behavior for SaaS bundle execution. If false, continue all folders and aggregate failures.",
    )
    SAAS_BUNDLE_RUNNER_TEMPLATE_S3_URI: str = Field(
        default="",
        description="Optional s3://bucket/key URI for centralized run_all.sh template used in generated group PR bundles.",
    )
    SAAS_BUNDLE_RUNNER_TEMPLATE_VERSION: str = Field(
        default="v1",
        description="Version label for centralized run_all.sh template (stored in bundle metadata).",
    )
    SAAS_BUNDLE_RUNNER_TEMPLATE_CACHE_SECONDS: int = Field(
        default=300,
        description="In-process cache TTL for centralized run_all.sh template fetches from S3.",
    )
    BUNDLE_REPORTING_TOKEN_SECRET: str = Field(
        default="",
        description=(
            "Secret for signing downloaded-bundle run reporting tokens. "
            "Falls back to JWT_SECRET when unset."
        ),
    )
    BUNDLE_REPORTING_TOKEN_TTL_SECONDS: int = Field(
        default=86400,
        description="Expiration for bundle run reporting tokens in seconds.",
    )
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend URL for invite links and redirects",
    )
    API_PUBLIC_URL: str = Field(
        default="http://localhost:8000",
        description=(
            "Public base URL for the backend API (scheme + host + optional port). "
            "Used to prefill CloudFormation EventBridge API Destination endpoints."
        ),
    )
    EMAIL_FROM: str = Field(
        default="noreply@example.com",
        description="From address for outgoing emails (invites, etc.)",
    )
    DIGEST_CRON_SECRET: str = Field(
        default="",
        description="Shared secret for POST /api/internal/weekly-digest (EventBridge/cron). If unset, endpoint returns 403.",
    )
    CONTROL_PLANE_EVENTS_SECRET: str = Field(
        default="",
        description="Shared secret for POST /api/internal/control-plane-events. If unset, endpoint returns 503.",
    )
    CONTROL_PLANE_SHADOW_MODE: bool = Field(
        default=True,
        description="When true, control-plane pipeline writes only to shadow state tables.",
    )
    CONTROL_PLANE_SOURCE: str = Field(
        default="event_monitor_shadow",
        description="Source label for control-plane shadow pipeline outputs.",
    )
    CONTROL_PLANE_AUTHORITATIVE_CONTROLS: str = Field(
        default="",
        description=(
            "Comma-separated canonical control IDs (e.g. EC2.53,S3.1) that are promoted to "
            "authoritative control-plane state when CONTROL_PLANE_SHADOW_MODE=false. "
            "Promoted controls will auto-resolve/reopen live findings based on shadow status."
        ),
    )
    WORKER_POOL: str = Field(
        default="legacy",
        description="Worker queue pool selector: legacy | events | inventory | all.",
    )
    CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES: int = Field(
        default=60,
        description="Default lookback window for reconcile_recently_touched_resources.",
    )
    CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD: int = Field(
        default=500,
        description="Default maximum resources collected per inventory reconciliation shard job.",
    )
    CONTROL_PLANE_INVENTORY_SERVICES: str = Field(
        default="ec2,s3,cloudtrail,config,iam,ebs,rds,eks,ssm,guardduty",
        description="Comma-separated inventory services covered by reconciliation sweeps.",
    )
    CONTROL_PLANE_PREREQ_MAX_STALENESS_MINUTES: int = Field(
        default=30,
        description=(
            "Maximum allowed age (in minutes) of control-plane intake freshness for reconciliation enqueue."
        ),
    )
    CONTROL_PLANE_PREREQ_MAX_QUEUE_DEPTH: int = Field(
        default=100,
        description=(
            "Maximum allowed inventory reconciliation queue depth before new reconciliation enqueues are gated."
        ),
    )
    CONTROL_PLANE_PREREQ_MAX_DLQ_DEPTH: int = Field(
        default=0,
        description=(
            "Maximum allowed inventory reconciliation DLQ depth before new reconciliation enqueues are gated."
        ),
    )
    CONTROL_PLANE_POST_APPLY_RECONCILE_ENABLED: bool = Field(
        default=True,
        description=(
            "When true, successful PR bundle apply executions attempt immediate inventory reconciliation enqueue."
        ),
    )
    CONTROL_PLANE_POST_APPLY_RECONCILE_MODE: str = Field(
        default="targeted_then_global",
        description=(
            "Post-apply reconcile strategy: targeted_then_global (default) or global_only."
        ),
    )
    CONTROL_PLANE_AUTO_DISABLE_ASSUME_ROLE_FAILURES: bool = Field(
        default=True,
        description=(
            "When true, repeated AssumeRole failures on worker retries can auto-disable the affected AWS account."
        ),
    )
    CONTROL_PLANE_ASSUME_ROLE_QUARANTINE_RECEIVE_COUNT: int = Field(
        default=3,
        description=(
            "SQS ApproximateReceiveCount threshold before auto-disabling accounts with repeated AssumeRole failures."
        ),
    )
    TENANT_RECONCILIATION_ENABLED: bool = Field(
        default=False,
        description=(
            "Enable tenant-facing reconciliation endpoints. "
            "When false, only tenants listed in TENANT_RECONCILIATION_PILOT_TENANTS can access."
        ),
    )
    TENANT_RECONCILIATION_PILOT_TENANTS: str = Field(
        default="",
        description="Comma-separated tenant UUIDs allowed to use tenant reconciliation while feature is disabled globally.",
    )
    TENANT_RECONCILIATION_MAX_SERVICES: int = Field(
        default=6,
        description="Maximum number of services allowed in one tenant reconciliation run.",
    )
    TENANT_RECONCILIATION_MAX_RESOURCES_CAP: int = Field(
        default=2000,
        description="Hard cap for max_resources in tenant reconciliation requests.",
    )
    TENANT_RECONCILIATION_COOLDOWN_SECONDS: int = Field(
        default=120,
        description="Minimum cooldown between tenant-triggered reconciliation runs for the same account.",
    )
    TENANT_RECONCILIATION_SCHEDULE_MIN_INTERVAL_MINUTES: int = Field(
        default=60,
        description="Minimum allowed schedule interval for tenant-managed reconciliation.",
    )
    TENANT_RECONCILIATION_ALERT_FAILURE_THRESHOLD: int = Field(
        default=3,
        description="Failure count threshold used when emitting repeated reconciliation failure alerts.",
    )
    RECONCILIATION_SCHEDULER_SECRET: str = Field(
        default="",
        description=(
            "Shared secret for POST /api/internal/reconciliation/schedule-tick. "
            "If unset, CONTROL_PLANE_EVENTS_SECRET is used as fallback."
        ),
    )
    ONLY_IN_SCOPE_CONTROLS: bool = Field(
        default=True,
        description=(
            "If true, filter findings/actions to the controls defined in backend.services.control_scope "
            "(exclude pr_only/out-of-scope). This reduces noise during the MVP phase."
        ),
    )
    DIGEST_ENABLED: bool = Field(
        default=True,
        description="If False, weekly digest email is not sent (e.g. turn off in dev).",
    )
    SAAS_ADMIN_EMAILS: str = Field(
        default="",
        description="Comma-separated SaaS admin emails allowed to access /api/saas endpoints.",
    )
    S3_SUPPORT_BUCKET: str = Field(
        default="",
        description="S3 bucket for admin->tenant support files.",
    )
    S3_SUPPORT_BUCKET_REGION: str = Field(
        default="",
        description="AWS region for S3_SUPPORT_BUCKET. Defaults to AWS_REGION when unset.",
    )

    # API
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins (e.g. frontend URL)",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS split into a list for FastAPI."""
        if not self.CORS_ORIGINS.strip():
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_local(self) -> bool:
        return self.ENV.lower() == "local"

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "prod"

    @property
    def has_ingest_queue(self) -> bool:
        """True if ingest queue URL is set. Ingest trigger endpoint returns 503 when False."""
        return bool(self.SQS_INGEST_QUEUE_URL and self.SQS_INGEST_QUEUE_URL.strip())

    @property
    def has_events_fast_lane_queue(self) -> bool:
        """True if fast-lane events queue URL is configured."""
        return bool(
            self.SQS_EVENTS_FAST_LANE_QUEUE_URL
            and self.SQS_EVENTS_FAST_LANE_QUEUE_URL.strip()
        )

    @property
    def has_inventory_reconcile_queue(self) -> bool:
        """True if inventory reconciliation queue URL is configured."""
        return bool(
            self.SQS_INVENTORY_RECONCILE_QUEUE_URL
            and self.SQS_INVENTORY_RECONCILE_QUEUE_URL.strip()
        )

    @property
    def control_plane_inventory_services_list(self) -> list[str]:
        """Normalized inventory service allowlist for reconciliation sweeps."""
        default_services = ["ec2", "s3", "cloudtrail", "config", "iam", "ebs", "rds", "eks", "ssm", "guardduty"]
        raw = (self.CONTROL_PLANE_INVENTORY_SERVICES or "").strip()
        if not raw:
            return default_services
        services: list[str] = []
        seen: set[str] = set()
        for token in raw.split(","):
            service = token.strip().lower()
            if not service or service in seen:
                continue
            seen.add(service)
            services.append(service)
        return services or default_services

    @property
    def control_plane_post_apply_reconcile_mode(self) -> str:
        """Normalized post-apply reconcile mode."""
        mode = str(self.CONTROL_PLANE_POST_APPLY_RECONCILE_MODE or "").strip().lower()
        if mode in {"targeted_then_global", "global_only"}:
            return mode
        return "targeted_then_global"

    @property
    def control_plane_authoritative_controls_set(self) -> set[str]:
        """Uppercased set of canonical control IDs promoted to authoritative mode."""
        raw = (self.CONTROL_PLANE_AUTHORITATIVE_CONTROLS or "").strip()
        if not raw:
            return set()
        values: set[str] = set()
        for token in raw.split(","):
            control_id = token.strip()
            if not control_id:
                continue
            values.add(control_id.upper())
        return values

    @property
    def saas_admin_emails_list(self) -> set[str]:
        """Normalized allowlist for SaaS admin users."""
        if not self.SAAS_ADMIN_EMAILS.strip():
            return set()
        return {
            email.strip().lower()
            for email in self.SAAS_ADMIN_EMAILS.split(",")
            if email.strip()
        }

    @property
    def tenant_reconciliation_pilot_tenants_list(self) -> set[str]:
        """Normalized set of tenant UUID strings allowed for pilot rollout."""
        raw = (self.TENANT_RECONCILIATION_PILOT_TENANTS or "").strip()
        if not raw:
            return set()
        return {
            tenant_id.strip()
            for tenant_id in raw.split(",")
            if tenant_id.strip()
        }


# Single instance; import and use as: from config import settings
settings = Settings()
