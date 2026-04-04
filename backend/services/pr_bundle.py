"""
PR bundle service (Step 9.1).

Loads action context and dispatches by action_type to action-specific IaC
generators. Dispatch list extended to all 7 types with subsection refs:
9.2 (s3_block_public_access), 9.3 (enable_security_hub), 9.4 (enable_guardduty),
9.5 (CloudFormation for all 7), 9.9 (s3_bucket_block_public_access),
9.10 (s3_bucket_encryption), 9.11 (sg_restrict_public_ports), 9.12 (cloudtrail_enabled).
Deliverable: all 7 generators. Worker passes run.action (selectinload); no DB access.
"""
from __future__ import annotations

import re
import uuid
import json
import copy
import hashlib
from ipaddress import ip_network
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, NoReturn, Protocol, TypedDict

from typing_extensions import NotRequired

from backend.services.aws_config_bundle_support import (
    AWS_CONFIG_APPLY_SCRIPT_PATH,
    AWS_CONFIG_ROLLBACK_DIR,
    AWS_CONFIG_ROLLBACK_SCRIPT_PATH,
    aws_config_apply_script_content,
    aws_config_bundle_rollback_metadata,
    aws_config_restore_script_content,
)
from backend.services.aws_sg_bundle_support import (
    AWS_SG_APPLY_SCRIPT_PATH,
    AWS_SG_ROLLBACK_SCRIPT_PATH,
    aws_sg_bundle_rollback_metadata,
    aws_sg_capture_script_content,
    aws_sg_restore_script_content,
)
from backend.services.aws_cloudfront_bundle_support import (
    AWS_CLOUDFRONT_OAC_DISCOVERY_SCRIPT_PATH,
    AWS_CLOUDFRONT_OAC_DISCOVERY_QUERY_PATH,
    aws_cloudfront_oac_discovery_script_content,
)
from backend.services.aws_s3_bundle_support import (
    AWS_S3_POLICY_CAPTURE_SCRIPT_PATH,
    AWS_S3_POLICY_FETCH_SCRIPT_PATH,
    AWS_S3_POLICY_RESTORE_SCRIPT_PATH,
    aws_s3_bundle_rollback_metadata,
    aws_s3_policy_capture_script_content,
    aws_s3_policy_fetch_script_content,
    aws_s3_policy_restore_script_content,
)
from backend.services.aws_s3_lifecycle_bundle_support import (
    AWS_S3_LIFECYCLE_APPLY_SCRIPT_PATH,
    AWS_S3_LIFECYCLE_RESTORE_SCRIPT_PATH,
    aws_s3_lifecycle_bundle_rollback_metadata,
    aws_s3_lifecycle_merge_script_content,
    aws_s3_lifecycle_restore_script_content,
)
from backend.services.aws_s3_encryption_bundle_support import (
    AWS_S3_ENCRYPTION_CAPTURE_SCRIPT_PATH,
    AWS_S3_ENCRYPTION_RESTORE_SCRIPT_PATH,
    aws_s3_encryption_bundle_rollback_metadata,
    aws_s3_encryption_capture_script_content,
    aws_s3_encryption_restore_script_content,
)
from backend.services.remediation_support_bucket import (
    SUPPORT_BUCKET_ROLE_AWS_CONFIG_DELIVERY,
    SUPPORT_BUCKET_ROLE_CLOUDTRAIL_LOGS,
    SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS,
    terraform_support_bucket_blocks,
)
from backend.services.s3_lifecycle_preservation import (
    analyze_lifecycle_preservation,
    lifecycle_rules_to_terraform,
)
from backend.services.root_credentials_workflow import (
    ROOT_CREDENTIALS_REQUIRED_MESSAGE,
    ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
)
from backend.services.remediation_profile_resolver import normalize_support_tier

# ---------------------------------------------------------------------------
# Contract: return shape and action interface
# ---------------------------------------------------------------------------

PRBundleFormat = Literal["terraform", "cloudformation"]

TERRAFORM_FORMAT: PRBundleFormat = "terraform"
CLOUDFORMATION_FORMAT: PRBundleFormat = "cloudformation"
TERRAFORM_AWS_PROVIDER_VERSION_CONSTRAINT = "= 5.100.0"
TERRAFORM_EXTERNAL_PROVIDER_VERSION_CONSTRAINT = "= 2.3.5"
TERRAFORM_NULL_PROVIDER_VERSION_CONSTRAINT = "= 3.2.4"


class PRBundleFile(TypedDict):
    """A single file in a PR bundle."""

    path: str
    content: str


class PRBundleResult(TypedDict):
    """
    Return type of generate_pr_bundle.

    - format: IaC format (terraform | cloudformation).
    - files: List of { path, content } for generated files.
    - steps: Ordered list of human-readable steps for the user to apply the bundle.
    """

    format: str
    files: list[PRBundleFile]
    steps: list[str]
    metadata: NotRequired[dict[str, Any]]


class PRBundleErrorPayload(TypedDict):
    """Structured payload emitted when PR bundle generation cannot continue."""

    code: str
    detail: str
    action_type: str
    format: str
    strategy_id: str
    variant: str


class PRBundleGenerationError(RuntimeError):
    """Typed error for unsupported or non-runnable PR bundle requests."""

    def __init__(self, payload: PRBundleErrorPayload) -> None:
        super().__init__(payload["detail"])
        self.payload = payload

    def as_dict(self) -> PRBundleErrorPayload:
        return PRBundleErrorPayload(**self.payload)


def _create_bucket_if_missing_enabled(strategy_inputs: Mapping[str, Any] | None) -> bool:
    return _coerce_bool((strategy_inputs or {}).get("create_bucket_if_missing"), default=False)


def _terraform_minimal_private_bucket_blocks(
    *,
    resource_suffix: str,
    bucket_name_ref: str,
    count_expr: str,
    include_public_access_block: bool = True,
    include_encryption: bool = True,
) -> str:
    """Return Terraform blocks that create a minimal private bucket baseline."""
    public_access_block = ""
    public_access_dep = f"aws_s3_bucket_ownership_controls.{resource_suffix}"
    if include_public_access_block:
        public_access_block = f"""
resource "aws_s3_bucket_public_access_block" "{resource_suffix}" {{
  count  = {count_expr}
  bucket = aws_s3_bucket.{resource_suffix}[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  depends_on = [aws_s3_bucket_ownership_controls.{resource_suffix}]
}}
"""
        public_access_dep = f"aws_s3_bucket_public_access_block.{resource_suffix}"
    encryption_block = ""
    if include_encryption:
        encryption_block = f"""
resource "aws_s3_bucket_server_side_encryption_configuration" "{resource_suffix}" {{
  count  = {count_expr}
  bucket = aws_s3_bucket.{resource_suffix}[0].id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "alias/aws/s3"
    }}
    bucket_key_enabled = true
  }}

  depends_on = [{public_access_dep}]
}}
"""
    return f"""
resource "aws_s3_bucket" "{resource_suffix}" {{
  count  = {count_expr}
  bucket = {bucket_name_ref}
}}

resource "aws_s3_bucket_ownership_controls" "{resource_suffix}" {{
  count  = {count_expr}
  bucket = aws_s3_bucket.{resource_suffix}[0].id

  rule {{
    object_ownership = "BucketOwnerEnforced"
  }}
}}
{public_access_block}{encryption_block}"""


def _terraform_minimal_private_bucket_dependency(resource_suffix: str) -> str:
    """Return an always-declared helper resource reference for create-if-missing ordering."""
    return f"aws_s3_bucket_ownership_controls.{resource_suffix}"


def _merge_bundle_metadata(*parts: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    helper_bucket_inventory: list[dict[str, Any]] = []
    for part in parts:
        if not isinstance(part, Mapping):
            continue
        helper_items = part.get("helper_bucket_inventory")
        if isinstance(helper_items, list):
            for item in helper_items:
                if isinstance(item, Mapping):
                    helper_bucket_inventory.append(copy.deepcopy(dict(item)))
        for key, value in part.items():
            if key == "helper_bucket_inventory":
                continue
            merged[key] = copy.deepcopy(value)
    if helper_bucket_inventory:
        merged["helper_bucket_inventory"] = helper_bucket_inventory
    return merged


def _helper_bucket_inventory_entry(
    *,
    bucket_name: str,
    helper_bucket_role: str,
    created: bool,
) -> dict[str, Any]:
    return {
        "bucket_name": str(bucket_name or "").strip(),
        "helper_bucket_role": str(helper_bucket_role or "").strip(),
        "created": bool(created),
        "reused": not bool(created),
    }

class ActionLike(Protocol):
    """
    Minimal action interface required by generate_pr_bundle.

    Satisfied by backend.models.action.Action; allows testing without ORM.
    """

    id: uuid.UUID
    action_type: str
    account_id: str
    region: str | None
    target_id: str
    title: str
    control_id: str | None
    resource_id: str | None


# ---------------------------------------------------------------------------
# Action type constants and dispatch registry (all 7 types; subsection refs 9.2–9.5, 9.9–9.12)
# ---------------------------------------------------------------------------

ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS = "s3_block_public_access"       # 9.2, 9.5
ACTION_TYPE_ENABLE_SECURITY_HUB = "enable_security_hub"             # 9.3, 9.5
ACTION_TYPE_ENABLE_GUARDDUTY = "enable_guardduty"                  # 9.4, 9.5
ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS = "s3_bucket_block_public_access"  # 9.9
ACTION_TYPE_S3_BUCKET_ENCRYPTION = "s3_bucket_encryption"          # 9.10
ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING = "s3_bucket_access_logging"
ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION = "s3_bucket_lifecycle_configuration"
ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS = "s3_bucket_encryption_kms"
ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS = "sg_restrict_public_ports" # 9.11
ACTION_TYPE_CLOUDTRAIL_ENABLED = "cloudtrail_enabled"             # 9.12
ACTION_TYPE_AWS_CONFIG_ENABLED = "aws_config_enabled"
ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING = "ssm_block_public_sharing"
ACTION_TYPE_EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS = "ebs_snapshot_block_public_access"
ACTION_TYPE_EBS_DEFAULT_ENCRYPTION = "ebs_default_encryption"
ACTION_TYPE_S3_BUCKET_REQUIRE_SSL = "s3_bucket_require_ssl"
ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT = "iam_root_access_key_absent"
ACTION_TYPE_PR_ONLY = "pr_only"

# Optional PR-only bundle variants (selected at remediation run creation time).
# Used for real, runnable alternatives without changing action_type mapping.
PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3 = "cloudfront_oac_private_s3"

SUPPORTED_ACTION_TYPES = frozenset({
    ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_ENABLE_SECURITY_HUB,
    ACTION_TYPE_ENABLE_GUARDDUTY,
    ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_S3_BUCKET_ENCRYPTION,
    ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
    ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
    ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
    ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
    ACTION_TYPE_CLOUDTRAIL_ENABLED,
    ACTION_TYPE_AWS_CONFIG_ENABLED,
    ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING,
    ACTION_TYPE_EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_EBS_DEFAULT_ENCRYPTION,
    ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
    ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT,
})

_BLOCKED_PLACEHOLDER_TOKENS = frozenset(
    {
        "REPLACE_BUCKET_NAME",
        "REPLACE_LOG_BUCKET_NAME",
        "REPLACE_SECURITY_GROUP_ID",
    }
)
_PLACEHOLDER_TOKEN_PATTERN = re.compile(r"\b(REPLACE_[A-Z0-9_]+)\b")
_S3_BUCKET_NAME_PATTERN = re.compile(
    r"^(?!\d{1,3}(?:\.\d{1,3}){3}$)(?!xn--)(?!sthree-)(?!amzn-s3-demo-)[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
)
_S3_MIGRATE_POLICY_JSON_KEY = "existing_bucket_policy_json"
_S3_MIGRATE_POLICY_STATEMENT_COUNT_KEY = "existing_bucket_policy_statement_count"
_S3_WEBSITE_CONFIGURATION_JSON_KEY = "existing_bucket_website_configuration_json"
_S3_CLOUDFRONT_READONLY_POLICY_SID = "AllowCloudFrontReadOnly"


def _normalize_policy_json_document(policy_json: object) -> str | None:
    """Normalize policy JSON into a canonical string."""
    if not isinstance(policy_json, str):
        return None
    raw = policy_json.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None

    statements = parsed.get("Statement")
    if statements is None:
        parsed["Statement"] = []
    elif isinstance(statements, dict):
        parsed["Statement"] = [statements]
    elif not isinstance(statements, list):
        return None

    return json.dumps(parsed, separators=(",", ":"), sort_keys=True)


def _policy_statement_count(policy_json: str | None) -> int:
    """Return number of statements in a policy document."""
    normalized = _normalize_policy_json_document(policy_json)
    if not normalized:
        return 0
    parsed = json.loads(normalized)
    statements = parsed.get("Statement")
    if isinstance(statements, list):
        return len(statements)
    if isinstance(statements, dict):
        return 1
    return 0


def _policy_json_without_sid(policy_json: str | None, sid: str) -> str | None:
    normalized = _normalize_policy_json_document(policy_json)
    if normalized is None:
        return None
    parsed = json.loads(normalized)
    statements = parsed.get("Statement") or []
    parsed["Statement"] = [
        statement
        for statement in statements
        if str((statement or {}).get("Sid") or "").strip().lower() != sid.strip().lower()
    ]
    return json.dumps(parsed, separators=(",", ":"), sort_keys=True)


def _strip_s3_2_managed_policy_statement(policy_json: str | None) -> str | None:
    return _policy_json_without_sid(policy_json, _S3_CLOUDFRONT_READONLY_POLICY_SID)


def _coerce_non_negative_int(value: object) -> int | None:
    """Parse non-negative integer values from risk evidence."""
    try:
        candidate = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if candidate < 0:
        return None
    return candidate


def _coerce_bool(value: object, *, default: bool) -> bool:
    """Parse loose boolean values from strategy inputs."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    return default


def _coerce_cidr(value: object, *, default: str, version: int | None) -> str:
    """Normalize CIDR input or fall back to a safe default."""
    if not isinstance(value, str):
        return default
    cleaned = value.strip()
    if not cleaned:
        return default
    try:
        network = ip_network(cleaned, strict=False)
    except ValueError:
        return default
    if version is not None and network.version != version:
        return default
    return str(network)


def _resolve_sg_access_mode(strategy_inputs: dict[str, Any] | None) -> str:
    """Resolve the canonical EC2.53 access mode from guided strategy inputs."""
    inputs = strategy_inputs or {}
    access_mode = str(inputs.get("access_mode", "")).strip().lower()
    if not access_mode and _coerce_bool(inputs.get("remove_existing_public_rules"), default=False):
        access_mode = "close_and_revoke"
    return access_mode


def _resolve_bastion_security_group_ids(strategy_inputs: dict[str, Any] | None) -> list[str]:
    """Normalize configured bastion SG IDs from strategy inputs."""
    inputs = strategy_inputs or {}
    values = inputs.get("approved_bastion_security_group_ids")
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _resolve_sg_restrict_defaults(strategy_inputs: dict[str, Any] | None) -> tuple[str, str, bool]:
    """Resolve SG restrict defaults from guided strategy inputs."""
    inputs = strategy_inputs or {}
    access_mode = _resolve_sg_access_mode(strategy_inputs)
    allowed_cidr = _coerce_cidr(inputs.get("allowed_cidr"), default="10.0.0.0/8", version=4)
    allowed_cidr_ipv6 = _coerce_cidr(inputs.get("allowed_cidr_ipv6"), default="", version=6)
    remove_existing_public_rules = access_mode == "close_and_revoke"
    return allowed_cidr, allowed_cidr_ipv6, remove_existing_public_rules


def _resolve_aws_config_defaults(
    *,
    account_id: str,
    region: str,
    strategy: str,
    strategy_inputs: dict[str, Any],
) -> tuple[str, str, bool, bool]:
    """Resolve AWS Config guided inputs with legacy fallback behavior."""
    normalized_region = region.strip() or "us-east-1"
    default_bucket = f"security-autopilot-config-{account_id}-{normalized_region}"
    delivery_bucket_mode = str(strategy_inputs.get("delivery_bucket_mode", "")).strip().lower()
    if delivery_bucket_mode == "create_new":
        create_local_bucket = True
    elif delivery_bucket_mode == "use_existing":
        create_local_bucket = False
    else:
        create_local_bucket = strategy != "config_enable_centralized_delivery"

    existing_bucket_name = str(strategy_inputs.get("existing_bucket_name", "")).strip()
    legacy_delivery_bucket = str(strategy_inputs.get("delivery_bucket", "")).strip()
    bucket = existing_bucket_name or legacy_delivery_bucket or default_bucket

    recording_scope = str(strategy_inputs.get("recording_scope", "")).strip().lower()
    overwrite_recording_group = recording_scope == "all_resources"

    legacy_kms_key_arn = str(strategy_inputs.get("kms_key_arn", "")).strip()
    encrypt_with_kms = _coerce_bool(
        strategy_inputs.get("encrypt_with_kms"),
        default=bool(legacy_kms_key_arn),
    )
    kms_key_arn = legacy_kms_key_arn if encrypt_with_kms else ""

    return bucket, kms_key_arn, create_local_bucket, overwrite_recording_group


def _resolve_cloudtrail_defaults(
    strategy_inputs: dict[str, Any] | None,
) -> tuple[str, str, str, bool, bool, bool]:
    """Resolve CloudTrail guided-input defaults with legacy-safe fallbacks."""
    inputs = strategy_inputs or {}
    trail_name = str(inputs.get("trail_name", "")).strip() or "security-autopilot-trail"
    trail_bucket_name = str(inputs.get("trail_bucket_name", "")).strip()
    kms_key_arn = str(inputs.get("kms_key_arn", "")).strip()
    create_bucket_if_missing = _coerce_bool(inputs.get("create_bucket_if_missing"), default=False)
    create_bucket_policy = _coerce_bool(inputs.get("create_bucket_policy"), default=True)
    multi_region = _coerce_bool(inputs.get("multi_region"), default=True)
    return trail_name, trail_bucket_name, kms_key_arn, create_bucket_if_missing, create_bucket_policy, multi_region


def _resolve_s3_lifecycle_abort_days(strategy_inputs: dict[str, Any] | None) -> int:
    """Resolve S3.11 abort-days input with bounded defaults."""
    default_days = 7
    raw = (strategy_inputs or {}).get("abort_days")
    try:
        candidate = int(raw) if raw is not None else default_days
    except (TypeError, ValueError):
        return default_days
    if candidate < 1:
        return 1
    if candidate > 365:
        return 365
    return candidate


def _resolve_s3_kms_defaults(
    *,
    meta: dict[str, str],
    strategy_inputs: dict[str, Any] | None,
    format: PRBundleFormat,
) -> tuple[str, str]:
    """Resolve S3.15 key mode and effective key ARN."""
    default_kms_arn = f"arn:aws:kms:{meta['region']}:{meta['account_id']}:alias/aws/s3"
    inputs = strategy_inputs or {}
    raw_mode = str(inputs.get("kms_key_mode", "")).strip().lower()
    custom_kms_key_arn = str(inputs.get("kms_key_arn", "")).strip()

    if raw_mode in {"aws_managed", "custom"}:
        key_mode = raw_mode
    elif custom_kms_key_arn:
        key_mode = "custom"
    else:
        key_mode = "aws_managed"

    if key_mode == "custom":
        if not custom_kms_key_arn:
            _raise_pr_bundle_error(
                code="missing_kms_key_arn",
                detail=(
                    "kms_key_mode is set to custom, but no kms_key_arn was provided. "
                    "Set strategy_inputs.kms_key_arn to an approved customer-managed KMS key ARN."
                ),
                action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
                format=format,
            )
        return custom_kms_key_arn, key_mode

    return default_kms_arn, key_mode


def _strategy_risk_evidence(risk_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Extract evidence object from risk snapshot."""
    if not isinstance(risk_snapshot, dict):
        return {}
    evidence = risk_snapshot.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    return evidence


def _resolve_s3_migrate_policy_preservation(
    *,
    strategy_inputs: dict[str, Any] | None,
    risk_snapshot: dict[str, Any] | None,
    action_type: str,
    format: str,
    strategy_id: str | None,
    variant: str | None,
    missing_policy_error_code: str = "existing_bucket_policy_preservation_required",
    missing_policy_error_detail: str | None = None,
    fail_when_evidence_missing: bool = True,
) -> str | None:
    """
    Resolve policy-preservation input for CloudFront+OAC migration bundles.

    Priority:
      1) explicit strategy preservation inputs
      2) runtime risk evidence capture
      3) fail closed when policy statements exist or evidence is missing
    """
    inputs = strategy_inputs or {}
    explicit_policy = _normalize_policy_json_document(inputs.get(_S3_MIGRATE_POLICY_JSON_KEY))
    if explicit_policy is not None:
        return explicit_policy
    explicit_statement_count = _coerce_non_negative_int(inputs.get(_S3_MIGRATE_POLICY_STATEMENT_COUNT_KEY))
    if isinstance(explicit_statement_count, int):
        if explicit_statement_count == 0:
            return None
        _raise_pr_bundle_error(
            code=missing_policy_error_code,
            detail=missing_policy_error_detail
            or (
                "Existing bucket policy contains non-empty statements, but no preservation input "
                "was provided. Provide strategy_inputs.existing_bucket_policy_json or recreate the "
                "run after refreshing remediation options so policy preservation evidence is captured."
            ),
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
            variant=variant,
        )

    evidence = _strategy_risk_evidence(risk_snapshot)
    evidence_policy = _normalize_policy_json_document(evidence.get(_S3_MIGRATE_POLICY_JSON_KEY))
    if evidence_policy is not None:
        return evidence_policy

    evidence_statement_count = _coerce_non_negative_int(evidence.get(_S3_MIGRATE_POLICY_STATEMENT_COUNT_KEY))
    if isinstance(evidence_statement_count, int):
        if evidence_statement_count == 0:
            return None
        _raise_pr_bundle_error(
            code=missing_policy_error_code,
            detail=missing_policy_error_detail
            or (
                "Existing bucket policy contains non-empty statements, but no preservation input "
                "was provided. Provide strategy_inputs.existing_bucket_policy_json or recreate the "
                "run after refreshing remediation options so policy preservation evidence is captured."
            ),
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
            variant=variant,
        )

    if fail_when_evidence_missing:
        _raise_pr_bundle_error(
            code="bucket_policy_preservation_evidence_missing",
            detail=(
                "Unable to guarantee existing bucket policy preservation for CloudFront+OAC migration "
                "because policy evidence is missing. Recreate the run after refreshing remediation options "
                "or provide strategy_inputs.existing_bucket_policy_json explicitly."
            ),
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
            variant=variant,
        )

    return None


def _normalize_website_configuration_json_document(website_json: object) -> str | None:
    """Normalize S3 website-configuration JSON into a canonical string."""
    if not isinstance(website_json, str):
        return None
    raw = website_json.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    normalized: dict[str, Any] = {}
    for key in ("IndexDocument", "ErrorDocument", "RedirectAllRequestsTo", "RoutingRules"):
        value = parsed.get(key)
        if value in (None, "", [], {}):
            continue
        normalized[key] = value
    if not normalized:
        return None
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True)


def _resolve_s3_website_configuration(
    *,
    strategy_inputs: dict[str, Any] | None,
    risk_snapshot: dict[str, Any] | None,
    action_type: str,
    format: str,
    strategy_id: str | None,
) -> dict[str, Any]:
    """Resolve captured S3 website configuration for website-to-CloudFront migration."""
    inputs = strategy_inputs or {}
    website_json = _normalize_website_configuration_json_document(inputs.get(_S3_WEBSITE_CONFIGURATION_JSON_KEY))
    evidence = _strategy_risk_evidence(risk_snapshot)
    if website_json is None:
        website_json = _normalize_website_configuration_json_document(
            evidence.get(_S3_WEBSITE_CONFIGURATION_JSON_KEY)
        )
    if website_json is None:
        _raise_pr_bundle_error(
            code="s3_website_configuration_required",
            detail=(
                "Website migration requires captured existing_bucket_website_configuration_json so the "
                "bundle can translate the current website behavior and document rollback."
            ),
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
        )
    parsed = json.loads(website_json)
    redirect_all = parsed.get("RedirectAllRequestsTo")
    routing_rules = parsed.get("RoutingRules")
    if isinstance(redirect_all, dict) and redirect_all:
        _raise_pr_bundle_error(
            code="unsupported_website_configuration",
            detail="S3 website RedirectAllRequestsTo behavior requires manual review and is not executable in WI-5.",
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
        )
    if isinstance(routing_rules, list) and routing_rules:
        _raise_pr_bundle_error(
            code="unsupported_website_configuration",
            detail="S3 website RoutingRules require manual review and are not executable in WI-5.",
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
        )
    index_document = parsed.get("IndexDocument")
    if not isinstance(index_document, dict) or not str(index_document.get("Suffix", "")).strip():
        _raise_pr_bundle_error(
            code="unsupported_website_configuration",
            detail="Executable website migration requires an S3 website IndexDocument suffix.",
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
        )
    error_document = parsed.get("ErrorDocument")
    error_document_key = ""
    if error_document is not None:
        if not isinstance(error_document, dict) or not str(error_document.get("Key", "")).strip():
            _raise_pr_bundle_error(
                code="unsupported_website_configuration",
                detail="Executable website migration requires ErrorDocument to use a concrete object key.",
                action_type=action_type,
                format=format,
                strategy_id=strategy_id,
            )
        error_document_key = str(error_document.get("Key", "")).strip().lstrip("/")
    return {
        "json": website_json,
        "default_root_object": str(index_document.get("Suffix", "")).strip(),
        "error_document_key": error_document_key,
    }


def _raise_pr_bundle_error(
    *,
    code: str,
    detail: str,
    action_type: str | None = None,
    format: str | None = None,
    strategy_id: str | None = None,
    variant: str | None = None,
) -> NoReturn:
    """Raise a structured PR-bundle generation error."""
    payload: PRBundleErrorPayload = {
        "code": code,
        "detail": detail,
        "action_type": action_type or "",
        "format": format or "",
        "strategy_id": strategy_id or "",
        "variant": variant or "",
    }
    raise PRBundleGenerationError(payload)


def _is_non_executable_resolution(
    action_type: str,
    resolution: Mapping[str, Any] | None,
) -> bool:
    if action_type not in {
        ACTION_TYPE_CLOUDTRAIL_ENABLED,
        ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
    }:
        return False
    if not isinstance(resolution, Mapping):
        return False
    if (
        action_type == ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS
        and str(resolution.get("profile_id") or "").strip()
        == "s3_bucket_block_public_access_review_public_policy_scrub"
    ):
        return False
    try:
        return normalize_support_tier(resolution.get("support_tier")) != "deterministic_bundle"
    except ValueError:
        return False


def _generate_non_executable_resolution_bundle(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    strategy_id: str | None,
    resolution: Mapping[str, Any] | None,
) -> PRBundleResult:
    return {
        "format": format,
        "files": [
            PRBundleFile(
                path="decision.json",
                content=json.dumps(dict(resolution or {}), indent=2, sort_keys=True) + "\n",
            ),
            PRBundleFile(
                path="README.txt",
                content=_non_executable_bundle_readme(
                    action=action,
                    strategy_id=strategy_id,
                    resolution=resolution,
                ),
            ),
        ],
        "steps": _non_executable_bundle_steps(action=action, resolution=resolution),
        "metadata": {"non_executable_bundle": True},
    }


def _non_executable_bundle_readme(
    *,
    action: ActionLike,
    strategy_id: str | None,
    resolution: Mapping[str, Any] | None,
) -> str:
    support_tier = str((resolution or {}).get("support_tier") or "manual_guidance_only")
    blocked_reasons = list((resolution or {}).get("blocked_reasons") or [])
    reason_lines = "\n".join(f"- {reason}" for reason in blocked_reasons) or "- No explicit blocked reasons recorded."
    rationale = str((resolution or {}).get("decision_rationale") or "").strip() or "No rationale recorded."
    return f"""AWS Security Autopilot — Non-executable remediation guidance

Action
------
- action_type: {action.action_type}
- strategy_id: {strategy_id or ""}
- support_tier: {support_tier}

Why this bundle is non-executable
---------------------------------
{reason_lines}

Decision rationale
------------------
{rationale}

Contents
--------
- decision.json contains the canonical resolver decision, blocked reasons, and preservation summary.
- No Terraform or CloudFormation files were emitted because this branch is downgrade-only in Wave 6.
"""


