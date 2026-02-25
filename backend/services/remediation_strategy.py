"""
Remediation strategy registry and validation helpers.

Phase 1 introduces strategy selection for high-impact remediations so callers
must choose an explicit remediation path (and acknowledge risk when required).
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from backend.services.root_credentials_workflow import (
    ROOT_CREDENTIALS_REQUIRED_MESSAGE,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
)

Mode = Literal["pr_only", "direct_fix"]
RiskLevel = Literal["low", "medium", "high"]
InputType = Literal["string", "string_array"]


class StrategyInputField(TypedDict):
    """One user-provided input accepted by a remediation strategy."""

    key: str
    type: InputType
    required: bool
    description: str
    enum: NotRequired[list[str]]


class StrategyInputSchema(TypedDict):
    """Schema descriptor for strategy inputs."""

    fields: list[StrategyInputField]


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
    warnings: list[str]
    legacy_pr_bundle_variant: str | None


def _schema(fields: list[StrategyInputField] | None = None) -> StrategyInputSchema:
    return {"fields": fields or []}


STRATEGY_REGISTRY: dict[str, tuple[RemediationStrategy, ...]] = {
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
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=True,
            exception_only=True,
            warnings=[
                "Keeps public exposure; requires explicit business approval and compensating controls.",
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
                        "key": "delivery_bucket",
                        "type": "string",
                        "required": True,
                        "description": "Centralized S3 bucket for Config delivery.",
                    },
                    {
                        "key": "kms_key_arn",
                        "type": "string",
                        "required": False,
                        "description": "Optional KMS key ARN for encrypting Config delivery.",
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
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=True,
            exception_only=True,
            warnings=[
                "Skipping Config reduces change visibility and audit evidence quality.",
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
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=True,
            exception_only=True,
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
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=True,
            exception_only=True,
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
            warnings=[
                "Validate key policy access and regional key alignment before apply.",
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
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
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
                        "key": "exempt_principals",
                        "type": "string_array",
                        "required": True,
                        "description": "IAM principal ARNs exempted from the strict deny rule.",
                    }
                ]
            ),
            supports_exception_flow=False,
            exception_only=False,
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
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=True,
            exception_only=True,
            warnings=[
                "Allowing non-SSL requests increases credential and data interception risk.",
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
            input_schema=_schema(),
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
            input_schema=_schema(),
            supports_exception_flow=False,
            exception_only=False,
            warnings=[
                (
                    f"{ROOT_CREDENTIALS_REQUIRED_MESSAGE} "
                    f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
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
            requires_inputs=False,
            input_schema=_schema(),
            supports_exception_flow=True,
            exception_only=True,
            warnings=[
                "Root access keys are a critical compromise path and should be time-bounded exceptions only.",
            ],
            legacy_pr_bundle_variant=None,
        ),
    ),
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
    return len(list_strategies_for_action_type(action_type)) > 0


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


def validate_strategy_inputs(strategy: RemediationStrategy, raw_inputs: dict[str, Any] | None) -> dict[str, Any]:
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

    field_map = {field["key"]: field for field in fields}
    unknown_keys = [key for key in raw_inputs.keys() if key not in field_map]
    if unknown_keys:
        raise ValueError(f"strategy_inputs contains unknown field(s): {', '.join(sorted(unknown_keys))}.")

    normalized: dict[str, Any] = {}
    for key, field in field_map.items():
        required = field["required"]
        value = raw_inputs.get(key)

        if value is None:
            if required:
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
            enum_values = field.get("enum")
            if enum_values and cleaned not in enum_values:
                raise ValueError(
                    f"strategy_inputs.{key} must be one of: {', '.join(enum_values)}."
                )
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

        raise ValueError(f"Unsupported input type '{field['type']}' for strategy_inputs.{key}.")

    return normalized
