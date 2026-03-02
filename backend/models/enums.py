# backend/models/enums.py
from enum import Enum


class UserRole(str, Enum):
    """User role within a tenant."""
    admin = "admin"
    member = "member"


class AwsAccountStatus(str, Enum):
    pending = "pending"
    validated = "validated"
    error = "error"
    disabled = "disabled"


class SeverityLabel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class FindingStatus(str, Enum):
    """Security Hub WorkflowStatus."""
    NEW = "NEW"
    NOTIFIED = "NOTIFIED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class ActionStatus(str, Enum):
    """Workflow status for actions (aggregated from findings)."""
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    suppressed = "suppressed"


class EntityType(str, Enum):
    """Type of entity an exception applies to."""
    finding = "finding"
    action = "action"


class RemediationRunMode(str, Enum):
    """Whether a remediation run produces a PR bundle only or applies a direct fix."""
    pr_only = "pr_only"
    direct_fix = "direct_fix"


class RemediationRunStatus(str, Enum):
    """Current state of a remediation run."""
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class RemediationRunExecutionPhase(str, Enum):
    """Execution phase for SaaS-managed PR bundle execution."""
    plan = "plan"
    apply = "apply"


class RemediationRunExecutionStatus(str, Enum):
    """Current state of a SaaS-managed PR bundle execution."""
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class ActionGroupRunStatus(str, Enum):
    """Lifecycle status for an action-group execution run."""

    queued = "queued"
    started = "started"
    finished = "finished"
    failed = "failed"
    cancelled = "cancelled"


class ActionGroupExecutionStatus(str, Enum):
    """Per-action execution result status reported for a group run."""

    success = "success"
    failed = "failed"
    cancelled = "cancelled"
    unknown = "unknown"


class ActionGroupStatusBucket(str, Enum):
    """UI/status bucket for immutable group member outcomes."""

    not_run_yet = "not_run_yet"
    run_not_successful = "run_not_successful"
    run_successful_confirmed = "run_successful_confirmed"


class ActionGroupConfirmationSource(str, Enum):
    """Trusted confirmation sources for compliance-confirmed success."""

    security_hub = "security_hub"
    control_plane_reconcile = "control_plane_reconcile"


class EvidenceExportStatus(str, Enum):
    """Current state of an evidence pack export job."""
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class BaselineReportStatus(str, Enum):
    """Current state of a baseline report job (Step 13.2)."""
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class RootKeyRemediationState(str, Enum):
    """Lifecycle state for root-key remediation orchestration."""

    discovery = "discovery"
    migration = "migration"
    validation = "validation"
    disable_window = "disable_window"
    delete_window = "delete_window"
    completed = "completed"
    needs_attention = "needs_attention"
    rolled_back = "rolled_back"
    failed = "failed"


class RootKeyRemediationMode(str, Enum):
    """Execution mode for root-key remediation orchestration."""

    auto = "auto"
    manual = "manual"


class RootKeyRemediationRunStatus(str, Enum):
    """Operational status for root-key remediation run rows."""

    queued = "queued"
    running = "running"
    waiting_for_user = "waiting_for_user"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RootKeyDependencyStatus(str, Enum):
    """Dependency evaluation status for root-key remediation."""

    pass_ = "pass"
    warn = "warn"
    unknown = "unknown"
    fail = "fail"


class RootKeyArtifactStatus(str, Enum):
    """Artifact lifecycle status for root-key remediation."""

    pending = "pending"
    available = "available"
    redacted = "redacted"
    failed = "failed"


class RootKeyExternalTaskStatus(str, Enum):
    """User-attention task status for root-key remediation."""

    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class SecretMigrationRunStatus(str, Enum):
    """Lifecycle status for tenant-scoped secret migration runs."""

    queued = "queued"
    running = "running"
    success = "success"
    partial_failed = "partial_failed"
    failed = "failed"
    rolled_back = "rolled_back"


class SecretMigrationTransactionStatus(str, Enum):
    """Per-target status for secret migration transaction entries."""

    pending = "pending"
    success = "success"
    failed = "failed"
    rolled_back = "rolled_back"
    rollback_failed = "rollback_failed"
    skipped = "skipped"