def _non_executable_bundle_steps(
    *,
    action: ActionLike,
    resolution: Mapping[str, Any] | None,
) -> list[str]:
    support_tier = str((resolution or {}).get("support_tier") or "manual_guidance_only")
    return [
        f"Review decision.json for the canonical {support_tier} resolver decision for {action.action_type}.",
        "Preserve the existing configuration manually or update the target bucket configuration until an executable branch becomes safe.",
        "Recompute actions after the reviewed change is applied.",
    ]


def generate_pr_bundle(
    action: ActionLike | None,
    format: str = "terraform",
    strategy_id: str | None = None,
    strategy_inputs: dict[str, Any] | None = None,
    risk_snapshot: dict[str, Any] | None = None,
    variant: str | None = None,
    resolution: Mapping[str, Any] | None = None,
) -> PRBundleResult:
    """
    Generate a PR bundle for the given action by dispatching on action_type.

    Loads action context (action_type, account_id, region, target_id, title,
    control_id) from the provided action object and delegates to the
    appropriate generator. Unsupported or missing action raises a structured
    error.

    Args:
        action: Action instance (e.g. run.action from worker). Must have
            action_type, account_id, region, target_id, title, control_id.
            If None, raises PRBundleGenerationError.
        format: "terraform" or "cloudformation". Default terraform.
        strategy_id: Optional strategy identifier selected in remediation flow.
        strategy_inputs: Optional strategy input values.
        risk_snapshot: Optional evaluated risk snapshot to append in README.
        variant: Legacy variant string. When provided, mapped to strategy behavior.
        resolution: Optional canonical resolver decision for non-executable gating.

    Returns:
        Dict with keys: format, files (list of { path, content }), steps (list of strings).
    """
    normalized_format = _normalize_format(format)

    if action is None:
        _raise_pr_bundle_error(
            code="missing_action_context",
            detail="Action context is required for PR bundle generation.",
            format=normalized_format,
        )

    action_type = (action.action_type or "").strip().lower()
    if not action_type:
        _raise_pr_bundle_error(
            code="missing_action_type",
            detail="Action type is required for PR bundle generation.",
            format=normalized_format,
        )
    if action_type == ACTION_TYPE_PR_ONLY:
        _raise_pr_bundle_error(
            code="pr_only_action_type_unsupported",
            detail=(
                "Action type 'pr_only' does not map to executable IaC generation. "
                "Use a mapped remediation action type."
            ),
            action_type=action_type,
            format=normalized_format,
        )
    if action_type not in SUPPORTED_ACTION_TYPES:
        _raise_pr_bundle_error(
            code="unsupported_action_type",
            detail=f"Action type '{action_type}' is not supported for PR bundle generation.",
            action_type=action_type,
            format=normalized_format,
        )

    # Dispatch: all 7 generators (9.2–9.5, 9.9–9.12)
    result: PRBundleResult
    effective_strategy_id = (strategy_id or "").strip().lower() or None
    normalized_variant = (variant or "").strip().lower()
    if normalized_variant == PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3 and not effective_strategy_id:
        effective_strategy_id = "s3_migrate_cloudfront_oac_private"
    if _is_non_executable_resolution(action_type, resolution):
        return _generate_non_executable_resolution_bundle(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
            resolution=resolution,
        )

    if action_type == ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS:
        result = _generate_for_s3(action, normalized_format)
    elif action_type == ACTION_TYPE_ENABLE_SECURITY_HUB:
        result = _generate_for_security_hub(action, normalized_format)
    elif action_type == ACTION_TYPE_ENABLE_GUARDDUTY:
        result = _generate_for_guardduty(action, normalized_format)
    elif action_type == ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS:
        result = _generate_for_s3_bucket_strategy(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            variant=normalized_variant or None,
            resolution=resolution,
        )
    elif action_type == ACTION_TYPE_S3_BUCKET_ENCRYPTION:
        result = _generate_for_s3_bucket_encryption(action, normalized_format)
    elif action_type == ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING:
        result = _generate_for_s3_bucket_access_logging(
            action,
            normalized_format,
            strategy_inputs=strategy_inputs,
            strategy_id=effective_strategy_id,
            variant=normalized_variant or None,
        )
    elif action_type == ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION:
        result = _generate_for_s3_bucket_lifecycle_configuration(
            action,
            normalized_format,
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            resolution=resolution,
        )
    elif action_type == ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS:
        result = _generate_for_s3_bucket_encryption_kms(
            action,
            normalized_format,
            strategy_inputs=strategy_inputs,
        )
    elif action_type == ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS:
        result = _generate_for_sg_restrict_public_ports(
            action,
            normalized_format,
            strategy_inputs=strategy_inputs,
        )
    elif action_type == ACTION_TYPE_CLOUDTRAIL_ENABLED:
        result = _generate_for_cloudtrail_enabled(
            action,
            normalized_format,
            strategy_inputs=strategy_inputs,
        )
    elif action_type == ACTION_TYPE_AWS_CONFIG_ENABLED:
        result = _generate_for_aws_config_enabled(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
            strategy_inputs=strategy_inputs,
        )
    elif action_type == ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING:
        result = _generate_for_ssm_block_public_sharing(action, normalized_format)
    elif action_type == ACTION_TYPE_EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS:
        result = _generate_for_ebs_snapshot_block_public_access(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
        )
    elif action_type == ACTION_TYPE_EBS_DEFAULT_ENCRYPTION:
        result = _generate_for_ebs_default_encryption(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
            strategy_inputs=strategy_inputs,
        )
    elif action_type == ACTION_TYPE_S3_BUCKET_REQUIRE_SSL:
        result = _generate_for_s3_bucket_require_ssl(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            resolution=resolution,
        )
    elif action_type == ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT:
        result = _generate_for_iam_root_access_key_absent(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
        )
    else:
        result = _generate_unsupported(action, normalized_format)

    result = _maybe_append_terraform_readme(
        result,
        risk_snapshot=risk_snapshot,
        strategy_id=effective_strategy_id,
    )
    _ensure_no_blocked_placeholders(
        result,
        action_type=action_type,
        format=normalized_format,
        strategy_id=effective_strategy_id,
        variant=normalized_variant or None,
    )
    return result


def _blocked_placeholder_hits(result: PRBundleResult) -> list[tuple[str, str]]:
    """Return file/token hits for blocked unresolved placeholders."""
    hits: list[tuple[str, str]] = []
    for item in result.get("files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "file")
        content = item.get("content")
        if content is None:
            continue
        text = content if isinstance(content, str) else str(content)
        for token in set(_PLACEHOLDER_TOKEN_PATTERN.findall(text)):
            if token in _BLOCKED_PLACEHOLDER_TOKENS:
                hits.append((path, token))
    return hits


def _ensure_no_blocked_placeholders(
    result: PRBundleResult,
    *,
    action_type: str,
    format: str,
    strategy_id: str | None,
    variant: str | None,
) -> None:
    """
    Fail PR bundle generation when blocked unresolved placeholders remain.

    This prevents account-/resource-scoped parsing gaps from leaking invalid IaC
    into downloadable artifacts.
    """
    hits = _blocked_placeholder_hits(result)
    if not hits:
        return
    path, token = hits[0]
    _raise_pr_bundle_error(
        code="unresolved_placeholder_token",
        detail=(
            f"Generated bundle contains unresolved placeholder token '{token}' in file '{path}'. "
            "Refresh findings/action targets and retry remediation bundle generation."
        ),
        action_type=action_type,
        format=format,
        strategy_id=strategy_id,
        variant=variant,
    )


def _normalize_format(format: str) -> PRBundleFormat:
    """Return format as terraform or cloudformation; default terraform."""
    f = (format or "").strip().lower()
    if f == CLOUDFORMATION_FORMAT:
        return CLOUDFORMATION_FORMAT
    return TERRAFORM_FORMAT


def _terraform_readme_content() -> str:
    """README.txt content for Terraform bundles: credentials and region, no account ID as profile."""
    return """AWS Security Autopilot — Terraform bundle

Credentials and region
--------------------
- Use your normal AWS credentials: a named profile from ~/.aws/config (e.g. default) or environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).
- Do NOT set AWS_PROFILE to your account ID. Use a profile name (e.g. default) or leave unset to use the default profile.
- Set the region: export AWS_REGION=eu-north-1 (or your action's region).

Commands
--------
terraform init
terraform plan
terraform apply
"""


def _terraform_s3_bucket_block_guardrails_content() -> str:
    """
    README guardrails for S3.2 bucket-level block public access bundles.

    Clarifies this bundle is control-level hardening, not a full migration to
    CloudFront + OAC + private S3, and adds practical pre/apply/rollback checks.
    """
    return """

S3.2 post-fix access guidance
-----------------------------
What changes
- This bundle enforces S3 Block Public Access on the target bucket.
- It is NOT a full CloudFront + OAC + private S3 migration.
- Review-tier public-policy scrub branches remove unconditional public Allow statements before enabling Block Public Access.

How to access now
- CloudFront usage note: serve user traffic through a CloudFront HTTPS endpoint, not direct public S3 website/object URLs.
- Example HTTPS check:
  curl -I https://<cloudfront-domain>/<object-key>

Verify
- Confirm all four block-public-access flags are true:
  aws s3api get-public-access-block --bucket <bucket-name> --query 'PublicAccessBlockConfiguration' --output json
- Validate clients are using CloudFront (or another approved private path) and monitor for 4xx/AccessDenied spikes.

Rollback
- Restore the prior bucket policy/ACL backup if application access breaks.
- Emergency-only unblock command:
  aws s3api put-public-access-block --bucket <bucket-name> --public-access-block-configuration BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false
"""


def _terraform_s3_cloudfront_oac_private_guardrails_content() -> str:
    """
    README notes for CloudFront + OAC + private S3 migration variant.

    This bundle is runnable IaC for a safer S3 delivery pattern, but callers
    may still need project-specific policy/KMS updates.
    """
    return """

S3.2 migration variant (CloudFront + OAC + private S3)
-------------------------------------------------------
What changes
- Creates CloudFront + OAC, enforces S3 Block Public Access, and updates bucket policy for CloudFront-origin read access.
- Intended to replace direct public S3 access.

How to access now
- Use the CloudFront HTTPS domain output for clients/apps.
- Example HTTPS check:
  curl -I https://<cloudfront-domain>/<object-key>

Verify
- Existing bucket policy statements are preloaded into `terraform.auto.tfvars.json` when evidence is available.
- If additional internal/cross-account roles still need direct S3 reads, set `additional_read_principal_arns`.
- Validate key object paths and monitor CloudFront 4xx plus S3/KMS AccessDenied signals.

Rollback
- Restore previous bucket policy JSON if needed, then roll back CloudFront origin-routing changes.
- Keep rollback scoped and temporary; re-apply least-privilege policy once access is restored.
"""


def _terraform_s3_website_cloudfront_private_guardrails_content() -> str:
    """README notes for website-to-CloudFront migration variant."""
    return """

S3 website migration variant (CloudFront + private S3 + Route53)
---------------------------------------------------------------
What changes
- Creates CloudFront + OAC for the private S3 REST origin, updates Route53 aliases, removes S3 website hosting, and then enables S3 Block Public Access.
- Intended only for buckets currently using simple S3 website hosting (`IndexDocument` plus optional `ErrorDocument`).

How to access now
- Validate each hostname in `aliases` resolves to the new CloudFront distribution after apply.
- Example HTTPS check:
  curl -I https://<alias-hostname>/

Verify
- `terraform.auto.tfvars.json` includes the captured S3 website configuration for rollback documentation.
- Confirm Route53 aliases point to CloudFront and website hosting is removed:
  aws s3api get-bucket-website --bucket <bucket-name>
- Confirm all four block-public-access flags are true:
  aws s3api get-public-access-block --bucket <bucket-name> --query 'PublicAccessBlockConfiguration' --output json

Rollback
- Restore Route53 aliases and S3 website hosting before reopening direct public access.
- Use the captured `existing_bucket_website_configuration_json` value in `terraform.auto.tfvars.json` with `aws s3api put-bucket-website` if emergency rollback is required.
- Keep rollback temporary and re-apply private-origin controls after traffic is restored.
"""


def _terraform_ec2_53_access_guidance_content() -> str:
    """README guidance for EC2.53 post-fix operator access workflow."""
    return """

EC2.53 post-fix access guidance
-------------------------------
What changes
- Public SSH/RDP ingress on 22/3389 is restricted.
- For `close_and_revoke`, `ssm_only`, and `bastion_sg_reference`, run `scripts/sg_capture_state.py` before apply to snapshot exact public ingress pre-state under `.sg-rollback/sg_ingress_snapshot.json`.
- For `close_and_revoke`, `ssm_only`, and `bastion_sg_reference`, `rollback/sg_restore.py` restores the captured ingress rules, including rule descriptions, after `terraform destroy`.
- `ssm_only` removes public SSH/RDP ingress and does not add replacement SSH/RDP allowlists.
- `bastion_sg_reference` removes public SSH/RDP ingress and replaces it with source-security-group access from the approved bastion SG list.

How to access now
- Use SSM Session Manager for operator access instead of public SSH/RDP:
  aws ssm start-session --target <instance-id> --region <region>
- Keep bastion/VPN as fallback for non-SSM-managed workloads.
- When using `bastion_sg_reference`, connect through instances or services attached to the approved bastion security groups instead of direct public admin ingress.

Verify
- Confirm no 0.0.0.0/0 or ::/0 remains for 22/3389:
  aws ec2 describe-security-group-rules --region <region> --filters Name=group-id,Values=<security-group-id> --query "SecurityGroupRules[?(IsEgress==`false`) && ((FromPort==`22` || FromPort==`3389`) && (CidrIpv4=='0.0.0.0/0' || CidrIpv6=='::/0'))]" --output json

Rollback
- Standard rollback for `close_and_revoke`, `ssm_only`, and `bastion_sg_reference`: run `terraform destroy`, then `python3 rollback/sg_restore.py`.
- Emergency-only fallback if no snapshot exists:
  aws ec2 authorize-security-group-ingress --region <region> --group-id <security-group-id> --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=<admin-cidr>}]'
"""


def _terraform_s3_5_access_guidance_content() -> str:
    """README guidance for S3.5 TLS-only bucket access behavior."""
    return """

S3.5 post-fix access guidance
-----------------------------
What changes
- Adds `DenyInsecureTransport` to the bucket policy and preserves unrelated existing policy statements.

How to access now
- HTTPS requirement: all clients must use `https://` for S3 requests; `http://` requests are denied.

Verify
- Confirm bucket policy contains `DenyInsecureTransport`:
  aws s3api get-bucket-policy --bucket <bucket-name> --query Policy --output text
- Confirm HTTPS succeeds and HTTP is denied:
  curl -I https://<bucket-name>.s3.<region>.amazonaws.com/<object-key>
  curl -I http://<bucket-name>.s3.<region>.amazonaws.com/<object-key>

Rollback
- Before apply, if the bucket already has a policy, capture it:
  aws s3api get-bucket-policy --bucket <bucket-name> --query Policy --output text > pre-remediation-policy.json
- Restore prior bucket policy JSON backup if needed:
  aws s3api put-bucket-policy --bucket <bucket-name> --policy file://pre-remediation-policy.json
"""


def _terraform_ssm_7_access_guidance_content() -> str:
    """README guidance for SSM.7 document-sharing posture after remediation."""
    return """

SSM.7 post-fix access guidance
------------------------------
What changes
- Sets SSM service setting to block public document sharing.

How to access now
- SSM sharing guidance: share documents to specific AWS accounts (private share), not publicly:
  aws ssm modify-document-permission --name <document-name> --permission-type Share --account-ids-to-add <account-id>

Verify
- Confirm service setting remains `Disable`:
  aws ssm get-service-setting --setting-id arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/documents/console/public-sharing-permission --query 'ServiceSetting.SettingValue' --output text
- Confirm per-document share targets:
  aws ssm describe-document-permission --name <document-name> --permission-type Share

Rollback
- Emergency-only rollback to re-enable public sharing:
  aws ssm update-service-setting --setting-id arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/documents/console/public-sharing-permission --setting-value Enable
"""


def _terraform_aws_config_guardrails_content() -> str:
    """README guidance for Config.1 recorder/delivery preflight behavior."""
    return """

Config.1 preflight safeguards
-----------------------------
- This bundle inspects existing AWS Config recorder and delivery-channel state before mutating settings.
- The executable Terraform path snapshots exact pre-state under `.aws-config-rollback/` before mutation and ships a bundle-local restore command at `rollback/aws_config_restore.py`.
- Recorder safety default: `overwrite_recording_group = false` is only safe when the existing recorder already captures the full required scope for `Config.1`.
- If runtime evidence proves the existing recorder is selective/custom and still fails `Config.1`, the resolver auto-promotes `recording_scope=all_resources` and the generated bundle may intentionally set `overwrite_recording_group = true`.
- Delivery safety: if an existing delivery channel points to a different bucket, apply emits a warning before redirecting to `delivery_bucket_name`.
- Delivery fail-closed: when `create_local_bucket = false`, apply exits early if `delivery_bucket_name` is unreachable so remediation does not fail later with an ambiguous `NoSuchBucket` error.
- Rollback safety: the restore script replays the exact pre-remediation recorder, recording mode, delivery-channel, and target-bucket policy state; it fails closed if drift or non-empty created buckets make exact restoration ambiguous.
"""


def _terraform_s3_15_guardrails_content() -> str:
    """README guidance for S3.15 exact rollback behavior."""
    return """

S3.15 rollback safeguards
-------------------------
- This executable Terraform path snapshots the exact pre-remediation bucket encryption state under `.s3-encryption-rollback/`.
- Run `python3 scripts/s3_encryption_capture.py` before `terraform apply`. The generated helper already targets this bundle's bucket and region; `BUCKET_NAME` and `REGION` are optional overrides only.
- After `terraform destroy`, run `python3 rollback/s3_encryption_restore.py` to restore the captured encryption exactly.
- If the bucket originally had no default encryption configuration, the restore helper deletes the post-remediation config instead of forcing a fallback encryption mode.
"""


def _maybe_append_terraform_readme(
    result: PRBundleResult,
    risk_snapshot: dict[str, Any] | None = None,
    strategy_id: str | None = None,
) -> PRBundleResult:
    """Append README.txt to Terraform bundles so users see credential/risk instructions."""
    if result.get("format") != TERRAFORM_FORMAT or not result.get("files"):
        return result
    metadata = result.get("metadata")
    if isinstance(metadata, dict) and metadata.get("non_executable_bundle") is True:
        return result
    files = list(result["files"])
    if any(f.get("path") == "README.txt" for f in files):
        return result
    readme = _terraform_readme_content()
    plan_timestamp_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    readme += "\nTerraform proof metadata (C2/C5)\n-------------------------------\n"
    readme += f"- terraform_plan_timestamp_utc: {plan_timestamp_utc}\n"
    readme += (
        "- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to "
        "preserve unrelated existing configuration unless a generated diff explicitly changes it.\n"
    )
    if any(f.get("path") == "s3_bucket_block_public_access.tf" for f in files):
        readme += _terraform_s3_bucket_block_guardrails_content()
    if any(f.get("path") == "s3_cloudfront_oac_private_s3.tf" for f in files):
        readme += _terraform_s3_cloudfront_oac_private_guardrails_content()
    if any(f.get("path") == "s3_website_cloudfront_private.tf" for f in files):
        readme += _terraform_s3_website_cloudfront_private_guardrails_content()
    if any(f.get("path") == "sg_restrict_public_ports.tf" for f in files):
        readme += _terraform_ec2_53_access_guidance_content()
    if any(f.get("path") == "s3_bucket_require_ssl.tf" for f in files):
        readme += _terraform_s3_5_access_guidance_content()
    if any(f.get("path") == "s3_bucket_encryption_kms.tf" for f in files):
        readme += _terraform_s3_15_guardrails_content()
    if any(f.get("path") == "ssm_block_public_sharing.tf" for f in files):
        readme += _terraform_ssm_7_access_guidance_content()
    if any(f.get("path") == "aws_config_enabled.tf" for f in files):
        readme += _terraform_aws_config_guardrails_content()
    if strategy_id:
        readme += "\n\nSelected strategy\n-----------------\n"
        readme += f"- strategy_id: {strategy_id}\n"
    if isinstance(risk_snapshot, dict):
        checks = risk_snapshot.get("checks")
        recommendation = risk_snapshot.get("recommendation")
        if recommendation:
            readme += "\nRisk recommendation\n-------------------\n"
            readme += f"- {recommendation}\n"
        if isinstance(checks, list) and checks:
            readme += "\nDependency review checklist\n---------------------------\n"
            for check in checks:
                if not isinstance(check, dict):
                    continue
                code = str(check.get("code", "check"))
                status = str(check.get("status", "unknown"))
                message = str(check.get("message", "")).strip()
                if message:
                    readme += f"- [{status}] {code}: {message}\n"
                else:
                    readme += f"- [{status}] {code}\n"
    files.append(PRBundleFile(path="README.txt", content=readme))
    updated = PRBundleResult(format=result["format"], files=files, steps=result["steps"])
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        updated["metadata"] = dict(metadata)
    return updated


def _action_meta(action: ActionLike | None) -> dict[str, str]:
    """Build substitution dict for action metadata (comments, steps). Includes target_id for resource-level actions (9.9–9.12)."""
    if action is None:
        return {
            "action_id": "",
            "action_title": "Unknown action",
            "account_id": "",
            "region": "N/A",
            "control_id": "",
            "target_id": "",
            "bundle_nonce": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        }
    return {
        "action_id": str(action.id),
        "action_title": (action.title or "Remediation").replace("\n", " ").strip()[:200],
        "account_id": action.account_id or "",
        "region": action.region or "N/A",
        "control_id": action.control_id or "",
        "target_id": (action.target_id or "").strip()[:512],
        "bundle_nonce": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
    }


def _s3_cloudfront_oac_name(meta: Mapping[str, Any]) -> str:
    bucket_name = _s3_bucket_name_from_target_id(str(meta.get("target_id", "")))
    action_id_seed = str(meta.get("action_id", "")).replace("-", "")
    bundle_nonce = str(meta.get("bundle_nonce", ""))
    seed = f"{bucket_name}-{action_id_seed}-{bundle_nonce}"
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:12]
    return f"security-autopilot-oac-{digest}"[:64]


def _cloudfront_oac_discovery_query_content(meta: Mapping[str, Any], *, oac_name: str) -> str:
    bucket_name = _s3_bucket_name_from_target_id(str(meta.get("target_id", "")))
    region = str(meta.get("region", "")).strip()
    payload = {
        "bucket_name": bucket_name,
        "expected_bucket_regional_domain_name": f"{bucket_name}.s3.{region}.amazonaws.com",
        "expected_distribution_comment": f"Security Autopilot migration for {bucket_name}",
        "expected_oac_name": oac_name,
        "expected_origin_id": f"s3-{bucket_name}",
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _s3_bucket_name_from_target_id(target_id: str) -> str:
    """
    Extract S3 bucket name from target_id.
    target_id may be: composite (account|region|arn:aws:s3:::bucketname|control) or plain ARN/bucket name.
    Returns the bucket name only (e.g. demomarcoss) or REPLACE_BUCKET_NAME if not parseable.
    """
    if not (target_id or "").strip():
        return "REPLACE_BUCKET_NAME"
    tid = (target_id or "").strip()

    # Prefer explicit S3 ARN extraction across composite target IDs.
    if "arn:aws:s3:::" in tid:
        for part in tid.split("|"):
            if "arn:aws:s3:::" not in part:
                continue
            candidate = _bucket_name_candidate(part)
            if candidate:
                return candidate
        candidate = _bucket_name_candidate(tid)
        if candidate:
            return candidate

    # For normalized target IDs (account|region|resource|control), use resource slot.
    if "|" in tid:
        segments = [segment.strip() for segment in tid.split("|")]
        if len(segments) >= 3:
            candidate = _bucket_name_candidate(segments[2])
            if candidate:
                return candidate
        return "REPLACE_BUCKET_NAME"

    candidate = _bucket_name_candidate(tid)
    return candidate or "REPLACE_BUCKET_NAME"


def _bucket_name_candidate(raw: str) -> str | None:
    """Extract normalized bucket name candidate from ARN/plain/kv forms."""
    value = (raw or "").strip().strip("'\"")
    if not value:
        return None

    if "arn:aws:s3:::" in value:
        value = value.split("arn:aws:s3:::")[-1]
    elif value.lower().startswith("arn:"):
        return None

    if value.startswith("AWS::::Account:") or value.lower().startswith("account:"):
        return None
    if value.lower().startswith("aws-account-"):
        return None
    if re.fullmatch(r"\d{12}", value):
        return None

    kv_match = re.search(
        r"(?:bucket(?:_name)?|bucketname)\s*[:=]\s*([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])",
        value,
        flags=re.IGNORECASE,
    )
    if kv_match:
        value = kv_match.group(1)

    value = value.split("/", 1)[0].strip()
    if not value:
        return None

    if not _S3_BUCKET_NAME_PATTERN.fullmatch(value):
        return None
    return value


def _security_group_id_from_target_id(target_id: str) -> str:
    """
    Extract SG ID from target_id.
    Accepts plain SG ID, SG ARN, or composite strings that include SG ARN/ID.
    Returns normalized sg-* or REPLACE_SECURITY_GROUP_ID if not parseable.
    """
    tid = (target_id or "").strip()
    if not tid:
        return "REPLACE_SECURITY_GROUP_ID"

    # Prefer strict AWS-like SG id pattern.
    match = re.search(r"(sg-[0-9a-fA-F]{8,})", tid)
    if match:
        return match.group(1)

    # Fallback for legacy/synthetic IDs used in tests and older data.
    match = re.search(r"(sg-[A-Za-z0-9-]+)", tid)
    if match:
        return match.group(1)

    # Parse SG ARN/resource forms that may omit the sg- prefix in some payloads.
    match = re.search(r"security-group/([A-Za-z0-9-]+)", tid)
    if match:
        token = (match.group(1) or "").strip()
        if re.fullmatch(r"[0-9a-fA-F]{8,}", token):
            return f"sg-{token.lower()}"

    # Parse key/value forms such as SecurityGroupId=sg-...
    match = re.search(
        r"(?:security[_ -]?group[_ -]?id|group[_ -]?id)\s*[:=]\s*['\"]?([A-Za-z0-9-]+)",
        tid,
        flags=re.IGNORECASE,
    )
    if match:
        token = (match.group(1) or "").strip()
        if token.startswith("sg-"):
            return token
        if re.fullmatch(r"[0-9a-fA-F]{8,}", token):
            return f"sg-{token.lower()}"

    return "REPLACE_SECURITY_GROUP_ID"


def _security_group_id_from_action_context(action: ActionLike, target_id: str) -> str | None:
    """
    Resolve SG ID from action context, trying target_id first then richer fields.

    Older/stale actions may have account-scoped target_id while resource_id still
    contains the SG ARN. Returning None lets callers raise a structured error
    instead of emitting invalid IaC with placeholder IDs.
    """
    candidates = [
        target_id,
        getattr(action, "resource_id", None),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = _security_group_id_from_target_id(str(candidate))
        if resolved != "REPLACE_SECURITY_GROUP_ID":
            return resolved
    return None


def _s3_bucket_name_from_action_context(action: ActionLike, target_id: str) -> str:
    """Resolve bucket name from target_id first, then resource_id as fallback."""
    candidates = [
        target_id,
        getattr(action, "resource_id", None),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = _s3_bucket_name_from_target_id(str(candidate))
        if resolved != "REPLACE_BUCKET_NAME":
            return resolved
    return "REPLACE_BUCKET_NAME"


# ---------------------------------------------------------------------------
# S3 Block Public Access (account-level) — Step 9.2
# ---------------------------------------------------------------------------
# Scope: account-level; region is not used (S3 Control API is account-level).
# Resource: aws_s3_account_public_access_block (HashiCorp AWS provider).
# File: s3_block_public_access.tf + providers.tf (Terraform); .yaml (CloudFormation).
# ---------------------------------------------------------------------------


def _generate_for_s3(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for s3_block_public_access (account-level). Step 9.2."""
    meta = _action_meta(action)
    if format == CLOUDFORMATION_FORMAT:
        files = [PRBundleFile(path="s3_block_public_access.yaml", content=_cloudformation_s3_content(meta))]
        steps = [
            f"Ensure AWS credentials target account {meta['account_id']}.",
            "Validate the template (e.g. aws cloudformation validate-template) and create/update the stack.",
            "Deploy the stack to enable S3 Block Public Access.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify the finding is resolved.",
        ]
    else:
        # Terraform: providers.tf first (init-ready), then resource file (Step 9.2).
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_s3_providers_content(meta)),
            PRBundleFile(path="s3_block_public_access.tf", content=_terraform_s3_content(meta)),
        ]
        steps = [
            f"Ensure AWS provider is configured for account {meta['account_id']}.",
            "Run `terraform init` and `terraform plan` to preview changes.",
            "Run `terraform apply` to enable S3 Block Public Access.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify the finding is resolved.",
        ]

    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_providers_content(meta: dict[str, str]) -> str:
    """Provider and backend hint for S3 account-level (no region required). Step 9.2."""
    return f"""# Configure AWS provider with credentials for account {meta["account_id"]}.
# Account-level S3 Block Public Access uses S3 Control API; region is not required for this resource.

terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "{TERRAFORM_AWS_PROVIDER_VERSION_CONSTRAINT}"
    }}
  }}
}}

