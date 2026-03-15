"""
Remediation strategy registry and validation helpers.

Phase 1 introduces strategy selection for high-impact remediations so callers
must choose an explicit remediation path (and acknowledge risk when required).
"""
from __future__ import annotations

from ipaddress import ip_network
from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from backend.services.root_credentials_workflow import (
    ROOT_CREDENTIALS_REQUIRED_MESSAGE,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
)

Mode = Literal["pr_only", "direct_fix"]
RiskLevel = Literal["low", "medium", "high"]
BlastRadius = Literal["account", "resource", "access_changing"]
InputType = Literal["string", "string_array", "select", "boolean", "cidr", "number"]
DiffLineType = Literal["add", "remove", "unchanged"]


class StrategyInputOption(TypedDict):
    """One selectable option for a select-style strategy input."""

    value: str
    label: NotRequired[str]
    description: NotRequired[str]
    impact_text: NotRequired[str]


class StrategyInputVisibleWhen(TypedDict):
    """Conditional visibility expression used by UI renderers."""

    field: str
    equals: Any


class StrategyInputSchemaField(TypedDict):
    """One user-provided input accepted by a remediation strategy."""

    key: str
    type: InputType
    required: bool
    description: str
    enum: NotRequired[list[str]]
    placeholder: NotRequired[str]
    help_text: NotRequired[str]
    default_value: NotRequired[Any]
    options: NotRequired[list[StrategyInputOption]]
    visible_when: NotRequired[StrategyInputVisibleWhen]
    impact_text: NotRequired[str]
    group: NotRequired[str]
    min: NotRequired[float | int]
    max: NotRequired[float | int]
    safe_default_value: NotRequired[Any]
    safe_default_label: NotRequired[str]


# Backward-compatible alias used throughout this module.
StrategyInputField = StrategyInputSchemaField


class StrategyInputSchema(TypedDict):
    """Schema descriptor for strategy inputs."""

    fields: list[StrategyInputField]


class PreviewDiffLine(TypedDict):
    """One before/after diff line used in remediation preview surfaces."""

    type: DiffLineType
    label: str
    value: str


class RemediationStateSimulation(TypedDict):
    """Structured before/after simulator payload for remediation preview."""

    before_state: dict[str, Any]
    after_state: dict[str, Any]
    diff_lines: list[PreviewDiffLine]


class RemediationStrategy(TypedDict):
    """Declarative strategy definition used by API, UI, and workers."""

    strategy_id: str
    action_type: str
    label: str
    mode: Mode
    risk_level: RiskLevel
    recommended: bool
    requires_inputs: bool
    input_schema: StrategyInputSchema
    supports_exception_flow: bool
    exception_only: bool
    impact_text: NotRequired[str]
    estimated_resolution_time: NotRequired[str]
    supports_immediate_reeval: NotRequired[bool]
    blast_radius: NotRequired[BlastRadius]
    warnings: list[str]
    legacy_pr_bundle_variant: str | None


def _schema(fields: list[StrategyInputField] | None = None) -> StrategyInputSchema:
    return {"fields": fields or []}


_EXCEPTION_DURATION_OPTIONS: tuple[StrategyInputOption, ...] = (
    {"value": "7", "label": "7 days"},
    {"value": "14", "label": "14 days"},
    {"value": "30", "label": "30 days"},
    {"value": "90", "label": "90 days"},
)


def _exception_strategy_input_schema() -> StrategyInputSchema:
    return _schema(
        [
            {
                "key": "exception_duration_days",
                "type": "select",
                "required": False,
                "description": "How long should this exception remain active?",
                "default_value": "30",
                "group": "Exception",
                "options": list(_EXCEPTION_DURATION_OPTIONS),
            },
            {
                "key": "exception_reason",
                "type": "string",
                "required": False,
                "description": "Why can't you apply this fix right now?",
                "placeholder": "Describe the temporary business or operational constraint.",
                "group": "Exception",
            },
        ]
    )


