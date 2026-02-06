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
        default="https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.1.0.yaml",
        description="Full HTTPS URL to the Read Role template. Default: project S3 bucket in eu-north-1. Override for CloudFront or custom domain.",
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
        default=60 * 24 * 7,  # 7 days
        description="JWT access token expiry in minutes",
    )
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend URL for invite links and redirects",
    )
    EMAIL_FROM: str = Field(
        default="noreply@example.com",
        description="From address for outgoing emails (invites, etc.)",
    )
    DIGEST_CRON_SECRET: str = Field(
        default="",
        description="Shared secret for POST /api/internal/weekly-digest (EventBridge/cron). If unset, endpoint returns 403.",
    )
    DIGEST_ENABLED: bool = Field(
        default=True,
        description="If False, weekly digest email is not sent (e.g. turn off in dev).",
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


# Single instance; import and use as: from config import settings
settings = Settings()