# provider "aws" {{
#   region = "us-east-1"  # Optional; account-level block applies to all regions
# }}
"""


def _terraform_s3_content(meta: dict[str, str]) -> str:
    """Exact Terraform structure per implementation plan 9.2."""
    return f"""# S3 Block Public Access (account-level) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]}
# Control: {meta["control_id"]}

resource "aws_s3_account_public_access_block" "security_autopilot" {{
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}
"""


# ---------------------------------------------------------------------------
# CloudFormation: All seven action types — Step 9.5 (9.2–9.5, 9.9–9.12)
# ---------------------------------------------------------------------------
# 9.2 S3 account-level: Lambda custom resource for s3control:PutPublicAccessBlock.
# 9.3 Security Hub: AWS::SecurityHub::Hub. 9.4 GuardDuty: AWS::GuardDuty::Detector.
# 9.9 S3 bucket block: AWS::S3::Bucket + PublicAccessBlockConfiguration.
# 9.10 S3 bucket encryption: AWS::S3::Bucket + BucketEncryption.
# 9.11 SG restrict: custom revoke Lambda + AWS::EC2::SecurityGroupIngress (22/3389).
# 9.12 CloudTrail: AWS::CloudTrail::Trail. All templates valid YAML and applyable.
# ---------------------------------------------------------------------------


def _cloudformation_s3_content(meta: dict[str, str]) -> str:
    """Step 9.5: CloudFormation custom resource for S3 account-level block."""
    account_id = meta["account_id"]
    return f"""# S3 Block Public Access (account-level) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {account_id}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "Enable S3 account-level Block Public Access via Lambda custom resource."
Metadata:
  SecurityAutopilot:
    ActionId: "{meta["action_id"]}"
    ControlId: "{meta["control_id"]}"
    RemediationAPI: "s3control:PutPublicAccessBlock"
Parameters:
  AccountId:
    Type: String
    Default: "{account_id or ""}"
    Description: AWS account ID that should receive account-level S3 Block Public Access.
Resources:
  S3AccountPublicAccessBlockRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: s3-account-public-access-block
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - s3control:PutPublicAccessBlock
                Resource: "*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  S3AccountPublicAccessBlockFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt S3AccountPublicAccessBlockRole.Arn
      Code:
        ZipFile: |
          import boto3
          import cfnresponse

          def _resolve_account_id(event, context):
              explicit = (event.get("ResourceProperties", {{}}).get("AccountId") or "").strip()
              if explicit:
                  return explicit
              arn = getattr(context, "invoked_function_arn", "") or ""
              parts = arn.split(":")
              return parts[4] if len(parts) > 4 else ""

          def handler(event, context):
              request_type = event.get("RequestType")
              try:
                  if request_type == "Delete":
                      cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "S3PublicAccessBlock")
                      return
                  account_id = _resolve_account_id(event, context)
                  if not account_id:
                      raise ValueError("AccountId is required.")
                  s3control = boto3.client("s3control")
                  s3control.put_public_access_block(
                      AccountId=account_id,
                      PublicAccessBlockConfiguration={{
                          "BlockPublicAcls": True,
                          "IgnorePublicAcls": True,
                          "BlockPublicPolicy": True,
                          "RestrictPublicBuckets": True,
                      }},
                  )
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "S3PublicAccessBlock")
              except Exception as exc:
                  cfnresponse.send(
                      event,
                      context,
                      cfnresponse.FAILED,
                      {{"Error": str(exc)}},
                      "S3PublicAccessBlock",
                  )
  S3AccountPublicAccessBlock:
    Type: Custom::S3AccountPublicAccessBlock
    Properties:
      ServiceToken: !GetAtt S3AccountPublicAccessBlockFunction.Arn
      AccountId: !Ref AccountId
"""


# ---------------------------------------------------------------------------
# Security Hub enablement (per region) — Step 9.3
# ---------------------------------------------------------------------------
# Scope: per region; region is required. Provider must set region.
# Resource: aws_securityhub_account (HashiCorp AWS provider). MVP: account only.
# Files: providers.tf (with region) + enable_security_hub.tf (Terraform); .yaml (CloudFormation).
# ---------------------------------------------------------------------------


def _generate_for_security_hub(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for enable_security_hub (per region). Step 9.3."""
    meta = _action_meta(action)
    region = meta["region"]
    if format == CLOUDFORMATION_FORMAT:
        files = [PRBundleFile(path="enable_security_hub.yaml", content=_cloudformation_security_hub_content(meta))]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Validate the template and create/update the stack.",
            "Deploy the stack to enable Security Hub.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        # Terraform: providers.tf with region (required for Security Hub), then resource file (Step 9.3).
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_security_hub_providers_content(meta)),
            PRBundleFile(path="enable_security_hub.tf", content=_terraform_security_hub_content(meta)),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable Security Hub.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]

    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_security_hub_providers_content(meta: dict[str, str]) -> str:
    """Provider block with region for Security Hub (regional). Step 9.3."""
    region = meta["region"]
    account_id = meta["account_id"]
    return f"""# Configure AWS provider with credentials for account {account_id} and region {region}.
# Security Hub is regional; the provider region must match the target region.

terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "{TERRAFORM_AWS_PROVIDER_VERSION_CONSTRAINT}"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"
}}
"""


def _terraform_security_hub_content(meta: dict[str, str]) -> str:
    """Exact Terraform structure per implementation plan 9.3."""
    region = meta["region"]
    return f"""# Security Hub enablement - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {region}
# Control: {meta["control_id"]}

resource "aws_securityhub_account" "security_autopilot" {{}}
"""


def _cloudformation_security_hub_content(meta: dict[str, str]) -> str:
    """Step 9.5: Valid, applyable CloudFormation for Security Hub enablement (per region)."""
    region = meta["region"]
    return f"""# Security Hub enablement - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {region}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "Security Hub enablement - Security Autopilot remediation. Deploy in region {region}."
Metadata:
  SecurityAutopilot:
    ActionId: "{meta["action_id"]}"
    ControlId: "{meta["control_id"]}"
    Region: "{region}"
Resources:
  SecurityAutopilotHub:
    Type: AWS::SecurityHub::Hub
"""


# ---------------------------------------------------------------------------
# GuardDuty enablement (per region) — Step 9.4
# ---------------------------------------------------------------------------
# Scope: per region; region is required. Provider must set region.
# Resource: aws_guardduty_detector with enable = true (HashiCorp AWS provider).
# Files: providers.tf (with region) + enable_guardduty.tf (Terraform); .yaml (CloudFormation).
# ---------------------------------------------------------------------------


def _generate_for_guardduty(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for enable_guardduty (per region). Step 9.4."""
    meta = _action_meta(action)
    region = meta["region"]
    if format == CLOUDFORMATION_FORMAT:
        files = [PRBundleFile(path="enable_guardduty.yaml", content=_cloudformation_guardduty_content(meta))]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Validate the template and create/update the stack.",
            "Deploy the stack to enable GuardDuty.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        # Terraform: providers.tf with region (required for GuardDuty), then resource file (Step 9.4).
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_guardduty_providers_content(meta)),
            PRBundleFile(path="enable_guardduty.tf", content=_terraform_guardduty_content(meta)),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable GuardDuty.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]

    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_guardduty_providers_content(meta: dict[str, str]) -> str:
    """Provider block with region for GuardDuty (regional). Step 9.4."""
    region = meta["region"]
    account_id = meta["account_id"]
    return f"""# Configure AWS provider with credentials for account {account_id} and region {region}.
# GuardDuty is regional; the provider region must match the target region.

terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "{TERRAFORM_AWS_PROVIDER_VERSION_CONSTRAINT}"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"
}}
"""


def _terraform_guardduty_content(meta: dict[str, str]) -> str:
    """Exact Terraform structure per implementation plan 9.4."""
    region = meta["region"]
    return f"""# GuardDuty enablement - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {region}
# Control: {meta["control_id"]}

resource "aws_guardduty_detector" "security_autopilot" {{
  enable = true
}}
"""


def _cloudformation_guardduty_content(meta: dict[str, str]) -> str:
    """Step 9.5: Valid, applyable CloudFormation for GuardDuty enablement (per region)."""
    region = meta["region"]
    return f"""# GuardDuty enablement - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {region}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "GuardDuty enablement - Security Autopilot remediation. Deploy in region {region}."
Metadata:
  SecurityAutopilot:
    ActionId: "{meta["action_id"]}"
    ControlId: "{meta["control_id"]}"
    Region: "{region}"
Resources:
  SecurityAutopilotDetector:
    Type: AWS::GuardDuty::Detector
    Properties:
      Enable: true