def map_exception_strategy_inputs(strategy_inputs: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize exception strategy inputs into existing exception-flow defaults.

    Returns:
    - duration_days: one of 7/14/30/90 (default 30)
    - reason: optional free-text reason
    """
    safe_inputs = strategy_inputs if isinstance(strategy_inputs, dict) else {}
    duration_days = 30
    raw_duration = safe_inputs.get("exception_duration_days")
    if isinstance(raw_duration, str):
        cleaned_duration = raw_duration.strip()
        if cleaned_duration.isdigit():
            parsed = int(cleaned_duration)
            if parsed in {7, 14, 30, 90}:
                duration_days = parsed

    reason = ""
    raw_reason = safe_inputs.get("exception_reason")
    if isinstance(raw_reason, str):
        reason = raw_reason.strip()

    return {"duration_days": duration_days, "reason": reason}


def _iam_root_action_mode_schema(*, default_mode: str) -> StrategyInputSchema:
    """Shared guided-choice schema for IAM root key action mode."""
    return _schema(
        [
            {
                "key": "action_mode",
                "type": "select",
                "required": False,
                "description": "How would you like to handle the active root access key?",
                "default_value": default_mode,
                "options": [
                    {
                        "value": "disable_key",
                        "label": "Disable key (recommended)",
                        "impact_text": (
                            "The root access key will be set to Inactive. You can re-enable it later if needed. "
                            "This is the safest first step."
                        ),
                    },
                    {
                        "value": "delete_key",
                        "label": "Delete key permanently",
                        "impact_text": (
                            "The root access key will be permanently deleted. This cannot be undone. "
                            "Root MFA must be active."
                        ),
                    },
                ],
                "group": "Root Access Key",
            }
        ]
    )


STRATEGY_REGISTRY: dict[str, tuple[RemediationStrategy, ...]] = {
    "s3_block_public_access": (
        RemediationStrategy(
            strategy_id="s3_account_block_public_access_direct_fix",
            action_type="s3_block_public_access",
            label="Enable account-level S3 Block Public Access (direct fix)",
            mode="direct_fix",
            risk_level="low",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="All four account-level public access block settings will be enabled.",
            warnings=[
                "Account-level public access block can affect intentionally public bucket policies.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="s3_account_block_public_access_pr_bundle",
            action_type="s3_block_public_access",
            label="Enable account-level S3 Block Public Access (PR bundle)",
            mode="pr_only",
            risk_level="low",
            recommended=False,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="All four account-level public access block settings will be enabled.",
            warnings=[
                "Review workloads that intentionally rely on public bucket policies before apply.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    # Existing S3.2/S3.8 path migrated into strategy model (legacy variant back-compat).
    "s3_bucket_block_public_access": (
        RemediationStrategy(
            strategy_id="s3_bucket_block_public_access_standard",
            action_type="s3_bucket_block_public_access",
            label="Block public access on bucket",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "All four bucket-level public access block settings will be enabled for this bucket."
            ),
            warnings=[
                (
                    "May break workloads that depend on direct public S3 access. "
                    "Analyze the affected S3 bucket policy/ACL/public-access-block settings, "
                    "the bucket KMS key policy/grants (if SSE-KMS), CloudFront OAC/OAI configuration, "
                    "and any VPC endpoint or cross-account IAM principals that access the bucket. "
                    "If IAM Access Analyzer is enabled in this account/region, dependency validation can be automated."
                ),
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="s3_migrate_cloudfront_oac_private",
            action_type="s3_bucket_block_public_access",
            label="Migrate to CloudFront + OAC + private S3",
            mode="pr_only",
            risk_level="medium",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "Bucket-level public access block settings will be enabled and access will be served "
                "through CloudFront + OAC."
            ),
            warnings=[
                (
                    "Requires careful validation of bucket policies and KMS permissions. "
                    "Analyze the affected S3 bucket policy/ACL/public-access-block settings, "
                    "the bucket KMS key policy/grants (if SSE-KMS), CloudFront OAC/OAI configuration, "
                    "and any VPC endpoint or cross-account IAM principals that access the bucket. "
                    "If IAM Access Analyzer is enabled in this account/region, dependency validation can be automated."
                ),
            ],
            legacy_pr_bundle_variant="cloudfront_oac_private_s3",
        ),
        RemediationStrategy(
            strategy_id="s3_keep_public_exception",
            action_type="s3_bucket_block_public_access",
            label="Keep intentionally public (exception path)",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_exception_strategy_input_schema(),
            supports_exception_flow=True,
            exception_only=True,
            impact_text=(
                "Bucket-level public access block settings remain unchanged while exception workflow is used."
            ),
            warnings=[
                "Keeps public exposure; requires explicit business approval and compensating controls.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "s3_bucket_encryption": (
        RemediationStrategy(
            strategy_id="s3_enable_sse_s3_aes256",
            action_type="s3_bucket_encryption",
            label="Enable S3 default encryption (AES256)",
            mode="pr_only",
            risk_level="low",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="Default bucket encryption will be enabled using SSE-S3 (AES256).",
            warnings=[
                "Default encryption applies to new objects; existing objects are not re-encrypted automatically.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    # Phase 1 additions
    "aws_config_enabled": (
        RemediationStrategy(
            strategy_id="config_enable_account_local_delivery",
            action_type="aws_config_enabled",
            label="Enable AWS Config with account-local delivery",
            mode="pr_only",
            risk_level="medium",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            warnings=[
                "Enabling Config can increase logging/storage costs.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="config_enable_centralized_delivery",
            action_type="aws_config_enabled",
            label="Enable AWS Config with centralized delivery bucket",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "recording_scope",
                        "type": "select",
                        "required": False,
                        "description": "How should AWS Config recording scope be set?",
                        "default_value": "keep_existing",
                        "group": "Recorder Settings",
                        "options": [
                            {
                                "value": "all_resources",
                                "label": "All resources",
                            },
                            {
                                "value": "keep_existing",
                                "label": "Keep existing scope",
                            },
                        ],
                    },
                    {
                        "key": "delivery_bucket_mode",
                        "type": "select",
                        "required": False,
                        "description": "Where should AWS Config deliver snapshots and history?",
                        "default_value": "use_existing",
                        "group": "Delivery Settings",
                        "options": [
                            {
                                "value": "create_new",
                                "label": "Create new dedicated bucket",
                            },
                            {
                                "value": "use_existing",
                                "label": "Use existing bucket",
                            },
                        ],
                    },
                    {
                        "key": "existing_bucket_name",
                        "type": "string",
                        "required": False,
                        "description": "Existing S3 bucket name for AWS Config delivery.",
                        "placeholder": "security-autopilot-config-123456789012",
                        "visible_when": {
                            "field": "delivery_bucket_mode",
                            "equals": "use_existing",
                        },
                        "group": "Delivery Settings",
                    },
                    {
                        "key": "delivery_bucket",
                        "type": "string",
                        "required": True,
                        "description": "Centralized S3 bucket for Config delivery.",
                        "safe_default_value": "security-autopilot-config-{{account_id}}",
                        "safe_default_label": "Use a dedicated Config bucket",
                    },
                    {
                        "key": "encrypt_with_kms",
                        "type": "boolean",
                        "required": False,
                        "description": "Encrypt AWS Config delivery channel with a KMS key.",
                        "default_value": False,
                        "group": "Encryption Settings",
                    },
                    {
                        "key": "kms_key_arn",
                        "type": "string",
                        "required": False,
                        "description": "Optional KMS key ARN for encrypting Config delivery.",
                        "visible_when": {
                            "field": "encrypt_with_kms",
                            "equals": True,
                        },
                        "group": "Encryption Settings",
                    },
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            warnings=[
                "Cross-account bucket and key policies must be reviewed before apply.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="config_keep_exception",
            action_type="aws_config_enabled",
            label="Keep current state (exception path)",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_exception_strategy_input_schema(),
            supports_exception_flow=True,
            exception_only=True,
            warnings=[
                "Skipping Config reduces change visibility and audit evidence quality.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "cloudtrail_enabled": (
        RemediationStrategy(
            strategy_id="cloudtrail_enable_guided",
            action_type="cloudtrail_enabled",
            label="Enable CloudTrail logging (guided choices)",
            mode="pr_only",
            risk_level="medium",
            recommended=True,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "trail_name",
                        "type": "string",
                        "required": False,
                        "description": "Name for the CloudTrail trail.",
                        "default_value": "security-autopilot-trail",
                        "group": "Trail Settings",
                        "safe_default_value": "security-autopilot-trail",
                        "safe_default_label": "Use the standard trail name",
                    },
                    {
                        "key": "create_bucket_policy",
                        "type": "boolean",
                        "required": False,
                        "description": (
                            "Automatically add required S3 bucket policy statements for "
                            "CloudTrail delivery."
                        ),
                        "default_value": True,
                        "group": "Delivery Settings",
                    },
                    {
                        "key": "multi_region",
                        "type": "boolean",
                        "required": False,
                        "description": "Enable CloudTrail logging across all regions.",
                        "default_value": True,
                        "group": "Trail Settings",
                    },
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            warnings=[
                "CloudTrail log delivery and retention can increase storage costs.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "enable_security_hub": (
        RemediationStrategy(
            strategy_id="security_hub_enable_direct_fix",
            action_type="enable_security_hub",
            label="Enable Security Hub (direct fix)",
            mode="direct_fix",
            risk_level="low",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="AWS Security Hub will be enabled in this region.",
            warnings=[
                "Enabling Security Hub can increase findings volume until standards are tuned.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="security_hub_enable_pr_bundle",
            action_type="enable_security_hub",
            label="Enable Security Hub (PR bundle)",
            mode="pr_only",
            risk_level="low",
            recommended=False,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="AWS Security Hub will be enabled in this region.",
            warnings=[
                "Apply the generated bundle to activate Security Hub and default standards in this region.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "enable_guardduty": (
        RemediationStrategy(
            strategy_id="guardduty_enable_direct_fix",
            action_type="enable_guardduty",
            label="Enable GuardDuty (direct fix)",
            mode="direct_fix",
            risk_level="low",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="Amazon GuardDuty will be enabled in this region.",
            warnings=[
                "GuardDuty detector and data-source coverage can increase service usage charges.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="guardduty_enable_pr_bundle",
            action_type="enable_guardduty",
            label="Enable GuardDuty (PR bundle)",
            mode="pr_only",
            risk_level="low",
            recommended=False,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="Amazon GuardDuty will be enabled in this region.",
            warnings=[
                "Apply the generated bundle to enable a GuardDuty detector in this region.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "ssm_block_public_sharing": (
        RemediationStrategy(
            strategy_id="ssm_disable_public_document_sharing",
            action_type="ssm_block_public_sharing",
            label="Disable public SSM document sharing",
            mode="pr_only",
            risk_level="medium",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="Public sharing of SSM documents will be blocked.",
            warnings=[
                "Shared public documents will no longer be publicly available.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="ssm_keep_public_sharing_exception",
            action_type="ssm_block_public_sharing",
            label="Keep public sharing (exception path)",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_exception_strategy_input_schema(),
            supports_exception_flow=True,
            exception_only=True,
            impact_text=(
                "Public sharing of SSM documents will remain enabled while the exception path is active."
            ),
            warnings=[
                "Publicly shareable SSM documents can expose sensitive operational content.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "ebs_snapshot_block_public_access": (
        RemediationStrategy(
            strategy_id="snapshot_block_all_sharing",
            action_type="ebs_snapshot_block_public_access",
            label="Block all public snapshot sharing",
            mode="pr_only",
            risk_level="medium",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="Public access to EBS snapshots will be blocked at the account level.",
            warnings=[
                "Existing workflows that rely on public snapshot sharing may fail.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="snapshot_block_new_sharing_only",
            action_type="ebs_snapshot_block_public_access",
            label="Block new public sharing only",
            mode="pr_only",
            risk_level="medium",
            recommended=False,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "New public sharing for EBS snapshots will be blocked while previously public snapshots "
                "remain unchanged."
            ),
            warnings=[
                "Previously shared public snapshots may remain exposed.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="snapshot_keep_sharing_exception",
            action_type="ebs_snapshot_block_public_access",
            label="Keep public sharing (exception path)",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_exception_strategy_input_schema(),
            supports_exception_flow=True,
            exception_only=True,
            impact_text=(
                "Public EBS snapshot sharing posture will remain unchanged while the exception path is active."
            ),
            warnings=[
                "Public snapshots can leak data and AMI lineage.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "ebs_default_encryption": (
        RemediationStrategy(
            strategy_id="ebs_enable_default_encryption_aws_managed_kms",
            action_type="ebs_default_encryption",
            label="Enable default EBS encryption (AWS managed key)",
            mode="direct_fix",
            risk_level="low",
            recommended=True,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="All new EBS volumes in this region will be encrypted by default.",
            warnings=[
                "New volumes will encrypt by default; existing volumes are unchanged.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="ebs_enable_default_encryption_aws_managed_kms_pr_bundle",
            action_type="ebs_default_encryption",
            label="Generate PR bundle for default EBS encryption (AWS managed key)",
            mode="pr_only",
            risk_level="low",
            recommended=False,
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            impact_text="All new EBS volumes in this region will be encrypted by default.",
            warnings=[
                "Apply the bundle before creating new volumes to enforce encryption by default.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="ebs_enable_default_encryption_customer_kms",
            action_type="ebs_default_encryption",
            label="Enable default EBS encryption (customer KMS key)",
            mode="direct_fix",
            risk_level="medium",
            recommended=False,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "kms_key_arn",
                        "type": "string",
                        "required": True,
                        "description": "Customer-managed KMS key ARN to set as EBS default key.",
                    }
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "All new EBS volumes in this region will be encrypted by default using the specified "
                "customer-managed KMS key."
            ),
            warnings=[
                "Key policy and grant coverage must include all required compute roles.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="ebs_enable_default_encryption_customer_kms_pr_bundle",
            action_type="ebs_default_encryption",
            label="Generate PR bundle for default EBS encryption (customer KMS key)",
            mode="pr_only",
            risk_level="medium",
            recommended=False,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "kms_key_arn",
                        "type": "string",
                        "required": True,
                        "description": "Customer-managed KMS key ARN to set as EBS default key.",
                    }
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "All new EBS volumes in this region will be encrypted by default using the specified "
                "customer-managed KMS key."
            ),
            warnings=[
                "Validate key policy access and regional key alignment before apply.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "s3_bucket_access_logging": (
        RemediationStrategy(
            strategy_id="s3_enable_access_logging_guided",
            action_type="s3_bucket_access_logging",
            label="Enable S3 access logging (guided)",
            mode="pr_only",
            risk_level="low",
            recommended=True,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "log_bucket_name",
                        "type": "string",
                        "required": True,
                        "description": (
                            "Name of the S3 bucket that receives access logs "
                            "(must be different from the source bucket)."
                        ),
                        "placeholder": "security-autopilot-access-logs-123456789012",
                        "impact_text": (
                            "S3 server access logs will be delivered to the selected dedicated "
                            "log bucket."
                        ),
                        "group": "Logging Settings",
                        "safe_default_value": "security-autopilot-access-logs-{{account_id}}",
                        "safe_default_label": "Use a dedicated access-log bucket",
                    },
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "S3 server access logs will be enabled and delivered to a dedicated destination bucket."
            ),
            warnings=[
                "Do not use the source bucket as the logging destination.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "s3_bucket_lifecycle_configuration": (
        RemediationStrategy(
            strategy_id="s3_enable_abort_incomplete_uploads",
            action_type="s3_bucket_lifecycle_configuration",
            label="Enable lifecycle cleanup for incomplete uploads",
            mode="pr_only",
            risk_level="low",
            recommended=True,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "abort_days",
                        "type": "number",
                        "required": False,
                        "description": (
                            "Days after which incomplete multipart uploads are automatically cleaned up."
                        ),
                        "default_value": 7,
                        "min": 1,
                        "max": 365,
                        "impact_text": (
                            "Incomplete multipart uploads older than the configured number of days "
                            "will be automatically aborted."
                        ),
                        "group": "Lifecycle Settings",
                    },
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "A lifecycle rule will abort incomplete multipart uploads after the configured number of days."
            ),
            warnings=[
                "Lifecycle policy changes can affect storage behavior and cost.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "s3_bucket_encryption_kms": (
        RemediationStrategy(
            strategy_id="s3_enable_sse_kms_guided",
            action_type="s3_bucket_encryption_kms",
            label="Enable S3 default encryption (SSE-KMS)",
            mode="pr_only",
            risk_level="low",
            recommended=True,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "kms_key_mode",
                        "type": "select",
                        "required": False,
                        "description": "Select which KMS key mode to use for default bucket encryption.",
                        "default_value": "aws_managed",
                        "options": [
                            {
                                "value": "aws_managed",
                                "label": "AWS managed key (aws/s3)",
                            },
                            {
                                "value": "custom",
                                "label": "Custom KMS key",
                            },
                        ],
                        "group": "Encryption Settings",
                        "safe_default_value": "aws_managed",
                        "safe_default_label": "Use AWS managed key (aws/s3)",
                    },
                    {
                        "key": "kms_key_arn",
                        "type": "string",
                        "required": False,
                        "description": "Customer-managed KMS key ARN to use when key mode is custom.",
                        "placeholder": "arn:aws:kms:us-east-1:123456789012:key/1234abcd-5678-ef90-1234-56789abcdef0",
                        "visible_when": {
                            "field": "kms_key_mode",
                            "equals": "custom",
                        },
                        "group": "Encryption Settings",
                    },
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "Default bucket encryption will be enforced with SSE-KMS using either aws/s3 "
                "or the selected customer-managed KMS key."
            ),
            warnings=[
                "Ensure KMS key policy grants required S3 and workload principals when using a custom key.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "s3_bucket_require_ssl": (
        RemediationStrategy(
            strategy_id="s3_enforce_ssl_strict_deny",
            action_type="s3_bucket_require_ssl",
            label="Enforce SSL-only S3 requests (strict deny)",
            mode="pr_only",
            risk_level="high",
            recommended=True,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "preserve_existing_policy",
                        "type": "boolean",
                        "required": False,
                        "description": "Merge with existing bucket policy statements instead of replacing.",
                        "default_value": True,
                        "impact_text": (
                            "After applying, non-HTTPS requests to this bucket will be denied "
                            "(HTTP requests receive 403)."
                        ),
                        "group": "Policy Settings",
                    },
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "After applying, all HTTP (non-HTTPS) requests to this bucket will receive a "
                "403 Forbidden response."
            ),
            warnings=[
                "Non-TLS clients or legacy integrations will fail after apply.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="s3_enforce_ssl_with_principal_exemptions",
            action_type="s3_bucket_require_ssl",
            label="Enforce SSL with principal exemptions",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "preserve_existing_policy",
                        "type": "boolean",
                        "required": False,
                        "description": "Merge with existing bucket policy statements instead of replacing.",
                        "default_value": True,
                        "impact_text": (
                            "After applying, non-HTTPS requests to this bucket will be denied "
                            "(HTTP requests receive 403)."
                        ),
                        "group": "Policy Settings",
                    },
                    {
                        "key": "exempt_principals",
                        "type": "string_array",
                        "required": True,
                        "description": "IAM principal ARNs exempted from the strict deny rule.",
                        "group": "Policy Settings",
                    }
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            impact_text=(
                "After applying, all HTTP (non-HTTPS) requests to this bucket will receive a "
                "403 Forbidden response."
            ),
            warnings=[
                "Exemptions weaken blanket enforcement and must be tightly scoped.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="s3_keep_non_ssl_exception",
            action_type="s3_bucket_require_ssl",
            label="Keep non-SSL behavior (exception path)",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_exception_strategy_input_schema(),
            supports_exception_flow=True,
            exception_only=True,
            impact_text=(
                "Non-HTTPS requests remain allowed until the exception is resolved and SSL enforcement "
                "is applied."
            ),
            warnings=[
                "Allowing non-SSL requests increases credential and data interception risk.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "sg_restrict_public_ports": (
        RemediationStrategy(
            strategy_id="sg_restrict_public_ports_guided",
            action_type="sg_restrict_public_ports",
            label="Secure remote admin access (guided choices)",
            mode="pr_only",
            risk_level="low",
            recommended=True,
            requires_inputs=True,
            input_schema=_schema(
                [
                    {
                        "key": "access_mode",
                        "type": "select",
                        "required": True,
                        "description": "How would you like to secure remote access?",
                        "default_value": "close_public",
                        "group": "Access Control",
                        "options": [
                            {
                                "value": "close_public",
                                "label": "Close all public access",
                                "impact_text": (
                                    "Public SSH/RDP access on ports 22 and 3389 will remain until you "
                                    "manually remove the 0.0.0.0/0 rules. New restricted rules will be added."
                                ),
                            },
                            {
                                "value": "close_and_revoke",
                                "label": "Close public and auto-remove old rules",
                                "impact_text": (
                                    "All existing 0.0.0.0/0 rules on ports 22 and 3389 will be automatically "
                                    "removed. Make sure you have alternative access (SSM, VPN) before applying."
                                ),
                            },
                            {
                                "value": "restrict_to_ip",
                                "label": "Restrict to my IP",
                                "impact_text": (
                                    "Only traffic from the provided CIDR will be allowed on ports 22 and 3389. "
                                    "All other sources will be denied."
                                ),
                            },
                            {
                                "value": "restrict_to_cidr",
                                "label": "Restrict to custom CIDR",
                                "impact_text": (
                                    "Only traffic from the provided CIDR range (for example, office/VPN) "
                                    "will be allowed on ports 22 and 3389."
                                ),
                            },
                        ],
                    },
                    {
                        "key": "allowed_cidr",
                        "type": "cidr",
                        "required": False,
                        "description": "Allowed IPv4 CIDR for SSH/RDP (for example, office or VPN range).",
                        "placeholder": "203.0.113.10/32",
                        "visible_when": {
                            "field": "access_mode",
                            "equals": ["restrict_to_ip", "restrict_to_cidr"],
                        },
                        "group": "Access Control",
                        "safe_default_value": "{{detected_public_ipv4_cidr}}",
                        "safe_default_label": "Use detected public IPv4 CIDR",
                    },
                    {
                        "key": "allowed_cidr_ipv6",
                        "type": "cidr",
                        "required": False,
                        "description": "Optional allowed IPv6 CIDR for SSH/RDP.",
                        "placeholder": "2001:db8::/64",
                        "visible_when": {
                            "field": "access_mode",
                            "equals": ["restrict_to_ip", "restrict_to_cidr"],
                        },
                        "group": "Access Control",
                    },
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
            warnings=[
                (
                    "Restricting or revoking public admin ingress can lock out operators. "
                    "Confirm SSM, VPN, or bastion access before apply."
                ),
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
    "iam_root_access_key_absent": (
        RemediationStrategy(
            strategy_id="iam_root_key_disable",
            action_type="iam_root_access_key_absent",
            label="Disable root access key",
            mode="pr_only",
            risk_level="high",
            recommended=True,
            requires_inputs=False,
            input_schema=_iam_root_action_mode_schema(default_mode="disable_key"),
            supports_exception_flow=False,
            exception_only=False,
            warnings=[
                (
                    f"{ROOT_CREDENTIALS_REQUIRED_MESSAGE} "
                    f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
                ),
                "Disabling root keys can impact break-glass automations that still use root credentials.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="iam_root_key_delete",
            action_type="iam_root_access_key_absent",
            label="Delete root access key",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=False,
            input_schema=_iam_root_action_mode_schema(default_mode="delete_key"),
            supports_exception_flow=False,
            exception_only=False,
            warnings=[
                (
                    f"{ROOT_CREDENTIALS_REQUIRED_MESSAGE} "
                    f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
                ),
                (
                    "Gate: Root MFA must be active before this delete path is selectable. "
                    "If AccountMFAEnabled=0, strategy selection is blocked."
                ),
                "Deleting root keys is irreversible and requires validated fallback access.",
            ],
            legacy_pr_bundle_variant=None,
        ),
        RemediationStrategy(
            strategy_id="iam_root_key_keep_exception",
            action_type="iam_root_access_key_absent",
            label="Keep root key (exception path)",
            mode="pr_only",
            risk_level="high",
            recommended=False,
            requires_inputs=True,
            input_schema=_exception_strategy_input_schema(),
            supports_exception_flow=True,
            exception_only=True,
            warnings=[
                "Root access keys are a critical compromise path and should be time-bounded exceptions only.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
}

OPTIONAL_STRATEGY_ACTION_TYPES: set[str] = {
    # Keep these strategy catalogs optional so legacy create-run callers that do
    # not send strategy_id remain backward compatible.
    "enable_security_hub",
    "enable_guardduty",
}

_ROLLBACK_COMMAND_BY_ACTION_TYPE: dict[str, str] = {
    "s3_block_public_access": (
        "aws s3control delete-public-access-block --account-id <ACCOUNT_ID>"
    ),
    "s3_bucket_block_public_access": (
        "aws s3api delete-public-access-block --bucket <BUCKET_NAME>"
    ),
    "s3_bucket_encryption": (
        "aws s3api delete-bucket-encryption --bucket <BUCKET_NAME>"
    ),
    "aws_config_enabled": (
        "aws configservice stop-configuration-recorder "
        "--configuration-recorder-name <RECORDER_NAME>"
    ),
    "cloudtrail_enabled": (
        "aws cloudtrail stop-logging --name <TRAIL_NAME>"
    ),
    "enable_security_hub": "aws securityhub disable-security-hub",
    "enable_guardduty": (
        "aws guardduty delete-detector --detector-id <DETECTOR_ID>"
    ),
    "ssm_block_public_sharing": (
        "aws ssm update-service-setting "
        "--setting-id /ssm/documents/console/public-sharing-permission "
        "--setting-value Enable"
    ),
    "ebs_snapshot_block_public_access": (
        "aws ec2 disable-snapshot-block-public-access"
    ),
    "ebs_default_encryption": "aws ec2 disable-ebs-encryption-by-default",
    "s3_bucket_access_logging": (
        "aws s3api put-bucket-logging --bucket <SOURCE_BUCKET> --bucket-logging-status '{}'"
    ),
    "s3_bucket_lifecycle_configuration": (
        "aws s3api delete-bucket-lifecycle --bucket <BUCKET_NAME>"
    ),
    "s3_bucket_encryption_kms": (
        "aws s3api put-bucket-encryption --bucket <BUCKET_NAME> "
        "--server-side-encryption-configuration "
        "'{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}'"
    ),
    "s3_bucket_require_ssl": (
        "aws s3api delete-bucket-policy --bucket <BUCKET_NAME>"
    ),
    "sg_restrict_public_ports": (
        "aws ec2 authorize-security-group-ingress --group-id <SECURITY_GROUP_ID> "
        "--ip-permissions "
        "'[{\"IpProtocol\":\"tcp\",\"FromPort\":22,\"ToPort\":22,\"IpRanges\":[{\"CidrIp\":\"0.0.0.0/0\"}]},"
        "{\"IpProtocol\":\"tcp\",\"FromPort\":3389,\"ToPort\":3389,\"IpRanges\":[{\"CidrIp\":\"0.0.0.0/0\"}]}]'"
    ),
    "iam_root_access_key_absent": (
        "aws iam update-access-key --access-key-id <ROOT_ACCESS_KEY_ID> --status Active"
    ),
}

_ROLLBACK_COMMAND_BY_STRATEGY_ID: dict[str, str] = {
    "iam_root_key_delete": "aws iam create-access-key",
}

_ESTIMATED_RESOLUTION_TIME_BY_ACTION_TYPE: dict[str, str] = {
    # Security Hub / GuardDuty control family
    "enable_security_hub": "~1 hour",
    "enable_guardduty": "~1 hour",
    # Config / CloudTrail control family
    "aws_config_enabled": "1-6 hours",
    "cloudtrail_enabled": "1-6 hours",
    # Remaining controls (EC2, S3, IAM, SSM)
    "s3_block_public_access": "12-24 hours",
    "s3_bucket_block_public_access": "12-24 hours",
    "s3_bucket_encryption": "12-24 hours",
    "ssm_block_public_sharing": "12-24 hours",
    "ebs_snapshot_block_public_access": "12-24 hours",
    "ebs_default_encryption": "12-24 hours",
    "s3_bucket_access_logging": "12-24 hours",
    "s3_bucket_lifecycle_configuration": "12-24 hours",
    "s3_bucket_encryption_kms": "12-24 hours",
    "s3_bucket_require_ssl": "12-24 hours",
    "sg_restrict_public_ports": "12-24 hours",
    "iam_root_access_key_absent": "12-24 hours",
}

_NO_IMMEDIATE_REEVAL_ACTION_TYPES: set[str] = {
    "enable_security_hub",
    "enable_guardduty",
}

_BLAST_RADIUS_BY_ACTION_TYPE: dict[str, BlastRadius] = {
    # Account-wide additive controls
    "s3_block_public_access": "account",
    "aws_config_enabled": "account",
    "enable_security_hub": "account",
    "enable_guardduty": "account",
    "ssm_block_public_sharing": "account",
    "ebs_snapshot_block_public_access": "account",
    "ebs_default_encryption": "account",
    # Resource-specific additive controls
    "s3_bucket_block_public_access": "resource",
    "s3_bucket_encryption": "resource",
    "cloudtrail_enabled": "resource",
    "s3_bucket_access_logging": "resource",
    "s3_bucket_lifecycle_configuration": "resource",
    "s3_bucket_encryption_kms": "resource",
    "s3_bucket_require_ssl": "resource",
    # Access-changing controls
    "sg_restrict_public_ports": "access_changing",
    "iam_root_access_key_absent": "access_changing",
}


def list_strategies_for_action_type(action_type: str | None) -> list[RemediationStrategy]:
    """Return declared strategies for an action_type."""
    if not action_type:
        return []
    return list(STRATEGY_REGISTRY.get(action_type.strip(), ()))


def list_mode_options_for_action_type(action_type: str | None) -> list[Mode]:
    """Return unique mode options in stable order for the action type."""
    options: list[Mode] = []
    seen: set[str] = set()
    for strategy in list_strategies_for_action_type(action_type):
        mode = strategy["mode"]
        if mode in seen:
            continue
        seen.add(mode)
        options.append(mode)
    return options


def strategy_required_for_action_type(action_type: str | None) -> bool:
    """True when the action type is covered by strategy catalog entries."""
    if not action_type:
        return False
    normalized_action = action_type.strip()
    if normalized_action in OPTIONAL_STRATEGY_ACTION_TYPES:
        return False
    return len(list_strategies_for_action_type(normalized_action)) > 0


def get_strategy(action_type: str | None, strategy_id: str | None) -> RemediationStrategy | None:
    """Lookup one strategy by action_type and strategy_id."""
    if not action_type or not strategy_id:
        return None
    normalized_action = action_type.strip()
    normalized_strategy = strategy_id.strip()
    for strategy in STRATEGY_REGISTRY.get(normalized_action, ()):
        if strategy["strategy_id"] == normalized_strategy:
            return strategy
    return None


def get_rollback_command(action_type: str | None, strategy_id: str | None = None) -> str | None:
    """Return rollback command guidance for a remediation strategy/action."""
    if strategy_id:
        strategy_command = _ROLLBACK_COMMAND_BY_STRATEGY_ID.get(strategy_id.strip())
        if strategy_command:
            return strategy_command
    if not action_type:
        return None
    return _ROLLBACK_COMMAND_BY_ACTION_TYPE.get(action_type.strip())


def get_estimated_resolution_time(action_type: str | None, strategy_id: str | None = None) -> str:
    """Return estimated time to Security Hub PASSED for a strategy/action."""
    strategy = get_strategy(action_type, strategy_id)
    strategy_estimate = strategy.get("estimated_resolution_time") if strategy else None
    if isinstance(strategy_estimate, str) and strategy_estimate.strip():
        return strategy_estimate.strip()
    if not action_type:
        return "12-24 hours"
    return _ESTIMATED_RESOLUTION_TIME_BY_ACTION_TYPE.get(action_type.strip(), "12-24 hours")


def supports_immediate_reeval(action_type: str | None, strategy_id: str | None = None) -> bool:
    """Return whether immediate re-evaluation trigger is supported for a strategy/action."""
    strategy = get_strategy(action_type, strategy_id)
    if strategy and strategy.get("exception_only"):
        return False
    strategy_support = strategy.get("supports_immediate_reeval") if strategy else None
    if isinstance(strategy_support, bool):
        return strategy_support
    if not action_type:
        return False
    return action_type.strip() not in _NO_IMMEDIATE_REEVAL_ACTION_TYPES


def get_blast_radius(action_type: str | None, strategy_id: str | None = None) -> BlastRadius:
    """Return blast-radius category for a remediation strategy/action."""
    strategy = get_strategy(action_type, strategy_id)
    strategy_radius = strategy.get("blast_radius") if strategy else None
    if strategy_radius in {"account", "resource", "access_changing"}:
        return strategy_radius
    if not action_type:
        return "resource"
    return _BLAST_RADIUS_BY_ACTION_TYPE.get(action_type.strip(), "resource")


def _get_strategy_by_id(strategy_id: str | None) -> RemediationStrategy | None:
    if not strategy_id:
        return None
    normalized_strategy = strategy_id.strip()
    if not normalized_strategy:
        return None
    for strategies in STRATEGY_REGISTRY.values():
        for strategy in strategies:
            if strategy["strategy_id"] == normalized_strategy:
                return strategy
    return None


def _resolve_impact_field_values(
    fields: list[StrategyInputField],
    strategy_inputs: dict[str, Any],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in fields:
        key = field["key"]
        value = strategy_inputs.get(key)
        if value is None:
            value = field.get("default_value")
        values[key] = value
    return values


def _impact_equals(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_impact_equals(actual, item) for item in expected)
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, (int, float)):
        return actual == expected
    return str(actual or "").strip() == str(expected or "").strip()


def _is_impact_field_visible(field: StrategyInputField, values: dict[str, Any]) -> bool:
    visible_when = field.get("visible_when")
    if not visible_when:
        return True
    actual = values.get(visible_when["field"])
    return _impact_equals(actual, visible_when["equals"])


def _append_impact_text(texts: list[str], text: Any) -> None:
    if not isinstance(text, str):
        return
    cleaned = text.strip()
    if cleaned and cleaned not in texts:
        texts.append(cleaned)


def get_impact_summary(strategy_id: str | None, strategy_inputs: dict[str, Any] | None) -> str:
    """
    Build a human-readable impact summary for preview surfaces.

    Includes strategy-level impact text plus visible field/selected-option impact text.
    """
    strategy = _get_strategy_by_id(strategy_id)
    if strategy is None:
        return ""

    fields = strategy["input_schema"].get("fields", [])
    safe_inputs = strategy_inputs if isinstance(strategy_inputs, dict) else {}
    values = _resolve_impact_field_values(fields, safe_inputs)

    impact_parts: list[str] = []
    _append_impact_text(impact_parts, strategy.get("impact_text"))
    for field in fields:
        if not _is_impact_field_visible(field, values):
            continue
        _append_impact_text(impact_parts, field.get("impact_text"))
        if field["type"] != "select":
            continue
        selected_value = values.get(field["key"])
        for option in field.get("options", []):
            if option.get("value") == selected_value:
                _append_impact_text(impact_parts, option.get("impact_text"))
                break
    return " ".join(impact_parts)


_STATE_SIMULATION_STRATEGY_IDS = frozenset(
    {
        "sg_restrict_public_ports_guided",
        "s3_enforce_ssl_strict_deny",
        "s3_enforce_ssl_with_principal_exemptions",
        "config_enable_centralized_delivery",
        "config_enable_account_local_delivery",
    }
)


def strategy_supports_state_simulation(strategy_id: str | None) -> bool:
    if not strategy_id:
        return False
    return strategy_id.strip() in _STATE_SIMULATION_STRATEGY_IDS


def _empty_state_simulation() -> RemediationStateSimulation:
    return {"before_state": {}, "after_state": {}, "diff_lines": []}


def _simulation_evidence(runtime_signals: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(runtime_signals, dict):
        return {}
    evidence = runtime_signals.get("evidence")
    if isinstance(evidence, dict):
        return evidence
    return {}


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _normalize_port_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    ports: set[int] = set()
    for item in value:
        if isinstance(item, int):
            ports.add(item)
            continue
        if isinstance(item, str) and item.isdigit():
            ports.add(int(item))
    return sorted(ports)


def _format_tcp_ports(ports: list[int]) -> str:
    if not ports:
        return "none"
    return ", ".join(f"tcp/{port}" for port in ports)


def _append_diff_line(
    diff_lines: list[PreviewDiffLine],
    diff_type: DiffLineType,
    label: str,
    value: str,
) -> None:
    cleaned_label = label.strip()
    cleaned_value = value.strip()
    if not cleaned_label or not cleaned_value:
        return
    diff_lines.append({"type": diff_type, "label": cleaned_label, "value": cleaned_value})


def _simulate_ec2_53(values: dict[str, Any], runtime_signals: dict[str, Any] | None) -> RemediationStateSimulation:
    evidence = _simulation_evidence(runtime_signals)
    access_mode = str(values.get("access_mode") or "close_public").strip() or "close_public"
    allowed_cidr = str(values.get("allowed_cidr") or "10.0.0.0/8").strip() or "10.0.0.0/8"
    allowed_cidr_ipv6 = str(values.get("allowed_cidr_ipv6") or "").strip()
    public_ipv4_ports = _normalize_port_list(evidence.get("public_admin_ipv4_ports"))
    public_ipv6_ports = _normalize_port_list(evidence.get("public_admin_ipv6_ports"))
    remove_public = access_mode == "close_and_revoke"

    before_state: dict[str, Any] = {
        "security_group_id": evidence.get("security_group_id"),
        "public_admin_ipv4_ports": public_ipv4_ports,
        "public_admin_ipv6_ports": public_ipv6_ports,
        "access_mode": access_mode,
    }
    after_state: dict[str, Any] = {
        "security_group_id": evidence.get("security_group_id"),
        "public_admin_ipv4_ports": [] if remove_public else public_ipv4_ports,
        "public_admin_ipv6_ports": [] if remove_public else public_ipv6_ports,
        "restricted_ipv4_cidr": allowed_cidr,
        "restricted_ipv6_cidr": allowed_cidr_ipv6 or None,
        "access_mode": access_mode,
    }

    diff_lines: list[PreviewDiffLine] = []
    if public_ipv4_ports:
        _append_diff_line(
            diff_lines,
            "remove" if remove_public else "unchanged",
            "Public admin ingress (IPv4)",
            f"0.0.0.0/0 on {_format_tcp_ports(public_ipv4_ports)}",
        )
    else:
        _append_diff_line(diff_lines, "unchanged", "Public admin ingress (IPv4)", "none detected")

    if public_ipv6_ports:
        _append_diff_line(
            diff_lines,
            "remove" if remove_public else "unchanged",
            "Public admin ingress (IPv6)",
            f"::/0 on {_format_tcp_ports(public_ipv6_ports)}",
        )
    else:
        _append_diff_line(diff_lines, "unchanged", "Public admin ingress (IPv6)", "none detected")

    _append_diff_line(
        diff_lines,
        "add",
        "Restricted admin ingress (IPv4)",
        f"{allowed_cidr} on tcp/22, tcp/3389",
    )
    if allowed_cidr_ipv6:
        _append_diff_line(
            diff_lines,
            "add",
            "Restricted admin ingress (IPv6)",
            f"{allowed_cidr_ipv6} on tcp/22, tcp/3389",
        )
    return {"before_state": before_state, "after_state": after_state, "diff_lines": diff_lines}


def _simulate_s3_5(values: dict[str, Any], runtime_signals: dict[str, Any] | None) -> RemediationStateSimulation:
    evidence = _simulation_evidence(runtime_signals)
    bucket = str(evidence.get("target_bucket") or "").strip() or None
    ssl_enforced_before = _coerce_bool(evidence.get("s3_ssl_deny_present"))
    statement_count_raw = evidence.get("existing_bucket_policy_statement_count")
    statement_count = int(statement_count_raw) if isinstance(statement_count_raw, int) else None
    preserve_existing = _coerce_bool(values.get("preserve_existing_policy"))
    if preserve_existing is None:
        preserve_existing = True

    before_state: dict[str, Any] = {
        "bucket": bucket,
        "ssl_enforced": ssl_enforced_before,
        "existing_policy_statement_count": statement_count,
        "preserve_existing_policy": preserve_existing,
    }
    after_state: dict[str, Any] = {
        "bucket": bucket,
        "ssl_enforced": True,
        "existing_policy_statement_count": statement_count,
        "preserve_existing_policy": preserve_existing,
    }

    diff_lines: list[PreviewDiffLine] = []
    if ssl_enforced_before is True:
        _append_diff_line(diff_lines, "unchanged", "HTTPS-only access", "already enforced via bucket policy")
    else:
        _append_diff_line(
            diff_lines,
            "add",
            "HTTPS-only access",
            "Deny requests with aws:SecureTransport=false (HTTP traffic blocked)",
        )

    if statement_count is None:
        _append_diff_line(diff_lines, "unchanged", "Existing policy statements", "state unavailable")
    elif statement_count == 0:
        _append_diff_line(diff_lines, "unchanged", "Existing policy statements", "none")
    elif preserve_existing:
        _append_diff_line(
            diff_lines,
            "unchanged",
            "Existing policy statements",
            f"preserved ({statement_count} statements)",
        )
    else:
        _append_diff_line(
            diff_lines,
            "remove",
            "Existing policy statements",
            f"may be replaced ({statement_count} statements)",
        )

    return {"before_state": before_state, "after_state": after_state, "diff_lines": diff_lines}


def _resolve_config_target_bucket(
    strategy_id: str,
    values: dict[str, Any],
    before_bucket: str | None,
) -> str:
    if strategy_id == "config_enable_account_local_delivery":
        return before_bucket or "security-autopilot-config-bucket"

    delivery_mode = str(values.get("delivery_bucket_mode") or "use_existing").strip() or "use_existing"
    existing_bucket = str(values.get("existing_bucket_name") or "").strip()
    explicit_bucket = str(values.get("delivery_bucket") or "").strip()
    if delivery_mode == "create_new":
        return explicit_bucket or existing_bucket or "security-autopilot-config-bucket"
    return existing_bucket or explicit_bucket or before_bucket or "existing_bucket_required"


def _resolve_config_scope(strategy_id: str, values: dict[str, Any], before_scope: str) -> str:
    if strategy_id == "config_enable_account_local_delivery":
        return "all_resources"
    selected_scope = str(values.get("recording_scope") or "keep_existing").strip() or "keep_existing"
    if selected_scope == "all_resources":
        return "all_resources"
    if before_scope in {"all_resources", "custom"}:
        return before_scope
    return "all_resources"


def _simulate_config_1(
    strategy_id: str,
    values: dict[str, Any],
    runtime_signals: dict[str, Any] | None,
) -> RemediationStateSimulation:
    evidence = _simulation_evidence(runtime_signals)
    before_recorder_enabled = _coerce_bool(evidence.get("config_recorder_exists"))
    before_scope = str(evidence.get("config_recording_scope") or "not_configured").strip() or "not_configured"
    before_bucket = str(evidence.get("config_delivery_bucket_name") or "").strip() or None
    before_kms_key = str(evidence.get("config_delivery_kms_key_arn") or "").strip() or None

    target_scope = _resolve_config_scope(strategy_id, values, before_scope)
    target_bucket = _resolve_config_target_bucket(strategy_id, values, before_bucket)
    encrypt_with_kms = _coerce_bool(values.get("encrypt_with_kms")) is True
    requested_kms_key = str(values.get("kms_key_arn") or "").strip()
    target_kms_key = requested_kms_key if encrypt_with_kms and requested_kms_key else None

    before_state: dict[str, Any] = {
        "recorder_enabled": before_recorder_enabled,
        "recording_scope": before_scope,
        "delivery_bucket": before_bucket,
        "delivery_kms_key_arn": before_kms_key,
    }
    after_state: dict[str, Any] = {
        "recorder_enabled": True,
        "recording_scope": target_scope,
        "delivery_bucket": target_bucket,
        "delivery_kms_key_arn": target_kms_key,
    }

    diff_lines: list[PreviewDiffLine] = []
    if before_recorder_enabled is True:
        _append_diff_line(diff_lines, "unchanged", "Configuration recorder", "enabled")
    else:
        _append_diff_line(diff_lines, "add", "Configuration recorder", "enabled")

    if before_scope == target_scope:
        _append_diff_line(diff_lines, "unchanged", "Recording scope", target_scope)
    elif before_scope != "not_configured":
        _append_diff_line(diff_lines, "remove", "Recording scope", before_scope)
        _append_diff_line(diff_lines, "add", "Recording scope", target_scope)
    else:
        _append_diff_line(diff_lines, "add", "Recording scope", target_scope)

    if before_bucket and before_bucket != target_bucket:
        _append_diff_line(diff_lines, "remove", "Delivery bucket", before_bucket)
        _append_diff_line(diff_lines, "add", "Delivery bucket", target_bucket)
    elif before_bucket == target_bucket:
        _append_diff_line(diff_lines, "unchanged", "Delivery bucket", target_bucket)
    else:
        _append_diff_line(diff_lines, "add", "Delivery bucket", target_bucket)

    if before_kms_key == target_kms_key and before_kms_key:
        _append_diff_line(diff_lines, "unchanged", "Delivery encryption (KMS)", before_kms_key)
    elif before_kms_key and not target_kms_key:
        _append_diff_line(diff_lines, "remove", "Delivery encryption (KMS)", before_kms_key)
    elif target_kms_key:
        _append_diff_line(diff_lines, "add", "Delivery encryption (KMS)", target_kms_key)
    else:
        _append_diff_line(diff_lines, "unchanged", "Delivery encryption (KMS)", "none")

    return {"before_state": before_state, "after_state": after_state, "diff_lines": diff_lines}


def build_remediation_state_simulation(
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    runtime_signals: dict[str, Any] | None = None,
) -> RemediationStateSimulation:
    """Build before/after state and diff lines for supported remediation strategies."""
    if not strategy_supports_state_simulation(strategy_id):
        return _empty_state_simulation()
    strategy = _get_strategy_by_id(strategy_id)
    if strategy is None:
        return _empty_state_simulation()

    fields = strategy["input_schema"].get("fields", [])
    safe_inputs = strategy_inputs if isinstance(strategy_inputs, dict) else {}
    values = _resolve_impact_field_values(fields, safe_inputs)
    strategy_key = strategy["strategy_id"]

    if strategy_key == "sg_restrict_public_ports_guided":
        return _simulate_ec2_53(values, runtime_signals)
    if strategy_key in {"s3_enforce_ssl_strict_deny", "s3_enforce_ssl_with_principal_exemptions"}:
        return _simulate_s3_5(values, runtime_signals)
    if strategy_key in {"config_enable_centralized_delivery", "config_enable_account_local_delivery"}:
        return _simulate_config_1(strategy_key, values, runtime_signals)
    return _empty_state_simulation()


def map_legacy_variant_to_strategy(action_type: str | None, pr_bundle_variant: str | None) -> str | None:
    """Map legacy `pr_bundle_variant` values into strategy IDs when available."""
    if not action_type or not pr_bundle_variant:
        return None
    normalized_variant = pr_bundle_variant.strip()
    if not normalized_variant:
        return None
    for strategy in STRATEGY_REGISTRY.get(action_type.strip(), ()):
        if strategy.get("legacy_pr_bundle_variant") == normalized_variant:
            return strategy["strategy_id"]
    return None


def validate_strategy(action_type: str | None, strategy_id: str | None, mode: Mode) -> RemediationStrategy:
    """Validate selected strategy exists and matches requested run mode."""
    strategy = get_strategy(action_type, strategy_id)
    if strategy is None:
        raise ValueError(f"Unknown strategy_id '{strategy_id}' for action_type '{action_type}'.")
    if strategy["mode"] != mode:
        raise ValueError(
            f"Strategy '{strategy_id}' requires mode '{strategy['mode']}', but got '{mode}'."
        )
    return strategy


def validate_strategy_inputs(
    strategy: RemediationStrategy,
    raw_inputs: dict[str, Any] | None,
    *,
    allow_missing_required_keys: set[str] | None = None,
) -> dict[str, Any]:
    """
    Validate and normalize strategy inputs according to strategy input schema.

    - Unknown fields are rejected.
    - Required fields must be present and non-empty.
    - string_array fields are normalized to unique, non-empty strings.
    """
    fields = strategy["input_schema"].get("fields", [])
    if not fields:
        return {}

    if raw_inputs is None:
        raw_inputs = {}
    if not isinstance(raw_inputs, dict):
        raise ValueError("strategy_inputs must be an object.")

    allowed_missing = allow_missing_required_keys or set()
    field_map = {field["key"]: field for field in fields}
    unknown_keys = [key for key in raw_inputs.keys() if key not in field_map]
    if unknown_keys:
        raise ValueError(f"strategy_inputs contains unknown field(s): {', '.join(sorted(unknown_keys))}.")

    normalized: dict[str, Any] = {}
    for key, field in field_map.items():
        required = field["required"]
        value = raw_inputs.get(key)

        if value is None:
            if required and not _field_has_implicit_default(field) and key not in allowed_missing:
                raise ValueError(f"strategy_inputs.{key} is required.")
            continue

        if field["type"] == "string":
            if not isinstance(value, str):
                raise ValueError(f"strategy_inputs.{key} must be a string.")
            cleaned = value.strip()
            if required and not cleaned:
                raise ValueError(f"strategy_inputs.{key} cannot be empty.")
            if not cleaned:
                continue
            _validate_enum_and_options(key, cleaned, field)
            normalized[key] = cleaned
            continue

        if field["type"] == "string_array":
            if not isinstance(value, list):
                raise ValueError(f"strategy_inputs.{key} must be an array of strings.")
            cleaned_values: list[str] = []
            seen: set[str] = set()
            for item in value:
                if not isinstance(item, str):
                    raise ValueError(f"strategy_inputs.{key} must contain only strings.")
                cleaned_item = item.strip()
                if not cleaned_item:
                    continue
                if cleaned_item in seen:
                    continue
                seen.add(cleaned_item)
                cleaned_values.append(cleaned_item)
            if required and not cleaned_values:
                raise ValueError(f"strategy_inputs.{key} must include at least one value.")
            if cleaned_values:
                normalized[key] = cleaned_values
            continue

        if field["type"] == "select":
            if not isinstance(value, str):
                raise ValueError(f"strategy_inputs.{key} must be a string.")
            cleaned = value.strip()
            if required and not cleaned:
                raise ValueError(f"strategy_inputs.{key} cannot be empty.")
            if not cleaned:
                continue
            _validate_enum_and_options(key, cleaned, field)
            normalized[key] = cleaned
            continue

        if field["type"] == "boolean":
            if type(value) is not bool:
                raise ValueError(f"strategy_inputs.{key} must be a boolean.")
            normalized[key] = value
            continue

        if field["type"] == "cidr":
            if not isinstance(value, str):
                raise ValueError(f"strategy_inputs.{key} must be a CIDR string.")
            cleaned = value.strip()
            if required and not cleaned:
                raise ValueError(f"strategy_inputs.{key} cannot be empty.")
            if not cleaned:
                continue
            try:
                normalized[key] = str(ip_network(cleaned, strict=False))
            except ValueError as exc:
                raise ValueError(f"strategy_inputs.{key} must be a valid CIDR.") from exc
            continue

        if field["type"] == "number":
            if type(value) not in (int, float):
                raise ValueError(f"strategy_inputs.{key} must be a number.")
            min_value = field.get("min")
            if isinstance(min_value, (int, float)) and value < min_value:
                raise ValueError(f"strategy_inputs.{key} must be >= {min_value}.")
            max_value = field.get("max")
            if isinstance(max_value, (int, float)) and value > max_value:
                raise ValueError(f"strategy_inputs.{key} must be <= {max_value}.")
            normalized[key] = value
            continue

        raise ValueError(f"Unsupported input type '{field['type']}' for strategy_inputs.{key}.")

    if strategy.get("action_type") == "iam_root_access_key_absent":
        action_mode = normalized.get("action_mode")
        if action_mode == "delete_key" and strategy.get("strategy_id") == "iam_root_key_disable":
            raise ValueError(
                "strategy_inputs.action_mode=delete_key requires strategy_id 'iam_root_key_delete'."
            )
        if action_mode == "disable_key" and strategy.get("strategy_id") == "iam_root_key_delete":
            raise ValueError(
                "strategy_inputs.action_mode=disable_key requires strategy_id 'iam_root_key_disable'."
            )

    return normalized


def _field_has_implicit_default(field: StrategyInputField) -> bool:
    if "default_value" in field:
        return True
    safe_default = field.get("safe_default_value")
    return isinstance(safe_default, str) and "{{" not in safe_default and bool(safe_default.strip())


def _validate_enum_and_options(key: str, value: str, field: StrategyInputField) -> None:
    enum_values = field.get("enum")
    if enum_values and value not in enum_values:
        raise ValueError(f"strategy_inputs.{key} must be one of: {', '.join(enum_values)}.")

    options = field.get("options")
    if not options:
        return

    option_values = [option["value"] for option in options]
    if value not in option_values:
        raise ValueError(f"strategy_inputs.{key} must be one of: {', '.join(option_values)}.")
