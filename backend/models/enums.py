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