"""


# ---------------------------------------------------------------------------
# S3 bucket-level block public access — Step 9.9 (action_type: s3_bucket_block_public_access, control_id: S3.2)
# ---------------------------------------------------------------------------
# Scope: per bucket; target_id = bucket name. Control S3.2 → s3_bucket_block_public_access (control_scope 9.8).
# Terraform: aws_s3_bucket_public_access_block. CloudFormation: AWS::S3::Bucket + PublicAccessBlockConfiguration.
# ---------------------------------------------------------------------------


def _generate_for_s3_bucket_block_public_access(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    strategy_id: str | None,
    resolution: Mapping[str, Any] | None,
) -> PRBundleResult:
    """Generate IaC for s3_bucket_block_public_access (per bucket, S3.2). Step 9.9."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    if _s3_2_public_policy_scrub_requested(resolution):
        if format == CLOUDFORMATION_FORMAT:
            _raise_pr_bundle_error(
                code="unsupported_variant_format",
                detail=(
                    "Profile 's3_bucket_block_public_access_review_public_policy_scrub' is only supported for terraform format."
                ),
                action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
                format=format,
                strategy_id=strategy_id,
                variant=None,
            )
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_block_public_access.tf",
                content=_terraform_s3_bucket_block_public_access_policy_scrub_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "What changes: removes unconditional public Allow statements before enabling Block Public Access.",
            "Review the generated Terraform carefully; this branch preserves Deny statements and conditional wildcard statements.",
            "Run `terraform init` and inspect `terraform plan`, especially removed_statement_count and removed_statement_identifiers.",
            "Confirm conditional wildcard statements, Deny statements, and required non-public access paths are preserved before apply.",
            "Run `terraform apply` only after the review confirms no required public Allow statements will be removed unexpectedly.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
        return PRBundleResult(format=format, files=files, steps=steps)
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="s3_bucket_block_public_access.yaml",
                content=_cloudformation_s3_bucket_block_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "What changes: sets Bucket PublicAccessBlockConfiguration (BlockPublicAcls/BlockPublicPolicy/IgnorePublicAcls/RestrictPublicBuckets).",
            "How to access now: CloudFront usage note - serve traffic through CloudFront HTTPS endpoints, not direct public S3 website/object URLs.",
            "Set Parameter BucketName to the target bucket (or use default).",
            "Validate the template and create/update the stack.",
            "Verify: run `aws s3api get-public-access-block --bucket <bucket-name> --query 'PublicAccessBlockConfiguration' --output json` and confirm all flags are true.",
            "Rollback: emergency-only unblock command `aws s3api put-public-access-block --bucket <bucket-name> --public-access-block-configuration BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false`.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_block_public_access.tf",
                content=_terraform_s3_bucket_block_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "IMPORTANT: this bundle is control hardening (Block Public Access), not a complete CloudFront+OAC migration.",
            "Inventory dependencies first (website hosting, log delivery, cross-account/service principals, KMS if SSE-KMS).",
            f"Set bucket name in the Terraform file (target: {bucket_name}).",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable block public access on the bucket.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _generate_for_s3_cloudfront_oac_private(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    risk_snapshot: dict[str, Any] | None,
    variant: str | None,
    resolution: Mapping[str, Any] | None,
) -> PRBundleResult:
    """
    Generate IaC for real migration path: CloudFront + OAC + private S3 (S3.2).

    This variant is selected explicitly from the remediation flow and produces
    runnable Terraform for a safer public content pattern.
    """
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    oac_name = _s3_cloudfront_oac_name(meta)
    create_bucket_if_missing = _create_bucket_if_missing_enabled(strategy_inputs)

    if format == CLOUDFORMATION_FORMAT:
        _raise_pr_bundle_error(
            code="unsupported_variant_format",
            detail=(
                "Variant 'cloudfront_oac_private_s3' is only supported for terraform format."
            ),
            action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
            format=format,
            strategy_id="s3_migrate_cloudfront_oac_private",
            variant=PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3,
        )

    apply_time_merge = _s3_2_apply_time_merge_requested(resolution) and not create_bucket_if_missing
    files = [
        PRBundleFile(
            path="providers.tf",
            content=_terraform_regional_providers_content(meta),
        ),
        PRBundleFile(
            path="s3_cloudfront_oac_private_s3.tf",
            content=(
                _terraform_s3_cloudfront_oac_private_apply_time_content(
                    meta,
                    oac_name=oac_name,
                    create_bucket_if_missing=create_bucket_if_missing,
                )
                if apply_time_merge
                else _terraform_s3_cloudfront_oac_private_content(
                    meta,
                    oac_name=oac_name,
                    create_bucket_if_missing=create_bucket_if_missing,
                )
            ),
        ),
        PRBundleFile(
            path=AWS_CLOUDFRONT_OAC_DISCOVERY_SCRIPT_PATH,
            content=aws_cloudfront_oac_discovery_script_content(),
        ),
        PRBundleFile(
            path=AWS_CLOUDFRONT_OAC_DISCOVERY_QUERY_PATH,
            content=_cloudfront_oac_discovery_query_content(meta, oac_name=oac_name),
        ),
    ]
    preservation_policy: str | None = None
    if not apply_time_merge and not create_bucket_if_missing:
        preservation_policy = _resolve_s3_migrate_policy_preservation(
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
            format=format,
            strategy_id=strategy_id,
            variant=variant,
        )
        preservation_policy = _strip_s3_2_managed_policy_statement(preservation_policy)
    if preservation_policy is not None:
        files.append(
            PRBundleFile(
                path="terraform.auto.tfvars.json",
                content=(
                    json.dumps(
                        {
                            _S3_MIGRATE_POLICY_JSON_KEY: preservation_policy,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ),
            )
        )
    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {region}.",
        f"Review variables in s3_cloudfront_oac_private_s3.tf (target bucket: {bucket_name}).",
        (
            "This bundle will create the missing target bucket with a minimal private baseline before creating CloudFront + OAC."
            if create_bucket_if_missing
            else (
            "When safe, this bundle will adopt the existing Security Autopilot CloudFront distribution/OAC for the target bucket instead of creating duplicates."
            if not apply_time_merge and preservation_policy is None
            else (
            "Current bucket policy will be fetched and merged at terraform plan/apply time with customer credentials."
            if apply_time_merge
            else (
                "Review terraform.auto.tfvars.json; existing bucket policy statements were preloaded "
                "for safe preservation."
                if preservation_policy is not None
                else "No existing bucket policy statements were detected; existing_bucket_policy_json remains empty."
            )
            )
            )
        ),
        "If needed, set additional_read_principal_arns before apply.",
        "Run `terraform init` and `terraform plan`.",
        "Run `terraform apply` to create CloudFront+OAC and enforce private S3 access.",
        "Switch clients/apps to CloudFront domain output and validate traffic.",
        "Return to the action and click **Recompute actions** or trigger ingest to verify.",
    ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _generate_for_s3_website_cloudfront_private(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    risk_snapshot: dict[str, Any] | None,
    resolution: Mapping[str, Any] | None,
) -> PRBundleResult:
    """Generate IaC for website-to-CloudFront private-origin S3 migration."""
    meta = _action_meta(action)
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    if format == CLOUDFORMATION_FORMAT:
        _raise_pr_bundle_error(
            code="unsupported_variant_format",
            detail=(
                "Strategy 's3_migrate_website_cloudfront_private' is only supported for terraform format."
            ),
            action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
            format=format,
            strategy_id=strategy_id,
        )

    website_config = _resolve_s3_website_configuration(
        strategy_inputs=strategy_inputs,
        risk_snapshot=risk_snapshot,
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        format=format,
        strategy_id=strategy_id,
    )
    apply_time_merge = _s3_2_apply_time_merge_requested(resolution)
    preservation_policy: str | None = None
    if not apply_time_merge:
        preservation_policy = _resolve_s3_migrate_policy_preservation(
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
            format=format,
            strategy_id=strategy_id,
            variant=None,
        )
    strategy_values = dict(strategy_inputs or {})
    aliases = [str(alias).strip() for alias in strategy_values.get("aliases", []) if str(alias).strip()]
    route53_hosted_zone_id = str(strategy_values.get("route53_hosted_zone_id", "")).strip()
    acm_certificate_arn = str(strategy_values.get("acm_certificate_arn", "")).strip()
    default_root_object = (
        str(strategy_values.get("default_root_object_override", "")).strip()
        or website_config["default_root_object"]
    )
    price_class = str(strategy_values.get("price_class", "")).strip() or "PriceClass_100"
    files = [
        PRBundleFile(
            path="providers.tf",
            content=_terraform_regional_providers_content(meta, include_null_provider=True),
        ),
        PRBundleFile(
            path="s3_website_cloudfront_private.tf",
            content=(
                _terraform_s3_website_cloudfront_private_apply_time_content(
                    meta,
                    aliases=aliases,
                    route53_hosted_zone_id=route53_hosted_zone_id,
                    acm_certificate_arn=acm_certificate_arn,
                    default_root_object=default_root_object,
                    error_document_key=website_config["error_document_key"],
                    price_class=price_class,
                )
                if apply_time_merge
                else _terraform_s3_website_cloudfront_private_content(
                    meta,
                    aliases=aliases,
                    route53_hosted_zone_id=route53_hosted_zone_id,
                    acm_certificate_arn=acm_certificate_arn,
                    default_root_object=default_root_object,
                    error_document_key=website_config["error_document_key"],
                    price_class=price_class,
                )
            ),
        ),
        PRBundleFile(
            path="terraform.auto.tfvars.json",
            content=json.dumps(
                {
                    key: value
                    for key, value in {
                        _S3_WEBSITE_CONFIGURATION_JSON_KEY: website_config["json"],
                        _S3_MIGRATE_POLICY_JSON_KEY: preservation_policy,
                    }.items()
                    if value is not None
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        ),
    ]
    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
        f"Review aliases, certificate, and rollback inputs in s3_website_cloudfront_private.tf (bucket: {bucket_name}).",
        (
            "Current bucket policy will be fetched and merged at terraform plan/apply time with customer credentials."
            if apply_time_merge
            else (
                "Review terraform.auto.tfvars.json; it contains the captured website configuration and existing "
                "bucket policy preservation JSON for rollback-aware cutover."
                if preservation_policy is not None
                else "Review terraform.auto.tfvars.json; it contains the captured website configuration for rollback-aware cutover."
            )
        ),
        "Run `terraform init` and `terraform plan`.",
        "Run `terraform apply` to create CloudFront, update Route53 aliases, remove S3 website hosting, and enable bucket public-access block settings.",
        "Validate each alias resolves to the CloudFront domain and check key pages over HTTPS before declaring the cutover complete.",
        "Rollback order if needed: restore Route53 aliases and S3 website hosting first, then relax bucket access only as a temporary emergency measure.",
        "Return to the action and click **Recompute actions** or trigger ingest to verify.",
    ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_bucket_block_content(meta: dict[str, str]) -> str:
    """Terraform for per-bucket S3 block public access (S3.2). Step 9.9: aws_s3_bucket_public_access_block."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket control hardening (Block Public Access) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}
# NOTE: This is NOT a full CloudFront + OAC + private S3 migration.
#       Review dependent consumers and bucket policy/KMS requirements before apply.

resource "aws_s3_bucket_public_access_block" "security_autopilot" {{
  bucket = "{bucket}"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}
"""


def _terraform_s3_bucket_block_public_access_policy_scrub_content(meta: dict[str, str]) -> str:
    """Terraform for review-tier S3.2 public-policy scrub before BPA enablement."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket public-policy scrub review bundle - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}
# NOTE: Review this plan carefully. It removes only unconditional public Allow statements,
#       preserves Deny statements and conditional wildcard statements, and then enables
#       S3 Block Public Access on the bucket.

data "aws_s3_bucket_policy" "existing" {{
  bucket = "{bucket}"
}}

locals {{
  existing_policy_document = try(
    jsondecode(data.aws_s3_bucket_policy.existing.policy),
    {{
      Version   = "2012-10-17"
      Statement = []
    }}
  )
  existing_policy_id = try(local.existing_policy_document.Id, null)
  existing_policy_statements_candidate = try(local.existing_policy_document.Statement, null)
  existing_policy_statements = jsondecode(
    local.existing_policy_statements_candidate == null ? "[]" : (
      can(local.existing_policy_statements_candidate.Effect) ? format(
        "[%s]",
        jsonencode(local.existing_policy_statements_candidate)
      ) : jsonencode(local.existing_policy_statements_candidate)
    )
  )
  existing_policy_statement_metadata = [
    for idx, statement in local.existing_policy_statements : {{
      identifier = trimspace(try(tostring(statement.Sid), "")) != "" ? trimspace(tostring(statement.Sid)) : "statement-index-${{idx}}"
      statement  = statement
      remove = (
        lower(trimspace(try(tostring(statement.Effect), ""))) == "allow" &&
        !can(statement.Condition) &&
        (
          trimspace(try(tostring(statement.Principal), "")) == "*" ||
          trimspace(try(tostring(statement.Principal.AWS), "")) == "*" ||
          contains(
            [for identifier in try(statement.Principal.AWS, []) : trimspace(tostring(identifier))],
            "*"
          )
        )
      )
    }}
  ]
  removed_statement_identifiers = [
    for item in local.existing_policy_statement_metadata : item.identifier
    if item.remove
  ]
  preserved_policy_statements = [
    for item in local.existing_policy_statement_metadata : item.statement
    if !item.remove
  ]
  scrubbed_policy_document = merge(
    {{
      Version   = try(tostring(local.existing_policy_document.Version), "2012-10-17")
      Statement = local.preserved_policy_statements
    }},
    local.existing_policy_id == null ? {{}} : {{ Id = local.existing_policy_id }}
  )
}}

resource "aws_s3_bucket_policy" "security_autopilot" {{
  count  = length(local.preserved_policy_statements) > 0 ? 1 : 0
  bucket = "{bucket}"
  policy = jsonencode(local.scrubbed_policy_document)
}}

resource "terraform_data" "delete_bucket_policy" {{
  count = length(local.preserved_policy_statements) == 0 ? 1 : 0

  triggers_replace = {{
    bucket_name            = "{bucket}"
    scrubbed_policy_sha256 = sha256(jsonencode(local.scrubbed_policy_document))
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
aws s3api delete-bucket-policy --bucket "{bucket}"
EOT
  }}
}}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {{
  bucket = "{bucket}"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  depends_on = [
    aws_s3_bucket_policy.security_autopilot,
    terraform_data.delete_bucket_policy,
  ]
}}

output "removed_statement_count" {{
  value       = length(local.removed_statement_identifiers)
  description = "Number of unconditional public Allow statements removed before enabling Block Public Access."
}}

output "removed_statement_identifiers" {{
  value       = local.removed_statement_identifiers
  description = "Statement Sids or synthetic statement indexes removed by the scrub."
}}
"""


def _terraform_s3_website_cloudfront_common_content(
    meta: dict[str, str],
    *,
    aliases: list[str],
    route53_hosted_zone_id: str,
    acm_certificate_arn: str,
    default_root_object: str,
    error_document_key: str,
    price_class: str,
    bucket_policy_source: str,
) -> str:
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    action_id_seed = (meta.get("action_id") or "").replace("-", "")
    bundle_nonce = meta.get("bundle_nonce", "")
    aliases_json = json.dumps(aliases)
    route53_hosted_zone_id_json = json.dumps(route53_hosted_zone_id)
    acm_certificate_arn_json = json.dumps(acm_certificate_arn)
    default_root_object_json = json.dumps(default_root_object)
    error_document_key_json = json.dumps(error_document_key)
    price_class_json = json.dumps(price_class)
    error_response_blocks = ""
    if error_document_key:
        error_page = json.dumps(f"/{error_document_key.lstrip('/')}")
        error_response_blocks = f"""

  custom_error_response {{
    error_code            = 403
    response_code         = 200
    response_page_path    = {error_page}
    error_caching_min_ttl = 0
  }}

  custom_error_response {{
    error_code            = 404
    response_code         = 404
    response_page_path    = {error_page}
    error_caching_min_ttl = 0
  }}"""
    return f"""# S3.2 website migration variant (CloudFront + private S3 + Route53) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

locals {{
  bucket_name               = "{bucket}"
  remediation_region        = "{meta["region"]}"
  oac_name_seed             = "${{local.bucket_name}}-{action_id_seed}-{bundle_nonce}"
  oac_name                  = substr("security-autopilot-oac-${{substr(md5(local.oac_name_seed), 0, 12)}}", 0, 64)
}}

variable "aliases" {{
  type        = list(string)
  description = "Route53 hostnames that should resolve to the CloudFront distribution."
  default     = {aliases_json}
}}

variable "route53_hosted_zone_id" {{
  type        = string
  description = "Route53 hosted zone ID that owns the aliases."
  default     = {route53_hosted_zone_id_json}
}}

variable "acm_certificate_arn" {{
  type        = string
  description = "CloudFront viewer certificate ARN (must be in us-east-1)."
  default     = {acm_certificate_arn_json}
}}

variable "price_class" {{
  type        = string
  description = "CloudFront price class."
  default     = {price_class_json}
}}

variable "default_root_object" {{
  type        = string
  description = "Default root object translated from the captured S3 website IndexDocument."
  default     = {default_root_object_json}
}}

variable "error_document_key" {{
  type        = string
  description = "Optional error document key translated from the captured S3 website configuration."
  default     = {error_document_key_json}
}}

variable "existing_bucket_website_configuration_json" {{
  type        = string
  description = "Captured S3 website configuration JSON for rollback documentation."
}}

data "aws_s3_bucket" "target" {{
  bucket = local.bucket_name
}}

resource "aws_cloudfront_origin_access_control" "security_autopilot" {{
  name                              = local.oac_name
  description                       = "OAC for Security Autopilot website migration"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}}

resource "aws_cloudfront_distribution" "security_autopilot" {{
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Security Autopilot website migration for ${{local.bucket_name}}"
  aliases             = var.aliases
  default_root_object = var.default_root_object
  price_class         = var.price_class

  origin {{
    domain_name              = data.aws_s3_bucket.target.bucket_regional_domain_name
    origin_id                = "s3-${{local.bucket_name}}"
    origin_access_control_id = aws_cloudfront_origin_access_control.security_autopilot.id
  }}

  default_cache_behavior {{
    target_origin_id         = "s3-${{local.bucket_name}}"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS"]
    cached_methods           = ["GET", "HEAD", "OPTIONS"]
    compress                 = true
    cache_policy_id          = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    origin_request_policy_id = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"
  }}{error_response_blocks}

  restrictions {{
    geo_restriction {{
      restriction_type = "none"
    }}
  }}

  viewer_certificate {{
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }}
}}

{bucket_policy_source}

resource "aws_route53_record" "website_ipv4" {{
  for_each = toset(var.aliases)
  zone_id  = var.route53_hosted_zone_id
  name     = each.value
  type     = "A"

  alias {{
    name                   = aws_cloudfront_distribution.security_autopilot.domain_name
    zone_id                = aws_cloudfront_distribution.security_autopilot.hosted_zone_id
    evaluate_target_health = false
  }}

  depends_on = [aws_s3_bucket_policy.security_autopilot]
}}

resource "aws_route53_record" "website_ipv6" {{
  for_each = toset(var.aliases)
  zone_id  = var.route53_hosted_zone_id
  name     = each.value
  type     = "AAAA"

  alias {{
    name                   = aws_cloudfront_distribution.security_autopilot.domain_name
    zone_id                = aws_cloudfront_distribution.security_autopilot.hosted_zone_id
    evaluate_target_health = false
  }}

  depends_on = [aws_s3_bucket_policy.security_autopilot]
}}

resource "null_resource" "disable_bucket_website" {{
  triggers = {{
    bucket_name               = local.bucket_name
    remediation_region        = local.remediation_region
    website_configuration_sha = md5(var.existing_bucket_website_configuration_json)
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
aws s3api delete-bucket-website --bucket "${{local.bucket_name}}" --region "${{local.remediation_region}}"
EOT
  }}

  depends_on = [
    aws_route53_record.website_ipv4,
    aws_route53_record.website_ipv6,
  ]
}}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {{
  bucket = data.aws_s3_bucket.target.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  depends_on = [null_resource.disable_bucket_website]
}}

output "cloudfront_distribution_id" {{
  value       = aws_cloudfront_distribution.security_autopilot.id
  description = "CloudFront distribution ID."
}}

output "cloudfront_domain_name" {{
  value       = aws_cloudfront_distribution.security_autopilot.domain_name
  description = "Use this CloudFront domain or the configured aliases instead of the S3 website endpoint."
}}

output "website_aliases" {{
  value       = var.aliases
  description = "Aliases expected to resolve to the CloudFront distribution after Route53 cutover."
}}
"""


def _terraform_s3_website_cloudfront_private_content(
    meta: dict[str, str],
    *,
    aliases: list[str],
    route53_hosted_zone_id: str,
    acm_certificate_arn: str,
    default_root_object: str,
    error_document_key: str,
    price_class: str,
) -> str:
    bucket_policy_source = """variable "existing_bucket_policy_json" {
  type        = string
  description = "Optional existing bucket policy JSON to preserve current non-public statements."
  default     = ""
}

data "aws_iam_policy_document" "bucket_policy" {
  source_policy_documents = var.existing_bucket_policy_json == "" ? [] : [var.existing_bucket_policy_json]

  statement {
    sid    = "AllowCloudFrontReadOnly"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.target.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.security_autopilot.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = data.aws_s3_bucket.target.id
  policy = data.aws_iam_policy_document.bucket_policy.json
}"""
    return _terraform_s3_website_cloudfront_common_content(
        meta,
        aliases=aliases,
        route53_hosted_zone_id=route53_hosted_zone_id,
        acm_certificate_arn=acm_certificate_arn,
        default_root_object=default_root_object,
        error_document_key=error_document_key,
        price_class=price_class,
        bucket_policy_source=bucket_policy_source,
    )


def _terraform_s3_website_cloudfront_private_apply_time_content(
    meta: dict[str, str],
    *,
    aliases: list[str],
    route53_hosted_zone_id: str,
    acm_certificate_arn: str,
    default_root_object: str,
    error_document_key: str,
    price_class: str,
) -> str:
    bucket_policy_source = """data "aws_s3_bucket_policy" "existing" {
  bucket = data.aws_s3_bucket.target.id
}

locals {
  existing_bucket_policy_document = try(jsondecode(data.aws_s3_bucket_policy.existing.policy), null)
  existing_bucket_policy_statements = try(local.existing_bucket_policy_document.Statement, [])
  filtered_existing_policy_statements = [
    for statement in local.existing_bucket_policy_statements : statement
    if try(statement.Sid, "") != "AllowCloudFrontReadOnly"
  ]
}

data "aws_iam_policy_document" "bucket_policy" {
  source_policy_documents = local.existing_bucket_policy_document == null ? [] : [
    jsonencode({
      Version   = try(local.existing_bucket_policy_document.Version, "2012-10-17")
      Statement = local.filtered_existing_policy_statements
    })
  ]

  statement {
    sid    = "AllowCloudFrontReadOnly"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.target.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.security_autopilot.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = data.aws_s3_bucket.target.id
  policy = data.aws_iam_policy_document.bucket_policy.json
}"""
    return _terraform_s3_website_cloudfront_common_content(
        meta,
        aliases=aliases,
        route53_hosted_zone_id=route53_hosted_zone_id,
        acm_certificate_arn=acm_certificate_arn,
        default_root_object=default_root_object,
        error_document_key=error_document_key,
        price_class=price_class,
        bucket_policy_source=bucket_policy_source,
    )


def _terraform_s3_cloudfront_oac_private_common_content(
    meta: dict[str, str],
    *,
    oac_name: str,
    create_bucket_if_missing: bool,
    existing_policy_source: str,
    existing_policy_document_expr: str,
) -> str:
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    create_bucket_if_missing_text = "true" if create_bucket_if_missing else "false"
    create_bucket_blocks = _terraform_minimal_private_bucket_blocks(
        resource_suffix="target_bucket",
        bucket_name_ref='local.bucket_name',
        count_expr="var.create_bucket_if_missing ? 1 : 0",
        include_public_access_block=False,
    )
    return f"""# S3.2 migration variant (CloudFront + OAC + private S3) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

locals {{
  bucket_name                         = "{bucket}"
  remediation_region                  = "{meta["region"]}"
  expected_bucket_regional_domain_name = "${{local.bucket_name}}.s3.${{local.remediation_region}}.amazonaws.com"
  expected_distribution_comment       = "Security Autopilot migration for ${{local.bucket_name}}"
  expected_origin_id                  = "s3-${{local.bucket_name}}"
  oac_name                            = "{oac_name}"
}}

variable "default_root_object" {{
  type        = string
  description = "Default object served by CloudFront at /"
  default     = "index.html"
}}

variable "price_class" {{
  type        = string
  description = "CloudFront price class"
  default     = "PriceClass_100"
}}

variable "cache_policy_id" {{
  type        = string
  description = "CloudFront cache policy (Managed-CachingOptimized default)"
  default     = "658327ea-f89d-4fab-a63d-7e88639e58f6"
}}

variable "origin_request_policy_id" {{
  type        = string
  description = "CloudFront origin request policy (Managed-CORS-S3Origin default)"
  default     = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"
}}

variable "existing_bucket_policy_json" {{
  type        = string
  description = "Optional existing bucket policy JSON to preserve current non-public statements."
  default     = ""
}}

variable "create_bucket_if_missing" {{
  type        = bool
  description = "When true, create the target bucket with a minimal private baseline before creating CloudFront + OAC."
  default     = {create_bucket_if_missing_text}
}}

variable "additional_read_principal_arns" {{
  type        = list(string)
  description = "Optional IAM principal ARNs that still require direct S3 GetObject access."
  default     = []
}}

variable "cloudfront_reuse_mode" {{
  type        = string
  description = "Precomputed CloudFront/OAC reuse mode from the runner preflight."
  default     = "create"
}}

variable "reuse_oac_id" {{
  type        = string
  description = "Precomputed OAC ID to reuse when cloudfront_reuse_mode requires it."
  default     = ""
}}

variable "reuse_distribution_id" {{
  type        = string
  description = "Precomputed CloudFront distribution ID to reuse when cloudfront_reuse_mode=reuse_distribution."
  default     = ""
}}

variable "reuse_distribution_arn" {{
  type        = string
  description = "Precomputed CloudFront distribution ARN to reuse when cloudfront_reuse_mode=reuse_distribution."
  default     = ""
}}

variable "reuse_distribution_domain_name" {{
  type        = string
  description = "Precomputed CloudFront domain name to reuse when cloudfront_reuse_mode=reuse_distribution."
  default     = ""
}}

{create_bucket_blocks}

data "aws_s3_bucket" "existing_target" {{
  count  = var.create_bucket_if_missing ? 0 : 1
  bucket = local.bucket_name
}}

{existing_policy_source}

locals {{
  target_bucket_id                   = var.create_bucket_if_missing ? aws_s3_bucket.target_bucket[0].id : data.aws_s3_bucket.existing_target[0].id
  target_bucket_arn                  = var.create_bucket_if_missing ? aws_s3_bucket.target_bucket[0].arn : data.aws_s3_bucket.existing_target[0].arn
  target_bucket_regional_domain_name = var.create_bucket_if_missing ? aws_s3_bucket.target_bucket[0].bucket_regional_domain_name : data.aws_s3_bucket.existing_target[0].bucket_regional_domain_name
  existing_policy_document = try(
    {existing_policy_document_expr},
    {{
      Version   = "2012-10-17"
      Statement = []
    }}
  )
  existing_policy_id = try(local.existing_policy_document.Id, null)
  existing_policy_statements = try(local.existing_policy_document.Statement, [])
  filtered_existing_policy_statements = [
    for stmt in local.existing_policy_statements : stmt
    if lower(try(tostring(stmt.Sid), "")) != "{_S3_CLOUDFRONT_READONLY_POLICY_SID.lower()}"
  ]
  filtered_existing_policy_document = merge(
    {{
      Version   = try(tostring(local.existing_policy_document.Version), "2012-10-17")
      Statement = local.filtered_existing_policy_statements
    }},
    local.existing_policy_id == null ? {{}} : {{ Id = local.existing_policy_id }}
  )
  cloudfront_reuse_mode = var.cloudfront_reuse_mode
  reuse_distribution    = local.cloudfront_reuse_mode == "reuse_distribution"
  reuse_oac_only        = local.cloudfront_reuse_mode == "reuse_oac_only"
  reuse_oac             = local.reuse_distribution || local.reuse_oac_only
  effective_oac_id = (
    local.reuse_oac
    ? var.reuse_oac_id
    : aws_cloudfront_origin_access_control.security_autopilot[0].id
  )
  effective_distribution_id = (
    local.reuse_distribution
    ? var.reuse_distribution_id
    : aws_cloudfront_distribution.security_autopilot[0].id
  )
  effective_distribution_arn = (
    local.reuse_distribution
    ? var.reuse_distribution_arn
    : aws_cloudfront_distribution.security_autopilot[0].arn
  )
  effective_distribution_domain_name = (
    local.reuse_distribution
    ? var.reuse_distribution_domain_name
    : aws_cloudfront_distribution.security_autopilot[0].domain_name
  )
}}

resource "aws_cloudfront_origin_access_control" "security_autopilot" {{
  count                             = local.reuse_oac ? 0 : 1
  name                              = local.oac_name
  description                       = "OAC for Security Autopilot remediation"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}}

resource "aws_cloudfront_distribution" "security_autopilot" {{
  count               = local.reuse_distribution ? 0 : 1
  enabled             = true
  is_ipv6_enabled     = true
  comment             = local.expected_distribution_comment
  default_root_object = var.default_root_object
  price_class         = var.price_class

  origin {{
    domain_name              = local.target_bucket_regional_domain_name
    origin_id                = local.expected_origin_id
    origin_access_control_id = local.effective_oac_id
  }}

  default_cache_behavior {{
    target_origin_id         = local.expected_origin_id
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS"]
    cached_methods           = ["GET", "HEAD", "OPTIONS"]
    compress                 = true
    cache_policy_id          = var.cache_policy_id
    origin_request_policy_id = var.origin_request_policy_id
  }}

  restrictions {{
    geo_restriction {{
      restriction_type = "none"
    }}
  }}

  viewer_certificate {{
    cloudfront_default_certificate = true
  }}
}}

data "aws_iam_policy_document" "bucket_policy" {{
  source_policy_documents = [jsonencode(local.filtered_existing_policy_document)]

  statement {{
    sid    = "{_S3_CLOUDFRONT_READONLY_POLICY_SID}"
    effect = "Allow"
    principals {{
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }}
    actions   = ["s3:GetObject"]
    resources = ["${{local.target_bucket_arn}}/*"]
    condition {{
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [local.effective_distribution_arn]
    }}
  }}

  dynamic "statement" {{
    for_each = var.additional_read_principal_arns
    content {{
      sid    = "AllowAdditionalRead${{substr(md5(statement.value), 0, 8)}}"
      effect = "Allow"
      principals {{
        type        = "AWS"
        identifiers = [statement.value]
      }}
      actions   = ["s3:GetObject"]
      resources = ["${{local.target_bucket_arn}}/*"]
    }}
  }}
}}

resource "aws_s3_bucket_policy" "security_autopilot" {{
  bucket = local.target_bucket_id
  policy = data.aws_iam_policy_document.bucket_policy.json
  depends_on = [{_terraform_minimal_private_bucket_dependency("target_bucket")}]
}}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {{
  bucket = local.target_bucket_id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

output "cloudfront_distribution_id" {{
  value       = local.effective_distribution_id
  description = "CloudFront distribution ID."
}}

output "cloudfront_domain_name" {{
  value       = local.effective_distribution_domain_name
  description = "Use this domain in clients instead of direct S3 public URLs."
}}

output "bucket_name" {{
  value       = local.target_bucket_id
  description = "Target S3 bucket migrated to private access via CloudFront OAC."
}}
"""


def _terraform_s3_cloudfront_oac_private_content(
    meta: dict[str, str],
    *,
    oac_name: str,
    create_bucket_if_missing: bool = False,
) -> str:
    """Terraform for S3.2 migration variant: CloudFront + OAC + private S3."""
    return _terraform_s3_cloudfront_oac_private_common_content(
        meta,
        oac_name=oac_name,
        create_bucket_if_missing=create_bucket_if_missing,
        existing_policy_source="",
        existing_policy_document_expr=(
            'var.existing_bucket_policy_json == "" ? { Version = "2012-10-17", Statement = [] } '
            ": jsondecode(var.existing_bucket_policy_json)"
        ),
    )


def _terraform_s3_cloudfront_oac_private_apply_time_content(
    meta: dict[str, str],
    *,
    oac_name: str,
    create_bucket_if_missing: bool = False,
) -> str:
    """Terraform for S3.2 OAC variant with apply-time policy capture."""
    return _terraform_s3_cloudfront_oac_private_common_content(
        meta,
        oac_name=oac_name,
        create_bucket_if_missing=create_bucket_if_missing,
        existing_policy_source="""data "aws_s3_bucket_policy" "existing" {
  count  = var.create_bucket_if_missing ? 0 : 1
  bucket = local.bucket_name
}""",
        existing_policy_document_expr="jsondecode(data.aws_s3_bucket_policy.existing[0].policy)",
    )


def _cloudformation_s3_bucket_block_content(meta: dict[str, str]) -> str:
    """CloudFormation for per-bucket S3 block public access (S3.2). Step 9.5 (all seven), 9.9."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket control hardening (Block Public Access) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}
# NOTE: This is NOT a full CloudFront + OAC + private S3 migration.
# For existing buckets, prefer Terraform (aws_s3_bucket_public_access_block). This template creates/updates a bucket with block.

AWSTemplateFormatVersion: "2010-09-09"
Description: "S3 bucket Block Public Access control hardening (not full CloudFront/OAC migration). Set BucketName parameter."
Parameters:
  BucketName:
    Type: String
    Default: "{bucket}"
    Description: S3 bucket name to apply public access block
Resources:
  BucketBlock:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BucketName
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
"""


# ---------------------------------------------------------------------------
# S3 bucket encryption — Step 9.10 (action_type: s3_bucket_encryption, control_id: S3.4)
# ---------------------------------------------------------------------------
# Scope: per bucket; target_id = bucket name. Control S3.4 → s3_bucket_encryption (control_scope 9.8).
# Terraform: aws_s3_bucket_server_side_encryption_configuration (AES256, bucket_key_enabled).
# CloudFormation: AWS::S3::Bucket with BucketEncryption / ServerSideEncryptionConfiguration.
# ---------------------------------------------------------------------------


def _generate_for_s3_bucket_encryption(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for s3_bucket_encryption (per bucket, S3.4). Step 9.10."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="s3_bucket_encryption.yaml",
                content=_cloudformation_s3_bucket_encryption_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Set Parameter BucketName to the target bucket.",
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_encryption.tf",
                content=_terraform_s3_bucket_encryption_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            f"Set bucket name in the Terraform file (target: {bucket_name}).",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable default encryption (AES256).",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_bucket_encryption_content(meta: dict[str, str]) -> str:
    """Terraform for S3 bucket default encryption (S3.4). Step 9.10: AES256, bucket_key_enabled."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket encryption - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {{
  bucket = "{bucket}"

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
    bucket_key_enabled = true
  }}
}}
"""


def _cloudformation_s3_bucket_encryption_content(meta: dict[str, str]) -> str:
    """CloudFormation for S3 bucket encryption (S3.4). Step 9.5 (all seven), 9.10."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket encryption - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "S3 bucket default encryption - Security Autopilot."
Parameters:
  BucketName:
    Type: String
    Default: "{bucket}"
    Description: S3 bucket name to enable encryption
Resources:
  BucketEncryption:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BucketName
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
            BucketKeyEnabled: true
"""


# ---------------------------------------------------------------------------
# S3 bucket access logging (S3.9)
# ---------------------------------------------------------------------------


def _resolve_s3_access_logging_log_bucket(
    *,
    source_bucket: str,
    strategy_inputs: dict[str, Any] | None,
    action_type: str,
    format: str,
    strategy_id: str | None,
    variant: str | None,
) -> str:
    """Resolve S3.9 log destination bucket, failing when source and destination are identical."""
    log_bucket = str((strategy_inputs or {}).get("log_bucket_name", "")).strip()
    if not log_bucket:
        return "REPLACE_LOG_BUCKET_NAME"
    if log_bucket == source_bucket:
        _raise_pr_bundle_error(
            code="log_bucket_matches_source_bucket",
            detail=(
                "Log destination must be a dedicated bucket. "
                "Do not use the source bucket as the log destination."
            ),
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
            variant=variant,
        )
    if not _S3_BUCKET_NAME_PATTERN.fullmatch(log_bucket):
        _raise_pr_bundle_error(
            code="invalid_log_bucket_name",
            detail=(
                "Provided log bucket name is invalid for S3 server access logging. "
                "Set strategy_inputs.log_bucket_name to a valid dedicated S3 bucket name."
            ),
            action_type=action_type,
            format=format,
            strategy_id=strategy_id,
            variant=variant,
        )
    return log_bucket


def _resolve_s3_access_logging_defaults(
    *,
    source_bucket: str,
    strategy_inputs: dict[str, Any] | None,
    action_type: str,
    format: str,
    strategy_id: str | None,
    variant: str | None,
) -> tuple[str, bool, bool]:
    log_bucket = _resolve_s3_access_logging_log_bucket(
        source_bucket=source_bucket,
        strategy_inputs=strategy_inputs,
        action_type=action_type,
        format=format,
        strategy_id=strategy_id,
        variant=variant,
    )
    create_log_bucket = _coerce_bool((strategy_inputs or {}).get("create_log_bucket"), default=False)
    create_bucket_if_missing = _create_bucket_if_missing_enabled(strategy_inputs)
    return log_bucket, create_log_bucket, create_bucket_if_missing


def _generate_for_s3_bucket_access_logging(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    strategy_inputs: dict[str, Any] | None = None,
    strategy_id: str | None = None,
    variant: str | None = None,
) -> PRBundleResult:
    """Generate IaC for S3 bucket access logging (S3.9)."""
    meta = _action_meta(action)
    region = meta["region"]
    source_bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    log_bucket_name, create_log_bucket, create_bucket_if_missing = _resolve_s3_access_logging_defaults(
        source_bucket=source_bucket_name,
        strategy_inputs=strategy_inputs,
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        format=format,
        strategy_id=strategy_id,
        variant=variant,
    )
    if format == CLOUDFORMATION_FORMAT:
        if create_bucket_if_missing:
            _raise_pr_bundle_error(
                code="unsupported_variant_format",
                detail=(
                    "Create-missing-bucket S3.9 bundles are only supported for terraform format."
                ),
                action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
                format=format,
                strategy_id=strategy_id,
                variant=variant,
            )
        files = [
            PRBundleFile(
                path="s3_bucket_access_logging.yaml",
                content=_cloudformation_s3_bucket_access_logging_content(
                    meta,
                    log_bucket_name=log_bucket_name,
                    create_log_bucket=create_log_bucket,
                ),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Set Parameter BucketName (source) and LogBucketName (dedicated destination).",
            (
                "When CreateLogBucket=true, the template creates the destination bucket with the shared support-bucket baseline."
                if create_log_bucket
                else "When CreateLogBucket=false, the destination bucket must already exist and already meet the shared support-bucket baseline."
            ),
            "Do not use the source bucket as the log destination.",
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_access_logging.tf",
                content=_terraform_s3_bucket_access_logging_content(
                    meta,
                    log_bucket_name=log_bucket_name,
                    create_log_bucket=create_log_bucket,
                    create_bucket_if_missing=create_bucket_if_missing,
                ),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "Set log_bucket_name to a dedicated destination bucket.",
            (
                "This bundle will create the missing source bucket with a minimal private baseline before enabling access logging."
                if create_bucket_if_missing
                else "This bundle assumes the source bucket already exists."
            ),
            (
                "This bundle will create the destination bucket with the shared support-bucket baseline before enabling access logging."
                if create_log_bucket
                else "This bundle assumes the destination bucket already exists and already meets the shared support-bucket baseline."
            ),
            (
                "If the destination bucket already exists and is already owned, set create_log_bucket=false and adopt_existing_log_bucket=true to reuse it while still applying the shared support-bucket baseline."
                if create_log_bucket
                else "If you need to harden an already-owned destination bucket in place, set adopt_existing_log_bucket=true."
            ),
            "Do not use the source bucket as the log destination.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable S3 server access logging.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    result = PRBundleResult(format=format, files=files, steps=steps)
    if format == TERRAFORM_FORMAT:
        result["metadata"] = _merge_bundle_metadata(
            result.get("metadata"),
            {
                "helper_bucket_inventory": [
                    _helper_bucket_inventory_entry(
                        bucket_name=log_bucket_name,
                        helper_bucket_role=SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS,
                        created=create_log_bucket,
                    )
                ]
            },
        )
    return result


def _terraform_s3_bucket_access_logging_content(
    meta: dict[str, str],
    *,
    log_bucket_name: str,
    create_log_bucket: bool,
    create_bucket_if_missing: bool,
) -> str:
    """Terraform for S3 bucket server access logging (S3.9)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    create_log_bucket_text = "true" if create_log_bucket else "false"
    create_bucket_if_missing_text = "true" if create_bucket_if_missing else "false"
    create_bucket_blocks = _terraform_minimal_private_bucket_blocks(
        resource_suffix="source_bucket",
        bucket_name_ref='var.source_bucket_name',
        count_expr="var.create_bucket_if_missing ? 1 : 0",
    )
    support_bucket_blocks = terraform_support_bucket_blocks(
        resource_suffix="access_logs",
        bucket_id_ref="local.log_bucket_id",
        bucket_name_ref='var.log_bucket_name',
        count_expr="local.manage_log_bucket_baseline ? 1 : 0",
        support_bucket_role=SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS,
    )
    return f"""# S3 bucket access logging - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

variable "source_bucket_name" {{
  type        = string
  description = "S3 source bucket where server access logging is enabled"
  default     = "{bucket}"
}}

variable "log_bucket_name" {{
  type        = string
  description = "S3 bucket that will receive access logs"
  default     = "{log_bucket_name}"
}}

variable "create_bucket_if_missing" {{
  type        = bool
  description = "When true, create the source bucket with a minimal private baseline before enabling access logging."
  default     = {create_bucket_if_missing_text}
}}

variable "create_log_bucket" {{
  type        = bool
  description = "When true, create the destination bucket with the shared support-bucket baseline."
  default     = {create_log_bucket_text}
}}

variable "adopt_existing_log_bucket" {{
  type        = bool
  description = "When true, reuse an already-owned destination bucket and apply the shared support-bucket baseline without creating the bucket."
  default     = false
}}

variable "log_prefix" {{
  type        = string
  description = "Prefix for delivered access logs"
  default     = "s3-access-logs/"
}}

locals {{
  source_bucket_name          = var.create_bucket_if_missing ? aws_s3_bucket.source_bucket[0].bucket : var.source_bucket_name
  manage_log_bucket_baseline = var.create_log_bucket || var.adopt_existing_log_bucket
  log_bucket_id              = var.create_log_bucket ? aws_s3_bucket.access_logs[0].id : var.log_bucket_name
}}

{create_bucket_blocks}

resource "aws_s3_bucket" "access_logs" {{
  count  = var.create_log_bucket ? 1 : 0
  bucket = var.log_bucket_name
}}

{support_bucket_blocks}

resource "aws_s3_bucket_logging" "security_autopilot" {{
  bucket        = local.source_bucket_name
  target_bucket = var.log_bucket_name
  target_prefix = var.log_prefix
  depends_on    = [
    aws_s3_bucket_policy.access_logs,
    {_terraform_minimal_private_bucket_dependency("source_bucket")},
  ]
}}
"""


def _cloudformation_s3_bucket_access_logging_content(
    meta: dict[str, str],
    *,
    log_bucket_name: str,
    create_log_bucket: bool,
) -> str:
    """CloudFormation for S3 bucket server access logging (S3.9)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    create_log_bucket_text = "true" if create_log_bucket else "false"
    log_bucket_resources = """Resources:"""
    if create_log_bucket:
        log_bucket_resources = """
Conditions:
  ShouldCreateLogBucket: !Equals [!Ref CreateLogBucket, "true"]
Resources:
  AccessLogBucket:
    Condition: ShouldCreateLogBucket
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref LogBucketName
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: alias/aws/s3
            BucketKeyEnabled: true
      LifecycleConfiguration:
        Rules:
          - Id: abort-incomplete-multipart
            Status: Enabled
            AbortIncompleteMultipartUpload:
              DaysAfterInitiation: 7
  AccessLogBucketPolicy:
    Condition: ShouldCreateLogBucket
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref AccessLogBucket
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Sid: DenyInsecureTransport
            Effect: Deny
            Principal: "*"
            Action: s3:*
            Resource:
              - !Sub arn:aws:s3:::${LogBucketName}
              - !Sub arn:aws:s3:::${LogBucketName}/*
            Condition:
              Bool:
                aws:SecureTransport: "false"
"""
    return f"""# S3 bucket access logging - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "Enable S3 server access logging for a bucket."
Parameters:
  BucketName:
    Type: String
    Default: "{bucket}"
    Description: Source bucket to enable logging on
  LogBucketName:
    Type: String
    Default: "{log_bucket_name}"
    Description: Destination bucket receiving access logs
  CreateLogBucket:
    Type: String
    Default: "{create_log_bucket_text}"
    AllowedValues:
      - "true"
      - "false"
    Description: When true, create the destination log bucket with the shared support-bucket baseline
  LogPrefix:
    Type: String
    Default: s3-access-logs/
    Description: Prefix for delivered access logs
{log_bucket_resources}
  BucketLogging:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BucketName
      LoggingConfiguration:
        DestinationBucketName: !Ref LogBucketName
        LogFilePrefix: !Ref LogPrefix
"""


# ---------------------------------------------------------------------------
# S3 bucket lifecycle configuration (S3.11)
# ---------------------------------------------------------------------------


def _generate_for_s3_bucket_lifecycle_configuration(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    strategy_inputs: dict[str, Any] | None = None,
    risk_snapshot: dict[str, Any] | None = None,
    resolution: Mapping[str, Any] | None = None,
) -> PRBundleResult:
    """Generate IaC for S3 bucket lifecycle configuration (S3.11)."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_action_context(action, meta["target_id"])
    abort_days = _resolve_s3_lifecycle_abort_days(strategy_inputs)
    lifecycle_analysis = _s3_lifecycle_analysis_from_risk_snapshot(
        risk_snapshot,
        abort_days=abort_days,
    )
    create_bucket_if_missing = _create_bucket_if_missing_enabled(strategy_inputs)
    apply_time_merge = _s3_11_apply_time_merge_requested(resolution)
    if format == CLOUDFORMATION_FORMAT:
        if create_bucket_if_missing:
            _raise_pr_bundle_error(
                code="unsupported_variant_format",
                detail=(
                    "Create-missing-bucket S3.11 bundles are only supported for terraform format."
                ),
                action_type=action.action_type,
                format=format,
                strategy_id="s3_enable_abort_incomplete_uploads",
            )
        if apply_time_merge:
            _raise_pr_bundle_error(
                code="cloudformation_lifecycle_additive_merge_unsupported",
                detail=(
                    "CloudFormation additive lifecycle merge is out of scope for S3.11. "
                    "Generate the Terraform bundle for apply-time lifecycle merge when runtime capture fails."
                ),
                action_type=action.action_type,
                format=format,
                strategy_id="s3_enable_abort_incomplete_uploads",
            )
        _ensure_cloudformation_lifecycle_supported(
            lifecycle_analysis,
            action_type=action.action_type,
            format=format,
        )
        files = [
            PRBundleFile(
                path="s3_bucket_lifecycle_configuration.yaml",
                content=_cloudformation_s3_bucket_lifecycle_configuration_content(
                    meta,
                    abort_days=abort_days,
                ),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            (
                "Set Parameter BucketName and optionally adjust AbortIncompleteMultipartDays "
                f"(default: {abort_days})."
            ),
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        if apply_time_merge and not create_bucket_if_missing:
            files = [
                PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
                PRBundleFile(
                    path="s3_bucket_lifecycle_configuration.tf",
                    content=_terraform_s3_bucket_lifecycle_configuration_apply_time_content(
                        meta,
                        bucket_name=bucket_name,
                        abort_days=abort_days,
                    ),
                ),
                PRBundleFile(
                    path=AWS_S3_LIFECYCLE_APPLY_SCRIPT_PATH,
                    content=aws_s3_lifecycle_merge_script_content(
                        bucket_name=bucket_name,
                        region=region,
                        abort_days=abort_days,
                    ),
                ),
                PRBundleFile(
                    path=AWS_S3_LIFECYCLE_RESTORE_SCRIPT_PATH,
                    content=aws_s3_lifecycle_restore_script_content(),
                ),
            ]
            steps = [
                f"Configure AWS provider for account {meta['account_id']} and region {region}.",
                (
                    f"The bundle targets bucket {bucket_name} and will fetch the current lifecycle configuration "
                    f"at apply time before enforcing abort-days={abort_days}."
                ),
                "Run `terraform init` and `terraform plan`.",
                "Run `terraform apply`; the helper snapshots exact pre-state to `.s3-lifecycle-rollback/lifecycle_snapshot.json` before merging the managed abort rule.",
                f"Rollback: run `python3 {AWS_S3_LIFECYCLE_RESTORE_SCRIPT_PATH}` to restore the captured lifecycle configuration exactly.",
                "Return to the action and click **Recompute actions** or trigger ingest to verify.",
            ]
            result = PRBundleResult(format=format, files=files, steps=steps)
            result["metadata"] = aws_s3_lifecycle_bundle_rollback_metadata(str(action.id))
            return result

        _ensure_terraform_lifecycle_renderable(
            lifecycle_analysis,
            action_type=action.action_type,
            format=format,
        )
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_lifecycle_configuration.tf",
                content=_terraform_s3_bucket_lifecycle_configuration_content(
                    meta,
                    abort_days=abort_days,
                    existing_rules=lifecycle_analysis["preserved_rules"],
                    bucket_name=bucket_name,
                    create_bucket_if_missing=create_bucket_if_missing,
                ),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            (
                f"Set bucket name (target: {bucket_name}) and lifecycle day threshold "
                f"(default: {abort_days}) if needed."
            ),
            (
                "This bundle will create the missing target bucket with a minimal private baseline before applying the lifecycle rule."
                if create_bucket_if_missing
                else "This bundle assumes the target bucket already exists."
            ),
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to configure lifecycle policy.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_bucket_lifecycle_configuration_content(
    meta: dict[str, str],
    *,
    abort_days: int,
    existing_rules: list[dict[str, Any]] | None = None,
    bucket_name: str | None = None,
    create_bucket_if_missing: bool = False,
) -> str:
    """Terraform for S3 bucket lifecycle configuration (S3.11)."""
    bucket = bucket_name or _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    rendered_existing_rules = lifecycle_rules_to_terraform(existing_rules or [])
    managed_rule = _managed_abort_rule_block()
    rule_blocks = "\n\n".join(block for block in (rendered_existing_rules, managed_rule) if block)
    create_bucket_if_missing_text = "true" if create_bucket_if_missing else "false"
    create_bucket_blocks = _terraform_minimal_private_bucket_blocks(
        resource_suffix="target_bucket",
        bucket_name_ref='local.target_bucket_name',
        count_expr="var.create_bucket_if_missing ? 1 : 0",
    )
    return f"""# S3 bucket lifecycle configuration - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

locals {{
  target_bucket_name = "{bucket}"
}}

variable "create_bucket_if_missing" {{
  type        = bool
  description = "When true, create the target bucket with a minimal private baseline before applying the lifecycle rule."
  default     = {create_bucket_if_missing_text}
}}

variable "abort_incomplete_multipart_days" {{
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = {abort_days}
}}

{create_bucket_blocks}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {{
  bucket = local.target_bucket_name
  depends_on = [{_terraform_minimal_private_bucket_dependency("target_bucket")}]

{rule_blocks}
}}
"""


def _terraform_s3_bucket_lifecycle_configuration_apply_time_content(
    meta: dict[str, str],
    *,
    bucket_name: str,
    abort_days: int,
) -> str:
    """Terraform for S3.11 apply-time lifecycle merge fallback."""
    return f"""# S3 bucket lifecycle configuration - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket_name}
# Control: {meta["control_id"]}

locals {{
  target_bucket_name = "{bucket_name}"
}}

variable "remediation_region" {{
  type        = string
  description = "Region for lifecycle remediation."
  default     = "{meta["region"]}"
}}

variable "abort_incomplete_multipart_days" {{
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = {abort_days}
}}

resource "terraform_data" "security_autopilot" {{
  triggers_replace = {{
    bucket_name                    = local.target_bucket_name
    remediation_region             = var.remediation_region
    abort_incomplete_multipart_days = tostring(var.abort_incomplete_multipart_days)
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
export BUCKET_NAME="${{local.target_bucket_name}}"
export REGION="${{var.remediation_region}}"
export ABORT_INCOMPLETE_MULTIPART_DAYS="${{var.abort_incomplete_multipart_days}}"

python3 ./{AWS_S3_LIFECYCLE_APPLY_SCRIPT_PATH}
EOT
  }}
}}
"""


def _managed_abort_rule_block() -> str:
    return """  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }"""


def _s3_lifecycle_analysis_from_risk_snapshot(
    risk_snapshot: dict[str, Any] | None,
    *,
    abort_days: int,
) -> dict[str, Any]:
    evidence = _strategy_risk_evidence(risk_snapshot)
    lifecycle_json = evidence.get("existing_lifecycle_configuration_json")
    if not isinstance(lifecycle_json, str):
        lifecycle_json = None
    return analyze_lifecycle_preservation(lifecycle_json, abort_days=abort_days)


def _ensure_cloudformation_lifecycle_supported(
    lifecycle_analysis: Mapping[str, Any],
    *,
    action_type: str,
    format: str,
) -> None:
    if lifecycle_analysis.get("rule_count") in (None, 0):
        return
    if lifecycle_analysis.get("equivalent_safe_state") is True:
        return
    _raise_pr_bundle_error(
        code="cloudformation_lifecycle_additive_merge_unsupported",
        detail=(
            "CloudFormation additive lifecycle merge is out of scope for S3.11. "
            "Generate the Terraform bundle for captured lifecycle-preservation cases instead."
        ),
        action_type=action_type,
        format=format,
        strategy_id="s3_enable_abort_incomplete_uploads",
    )


def _ensure_terraform_lifecycle_renderable(
    lifecycle_analysis: Mapping[str, Any],
    *,
    action_type: str,
    format: str,
) -> None:
    if lifecycle_analysis.get("merge_renderable") is True:
        return
    if lifecycle_analysis.get("rule_count") in (None, 0):
        return
    if lifecycle_analysis.get("equivalent_safe_state") is True:
        return
    _raise_pr_bundle_error(
        code="lifecycle_additive_merge_unsupported",
        detail=str(
            lifecycle_analysis.get("render_failure_reason")
            or "Captured lifecycle configuration cannot be rendered safely for additive merge."
        ),
        action_type=action_type,
        format=format,
        strategy_id="s3_enable_abort_incomplete_uploads",
    )


def _cloudformation_s3_bucket_lifecycle_configuration_content(
    meta: dict[str, str],
    *,
    abort_days: int,
) -> str:
    """CloudFormation for S3 bucket lifecycle configuration (S3.11)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket lifecycle configuration - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}
# IMPORTANT: applies lifecycle rule via Lambda custom resource (PutLifecycleConfiguration).
# Delete path is no-op and does NOT remove existing lifecycle rules.

AWSTemplateFormatVersion: "2010-09-09"
Description: "Configure S3 lifecycle policy for a bucket via Lambda custom resource."
Metadata:
  SecurityAutopilot:
    ActionId: "{meta["action_id"]}"
    ControlId: "{meta["control_id"]}"
    RemediationAPI: "s3:PutLifecycleConfiguration"
Parameters:
  BucketName:
    Type: String
    Default: "{bucket}"
    Description: Target bucket for lifecycle configuration
  AbortIncompleteMultipartDays:
    Type: Number
    Default: {abort_days}
    Description: Days before aborting incomplete multipart uploads
Resources:
  S3BucketLifecycleRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: s3-bucket-lifecycle-configuration
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - s3:PutLifecycleConfiguration
                Resource: "*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  S3BucketLifecycleFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt S3BucketLifecycleRole.Arn
      Code:
        ZipFile: |
          import boto3
          import cfnresponse

          def _to_positive_int(value):
              number = int(value)
              if number < 1:
                  raise ValueError("AbortIncompleteMultipartDays must be >= 1.")
              return number

          def handler(event, context):
              request_type = event.get("RequestType")
              try:
                  if request_type == "Delete":
                      cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "S3BucketLifecycle")
                      return
                  props = event.get("ResourceProperties", {{}})
                  bucket_name = (props.get("BucketName") or "").strip()
                  if not bucket_name:
                      raise ValueError("BucketName is required.")
                  abort_days = _to_positive_int(props.get("AbortIncompleteMultipartDays", 7))
                  s3 = boto3.client("s3")
                  s3.put_bucket_lifecycle_configuration(
                      Bucket=bucket_name,
                      LifecycleConfiguration={{
                          "Rules": [
                              {{
                                  "ID": "security-autopilot-abort-incomplete-multipart",
                                  "Status": "Enabled",
                                  "Filter": {{}},
                                  "AbortIncompleteMultipartUpload": {{
                                      "DaysAfterInitiation": abort_days
                                  }},
                              }}
                          ]
                      }},
                  )
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "S3BucketLifecycle")
              except Exception as exc:
                  cfnresponse.send(
                      event,
                      context,
                      cfnresponse.FAILED,
                      {{"Error": str(exc)}},
                      "S3BucketLifecycle",
                  )
  S3BucketLifecycleConfiguration:
    Type: Custom::S3BucketLifecycleConfiguration
    Properties:
      ServiceToken: !GetAtt S3BucketLifecycleFunction.Arn
      BucketName: !Ref BucketName
      AbortIncompleteMultipartDays: !Ref AbortIncompleteMultipartDays
"""


# ---------------------------------------------------------------------------
# S3 bucket SSE-KMS encryption (S3.15)
# ---------------------------------------------------------------------------


def _generate_for_s3_bucket_encryption_kms(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    strategy_inputs: dict[str, Any] | None = None,
) -> PRBundleResult:
    """Generate IaC for S3 bucket SSE-KMS encryption (S3.15)."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    create_bucket_if_missing = _create_bucket_if_missing_enabled(strategy_inputs)
    kms_key_arn, kms_key_mode = _resolve_s3_kms_defaults(
        meta=meta,
        strategy_inputs=strategy_inputs,
        format=format,
    )
    if format == CLOUDFORMATION_FORMAT:
        if create_bucket_if_missing:
            _raise_pr_bundle_error(
                code="unsupported_variant_format",
                detail=(
                    "Create-missing-bucket S3.15 bundles are only supported for terraform format."
                ),
                action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
                format=format,
                strategy_id="s3_enable_sse_kms_guided",
            )
        files = [
            PRBundleFile(
                path="s3_bucket_encryption_kms.yaml",
                content=_cloudformation_s3_bucket_encryption_kms_content(
                    meta,
                    kms_key_arn=kms_key_arn,
                ),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            (
                "Set Parameter BucketName and KmsKeyArn to the target bucket and approved KMS key "
                f"(mode: {kms_key_mode})."
            ),
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_encryption_kms.tf",
                content=_terraform_s3_bucket_encryption_kms_content(
                    meta,
                    kms_key_arn=kms_key_arn,
                    create_bucket_if_missing=create_bucket_if_missing,
                ),
            ),
        ]
        if not create_bucket_if_missing:
            files.extend(
                [
                    PRBundleFile(
                        path=AWS_S3_ENCRYPTION_CAPTURE_SCRIPT_PATH,
                        content=aws_s3_encryption_capture_script_content(
                            bucket_name=bucket_name,
                            region=region,
                        ),
                    ),
                    PRBundleFile(
                        path=AWS_S3_ENCRYPTION_RESTORE_SCRIPT_PATH,
                        content=aws_s3_encryption_restore_script_content(),
                    ),
                ]
            )
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            f"Bucket defaults to target ({bucket_name}); generated key mode is {kms_key_mode}.",
            (
                "This bundle will create the missing target bucket with a minimal private baseline before enforcing SSE-KMS."
                if create_bucket_if_missing
                else "This bundle assumes the target bucket already exists."
            ),
            *(
                [
                    f"Run `BUCKET_NAME={bucket_name} REGION={region} python3 {AWS_S3_ENCRYPTION_CAPTURE_SCRIPT_PATH}` BEFORE terraform apply to snapshot exact bucket encryption pre-state to .s3-encryption-rollback/encryption_snapshot.json.",
                ]
                if not create_bucket_if_missing
                else []
            ),
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enforce SSE-KMS default encryption.",
            *(
                [
                    f"Rollback: run `terraform destroy` then `python3 {AWS_S3_ENCRYPTION_RESTORE_SCRIPT_PATH}` to restore the captured bucket encryption exactly.",
                ]
                if not create_bucket_if_missing
                else []
            ),
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    result = PRBundleResult(format=format, files=files, steps=steps)
    if format == TERRAFORM_FORMAT and not create_bucket_if_missing:
        result["metadata"] = aws_s3_encryption_bundle_rollback_metadata(str(action.id))
    return result


def _terraform_s3_bucket_encryption_kms_content(
    meta: dict[str, str],
    *,
    kms_key_arn: str,
    create_bucket_if_missing: bool = False,
) -> str:
    """Terraform for S3 bucket SSE-KMS encryption (S3.15)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    create_bucket_if_missing_text = "true" if create_bucket_if_missing else "false"
    create_bucket_blocks = _terraform_minimal_private_bucket_blocks(
        resource_suffix="target_bucket",
        bucket_name_ref='local.target_bucket_name',
        count_expr="var.create_bucket_if_missing ? 1 : 0",
        include_encryption=False,
    )
    return f"""# S3 bucket SSE-KMS encryption - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

locals {{
  target_bucket_name = "{bucket}"
}}

variable "create_bucket_if_missing" {{
  type        = bool
  description = "When true, create the target bucket with a minimal private baseline before enforcing SSE-KMS."
  default     = {create_bucket_if_missing_text}
}}

variable "kms_key_arn" {{
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "{kms_key_arn}"
}}

{create_bucket_blocks}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {{
  bucket = local.target_bucket_name
  depends_on = [{_terraform_minimal_private_bucket_dependency("target_bucket")}]

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }}
    bucket_key_enabled = true
  }}
}}
"""


def _cloudformation_s3_bucket_encryption_kms_content(
    meta: dict[str, str],
    *,
    kms_key_arn: str,
) -> str:
    """CloudFormation for S3 bucket SSE-KMS encryption (S3.15)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket SSE-KMS encryption - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "Enable SSE-KMS default encryption for a bucket."
Parameters:
  BucketName:
    Type: String
    Default: "{bucket}"
    Description: S3 bucket name to enable SSE-KMS encryption
  KmsKeyArn:
    Type: String
    Default: "{kms_key_arn}"
    Description: KMS key ARN used for default bucket encryption (override for customer-managed key)
Resources:
  BucketEncryption:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BucketName
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: !Ref KmsKeyArn
            BucketKeyEnabled: true
"""


# ---------------------------------------------------------------------------
# SG restrict public ports (22/3389) — Step 9.11 (action_type: sg_restrict_public_ports, control_id: EC2.53)
# ---------------------------------------------------------------------------
# Scope: per security group; target_id = SG ID. Canonical control EC2.53 → sg_restrict_public_ports (control_scope 9.8).
# Aliases: EC2.13 / EC2.19 / EC2.18 map to the same action_type and canonicalize to EC2.53.
# Restrict 0.0.0.0/0 and optional ::/0 on 22/3389 with optional allowlist (variables/parameters).
# Terraform bundle includes preflight revoke for conflicting 22/3389 CIDR rules; CloudFormation path remains operator-managed.
# Terraform: aws_vpc_security_group_ingress_rule with parameterized CIDR. CloudFormation: AWS::EC2::SecurityGroupIngress.
# ---------------------------------------------------------------------------


def _generate_for_sg_restrict_public_ports(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_inputs: dict[str, Any] | None = None,
) -> PRBundleResult:
    """Generate IaC for sg_restrict_public_ports (per security group, EC2.53). Step 9.11."""
    meta = _action_meta(action)
    sg_id = _security_group_id_from_action_context(action, meta["target_id"])
    access_mode = _resolve_sg_access_mode(strategy_inputs)
    if access_mode == "ssm_only":
        if not sg_id:
            _raise_pr_bundle_error(
                code="missing_security_group_id",
                detail=(
                    "Unable to infer a security group ID from action target/resource metadata. "
                    "Refresh findings and recompute actions, then retry PR bundle generation."
                ),
                action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
                format=format,
            )
        return _generate_for_sg_ssm_only(action, format, meta=meta, sg_id=sg_id)
    if access_mode == "bastion_sg_reference":
        if not sg_id:
            _raise_pr_bundle_error(
                code="missing_security_group_id",
                detail=(
                    "Unable to infer a security group ID from action target/resource metadata. "
                    "Refresh findings and recompute actions, then retry PR bundle generation."
                ),
                action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
                format=format,
            )
        return _generate_for_sg_bastion_reference(
            action,
            format,
            meta=meta,
            sg_id=sg_id,
            bastion_sg_ids=_resolve_bastion_security_group_ids(strategy_inputs),
        )

    region = meta["region"]
    allowed_cidr, allowed_cidr_ipv6, remove_existing_public_rules = _resolve_sg_restrict_defaults(
        strategy_inputs
    )
    if not sg_id:
        _raise_pr_bundle_error(
            code="missing_security_group_id",
            detail=(
                "Unable to infer a security group ID from action target/resource metadata. "
                "Refresh findings and recompute actions, then retry PR bundle generation."
            ),
            action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
            format=format,
        )
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="sg_restrict_public_ports.yaml",
                content=_cloudformation_sg_restrict_content(
                    meta,
                    sg_id,
                    allowed_cidr=allowed_cidr,
                    allowed_cidr_ipv6=allowed_cidr_ipv6,
                ),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "What changes: custom resource revokes 0.0.0.0/0 and ::/0 SSH/RDP ingress (22/3389) before restricted rules are added.",
            "How to access now: use SSM Session Manager for operator access `aws ssm start-session --target <instance-id> --region <region>`.",
            "Keep bastion/VPN fallback ready for instances not managed by SSM.",
            "IMPORTANT: review revoke-before-add behavior before applying.",
            "Set Parameters SecurityGroupId and AllowedCidr (e.g. 10.0.0.0/8). Optionally set AllowedCidrIpv6 (e.g. fd00::/8).",
            "Validate the template and create/update the stack.",
            "Verify: run `aws ec2 describe-security-group-rules --region <region> --filters Name=group-id,Values=<security-group-id> Name=is-egress,Values=false --query \"SecurityGroupRules[?((FromPort==`22`||FromPort==`3389`) && (CidrIpv4=='0.0.0.0/0' || CidrIpv6=='::/0'))]\" --output json` and confirm empty result.",
            "Rollback: re-authorize only temporary scoped admin ingress, for example `aws ec2 authorize-security-group-ingress --region <region> --group-id <security-group-id> --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=<admin-cidr>}]'`.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        terraform_files: list[PRBundleFile] = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="sg_restrict_public_ports.tf",
                content=_terraform_sg_restrict_content(
                    meta,
                    sg_id,
                    allowed_cidr=allowed_cidr,
                    allowed_cidr_ipv6=allowed_cidr_ipv6,
                    remove_existing_public_rules=remove_existing_public_rules,
                ),
            ),
        ]
        rollback_metadata: dict | None = None
        if remove_existing_public_rules:
            terraform_files += [
                PRBundleFile(
                    path=AWS_SG_APPLY_SCRIPT_PATH,
                    content=aws_sg_capture_script_content(),
                ),
                PRBundleFile(
                    path=AWS_SG_ROLLBACK_SCRIPT_PATH,
                    content=aws_sg_restore_script_content(),
                ),
            ]
            rollback_metadata = aws_sg_bundle_rollback_metadata(str(action.id))
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "Identify what is attached to this security group (EC2, ENIs, ALB/NLB, RDS, ECS/EKS) and treat production resources with extra caution.",
            "Review inbound rules and confirm which high-risk ports are open to 0.0.0.0/0 and/or ::/0. Public SSH/RDP and database ports are usually unnecessary.",
            "Confirm alternative admin access first (SSM Session Manager, bastion, or VPN). Optionally review VPC Flow Logs to confirm active source IPs.",
            "IMPORTANT: review remove_existing_public_rules before applying.",
            "Do not delete broad rules blindly. Narrow sources incrementally to VPN CIDR, office IP, or source security group.",
            f"Set security_group_id and allowed_cidr in the Terraform file (target SG: {sg_id}).",
            "Optionally set allowed_cidr_ipv6 (e.g. fd00::/8) to add IPv6-restricted ingress.",
            "By default, remove_existing_public_rules = false (no automatic revoke). Set remove_existing_public_rules = true only after validating alternative access paths.",
            *([
                f"When remove_existing_public_rules = true, run `SECURITY_GROUP_ID={sg_id} REGION={region} python3 {AWS_SG_APPLY_SCRIPT_PATH}` BEFORE terraform apply to snapshot exact public ingress pre-state to .sg-rollback/sg_ingress_snapshot.json.",
            ] if remove_existing_public_rules else [
                "When remove_existing_public_rules = true, bundle preflight revokes conflicting public/duplicate 22/3389 CIDR rules before creating restricted rules.",
            ]),
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to add restricted SSH/RDP ingress. Keep public 80/443 only where explicitly required.",
            "Test connectivity after each change and tighten in small steps.",
            *([
                f"Rollback: run `terraform destroy` then `python3 {AWS_SG_ROLLBACK_SCRIPT_PATH}` to restore the captured public ingress rules exactly, including descriptions.",
            ] if remove_existing_public_rules else []),
            "Avoid blind auto-remediation in production. If automation is enabled, prefer restrict-over-remove and use dev/test first.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
        result = PRBundleResult(format=format, files=terraform_files, steps=steps)
        if rollback_metadata:
            result["metadata"] = rollback_metadata
        return result
    return PRBundleResult(format=format, files=files, steps=steps)


def _generate_for_sg_ssm_only(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    meta: dict[str, str],
    sg_id: str,
) -> PRBundleResult:
    """Generate EC2.53 bundles that remove public SSH/RDP and rely on pre-existing SSM access."""
    region = meta["region"]
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="sg_restrict_public_ports.yaml",
                content=_cloudformation_sg_ssm_only_content(meta, sg_id),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Confirm SSM Session Manager access is already working for every workload attached to this security group before applying this bundle.",
            "What changes: custom resource revokes 0.0.0.0/0 and ::/0 SSH/RDP ingress (22/3389) and does not add replacement admin ingress rules.",
            "Keep bastion/VPN fallback ready for workloads that are not SSM-managed.",
            "IMPORTANT: review the revoke-only behavior before applying.",
            "Set Parameter SecurityGroupId if you need to override the detected target.",
            "Validate the template and create/update the stack.",
            "Verify: run `aws ec2 describe-security-group-rules --region <region> --filters Name=group-id,Values=<security-group-id> Name=is-egress,Values=false --query \"SecurityGroupRules[?((FromPort==`22`||FromPort==`3389`) && (CidrIpv4=='0.0.0.0/0' || CidrIpv6=='::/0'))]\" --output json` and confirm empty result.",
            "Rollback: delete the stack state if desired, then re-authorize only temporary scoped admin ingress manually after confirming the exact required source CIDRs.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
        return PRBundleResult(format=format, files=files, steps=steps)

    terraform_files: list[PRBundleFile] = [
        PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
        PRBundleFile(
            path="sg_restrict_public_ports.tf",
            content=_terraform_sg_ssm_only_content(meta, sg_id),
        ),
        PRBundleFile(
            path=AWS_SG_APPLY_SCRIPT_PATH,
            content=aws_sg_capture_script_content(),
        ),
        PRBundleFile(
            path=AWS_SG_ROLLBACK_SCRIPT_PATH,
            content=aws_sg_restore_script_content(),
        ),
    ]
    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {region}.",
        "Identify what is attached to this security group (EC2, ENIs, ALB/NLB, RDS, ECS/EKS) and treat production resources with extra caution.",
        "Confirm SSM Session Manager access is already working for every workload attached to this security group before applying this bundle.",
        "IMPORTANT: this bundle removes public SSH/RDP ingress and does not add replacement admin ingress rules.",
        f"Run `SECURITY_GROUP_ID={sg_id} REGION={region} python3 {AWS_SG_APPLY_SCRIPT_PATH}` BEFORE terraform apply to snapshot exact public ingress pre-state to .sg-rollback/sg_ingress_snapshot.json.",
        "Run `terraform init` and `terraform plan`.",
        "Run `terraform apply` to revoke public SSH/RDP ingress on ports 22 and 3389.",
        "Verify SSM Session Manager access still works and confirm no 0.0.0.0/0 or ::/0 remains for ports 22/3389.",
        f"Rollback: run `terraform destroy` then `python3 {AWS_SG_ROLLBACK_SCRIPT_PATH}` to restore the captured public ingress rules exactly, including descriptions.",
        "Return to the action and click **Recompute actions** or trigger ingest to verify.",
    ]
    result = PRBundleResult(format=format, files=terraform_files, steps=steps)
    result["metadata"] = aws_sg_bundle_rollback_metadata(str(action.id))
    return result


def _generate_for_sg_bastion_reference(
    action: ActionLike,
    format: PRBundleFormat,
    *,
    meta: dict[str, str],
    sg_id: str,
    bastion_sg_ids: list[str],
) -> PRBundleResult:
    """Generate EC2.53 bundles that replace public SSH/RDP with bastion SG references."""
    if not bastion_sg_ids:
        _raise_pr_bundle_error(
            code="missing_bastion_security_groups",
            detail=(
                "The 'bastion_sg_reference' branch requires approved_bastion_security_group_ids in the "
                "resolved strategy inputs. Configure tenant remediation settings, then retry bundle generation."
            ),
            action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
            format=format,
        )
    if format == CLOUDFORMATION_FORMAT:
        return _cloudformation_bastion_reference_bundle(meta, sg_id, bastion_sg_ids)
    return _terraform_bastion_reference_bundle(action, meta, sg_id, bastion_sg_ids)


def _terraform_bastion_reference_bundle(
    action: ActionLike,
    meta: dict[str, str],
    sg_id: str,
    bastion_sg_ids: list[str],
) -> PRBundleResult:
    files = [
        PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
        PRBundleFile(
            path="sg_restrict_public_ports.tf",
            content=_terraform_sg_bastion_reference_content(meta, sg_id, bastion_sg_ids),
        ),
        PRBundleFile(path=AWS_SG_APPLY_SCRIPT_PATH, content=aws_sg_capture_script_content()),
        PRBundleFile(path=AWS_SG_ROLLBACK_SCRIPT_PATH, content=aws_sg_restore_script_content()),
    ]
    region = meta["region"]
    bastions = ", ".join(bastion_sg_ids)
    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {region}.",
        "Identify what is attached to this security group (EC2, ENIs, ALB/NLB, RDS, ECS/EKS) and treat production resources with extra caution.",
        f"Confirm the approved bastion security groups are correct for this target before apply: {bastions}.",
        "IMPORTANT: this bundle removes public SSH/RDP ingress and replaces it with source-security-group access from the approved bastion SG list.",
        f"Run `SECURITY_GROUP_ID={sg_id} REGION={region} python3 {AWS_SG_APPLY_SCRIPT_PATH}` BEFORE terraform apply to snapshot exact public ingress pre-state to .sg-rollback/sg_ingress_snapshot.json.",
        "Run `terraform init` and `terraform plan`.",
        "Run `terraform apply` to revoke public SSH/RDP ingress on ports 22 and 3389 and add bastion-only replacement ingress.",
        "Verify no 0.0.0.0/0 or ::/0 remains for ports 22/3389 and confirm bastion-based operator access still works.",
        f"Rollback: run `terraform destroy` then `python3 {AWS_SG_ROLLBACK_SCRIPT_PATH}` to restore the captured public ingress rules exactly, including descriptions.",
        "Return to the action and click **Recompute actions** or trigger ingest to verify.",
    ]
    result = PRBundleResult(format=TERRAFORM_FORMAT, files=files, steps=steps)
    result["metadata"] = aws_sg_bundle_rollback_metadata(str(action.id))
    return result


def _cloudformation_bastion_reference_bundle(
    meta: dict[str, str],
    sg_id: str,
    bastion_sg_ids: list[str],
) -> PRBundleResult:
    region = meta["region"]
    bastions = ", ".join(bastion_sg_ids)
    files = [
        PRBundleFile(
            path="sg_restrict_public_ports.yaml",
            content=_cloudformation_sg_bastion_reference_content(meta, sg_id, bastion_sg_ids),
        )
    ]
    steps = [
        f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
        f"Confirm the approved bastion security groups are correct for this target before apply: {bastions}.",
        "What changes: custom resource revokes 0.0.0.0/0 and ::/0 SSH/RDP ingress (22/3389) and replaces it with source-security-group access from the approved bastion SG list.",
        "IMPORTANT: review the revoke-and-replace behavior before applying.",
        "Set Parameter SecurityGroupId if you need to override the detected target.",
        "Validate the template and create/update the stack.",
        "Verify: run `aws ec2 describe-security-group-rules --region <region> --filters Name=group-id,Values=<security-group-id> Name=is-egress,Values=false --query \"SecurityGroupRules[?((FromPort==`22`||FromPort==`3389`) && (CidrIpv4=='0.0.0.0/0' || CidrIpv6=='::/0'))]\" --output json` and confirm empty result.",
        "Rollback: delete the stack state if desired, then restore the prior ingress model manually if bastion-based access is no longer desired.",
        "Return to the action and click **Recompute actions** or trigger ingest to verify.",
    ]
    return PRBundleResult(format=CLOUDFORMATION_FORMAT, files=files, steps=steps)


def _terraform_sg_restrict_content(
    meta: dict[str, str],
    sg_id: str,
    *,
    allowed_cidr: str,
    allowed_cidr_ipv6: str,
    remove_existing_public_rules: bool,
) -> str:
    """Terraform for SG restrict public ports 22/3389 (EC2.53). Step 9.11: aws_vpc_security_group_ingress_rule with variables."""
    remove_existing_default = "true" if remove_existing_public_rules else "false"
    return f"""# SG restrict public ports (22/3389) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}
# Safe rollout: identify SG attachments and active traffic first; tighten incrementally and test after each change.
# Prefer replacing broad sources (0.0.0.0/0 or ::/0) with VPN/office CIDR or source security-group rules.

variable "security_group_id" {{
  type        = string
  default     = "{sg_id}"
  description = "Security group ID to restrict"
}}

variable "allowed_cidr" {{
  type        = string
  default     = "{allowed_cidr}"
  description = "CIDR allowed for SSH/RDP (e.g. VPN or bastion)"
}}

variable "allowed_cidr_ipv6" {{
  type        = string
  default     = "{allowed_cidr_ipv6}"
  description = "Optional IPv6 CIDR allowed for SSH/RDP (e.g. fd00::/8). Leave empty to skip IPv6 ingress."
}}

variable "remove_existing_public_rules" {{
  type        = bool
  default     = {remove_existing_default}
  description = "When true, revoke existing public SSH/RDP ingress (0.0.0.0/0 and ::/0) before adding restricted rules."
}}

variable "remediation_region" {{
  type        = string
  default     = "{meta["region"]}"
  description = "Region used by local AWS CLI revoke commands."
}}

resource "null_resource" "revoke_public_admin_ingress" {{
  count = var.remove_existing_public_rules == true ? 1 : 0

  triggers = {{
    security_group_id = var.security_group_id
    region            = var.remediation_region
    allowed_cidr      = var.allowed_cidr
    allowed_cidr_ipv6 = var.allowed_cidr_ipv6
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set +e
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{{CidrIp=0.0.0.0/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{{CidrIp=0.0.0.0/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{{CidrIpv6=::/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,Ipv6Ranges=[{{CidrIpv6=::/0}}]' >/dev/null 2>&1 || true
if [ -n "${{var.allowed_cidr}}" ]; then
  aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{{CidrIp=${{var.allowed_cidr}}}}]' >/dev/null 2>&1 || true
  aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{{CidrIp=${{var.allowed_cidr}}}}]' >/dev/null 2>&1 || true
fi
if [ -n "${{var.allowed_cidr_ipv6}}" ]; then
  aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{{CidrIpv6=${{var.allowed_cidr_ipv6}}}}]' >/dev/null 2>&1 || true
  aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,Ipv6Ranges=[{{CidrIpv6=${{var.allowed_cidr_ipv6}}}}]' >/dev/null 2>&1 || true
fi
exit 0
EOT
  }}
}}

resource "aws_vpc_security_group_ingress_rule" "ssh_restricted" {{
  security_group_id = var.security_group_id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from allowed CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}}

resource "aws_vpc_security_group_ingress_rule" "rdp_restricted" {{
  security_group_id = var.security_group_id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 3389
  to_port           = 3389
  ip_protocol       = "tcp"
  description       = "RDP from allowed CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}}

resource "aws_vpc_security_group_ingress_rule" "ssh_restricted_ipv6" {{
  count             = var.allowed_cidr_ipv6 != "" ? 1 : 0
  security_group_id = var.security_group_id
  cidr_ipv6         = var.allowed_cidr_ipv6
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from allowed IPv6 CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}}

resource "aws_vpc_security_group_ingress_rule" "rdp_restricted_ipv6" {{
  count             = var.allowed_cidr_ipv6 != "" ? 1 : 0
  security_group_id = var.security_group_id
  cidr_ipv6         = var.allowed_cidr_ipv6
  from_port         = 3389
  to_port           = 3389
  ip_protocol       = "tcp"
  description       = "RDP from allowed IPv6 CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}}
"""


def _terraform_sg_ssm_only_content(meta: dict[str, str], sg_id: str) -> str:
    """Terraform for EC2.53 ssm_only: revoke public SSH/RDP without adding replacement ingress."""
    return f"""# SG remove public admin ingress for SSM-only access - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}
# Requires operator access to already be available through SSM Session Manager before apply.
# This bundle removes public SSH/RDP ingress and intentionally does not add replacement SSH/RDP rules.

variable "security_group_id" {{
  type        = string
  default     = "{sg_id}"
  description = "Security group ID to harden for SSM-only operator access"
}}

variable "remediation_region" {{
  type        = string
  default     = "{meta["region"]}"
  description = "Region used by local AWS CLI revoke commands."
}}

resource "null_resource" "revoke_public_admin_ingress" {{
  triggers = {{
    security_group_id = var.security_group_id
    region            = var.remediation_region
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set +e
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{{CidrIp=0.0.0.0/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{{CidrIp=0.0.0.0/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{{CidrIpv6=::/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,Ipv6Ranges=[{{CidrIpv6=::/0}}]' >/dev/null 2>&1 || true
exit 0
EOT
  }}
}}
"""


def _terraform_sg_bastion_reference_content(
    meta: dict[str, str],
    sg_id: str,
    bastion_sg_ids: list[str],
) -> str:
    """Terraform for EC2.53 bastion_sg_reference: revoke public SSH/RDP and add SG-reference ingress."""
    bastion_defaults = ", ".join(f'"{sg}"' for sg in bastion_sg_ids)
    return f"""# SG replace public admin ingress with bastion SG references - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}
# Requires operator access to move through approved bastion security groups before apply.
# This bundle removes public SSH/RDP ingress and replaces it with source-security-group rules from the approved bastion list.

variable "security_group_id" {{
  type        = string
  default     = "{sg_id}"
  description = "Security group ID to harden for bastion-based operator access"
}}

variable "approved_bastion_security_group_ids" {{
  type        = list(string)
  default     = [{bastion_defaults}]
  description = "Approved bastion security group IDs that may retain SSH/RDP access"
}}

variable "remediation_region" {{
  type        = string
  default     = "{meta["region"]}"
  description = "Region used by local AWS CLI revoke commands."
}}

locals {{
  bastion_security_group_ids = toset(var.approved_bastion_security_group_ids)
}}

resource "null_resource" "revoke_public_admin_ingress" {{
  triggers = {{
    security_group_id = var.security_group_id
    region            = var.remediation_region
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set +e
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{{CidrIp=0.0.0.0/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{{CidrIp=0.0.0.0/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{{CidrIpv6=::/0}}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${{var.remediation_region}}" --group-id "${{var.security_group_id}}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,Ipv6Ranges=[{{CidrIpv6=::/0}}]' >/dev/null 2>&1 || true
exit 0
EOT
  }}
}}

resource "aws_vpc_security_group_ingress_rule" "bastion_ssh" {{
  for_each                      = local.bastion_security_group_ids
  security_group_id            = var.security_group_id
  referenced_security_group_id = each.value
  from_port                    = 22
  to_port                      = 22
  ip_protocol                  = "tcp"
  description                  = "SSH from approved bastion security group ${{each.value}} - Security Autopilot"
  depends_on                   = [null_resource.revoke_public_admin_ingress]
}}

resource "aws_vpc_security_group_ingress_rule" "bastion_rdp" {{
  for_each                      = local.bastion_security_group_ids
  security_group_id            = var.security_group_id
  referenced_security_group_id = each.value
  from_port                    = 3389
  to_port                      = 3389
  ip_protocol                  = "tcp"
  description                  = "RDP from approved bastion security group ${{each.value}} - Security Autopilot"
  depends_on                   = [null_resource.revoke_public_admin_ingress]
}}
"""


def _cloudformation_sg_restrict_content(
    meta: dict[str, str],
    sg_id: str,
    *,
    allowed_cidr: str,
    allowed_cidr_ipv6: str,
) -> str:
    """CloudFormation for SG restrict public ports (EC2.53). Step 9.5 (all seven), 9.11."""
    return f"""# SG restrict public ports (22/3389) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}
# IMPORTANT: review custom revoke behavior before applying.
# This CloudFormation template revokes 0.0.0.0/0 and ::/0 ingress on ports 22/3389 before adding restricted rules.
# Delete path is no-op and does NOT re-add public ingress rules.

AWSTemplateFormatVersion: "2010-09-09"
Description: "Restrict SSH/RDP to allowed CIDR - Security Autopilot with revoke-before-add custom resource."
Metadata:
  SecurityAutopilotNotes:
    - "Identify SG attachments and active dependencies before tightening ingress."
    - "Replace broad sources incrementally (VPN CIDR, office IP, or source SG), then test connectivity."
    - "Avoid blind auto-remediation in production; prefer restrict-over-remove."
    - "Custom resource revokes 0.0.0.0/0 and ::/0 on ports 22/3389 before ingress additions."
    - "Delete path is no-op and must not re-add revoked public ingress rules."
Parameters:
  SecurityGroupId:
    Type: AWS::EC2::SecurityGroup::Id
    Default: "{sg_id}"
    Description: Security group to add restricted ingress
  AllowedCidr:
    Type: String
    Default: "{allowed_cidr}"
    Description: CIDR allowed for SSH (22) and RDP (3389)
  AllowedCidrIpv6:
    Type: String
    Default: "{allowed_cidr_ipv6}"
    Description: Optional IPv6 CIDR allowed for SSH (22) and RDP (3389). Leave empty to skip IPv6 ingress.
Conditions:
  HasAllowedIpv6:
    Fn::Not:
      - Fn::Equals:
          - !Ref AllowedCidrIpv6
          - ""
Resources:
  RevokePublicIngressRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: sg-restrict-revoke-public-ingress
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - ec2:RevokeSecurityGroupIngress
                Resource: "*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  RevokePublicIngressFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt RevokePublicIngressRole.Arn
      Code:
        ZipFile: |
          import boto3
          import cfnresponse
          from botocore.exceptions import ClientError

          def _revoke(ec2, security_group_id, permission):
              try:
                  ec2.revoke_security_group_ingress(
                      GroupId=security_group_id,
                      IpPermissions=[permission],
                  )
              except ClientError as exc:
                  code = exc.response.get("Error", {{}}).get("Code", "")
                  if code != "InvalidPermission.NotFound":
                      raise

          def handler(event, context):
              request_type = event.get("RequestType")
              try:
                  if request_type == "Delete":
                      cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "RevokePublicIngress")
                      return
                  security_group_id = (event.get("ResourceProperties", {{}}).get("SecurityGroupId") or "").strip()
                  if not security_group_id:
                      raise ValueError("SecurityGroupId is required.")
                  ec2 = boto3.client("ec2")
                  ip_permissions = [
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 22,
                          "ToPort": 22,
                          "IpRanges": [{{"CidrIp": "0.0.0.0/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 3389,
                          "ToPort": 3389,
                          "IpRanges": [{{"CidrIp": "0.0.0.0/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 22,
                          "ToPort": 22,
                          "Ipv6Ranges": [{{"CidrIpv6": "::/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 3389,
                          "ToPort": 3389,
                          "Ipv6Ranges": [{{"CidrIpv6": "::/0"}}],
                      }},
                  ]
                  for permission in ip_permissions:
                      _revoke(ec2, security_group_id, permission)
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "RevokePublicIngress")
              except Exception as exc:
                  cfnresponse.send(
                      event,
                      context,
                      cfnresponse.FAILED,
                      {{"Error": str(exc)}},
                      "RevokePublicIngress",
                  )
  RevokePublicAdminIngress:
    Type: Custom::SecurityGroupIngressRevoke
    Properties:
      ServiceToken: !GetAtt RevokePublicIngressFunction.Arn
      SecurityGroupId: !Ref SecurityGroupId
  IngressSSH:
    DependsOn: RevokePublicAdminIngress
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 22
      ToPort: 22
      CidrIp: !Ref AllowedCidr
      Description: "SSH from allowed CIDR - Security Autopilot"
  IngressRDP:
    DependsOn: RevokePublicAdminIngress
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 3389
      ToPort: 3389
      CidrIp: !Ref AllowedCidr
      Description: "RDP from allowed CIDR - Security Autopilot"
  IngressSSHIPv6:
    Condition: HasAllowedIpv6
    DependsOn: RevokePublicAdminIngress
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 22
      ToPort: 22
      CidrIpv6: !Ref AllowedCidrIpv6
      Description: "SSH from allowed IPv6 CIDR - Security Autopilot"
  IngressRDPIPv6:
    Condition: HasAllowedIpv6
    DependsOn: RevokePublicAdminIngress
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 3389
      ToPort: 3389
      CidrIpv6: !Ref AllowedCidrIpv6
      Description: "RDP from allowed IPv6 CIDR - Security Autopilot"
"""


def _cloudformation_sg_ssm_only_content(meta: dict[str, str], sg_id: str) -> str:
    """CloudFormation for EC2.53 ssm_only: revoke public SSH/RDP without replacement ingress."""
    return f"""# SG remove public admin ingress for SSM-only access - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}
# IMPORTANT: confirm SSM Session Manager access works before apply.
# This template revokes public SSH/RDP ingress on ports 22/3389 and does not add replacement ingress rules.
# Delete path is no-op and does NOT restore revoked public ingress rules.

AWSTemplateFormatVersion: "2010-09-09"
Description: "Remove public SSH/RDP ingress and rely on SSM Session Manager access."
Metadata:
  SecurityAutopilotNotes:
    - "Confirm SSM Session Manager access is already working before applying this template."
    - "This template revokes 0.0.0.0/0 and ::/0 on ports 22/3389 and adds no replacement admin ingress rules."
    - "Keep bastion/VPN fallback ready for workloads that are not SSM-managed."
    - "Delete path is no-op and must not re-add revoked public ingress rules."
Parameters:
  SecurityGroupId:
    Type: AWS::EC2::SecurityGroup::Id
    Default: "{sg_id}"
    Description: Security group to remove public SSH/RDP ingress from
Resources:
  RevokePublicIngressRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: sg-ssm-only-revoke-public-ingress
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - ec2:RevokeSecurityGroupIngress
                Resource: "*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  RevokePublicIngressFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt RevokePublicIngressRole.Arn
      Code:
        ZipFile: |
          import boto3
          import cfnresponse
          from botocore.exceptions import ClientError

          def _revoke(ec2, security_group_id, permission):
              try:
                  ec2.revoke_security_group_ingress(
                      GroupId=security_group_id,
                      IpPermissions=[permission],
                  )
              except ClientError as exc:
                  code = exc.response.get("Error", {{}}).get("Code", "")
                  if code != "InvalidPermission.NotFound":
                      raise

          def handler(event, context):
              request_type = event.get("RequestType")
              try:
                  if request_type == "Delete":
                      cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "RevokePublicIngress")
                      return
                  security_group_id = (event.get("ResourceProperties", {{}}).get("SecurityGroupId") or "").strip()
                  if not security_group_id:
                      raise ValueError("SecurityGroupId is required.")
                  ec2 = boto3.client("ec2")
                  ip_permissions = [
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 22,
                          "ToPort": 22,
                          "IpRanges": [{{"CidrIp": "0.0.0.0/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 3389,
                          "ToPort": 3389,
                          "IpRanges": [{{"CidrIp": "0.0.0.0/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 22,
                          "ToPort": 22,
                          "Ipv6Ranges": [{{"CidrIpv6": "::/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 3389,
                          "ToPort": 3389,
                          "Ipv6Ranges": [{{"CidrIpv6": "::/0"}}],
                      }},
                  ]
                  for permission in ip_permissions:
                      _revoke(ec2, security_group_id, permission)
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "RevokePublicIngress")
              except Exception as exc:
                  cfnresponse.send(
                      event,
                      context,
                      cfnresponse.FAILED,
                      {{"Error": str(exc)}},
                      "RevokePublicIngress",
                  )
  RevokePublicAdminIngress:
    Type: Custom::SecurityGroupIngressRevoke
    Properties:
      ServiceToken: !GetAtt RevokePublicIngressFunction.Arn
      SecurityGroupId: !Ref SecurityGroupId
"""


def _cf_bastion_logical_id(prefix: str, sg_id: str, port: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", sg_id)
    return f"{prefix}{cleaned}{port}"


def _cloudformation_sg_bastion_reference_content(
    meta: dict[str, str],
    sg_id: str,
    bastion_sg_ids: list[str],
) -> str:
    """CloudFormation for EC2.53 bastion_sg_reference: revoke public SSH/RDP and add SG-reference ingress."""
    ingress_blocks: list[str] = []
    for bastion_sg_id in bastion_sg_ids:
        ingress_blocks.append(
            f"""  {_cf_bastion_logical_id("IngressSSHFrom", bastion_sg_id, 22)}:
    DependsOn: RevokePublicAdminIngress
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 22
      ToPort: 22
      SourceSecurityGroupId: "{bastion_sg_id}"
      Description: "SSH from approved bastion security group {bastion_sg_id} - Security Autopilot"
  {_cf_bastion_logical_id("IngressRDPFrom", bastion_sg_id, 3389)}:
    DependsOn: RevokePublicAdminIngress
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 3389
      ToPort: 3389
      SourceSecurityGroupId: "{bastion_sg_id}"
      Description: "RDP from approved bastion security group {bastion_sg_id} - Security Autopilot"
"""
        )
    ingress_resources = "\n".join(ingress_blocks)
    return f"""# SG replace public admin ingress with bastion SG references - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}
# IMPORTANT: confirm approved bastion security groups are correct before apply.
# This template revokes public SSH/RDP ingress on ports 22/3389 and replaces it with source-security-group rules from the approved bastion list.
# Delete path is no-op and does NOT restore revoked public ingress rules.

AWSTemplateFormatVersion: "2010-09-09"
Description: "Remove public SSH/RDP ingress and restrict operator access to approved bastion security groups."
Metadata:
  SecurityAutopilotNotes:
    - "Confirm the approved bastion security groups are correct before applying this template."
    - "This template revokes 0.0.0.0/0 and ::/0 on ports 22/3389 and replaces them with source-security-group ingress from the approved bastion list."
    - "Delete path is no-op and must not re-add revoked public ingress rules."
Parameters:
  SecurityGroupId:
    Type: AWS::EC2::SecurityGroup::Id
    Default: "{sg_id}"
    Description: Security group to remove public SSH/RDP ingress from
Resources:
  RevokePublicIngressRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: sg-bastion-reference-revoke-public-ingress
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - ec2:RevokeSecurityGroupIngress
                Resource: "*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  RevokePublicIngressFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt RevokePublicIngressRole.Arn
      Code:
        ZipFile: |
          import boto3
          import cfnresponse
          from botocore.exceptions import ClientError

          def _revoke(ec2, security_group_id, permission):
              try:
                  ec2.revoke_security_group_ingress(
                      GroupId=security_group_id,
                      IpPermissions=[permission],
                  )
              except ClientError as exc:
                  code = exc.response.get("Error", {{}}).get("Code", "")
                  if code != "InvalidPermission.NotFound":
                      raise

          def handler(event, context):
              request_type = event.get("RequestType")
              try:
                  if request_type == "Delete":
                      cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "RevokePublicIngress")
                      return
                  security_group_id = (event.get("ResourceProperties", {{}}).get("SecurityGroupId") or "").strip()
                  if not security_group_id:
                      raise ValueError("SecurityGroupId is required.")
                  ec2 = boto3.client("ec2")
                  ip_permissions = [
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 22,
                          "ToPort": 22,
                          "IpRanges": [{{"CidrIp": "0.0.0.0/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 3389,
                          "ToPort": 3389,
                          "IpRanges": [{{"CidrIp": "0.0.0.0/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 22,
                          "ToPort": 22,
                          "Ipv6Ranges": [{{"CidrIpv6": "::/0"}}],
                      }},
                      {{
                          "IpProtocol": "tcp",
                          "FromPort": 3389,
                          "ToPort": 3389,
                          "Ipv6Ranges": [{{"CidrIpv6": "::/0"}}],
                      }},
                  ]
                  for permission in ip_permissions:
                      _revoke(ec2, security_group_id, permission)
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "RevokePublicIngress")
              except Exception as exc:
                  cfnresponse.send(
                      event,
                      context,
                      cfnresponse.FAILED,
                      {{"Error": str(exc)}},
                      "RevokePublicIngress",
                  )
  RevokePublicAdminIngress:
    Type: Custom::SecurityGroupIngressRevoke
    Properties:
      ServiceToken: !GetAtt RevokePublicIngressFunction.Arn
      SecurityGroupId: !Ref SecurityGroupId
{ingress_resources}
"""


# ---------------------------------------------------------------------------
# CloudTrail enabled — Step 9.12 (action_type: cloudtrail_enabled, control_id: CloudTrail.1)
# ---------------------------------------------------------------------------
# Scope: account-level or per region; region from action. Control CloudTrail.1 → cloudtrail_enabled (control_scope 9.8).
# Multi-region trail + S3 bucket for logs (variable/parameter).
# Terraform: aws_cloudtrail. CloudFormation: AWS::CloudTrail::Trail.
# ---------------------------------------------------------------------------


def _generate_for_cloudtrail_enabled(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_inputs: dict[str, Any] | None = None,
) -> PRBundleResult:
    """Generate IaC for cloudtrail_enabled (multi-region trail, CloudTrail.1). Step 9.12."""
    meta = _action_meta(action)
    trail_name, trail_bucket_name, kms_key_arn, create_bucket_if_missing, create_bucket_policy, multi_region = _resolve_cloudtrail_defaults(
        strategy_inputs,
    )
    if not trail_bucket_name:
        _raise_pr_bundle_error(
            code="invalid_strategy_inputs",
            detail=(
                "strategy_inputs.trail_bucket_name is required for executable CloudTrail PR bundles. "
                "Configure cloudtrail.default_bucket_name or provide strategy_inputs.trail_bucket_name."
            ),
            action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
            format=format,
            strategy_id="cloudtrail_enable_guided",
        )
    region = meta["region"]
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="cloudtrail_enabled.yaml",
                content=_cloudformation_cloudtrail_content(
                    meta,
                    trail_name=trail_name,
                    trail_bucket_name=trail_bucket_name,
                    kms_key_arn=kms_key_arn,
                    create_bucket_if_missing=create_bucket_if_missing,
                    multi_region=multi_region,
                    create_bucket_policy=create_bucket_policy,
                ),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']}.",
            (
                "Review TrailBucketName. When CreateBucketIfMissing=true, this template creates the bucket; "
                "otherwise it must already exist."
            ),
            (
                "If you need to keep existing bucket policy management external, set "
                "CreateBucketPolicy=false."
            ),
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="cloudtrail_enabled.tf",
                content=_terraform_cloudtrail_content(
                    meta,
                    trail_name=trail_name,
                    trail_bucket_name=trail_bucket_name,
                    kms_key_arn=kms_key_arn,
                    create_bucket_if_missing=create_bucket_if_missing,
                    multi_region=multi_region,
                    create_bucket_policy=create_bucket_policy,
                ),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            (
                "Review trail_bucket_name. When create_bucket_if_missing = true, Terraform creates the bucket with the shared support-bucket baseline; "
                "otherwise the bucket must already exist."
            ),
            (
                "Set create_bucket_policy = false only when bucket policy statements are managed "
                "outside this bundle."
            ),
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable CloudTrail (multi-region).",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    result = PRBundleResult(format=format, files=files, steps=steps)
    if format == TERRAFORM_FORMAT:
        result["metadata"] = _merge_bundle_metadata(
            result.get("metadata"),
            {
                "helper_bucket_inventory": [
                    _helper_bucket_inventory_entry(
                        bucket_name=trail_bucket_name,
                        helper_bucket_role=SUPPORT_BUCKET_ROLE_CLOUDTRAIL_LOGS,
                        created=create_bucket_if_missing,
                    )
                ]
            },
        )
    return result


def _terraform_regional_providers_content(
    meta: dict[str, str],
    *,
    include_external_provider: bool = False,
    include_null_provider: bool = False,
) -> str:
    """Shared provider block with region for regional resources (9.9–9.12). Uses default credential chain (no profile)."""
    region = meta["region"]
    account_id = meta["account_id"]
    null_provider_block = ""
    if include_null_provider:
        null_provider_block = f"""
    null = {{
      source  = "hashicorp/null"
      version = "{TERRAFORM_NULL_PROVIDER_VERSION_CONSTRAINT}"
    }}"""
    external_provider_block = ""
    if include_external_provider:
        external_provider_block = f"""
    external = {{
      source  = "hashicorp/external"
      version = "{TERRAFORM_EXTERNAL_PROVIDER_VERSION_CONSTRAINT}"
    }}"""
    return f"""# Configure AWS provider for account {account_id} and region {region}.
# Credentials: default chain (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, or ~/.aws/credentials [default]).
# If you use a named profile, add: profile = "your-profile-name" (do not use account ID as profile name).

terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "{TERRAFORM_AWS_PROVIDER_VERSION_CONSTRAINT}"
    }}{external_provider_block}{null_provider_block}
  }}
}}

provider "aws" {{
  region = "{region}"
}}
"""


def _terraform_cloudtrail_content(
    meta: dict[str, str],
    *,
    trail_name: str,
    trail_bucket_name: str,
    kms_key_arn: str,
    create_bucket_if_missing: bool,
    multi_region: bool,
    create_bucket_policy: bool,
) -> str:
    """Terraform for CloudTrail enabled (multi-region, CloudTrail.1)."""
    create_bucket_if_missing_default = "true" if create_bucket_if_missing else "false"
    multi_region_default = "true" if multi_region else "false"
    create_bucket_policy_default = "true" if create_bucket_policy else "false"
    trail_bucket_default = f'  default     = "{trail_bucket_name}"\n' if trail_bucket_name else ""
    kms_key_default = kms_key_arn or ""
    policy_block = f"""
variable "remediation_region" {{
  type        = string
  default     = "{meta["region"]}"
  description = "Region used by local AWS CLI bucket-policy merge command."
}}

data "aws_iam_policy_document" "cloudtrail_delivery" {{
  statement {{
    sid     = "AWSCloudTrailAclCheck"
    effect  = "Allow"
    actions = ["s3:GetBucketAcl"]

    principals {{
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }}

    resources = [local.cloudtrail_bucket_arn]
  }}

  statement {{
    sid     = "AWSCloudTrailWrite"
    effect  = "Allow"
    actions = ["s3:PutObject"]

    principals {{
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }}

    resources = ["${{local.cloudtrail_bucket_arn}}/AWSLogs/{meta["account_id"]}/CloudTrail/*"]

    condition {{
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }}
  }}
}}

resource "null_resource" "cloudtrail_bucket_policy" {{
  count  = var.create_bucket_policy && !var.create_bucket_if_missing ? 1 : 0

  triggers = {{
    trail_bucket_name  = var.trail_bucket_name
    remediation_region = var.remediation_region
    account_id         = "{meta["account_id"]}"
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
TRAIL_BUCKET_NAME="${{var.trail_bucket_name}}"
AWS_REGION="${{var.remediation_region}}"
ACCOUNT_ID="{meta["account_id"]}"
export TRAIL_BUCKET_NAME AWS_REGION ACCOUNT_ID
python3 - <<'PY'
import json
import os
import subprocess
import sys

bucket = os.environ["TRAIL_BUCKET_NAME"]
region = os.environ["AWS_REGION"]
account_id = os.environ["ACCOUNT_ID"]

def run(cmd):
    return subprocess.run(cmd, check=True, text=True, capture_output=True)

existing = {{"Version": "2012-10-17", "Statement": []}}
try:
    response = run(
        [
            "aws",
            "s3api",
            "get-bucket-policy",
            "--bucket",
            bucket,
            "--region",
            region,
            "--output",
            "json",
        ]
    )
    policy_doc = json.loads(response.stdout).get("Policy", "")
    if policy_doc:
        existing = json.loads(policy_doc)
except subprocess.CalledProcessError as exc:
    if "NoSuchBucketPolicy" not in (exc.stderr or ""):
        print(exc.stderr, file=sys.stderr)
        raise

statements = existing.get("Statement", [])
if not isinstance(statements, list):
    statements = []

preserved = [
    statement
    for statement in statements
    if statement.get("Sid") not in {{"AWSCloudTrailAclCheck", "AWSCloudTrailWrite"}}
]

preserved.append(
    {{
        "Sid": "AWSCloudTrailAclCheck",
        "Effect": "Allow",
        "Principal": {{"Service": "cloudtrail.amazonaws.com"}},
        "Action": "s3:GetBucketAcl",
        "Resource": "arn:aws:s3:::" + bucket,
    }}
)
preserved.append(
    {{
        "Sid": "AWSCloudTrailWrite",
        "Effect": "Allow",
        "Principal": {{"Service": "cloudtrail.amazonaws.com"}},
        "Action": "s3:PutObject",
        "Resource": "arn:aws:s3:::" + bucket + "/AWSLogs/" + account_id + "/CloudTrail/*",
        "Condition": {{"StringEquals": {{"s3:x-amz-acl": "bucket-owner-full-control"}}}},
    }}
)

merged = {{
    "Version": existing.get("Version", "2012-10-17"),
    "Statement": preserved,
}}
run(
    [
        "aws",
        "s3api",
        "put-bucket-policy",
        "--bucket",
        bucket,
        "--region",
        region,
        "--policy",
        json.dumps(merged, separators=(",", ":")),
    ]
)
PY
EOT
  }}
}}
"""
    support_bucket_blocks = terraform_support_bucket_blocks(
        resource_suffix="cloudtrail_logs",
        bucket_id_ref="aws_s3_bucket.cloudtrail_logs[0].id",
        bucket_name_ref='local.cloudtrail_bucket_name',
        count_expr="var.create_bucket_if_missing ? 1 : 0",
        enable_versioning=True,
        service_write_data_source="data.aws_iam_policy_document.cloudtrail_delivery",
        support_bucket_role=SUPPORT_BUCKET_ROLE_CLOUDTRAIL_LOGS,
    )
    return f"""# CloudTrail enabled - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]}
# Control: {meta["control_id"]}
# Review trail_bucket_name below. Toggle create_bucket_if_missing to create the bucket in this bundle.

variable "trail_bucket_name" {{
  type        = string
  description = "S3 bucket name for CloudTrail logs."
{trail_bucket_default if trail_bucket_default else ""}
}}

variable "trail_name" {{
  type        = string
  default     = "{trail_name}"
  description = "CloudTrail trail name."
}}

variable "create_bucket_if_missing" {{
  type        = bool
  default     = {create_bucket_if_missing_default}
  description = "When true, create the CloudTrail log bucket and baseline controls in this bundle."
}}

variable "multi_region" {{
  type        = bool
  default     = {multi_region_default}
  description = "When true, enables multi-region CloudTrail logging."
}}

variable "create_bucket_policy" {{
  type        = bool
  default     = {create_bucket_policy_default}
  description = "When true, create required CloudTrail S3 bucket policy statements."
}}

variable "kms_key_arn" {{
  type        = string
  default     = "{kms_key_default}"
  description = "Optional KMS key ARN for CloudTrail log encryption."
}}

locals {{
  cloudtrail_bucket_name = var.create_bucket_if_missing ? aws_s3_bucket.cloudtrail_logs[0].bucket : var.trail_bucket_name
  cloudtrail_bucket_arn  = "arn:aws:s3:::${{local.cloudtrail_bucket_name}}"
}}

resource "aws_s3_bucket" "cloudtrail_logs" {{
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = var.trail_bucket_name
}}

{support_bucket_blocks}

resource "aws_cloudtrail" "security_autopilot" {{
  name                          = var.trail_name
  s3_bucket_name                = local.cloudtrail_bucket_name
  is_multi_region_trail          = var.multi_region
  include_global_service_events = true
  enable_logging                = true
  kms_key_id                    = var.kms_key_arn != "" ? var.kms_key_arn : null
  depends_on                    = [aws_s3_bucket_policy.cloudtrail_logs, null_resource.cloudtrail_bucket_policy]
}}
{policy_block if policy_block else ""}
"""


def _cloudformation_cloudtrail_content(
    meta: dict[str, str],
    *,
    trail_name: str,
    trail_bucket_name: str,
    kms_key_arn: str,
    create_bucket_if_missing: bool,
    multi_region: bool,
    create_bucket_policy: bool,
) -> str:
    """CloudFormation for CloudTrail enabled (CloudTrail.1). Step 9.5 (all seven), 9.12."""
    create_bucket_if_missing_default = "true" if create_bucket_if_missing else "false"
    multi_region_default = "true" if multi_region else "false"
    create_bucket_policy_default = "true" if create_bucket_policy else "false"
    kms_key_default = kms_key_arn or ""
    trail_bucket_parameter = (
        f"""  TrailBucketName:
    Type: String
    Default: "{trail_bucket_name}"
    Description: S3 bucket name for CloudTrail logs
"""
        if trail_bucket_name
        else """  TrailBucketName:
    Type: String
    Description: S3 bucket name for CloudTrail logs
"""
    )
    bucket_policy_resource = f"""
  TrailBucket:
    Condition: ShouldCreateBucket
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref TrailBucketName
      VersioningConfiguration:
        Status: Enabled
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: alias/aws/s3
            BucketKeyEnabled: true
      LifecycleConfiguration:
        Rules:
          - Id: abort-incomplete-multipart
            Status: Enabled
            AbortIncompleteMultipartUpload:
              DaysAfterInitiation: 7
  TrailBucketPolicy:
    Condition: ShouldCreateBucketPolicy
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !If [ShouldCreateBucket, !Ref TrailBucket, !Ref TrailBucketName]
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Sid: AWSCloudTrailAclCheck
            Effect: Allow
            Principal:
              Service: cloudtrail.amazonaws.com
            Action: s3:GetBucketAcl
            Resource: !Sub arn:aws:s3:::${{TrailBucketName}}
          - Sid: AWSCloudTrailWrite
            Effect: Allow
            Principal:
              Service: cloudtrail.amazonaws.com
            Action: s3:PutObject
            Resource: !Sub arn:aws:s3:::${{TrailBucketName}}/AWSLogs/{meta["account_id"]}/CloudTrail/*
            Condition:
              StringEquals:
                s3:x-amz-acl: bucket-owner-full-control
          - Sid: DenyInsecureTransport
            Effect: Deny
            Principal: "*"
            Action: s3:*
            Resource:
              - !Sub arn:aws:s3:::${{TrailBucketName}}
              - !Sub arn:aws:s3:::${{TrailBucketName}}/*
            Condition:
              Bool:
                aws:SecureTransport: "false"
"""
    return f"""# CloudTrail enabled - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "CloudTrail multi-region trail - Security Autopilot. Provide S3 bucket for logs."
Parameters:
  TrailName:
    Type: String
    Default: "{trail_name}"
    Description: CloudTrail trail name
{trail_bucket_parameter}
  CreateBucketIfMissing:
    Type: String
    Default: "{create_bucket_if_missing_default}"
    AllowedValues:
      - "true"
      - "false"
    Description: When true, create the CloudTrail log bucket in this stack.
  MultiRegion:
    Type: String
    Default: "{multi_region_default}"
    AllowedValues:
      - "true"
      - "false"
    Description: When true, enables multi-region CloudTrail logging.
  CreateBucketPolicy:
    Type: String
    Default: "{create_bucket_policy_default}"
    AllowedValues:
      - "true"
      - "false"
    Description: When true, create required CloudTrail S3 bucket policy statements.
  KmsKeyArn:
    Type: String
    Default: "{kms_key_default}"
    Description: Optional KMS key ARN for CloudTrail log encryption.
Conditions:
  ShouldCreateBucket: !Equals [!Ref CreateBucketIfMissing, "true"]
  ShouldCreateBucketPolicy: !Equals [!Ref CreateBucketPolicy, "true"]
  HasKmsKeyArn: !Not [!Equals [!Ref KmsKeyArn, ""]]
Resources:
  Trail:
    Type: AWS::CloudTrail::Trail
    Properties:
      TrailName: !Ref TrailName
      S3BucketName: !If [ShouldCreateBucket, !Ref TrailBucket, !Ref TrailBucketName]
      IsMultiRegionTrail: !Equals [!Ref MultiRegion, "true"]
      IncludeGlobalServiceEvents: true
      KMSKeyId: !If [HasKmsKeyArn, !Ref KmsKeyArn, !Ref AWS::NoValue]
{bucket_policy_resource if bucket_policy_resource else ""}
"""


# ---------------------------------------------------------------------------
# Phase 1 strategy-based generators
# ---------------------------------------------------------------------------


def _generate_for_s3_bucket_strategy(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    risk_snapshot: dict[str, Any] | None,
    variant: str | None,
    resolution: Mapping[str, Any] | None,
) -> PRBundleResult:
    """Generate S3 bucket public-access remediation according to selected strategy."""
    normalized_strategy = (strategy_id or "").strip().lower()
    if normalized_strategy == "s3_migrate_cloudfront_oac_private":
        return _generate_for_s3_cloudfront_oac_private(
            action,
            format,
            strategy_id=normalized_strategy,
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            variant=variant,
            resolution=resolution,
        )
    if normalized_strategy == "s3_migrate_website_cloudfront_private":
        return _generate_for_s3_website_cloudfront_private(
            action,
            format,
            strategy_id=normalized_strategy,
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            resolution=resolution,
        )
    if normalized_strategy == "s3_keep_public_exception":
        return _generate_for_exception_guidance(action, format, "Keep public S3 access (exception path)")
    return _generate_for_s3_bucket_block_public_access(
        action,
        format,
        strategy_id=normalized_strategy,
        resolution=resolution,
    )


def _generate_for_aws_config_enabled(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
) -> PRBundleResult:
    """Generate AWS Config enablement bundle from selected strategy."""
    meta = _action_meta(action)
    strategy = (strategy_id or "config_enable_account_local_delivery").strip().lower()
    inputs = strategy_inputs or {}
    if strategy == "config_keep_exception":
        return _generate_for_exception_guidance(action, format, "Keep AWS Config disabled (exception path)")

    if format == CLOUDFORMATION_FORMAT:
        content = _cloudformation_aws_config_enabled_content(meta, strategy=strategy, strategy_inputs=inputs)
        steps = [
            f"Configure AWS credentials for account {meta['account_id']}.",
        (
            "Validate the template and deploy the stack. Keep OverwriteRecordingGroup=false only when the "
            "existing recorder already captures the full Config.1 scope; selective/custom recorders should "
            "resolve to all-supported recording on the executable path."
        ),
            "Confirm AWS Config recorder is running and delivery channel is healthy.",
            "Recompute actions to verify remediation state.",
        ]
        return PRBundleResult(
            format=format,
            files=[PRBundleFile(path="aws_config_enabled.yaml", content=content)],
            steps=steps,
        )

    bucket, kms_key_arn, create_local_bucket, overwrite_recording_group = _resolve_aws_config_defaults(
        account_id=meta["account_id"],
        region=meta["region"],
        strategy=strategy,
        strategy_inputs=inputs,
    )
    content = _terraform_aws_config_enabled_content(meta, strategy=strategy, strategy_inputs=inputs)
    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
        (
            "Adjust bucket/KMS variables as needed. Keep overwrite_recording_group=false only when the existing "
            "recorder already captures the full Config.1 scope; selective/custom recorders should resolve to "
            "all-supported recording on the executable path."
        ),
        "Run `terraform init`, `terraform plan`, and `terraform apply`.",
        f"Use `python3 ./{AWS_CONFIG_ROLLBACK_SCRIPT_PATH}` only when you need to restore the exact pre-remediation AWS Config state captured by this bundle.",
        "Recompute actions to verify remediation state.",
    ]
    return PRBundleResult(
        format=format,
        files=[
            PRBundleFile(
                path="providers.tf",
                content=_terraform_regional_providers_content(meta, include_null_provider=True),
            ),
            PRBundleFile(path="aws_config_enabled.tf", content=content),
            PRBundleFile(
                path=AWS_CONFIG_APPLY_SCRIPT_PATH,
                content=aws_config_apply_script_content(
                    region=meta["region"],
                    bucket=bucket,
                    role_arn=(
                        f"arn:aws:iam::{meta['account_id']}:role/"
                        "aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig"
                    ),
                    account_id=meta["account_id"],
                    kms_key_arn=kms_key_arn,
                    create_local_bucket=create_local_bucket,
                    overwrite_recording_group=overwrite_recording_group,
                ),
            ),
            PRBundleFile(
                path=AWS_CONFIG_ROLLBACK_SCRIPT_PATH,
                content=aws_config_restore_script_content(region=meta["region"]),
            ),
        ],
        steps=steps,
        metadata=_merge_bundle_metadata(
            aws_config_bundle_rollback_metadata(str(action.id)),
            {
                "helper_bucket_inventory": [
                    _helper_bucket_inventory_entry(
                        bucket_name=bucket,
                        helper_bucket_role=SUPPORT_BUCKET_ROLE_AWS_CONFIG_DELIVERY,
                        created=create_local_bucket,
                    )
                ]
            },
        ),
    )


def _generate_for_ssm_block_public_sharing(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate SSM document public-sharing block bundle."""
    meta = _action_meta(action)
    setting_id = (
        f"arn:aws:ssm:{meta['region']}:{meta['account_id']}:"
        "servicesetting/ssm/documents/console/public-sharing-permission"
    )
    if format == CLOUDFORMATION_FORMAT:
        return PRBundleResult(
            format=format,
            files=[
                PRBundleFile(
                    path="ssm_block_public_sharing.yaml",
                    content=_cloudformation_ssm_block_public_sharing_content(meta),
                )
            ],
            steps=[
                f"Configure AWS credentials for account {meta['account_id']} and region {meta['region']}.",
                "What changes: sets the SSM public-sharing service setting to Disable.",
                "How to access now: share SSM documents privately per account `aws ssm modify-document-permission --name <document-name> --permission-type Share --account-ids-to-add <account-id>`.",
                "Deploy the template to enforce blocked public sharing.",
                f"Verify: `aws ssm get-service-setting --setting-id {setting_id} --query 'ServiceSetting.SettingValue' --output text` returns Disable.",
                "Verify: `aws ssm describe-document-permission --name <document-name> --permission-type Share` shows explicit account shares (not public).",
                f"Rollback: emergency-only command `aws ssm update-service-setting --setting-id {setting_id} --setting-value Enable`.",
                "Recompute actions to verify remediation state.",
            ],
        )

    return PRBundleResult(
        format=format,
        files=[
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="ssm_block_public_sharing.tf",
                content=_terraform_ssm_block_public_sharing_content(meta),
            ),
        ],
        steps=[
            f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
            "Run `terraform init`, `terraform plan`, and `terraform apply`.",
            "Recompute actions to verify remediation state.",
        ],
    )


def _generate_for_ebs_snapshot_block_public_access(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
) -> PRBundleResult:
    """Generate EBS snapshot public sharing block bundle."""
    meta = _action_meta(action)
    strategy = (strategy_id or "snapshot_block_all_sharing").strip().lower()
    if strategy == "snapshot_keep_sharing_exception":
        return _generate_for_exception_guidance(action, format, "Keep snapshot sharing as exception")
    state = "block-all-sharing" if strategy != "snapshot_block_new_sharing_only" else "block-new-sharing"

    if format == CLOUDFORMATION_FORMAT:
        return PRBundleResult(
            format=format,
            files=[
                PRBundleFile(
                    path="ebs_snapshot_block_public_access.yaml",
                    content=_cloudformation_ebs_snapshot_block_public_access_content(meta, state=state),
                )
            ],
            steps=[
                f"Configure AWS credentials for account {meta['account_id']} and region {meta['region']}.",
                "Deploy template and verify snapshot block public access state.",
                "Recompute actions to verify remediation state.",
            ],
        )

    return PRBundleResult(
        format=format,
        files=[
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="ebs_snapshot_block_public_access.tf",
                content=_terraform_ebs_snapshot_block_public_access_content(meta, state=state),
            ),
        ],
        steps=[
            f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
            "Run `terraform init`, `terraform plan`, and `terraform apply`.",
            "Recompute actions to verify remediation state.",
        ],
    )


def _generate_for_ebs_default_encryption(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
) -> PRBundleResult:
    """Generate EBS default encryption bundle (AWS managed or customer KMS)."""
    meta = _action_meta(action)
    strategy = (strategy_id or "ebs_enable_default_encryption_aws_managed_kms").strip().lower()
    inputs = strategy_inputs or {}
    kms_key_arn = str(inputs.get("kms_key_arn", "")).strip()
    uses_customer_kms = "customer_kms" in strategy
    if uses_customer_kms and not kms_key_arn:
        _raise_pr_bundle_error(
            code="invalid_strategy_inputs",
            detail=(
                "strategy_inputs.kms_key_arn is required for customer-managed EBS default encryption bundles."
            ),
            action_type=ACTION_TYPE_EBS_DEFAULT_ENCRYPTION,
            format=format,
            strategy_id=strategy,
        )

    if format == CLOUDFORMATION_FORMAT:
        return PRBundleResult(
            format=format,
            files=[
                PRBundleFile(
                    path="ebs_default_encryption.yaml",
                    content=_cloudformation_ebs_default_encryption_content(
                        meta,
                        customer_kms=uses_customer_kms,
                        kms_key_arn=kms_key_arn,
                    ),
                )
            ],
            steps=[
                f"Configure AWS credentials for account {meta['account_id']} and region {meta['region']}.",
                "Deploy template and confirm EBS encryption-by-default is enabled.",
                "If customer KMS was selected, validate key policy grants for compute principals.",
                "Recompute actions to verify remediation state.",
            ],
        )

    return PRBundleResult(
        format=format,
        files=[
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="ebs_default_encryption.tf",
                content=_terraform_ebs_default_encryption_content(
                    meta,
                    customer_kms=uses_customer_kms,
                    kms_key_arn=kms_key_arn,
                ),
            ),
        ],
        steps=[
            f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
            "Run `terraform init`, `terraform plan`, and `terraform apply`.",
            "If customer KMS was selected, validate key policy grants for compute principals.",
            "Recompute actions to verify remediation state.",
        ],
    )


def _generate_for_s3_bucket_require_ssl(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
    strategy_inputs: dict[str, Any] | None,
    risk_snapshot: dict[str, Any] | None,
    resolution: Mapping[str, Any] | None,
) -> PRBundleResult:
    """Generate S3 SSL enforcement bundle."""
    meta = _action_meta(action)
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    strategy = (strategy_id or "s3_enforce_ssl_strict_deny").strip().lower()
    if strategy == "s3_keep_non_ssl_exception":
        return _generate_for_exception_guidance(action, format, "Keep non-SSL S3 access (exception path)")

    inputs = strategy_inputs or {}
    create_bucket_if_missing = _create_bucket_if_missing_enabled(strategy_inputs)
    preserve_existing_policy = _coerce_bool(inputs.get("preserve_existing_policy"), default=True)
    apply_time_merge = _s3_5_apply_time_merge_requested(resolution) and not create_bucket_if_missing
    preservation_policy: str | None = None
    if preserve_existing_policy and not apply_time_merge and not create_bucket_if_missing:
        preservation_policy = _resolve_s3_migrate_policy_preservation(
            strategy_inputs=strategy_inputs,
            risk_snapshot=risk_snapshot,
            action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
            format=format,
            strategy_id=strategy_id,
            variant=None,
            missing_policy_error_code="bucket_policy_preservation_evidence_missing",
            missing_policy_error_detail=(
                "Existing bucket policy statements were detected, but preservation evidence is missing. "
                "Regenerate after refreshing remediation options or provide "
                "strategy_inputs.existing_bucket_policy_json before generating this bundle."
            ),
            fail_when_evidence_missing=True,
        )

    exempt_principals = inputs.get("exempt_principals")
    if not isinstance(exempt_principals, list):
        exempt_principals = []

    if format == CLOUDFORMATION_FORMAT:
        if create_bucket_if_missing:
            _raise_pr_bundle_error(
                code="unsupported_variant_format",
                detail=(
                    "Create-missing-bucket S3.5 bundles are only supported for terraform format."
                ),
                action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
                format=format,
                strategy_id=strategy_id,
            )
        if apply_time_merge and preservation_policy is None:
            _raise_pr_bundle_error(
                code="bucket_policy_preservation_evidence_missing",
                detail=(
                    "CloudFormation S3.5 generation still requires captured existing_bucket_policy_json. "
                    "Regenerate after refreshing remediation options or use the Terraform bundle for apply-time merge."
                ),
                action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
                format=format,
                strategy_id=strategy_id,
            )
        return PRBundleResult(
            format=format,
            files=[
                PRBundleFile(
                    path="s3_bucket_require_ssl.yaml",
                    content=_cloudformation_s3_bucket_require_ssl_content(
                        meta,
                        exempt_principals=exempt_principals,
                        existing_policy_json=preservation_policy,
                        preserve_existing_policy=preserve_existing_policy,
                    ),
                )
            ],
            steps=[
                f"Configure AWS credentials for account {meta['account_id']}.",
                (
                    "What changes: merges existing bucket policy statements and adds "
                    "DenyInsecureTransport for the target bucket."
                    if preserve_existing_policy
                    else "What changes: replaces bucket policy statements with SSL-enforcement "
                    "statements including DenyInsecureTransport."
                ),
                "How to access now: HTTPS requirement - clients must use `https://` S3 requests; `http://` requests are denied.",
                (
                    "Deploy template; the custom resource merges existing bucket policy statements "
                    "before applying SSL deny."
                    if preserve_existing_policy
                    else "Deploy template; the custom resource applies SSL deny without preserving "
                    "existing policy statements."
                ),
                f"Verify: `aws s3api get-bucket-policy --bucket {bucket_name} --query Policy --output text` contains DenyInsecureTransport.",
                f"Verify: `curl -I https://{bucket_name}.s3.{meta['region']}.amazonaws.com/<object-key>` succeeds while `curl -I http://{bucket_name}.s3.{meta['region']}.amazonaws.com/<object-key>` is denied.",
                f"Rollback: restore prior policy with `aws s3api put-bucket-policy --bucket {bucket_name} --policy file://pre-remediation-policy.json` if required.",
                "Recompute actions to verify remediation state.",
            ],
        )

    files: list[PRBundleFile] = [
        PRBundleFile(
            path="providers.tf",
            content=_terraform_regional_providers_content(
                meta,
                include_external_provider=apply_time_merge,
            ),
        ),
        PRBundleFile(
            path="s3_bucket_require_ssl.tf",
            content=(
                _terraform_s3_bucket_require_ssl_apply_time_merge_content(
                    meta,
                    exempt_principals=exempt_principals,
                )
                if apply_time_merge
                else _terraform_s3_bucket_require_ssl_content(
                    meta,
                    exempt_principals=exempt_principals,
                    create_bucket_if_missing=create_bucket_if_missing,
                )
            ),
        ),
    ]
    if preservation_policy is not None:
        files.append(
            PRBundleFile(
                path="terraform.auto.tfvars.json",
                content=(
                    json.dumps(
                        {
                            _S3_MIGRATE_POLICY_JSON_KEY: preservation_policy,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ),
            )
        )
    if apply_time_merge:
        files.append(
            PRBundleFile(
                path=AWS_S3_POLICY_FETCH_SCRIPT_PATH,
                content=aws_s3_policy_fetch_script_content(),
            )
        )

    include_policy_capture_helpers = (
        not create_bucket_if_missing
        and preserve_existing_policy
        and (preservation_policy is not None or apply_time_merge)
    )
    rollback_metadata: dict[str, Any] | None = None
    if include_policy_capture_helpers:
        files.extend(
            [
                PRBundleFile(
                    path=AWS_S3_POLICY_CAPTURE_SCRIPT_PATH,
                    content=aws_s3_policy_capture_script_content(),
                ),
                PRBundleFile(
                    path=AWS_S3_POLICY_RESTORE_SCRIPT_PATH,
                    content=aws_s3_policy_restore_script_content(),
                ),
            ]
        )
        rollback_metadata = aws_s3_bundle_rollback_metadata(str(action.id))

    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
        (
            "Review terraform.auto.tfvars.json; existing bucket policy statements were preloaded "
            "for merge-safe preservation."
            if preservation_policy is not None and preserve_existing_policy
            else (
                "Current bucket policy will be fetched and merged at terraform plan/apply time with customer credentials."
                if apply_time_merge and preserve_existing_policy
                else (
                "This bundle will create the missing target bucket with a minimal private baseline before enforcing SSL-only requests."
                if create_bucket_if_missing
                else (
                "No existing bucket policy statements were detected; "
                "existing_bucket_policy_json remains empty."
                if preserve_existing_policy
                else "preserve_existing_policy=false selected; existing bucket policy statements "
                "are not preloaded."
                )
                )
            )
        ),
        *(
            [
                f"Run `BUCKET_NAME={bucket_name} REGION={meta['region']} python3 {AWS_S3_POLICY_CAPTURE_SCRIPT_PATH}` BEFORE terraform apply to snapshot exact bucket policy pre-state to .s3-rollback/policy_snapshot.json.",
            ]
            if include_policy_capture_helpers
            else []
        ),
        "Run `terraform init`, `terraform plan`, and `terraform apply`.",
        *(
            [
                f"Rollback: run `terraform destroy` then `python3 {AWS_S3_POLICY_RESTORE_SCRIPT_PATH}` to restore the captured bucket policy exactly.",
            ]
            if include_policy_capture_helpers
            else []
        ),
        "Validate impacted clients and recompute actions.",
    ]
    result = PRBundleResult(format=format, files=files, steps=steps)
    if rollback_metadata:
        result["metadata"] = rollback_metadata
    return result


def _s3_5_apply_time_merge_requested(resolution: Mapping[str, Any] | None) -> bool:
    if not isinstance(resolution, Mapping):
        return False
    summary = resolution.get("preservation_summary")
    if not isinstance(summary, Mapping):
        return False
    return summary.get("apply_time_merge") is True


def _s3_11_apply_time_merge_requested(resolution: Mapping[str, Any] | None) -> bool:
    if not isinstance(resolution, Mapping):
        return False
    summary = resolution.get("preservation_summary")
    if not isinstance(summary, Mapping):
        return False
    return summary.get("apply_time_merge") is True


def _s3_2_apply_time_merge_requested(resolution: Mapping[str, Any] | None) -> bool:
    if not isinstance(resolution, Mapping):
        return False
    summary = resolution.get("preservation_summary")
    if not isinstance(summary, Mapping):
        return False
    return summary.get("apply_time_merge") is True


def _s3_2_public_policy_scrub_requested(resolution: Mapping[str, Any] | None) -> bool:
    if not isinstance(resolution, Mapping):
        return False
    return str(resolution.get("profile_id") or "").strip() == (
        "s3_bucket_block_public_access_review_public_policy_scrub"
    )


def _generate_for_iam_root_access_key_absent(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
) -> PRBundleResult:
    """Generate executable IAM root access key remediation bundle (terraform only)."""
    meta = _action_meta(action)
    strategy = (strategy_id or "iam_root_key_disable").strip().lower()
    if strategy == "iam_root_key_keep_exception":
        return _generate_for_exception_guidance(action, format, "Keep root access key (exception path)")
    if format == CLOUDFORMATION_FORMAT:
        _raise_pr_bundle_error(
            code="unsupported_format_for_action_type",
            detail=(
                "cloudformation format is not supported for iam_root_access_key_absent. "
                "Generate terraform bundle and apply using root credentials. "
                f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
            ),
            action_type=ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT,
            format=format,
            strategy_id=strategy,
        )

    delete_root_keys = strategy == "iam_root_key_delete"
    provider_meta = dict(meta)
    if provider_meta["region"] == "N/A":
        provider_meta["region"] = "us-east-1"
    files = [
        PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(provider_meta)),
        PRBundleFile(
            path="iam_root_access_key_absent.tf",
            content=_terraform_iam_root_access_key_absent_content(meta, delete_root_keys=delete_root_keys),
        ),
    ]
    mode_label = "delete" if delete_root_keys else "disable"
    steps = [
        (
            f"{ROOT_CREDENTIALS_REQUIRED_MESSAGE} "
            f"Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
        ),
        "Authenticate AWS CLI with root credentials for the target account before apply.",
        "Run `terraform init` and `terraform plan` and confirm root key remediation mode.",
        f"Run `terraform apply` to {mode_label} root access keys.",
        "Validate root account fallback controls (MFA + break-glass process), then recompute actions.",
    ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _generate_for_exception_guidance(
    action: ActionLike,
    format: PRBundleFormat,
    title: str,
) -> NoReturn:
    """Exception-only strategy selections are not executable IaC bundles."""
    _raise_pr_bundle_error(
        code="exception_strategy_requires_exception_workflow",
        detail=(
            f"Strategy '{title}' is exception-only and does not generate executable IaC. "
            "Use the action exception workflow instead of PR bundle generation."
        ),
        action_type=(action.action_type or "").strip().lower(),
        format=format,
    )


def _terraform_aws_config_enabled_content(
    meta: dict[str, str],
    strategy: str,
    strategy_inputs: dict[str, Any],
) -> str:
    bucket, kms_key_arn, create_local_bucket, overwrite_recording_group = _resolve_aws_config_defaults(
        account_id=meta["account_id"],
        region=meta["region"],
        strategy=strategy,
        strategy_inputs=strategy_inputs,
    )
    create_local_bucket_text = "true" if create_local_bucket else "false"
    overwrite_recording_group_text = "true" if overwrite_recording_group else "false"
    return f"""# AWS Config enablement - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]}
# Control: {meta["control_id"]}

variable "remediation_region" {{
  type        = string
  default     = "{meta["region"]}"
  description = "Region for AWS Config enablement."
}}

variable "delivery_bucket_name" {{
  type        = string
  default     = "{bucket}"
  description = "S3 bucket for AWS Config delivery."
}}

variable "config_role_arn" {{
  type        = string
  default     = "arn:aws:iam::{meta["account_id"]}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig"
  description = "IAM role ARN used by AWS Config recorder."
}}

variable "kms_key_arn" {{
  type        = string
  default     = "{kms_key_arn}"
  description = "Optional KMS key ARN for Config delivery channel."
}}

variable "create_local_bucket" {{
  type        = bool
  default     = {create_local_bucket_text}
  description = "When true, create delivery bucket in this account if missing."
}}

variable "overwrite_recording_group" {{
  type        = bool
  default     = {overwrite_recording_group_text}
  description = "When true, overwrite an existing recorder recordingGroup with all-supported mode."
}}

resource "null_resource" "aws_config_enablement" {{
  triggers = {{
    region                    = var.remediation_region
    delivery_bucket           = var.delivery_bucket_name
    config_role_arn           = var.config_role_arn
    kms_key_arn               = var.kms_key_arn
    create_local_bucket       = tostring(var.create_local_bucket)
    overwrite_recording_group = tostring(var.overwrite_recording_group)
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
export REGION="${{var.remediation_region}}"
export BUCKET="${{var.delivery_bucket_name}}"
export ROLE_ARN="${{var.config_role_arn}}"
export KMS_ARN="${{var.kms_key_arn}}"
export CREATE_LOCAL_BUCKET="${{var.create_local_bucket}}"
export OVERWRITE_RECORDING_GROUP="${{var.overwrite_recording_group}}"
export ACCOUNT_ID="{meta["account_id"]}"
export ROLLBACK_DIR="{AWS_CONFIG_ROLLBACK_DIR}"

python3 ./{AWS_CONFIG_APPLY_SCRIPT_PATH}
EOT
  }}
}}
"""


def _cloudformation_aws_config_enabled_content(
    meta: dict[str, str],
    strategy: str,
    strategy_inputs: dict[str, Any],
) -> str:
    bucket, kms_key_arn, create_bucket, overwrite_recording_group = _resolve_aws_config_defaults(
        account_id=meta["account_id"],
        region=meta["region"],
        strategy=strategy,
        strategy_inputs=strategy_inputs,
    )
    overwrite_recording_group_default = "true" if overwrite_recording_group else "false"
    bucket_resource = ""
    bucket_ref = "ConfigDeliveryBucket"
    if create_bucket:
        bucket_resource = f"""
  ConfigDeliveryBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: "{bucket}"
"""
    else:
        bucket_ref = "DeliveryBucketName"
    kms_line = f"      S3KmsKeyArn: {kms_key_arn}\n" if kms_key_arn else ""
    parameter_block = f"""
  OverwriteRecordingGroup:
    Type: String
    Default: "{overwrite_recording_group_default}"
    AllowedValues:
      - "true"
      - "false"
    Description: Set true only when you want to overwrite an existing recorder recording group with all-supported mode.
"""
    if not create_bucket:
        parameter_block = f"""
  DeliveryBucketName:
    Type: String
    Default: "{bucket}"
    Description: Centralized S3 bucket for AWS Config delivery
{parameter_block}"""
    return f"""AWSTemplateFormatVersion: "2010-09-09"
Description: "Enable AWS Config recording and delivery channel."
Parameters:{parameter_block}
Conditions:
  ShouldOverwriteRecordingGroup: !Equals [!Ref OverwriteRecordingGroup, "true"]
Resources:{bucket_resource}
  ConfigRecorder:
    Type: AWS::Config::ConfigurationRecorder
    Properties:
      Name: security-autopilot-recorder
      RoleARN: arn:aws:iam::{meta["account_id"]}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig
      RecordingGroup: !If
        - ShouldOverwriteRecordingGroup
        - AllSupported: true
          IncludeGlobalResourceTypes: true
        - !Ref AWS::NoValue
  ConfigDeliveryChannel:
    Type: AWS::Config::DeliveryChannel
    Properties:
      Name: security-autopilot-delivery-channel
      S3BucketName: !Ref {bucket_ref}
{kms_line if kms_line else ""}
Outputs:
  ConfigRecorderOverwriteRecordingGroup:
    Description: Recorder overwrite toggle (false preserves existing recording-group scope when possible).
    Value: !Ref OverwriteRecordingGroup
  ConfigDeliveryChannelTargetBucket:
    Description: Existing delivery channels with this name will target this bucket after deploy.
    Value: !Sub "${{{bucket_ref}}}"
"""


def _terraform_ssm_block_public_sharing_content(meta: dict[str, str]) -> str:
    setting_id = (
        f"arn:aws:ssm:{meta['region']}:{meta['account_id']}:"
        "servicesetting/ssm/documents/console/public-sharing-permission"
    )
    return f"""# SSM block public document sharing - Action: {meta["action_id"]}
resource "aws_ssm_service_setting" "security_autopilot" {{
  setting_id    = "{setting_id}"
  setting_value = "Disable"
}}
"""


def _cloudformation_ssm_block_public_sharing_content(meta: dict[str, str]) -> str:
    setting_id = (
        f"arn:aws:ssm:{meta['region']}:{meta['account_id']}:"
        "servicesetting/ssm/documents/console/public-sharing-permission"
    )
    return f"""AWSTemplateFormatVersion: "2010-09-09"
Description: "Block public SSM document sharing via custom resource."
Resources:
  SSMServiceSettingFunctionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: ssm-service-setting
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - ssm:GetServiceSetting
                  - ssm:UpdateServiceSetting
                Resource: "*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  SSMServiceSettingFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt SSMServiceSettingFunctionRole.Arn
      Code:
        ZipFile: |
          import boto3
          import cfnresponse

          def handler(event, context):
              if event.get("RequestType") == "Delete":
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "SSMSetting")
                  return
              ssm = boto3.client("ssm")
              ssm.update_service_setting(
                  SettingId="{setting_id}",
                  SettingValue="Disable"
              )
              cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "SSMSetting")
  SSMPublicSharingSetting:
    Type: Custom::SSMServiceSetting
    Properties:
      ServiceToken: !GetAtt SSMServiceSettingFunction.Arn
"""


def _terraform_ebs_snapshot_block_public_access_content(meta: dict[str, str], state: str) -> str:
    return f"""# EBS snapshot block public access - Action: {meta["action_id"]}
resource "aws_ebs_snapshot_block_public_access" "security_autopilot" {{
  state = "{state}"
}}
"""


def _cloudformation_ebs_snapshot_block_public_access_content(meta: dict[str, str], state: str) -> str:
    return f"""AWSTemplateFormatVersion: "2010-09-09"
Description: "Configure EBS snapshot block public access."
Resources:
  EbsSnapshotBlockPublicAccess:
    Type: AWS::EC2::SnapshotBlockPublicAccess
    Properties:
      State: {state}
"""


def _terraform_ebs_default_encryption_content(
    meta: dict[str, str],
    customer_kms: bool,
    kms_key_arn: str,
) -> str:
    kms_block = ""
    if customer_kms:
        kms_arn = kms_key_arn or "REPLACE_KMS_KEY_ARN"
        kms_block = f"""
resource "aws_ebs_default_kms_key" "security_autopilot" {{
  key_arn = "{kms_arn}"
}}
"""
    return f"""# EBS default encryption - Action: {meta["action_id"]}
resource "aws_ebs_encryption_by_default" "security_autopilot" {{
  enabled = true
}}
{kms_block}
"""


def _cloudformation_ebs_default_encryption_content(
    meta: dict[str, str],
    customer_kms: bool,
    kms_key_arn: str,
) -> str:
    kms_update = ""
    if customer_kms:
        kms_update = f"""
              ec2.modify_ebs_default_kms_key_id(KmsKeyId="{kms_key_arn or 'REPLACE_KMS_KEY_ARN'}")
"""
    return f"""AWSTemplateFormatVersion: "2010-09-09"
Description: "Enable EBS default encryption via custom resource."
Resources:
  EbsDefaultEncryptionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: ebs-default-encryption
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - ec2:EnableEbsEncryptionByDefault
                  - ec2:GetEbsEncryptionByDefault
                  - ec2:GetEbsDefaultKmsKeyId
                  - ec2:ModifyEbsDefaultKmsKeyId
                Resource: "*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  EbsDefaultEncryptionFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt EbsDefaultEncryptionRole.Arn
      Code:
        ZipFile: |
          import boto3
          import cfnresponse

          def handler(event, context):
              if event.get("RequestType") == "Delete":
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "EbsDefaultEncryption")
                  return
              ec2 = boto3.client("ec2")
              ec2.enable_ebs_encryption_by_default()
{kms_update if kms_update else ""}
              cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "EbsDefaultEncryption")
  EbsDefaultEncryption:
    Type: Custom::EbsDefaultEncryption
    Properties:
      ServiceToken: !GetAtt EbsDefaultEncryptionFunction.Arn
"""


def _terraform_s3_bucket_require_ssl_content(
    meta: dict[str, str],
    exempt_principals: list[str],
    *,
    create_bucket_if_missing: bool = False,
) -> str:
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    exempt_principals_json = json.dumps(exempt_principals)
    create_bucket_if_missing_text = "true" if create_bucket_if_missing else "false"
    create_bucket_blocks = _terraform_minimal_private_bucket_blocks(
        resource_suffix="target_bucket",
        bucket_name_ref='local.target_bucket_name',
        count_expr="var.create_bucket_if_missing ? 1 : 0",
    )
    return f"""# Enforce SSL-only S3 requests - Action: {meta["action_id"]}
locals {{
  target_bucket_name = "{bucket}"
}}

variable "create_bucket_if_missing" {{
  type        = bool
  default     = {create_bucket_if_missing_text}
  description = "When true, create the target bucket with a minimal private baseline before enforcing SSL-only requests."
}}

variable "existing_bucket_policy_json" {{
  type        = string
  default     = ""
  description = "Optional existing bucket policy JSON for merge-safe preservation."
}}

variable "exempt_principal_arns" {{
  type        = list(string)
  default     = {exempt_principals_json}
  description = "Optional IAM principal ARNs exempted from strict SSL deny."
}}

{create_bucket_blocks}

data "aws_iam_policy_document" "required_ssl" {{
  statement {{
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {{
      type        = "*"
      identifiers = ["*"]
    }}
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${{local.target_bucket_name}}",
      "arn:aws:s3:::${{local.target_bucket_name}}/*",
    ]
    condition {{
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }}
  }}

  dynamic "statement" {{
    for_each = length(var.exempt_principal_arns) == 0 ? [] : [var.exempt_principal_arns]
    content {{
      sid    = "AllowExemptPrincipals"
      effect = "Allow"
      principals {{
        type        = "AWS"
        identifiers = statement.value
      }}
      actions = ["s3:*"]
      resources = [
        "arn:aws:s3:::${{local.target_bucket_name}}",
        "arn:aws:s3:::${{local.target_bucket_name}}/*",
      ]
    }}
  }}
}}

data "aws_iam_policy_document" "merged_policy" {{
  source_policy_documents   = var.existing_bucket_policy_json == "" ? [] : [var.existing_bucket_policy_json]
  override_policy_documents = [data.aws_iam_policy_document.required_ssl.json]
}}

resource "aws_s3_bucket_policy" "security_autopilot" {{
  bucket = local.target_bucket_name
  policy = data.aws_iam_policy_document.merged_policy.json
  depends_on = [{_terraform_minimal_private_bucket_dependency("target_bucket")}]
}}
"""


def _terraform_s3_bucket_require_ssl_apply_time_merge_content(
    meta: dict[str, str],
    exempt_principals: list[str],
) -> str:
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    exempt_principals_json = json.dumps(exempt_principals)
    return f"""# Enforce SSL-only S3 requests - Action: {meta["action_id"]}
locals {{
  target_bucket_name = "{bucket}"
}}

variable "exempt_principal_arns" {{
  type        = list(string)
  default     = {exempt_principals_json}
  description = "Optional IAM principal ARNs exempted from strict SSL deny."
}}

data "external" "existing_policy" {{
  program = ["python3", "${{path.module}}/{AWS_S3_POLICY_FETCH_SCRIPT_PATH}"]

  query = {{
    bucket_name = local.target_bucket_name
    region      = "{meta["region"]}"
  }}
}}

locals {{
  existing_policy_document = try(
    jsondecode(lookup(data.external.existing_policy.result, "policy_json", "")),
    {{
      Version   = "2012-10-17"
      Statement = []
    }}
  )
  existing_policy_id = try(local.existing_policy_document.Id, null)
  existing_policy_statements = try(local.existing_policy_document.Statement, [])
  filtered_existing_policy_statements = [
    for stmt in local.existing_policy_statements : stmt
    if !(
      lower(try(tostring(stmt.Sid), "")) == "denyinsecuretransport" ||
      (
        lower(try(tostring(stmt.Effect), "")) == "deny" &&
        lower(try(tostring(stmt.Condition.Bool["aws:SecureTransport"]), "")) == "false"
      )
    )
  ]
  filtered_existing_policy_document = merge(
    {{
      Version   = try(tostring(local.existing_policy_document.Version), "2012-10-17")
      Statement = local.filtered_existing_policy_statements
    }},
    local.existing_policy_id == null ? {{}} : {{ Id = local.existing_policy_id }}
  )
}}

data "aws_iam_policy_document" "required_ssl" {{
  statement {{
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {{
      type        = "*"
      identifiers = ["*"]
    }}
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${{local.target_bucket_name}}",
      "arn:aws:s3:::${{local.target_bucket_name}}/*",
    ]
    condition {{
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }}
  }}

  dynamic "statement" {{
    for_each = length(var.exempt_principal_arns) == 0 ? [] : [var.exempt_principal_arns]
    content {{
      sid    = "AllowExemptPrincipals"
      effect = "Allow"
      principals {{
        type        = "AWS"
        identifiers = statement.value
      }}
      actions = ["s3:*"]
      resources = [
        "arn:aws:s3:::${{local.target_bucket_name}}",
        "arn:aws:s3:::${{local.target_bucket_name}}/*",
      ]
    }}
  }}
}}

data "aws_iam_policy_document" "merged_policy" {{
  source_policy_documents   = [jsonencode(local.filtered_existing_policy_document)]
  override_policy_documents = [data.aws_iam_policy_document.required_ssl.json]
}}

resource "aws_s3_bucket_policy" "security_autopilot" {{
  bucket = local.target_bucket_name
  policy = data.aws_iam_policy_document.merged_policy.json
}}
"""


def _cloudformation_s3_bucket_require_ssl_content(
    meta: dict[str, str],
    exempt_principals: list[str],
    existing_policy_json: str | None = None,
    preserve_existing_policy: bool = True,
) -> str:
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    existing_policy_literal = json.dumps(existing_policy_json or "")
    preserve_existing_policy_literal = "true" if preserve_existing_policy else "false"
    exemptions = "      ExemptPrincipalArns: []"
    if exempt_principals:
        items = "\n".join(f"        - {json.dumps(principal)}" for principal in exempt_principals)
        exemptions = f"""
      ExemptPrincipalArns:
{items}
"""
    return f"""AWSTemplateFormatVersion: "2010-09-09"
Description: "Enforce SSL-only S3 requests."
Resources:
  S3SslPolicyMergeRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: s3-ssl-policy-merge
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - s3:GetBucketPolicy
                  - s3:PutBucketPolicy
                Resource:
                  - "arn:aws:s3:::{bucket}"
                  - "arn:aws:s3:::{bucket}/*"
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "*"
  S3SslPolicyMergeFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.12
      Handler: index.handler
      Timeout: 120
      Role: !GetAtt S3SslPolicyMergeRole.Arn
      Code:
        ZipFile: |
          import json
          import boto3
          import cfnresponse
          from botocore.exceptions import ClientError

          def _normalize_statements(statements):
              if isinstance(statements, list):
                  return statements
              if isinstance(statements, dict):
                  return [statements]
              return []

          def _to_bool(value, default=True):
              if isinstance(value, bool):
                  return value
              if isinstance(value, str):
                  normalized = value.strip().lower()
                  if normalized in {{"1", "true", "yes", "y", "on"}}:
                      return True
                  if normalized in {{"0", "false", "no", "n", "off"}}:
                      return False
              if isinstance(value, int):
                  if value == 1:
                      return True
                  if value == 0:
                      return False
              return default

          def _load_existing_policy(s3_client, bucket_name, preloaded_json, preserve_existing_policy):
              if not preserve_existing_policy:
                  return {{"Version": "2012-10-17", "Statement": []}}
              if preloaded_json:
                  parsed = json.loads(preloaded_json)
                  if isinstance(parsed, dict):
                      return parsed
              try:
                  response = s3_client.get_bucket_policy(Bucket=bucket_name)
                  policy_doc = response.get("Policy", "")
                  if policy_doc:
                      parsed = json.loads(policy_doc)
                      if isinstance(parsed, dict):
                          return parsed
              except ClientError as exc:
                  code = exc.response.get("Error", {{}}).get("Code", "")
                  if code != "NoSuchBucketPolicy":
                      raise
              return {{"Version": "2012-10-17", "Statement": []}}

          def handler(event, context):
              request_type = event.get("RequestType")
              if request_type == "Delete":
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}}, "S3SslPolicyMerge")
                  return
              try:
                  props = event.get("ResourceProperties", {{}})
                  bucket = (props.get("BucketName") or "").strip()
                  if not bucket:
                      raise ValueError("BucketName is required.")

                  exempt_principals = props.get("ExemptPrincipalArns") or []
                  if isinstance(exempt_principals, str):
                      exempt_principals = [exempt_principals]
                  elif not isinstance(exempt_principals, list):
                      exempt_principals = []

                  preserve_existing_policy = _to_bool(
                      props.get("PreserveExistingPolicy", True),
                      default=True,
                  )
                  preloaded_json = (props.get("ExistingBucketPolicyJson") or "").strip()
                  s3 = boto3.client("s3")
                  existing = _load_existing_policy(
                      s3,
                      bucket,
                      preloaded_json,
                      preserve_existing_policy,
                  )
                  statements = _normalize_statements(existing.get("Statement"))

                  preserved = [
                      statement
                      for statement in statements
                      if statement.get("Sid") not in {{"DenyInsecureTransport", "AllowExemptPrincipals"}}
                  ]
                  preserved.append(
                      {{
                          "Sid": "DenyInsecureTransport",
                          "Effect": "Deny",
                          "Principal": "*",
                          "Action": "s3:*",
                          "Resource": [
                              "arn:aws:s3:::" + bucket,
                              "arn:aws:s3:::" + bucket + "/*",
                          ],
                          "Condition": {{"Bool": {{"aws:SecureTransport": "false"}}}},
                      }}
                  )
                  if exempt_principals:
                      preserved.append(
                          {{
                              "Sid": "AllowExemptPrincipals",
                              "Effect": "Allow",
                              "Principal": {{"AWS": exempt_principals}},
                              "Action": "s3:*",
                              "Resource": [
                                  "arn:aws:s3:::" + bucket,
                                  "arn:aws:s3:::" + bucket + "/*",
                              ],
                          }}
                      )

                  merged = {{
                      "Version": existing.get("Version", "2012-10-17"),
                      "Statement": preserved,
                  }}
                  s3.put_bucket_policy(
                      Bucket=bucket,
                      Policy=json.dumps(merged, separators=(",", ":")),
                  )
                  cfnresponse.send(
                      event,
                      context,
                      cfnresponse.SUCCESS,
                      {{"StatementCount": len(preserved)}},
                      "S3SslPolicyMerge",
                  )
              except Exception as exc:
                  cfnresponse.send(
                      event,
                      context,
                      cfnresponse.FAILED,
                      {{"Error": str(exc)}},
                      "S3SslPolicyMerge",
                  )
  ApplyS3SslPolicyMerge:
    Type: Custom::S3SslPolicyMerge
    Properties:
      ServiceToken: !GetAtt S3SslPolicyMergeFunction.Arn
      BucketName: "{bucket}"
      ExistingBucketPolicyJson: {existing_policy_literal}
      PreserveExistingPolicy: {preserve_existing_policy_literal}
{exemptions if exemptions else ""}
"""


def _terraform_iam_root_access_key_absent_content(meta: dict[str, str], delete_root_keys: bool) -> str:
    """Terraform bundle content for root access key disable/delete workflow."""
    delete_flag = "true" if delete_root_keys else "false"
    mode = "delete" if delete_root_keys else "disable"
    return f"""# IAM root access key remediation - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]}
# Control: {meta["control_id"]}
# NOTE: This bundle requires AWS root credentials for the target account.
# NOTE: Runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}

variable "expected_account_id" {{
  type        = string
  default     = "{meta["account_id"]}"
  description = "Target account ID expected by this remediation."
}}

variable "delete_root_keys" {{
  type        = bool
  default     = {delete_flag}
  description = "When true, delete root keys after disabling. When false, disable only."
}}

resource "null_resource" "iam_root_access_key_absent" {{
  triggers = {{
    action_id           = "{meta["action_id"]}"
    expected_account_id = var.expected_account_id
    delete_root_keys    = tostring(var.delete_root_keys)
  }}

  provisioner "local-exec" {{
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
CALLER_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
CALLER_ARN="$(aws sts get-caller-identity --query Arn --output text)"
if [ "$CALLER_ACCOUNT" != "${{var.expected_account_id}}" ]; then
  echo "ERROR: caller account does not match expected account ID."
  exit 1
fi
case "$CALLER_ARN" in
  arn:aws:iam::*:root) ;;
  *)
    echo "ERROR: root credentials are required to {mode} root access keys."
    exit 1
    ;;
esac
KEY_IDS="$(aws iam list-access-keys --query 'AccessKeyMetadata[].AccessKeyId' --output text || true)"
if [ -z "$KEY_IDS" ] || [ "$KEY_IDS" = "None" ]; then
  echo "No root access keys found."
  exit 0
fi
for key_id in $KEY_IDS; do
  aws iam update-access-key --access-key-id "$key_id" --status Inactive >/dev/null
  if [ "${{var.delete_root_keys}}" = "true" ]; then
    aws iam delete-access-key --access-key-id "$key_id" >/dev/null
  fi
done
EOT
  }}
}}
"""


# ---------------------------------------------------------------------------
# Unsupported / pr_only / fallback
# ---------------------------------------------------------------------------


def _generate_unsupported(
    action: ActionLike | None,
    format: PRBundleFormat,
) -> NoReturn:
    """
    Raise a structured error for unsupported or missing action types.
    """
    action_type = (action.action_type or "pr_only").strip() if action else "pr_only"
    _raise_pr_bundle_error(
        code="unsupported_action_type",
        detail=f"Action type '{action_type}' is not supported for PR bundle generation.",
        action_type=action_type,
        format=format,
    )


__all__ = [
    "ActionLike",
    "PRBundleErrorPayload",
    "PRBundleGenerationError",
    "PRBundleFile",
    "PRBundleResult",
    "PRBundleFormat",
    "TERRAFORM_FORMAT",
    "CLOUDFORMATION_FORMAT",
    "ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS",
    "ACTION_TYPE_ENABLE_SECURITY_HUB",
    "ACTION_TYPE_ENABLE_GUARDDUTY",
    "ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS",
    "ACTION_TYPE_S3_BUCKET_ENCRYPTION",
    "ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING",
    "ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION",
    "ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS",
    "ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS",
    "ACTION_TYPE_CLOUDTRAIL_ENABLED",
    "ACTION_TYPE_AWS_CONFIG_ENABLED",
    "ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING",
    "ACTION_TYPE_EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS",
    "ACTION_TYPE_EBS_DEFAULT_ENCRYPTION",
    "ACTION_TYPE_S3_BUCKET_REQUIRE_SSL",
    "ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT",
    "ACTION_TYPE_PR_ONLY",
    "PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3",
    "SUPPORTED_ACTION_TYPES",
    "generate_pr_bundle",
]
