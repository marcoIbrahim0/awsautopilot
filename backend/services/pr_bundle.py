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
from typing import Any, Literal, Protocol, TypedDict

# ---------------------------------------------------------------------------
# Contract: return shape and action interface
# ---------------------------------------------------------------------------

PRBundleFormat = Literal["terraform", "cloudformation"]

TERRAFORM_FORMAT: PRBundleFormat = "terraform"
CLOUDFORMATION_FORMAT: PRBundleFormat = "cloudformation"


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


def generate_pr_bundle(
    action: ActionLike | None,
    format: str = "terraform",
    strategy_id: str | None = None,
    strategy_inputs: dict[str, Any] | None = None,
    risk_snapshot: dict[str, Any] | None = None,
    variant: str | None = None,
) -> PRBundleResult:
    """
    Generate a PR bundle for the given action by dispatching on action_type.

    Loads action context (action_type, account_id, region, target_id, title,
    control_id) from the provided action object and delegates to the
    appropriate generator. Unsupported or missing action yields a guidance
    placeholder.

    Args:
        action: Action instance (e.g. run.action from worker). Must have
            action_type, account_id, region, target_id, title, control_id.
            If None, returns unsupported-guidance bundle.
        format: "terraform" or "cloudformation". Default terraform.
        strategy_id: Optional strategy identifier selected in remediation flow.
        strategy_inputs: Optional strategy input values.
        risk_snapshot: Optional evaluated risk snapshot to append in README.
        variant: Legacy variant string. When provided, mapped to strategy behavior.

    Returns:
        Dict with keys: format, files (list of { path, content }), steps (list of strings).
    """
    normalized_format = _normalize_format(format)

    if action is None:
        return _maybe_append_terraform_readme(_generate_unsupported(None, normalized_format))

    action_type = (action.action_type or "").strip().lower()
    if action_type not in SUPPORTED_ACTION_TYPES:
        return _maybe_append_terraform_readme(_generate_unsupported(action, normalized_format))

    # Dispatch: all 7 generators (9.2–9.5, 9.9–9.12)
    result: PRBundleResult
    effective_strategy_id = (strategy_id or "").strip().lower() or None
    normalized_variant = (variant or "").strip().lower()
    if normalized_variant == PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3 and not effective_strategy_id:
        effective_strategy_id = "s3_migrate_cloudfront_oac_private"

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
        )
    elif action_type == ACTION_TYPE_S3_BUCKET_ENCRYPTION:
        result = _generate_for_s3_bucket_encryption(action, normalized_format)
    elif action_type == ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING:
        result = _generate_for_s3_bucket_access_logging(action, normalized_format)
    elif action_type == ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION:
        result = _generate_for_s3_bucket_lifecycle_configuration(action, normalized_format)
    elif action_type == ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS:
        result = _generate_for_s3_bucket_encryption_kms(action, normalized_format)
    elif action_type == ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS:
        result = _generate_for_sg_restrict_public_ports(action, normalized_format)
    elif action_type == ACTION_TYPE_CLOUDTRAIL_ENABLED:
        result = _generate_for_cloudtrail_enabled(action, normalized_format)
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
        )
    elif action_type == ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT:
        result = _generate_for_iam_root_access_key_absent(
            action,
            normalized_format,
            strategy_id=effective_strategy_id,
        )
    else:
        result = _generate_unsupported(action, normalized_format)

    return _maybe_append_terraform_readme(
        result,
        risk_snapshot=risk_snapshot,
        strategy_id=effective_strategy_id,
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

S3.2 guardrail (read before apply)
----------------------------------
- This bundle is control-level hardening: it enforces S3 Block Public Access on a bucket.
- It is NOT a full CloudFront + OAC + private S3 migration.
- Applying this can break workloads that rely on public S3 access (public object URLs, website endpoint, public ACLs/policies).

Pre-apply checks (required)
---------------------------
- Capture current bucket policy and ACL.
- Confirm whether bucket website hosting is enabled.
- Confirm whether this bucket is a log sink (CloudTrail / Config / ELB / CloudFront / S3 access logs).
- Confirm encryption mode (SSE-S3 vs SSE-KMS). If SSE-KMS, identify required KMS key policy updates.
- Identify cross-account principals and access points that need to keep access.
- If available, review CloudTrail S3 data events for recent GetObject/ListBucket/PutObject callers.

Apply sequence (recommended)
----------------------------
- Deploy CloudFront + OAC + bucket policy updates (and KMS policy updates if needed).
- Update clients/apps to use CloudFront instead of direct S3 public access.
- Then apply S3 Block Public Access.
- Monitor for AccessDenied/KMS errors and CloudFront 4xx spikes.

Rollback plan
-------------
- Keep a backup of prior bucket policy/ACL and restore quickly if needed.
- Temporarily re-enable only minimum required access to recover service.
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
- This bundle creates CloudFront distribution + OAC, enforces S3 Block Public Access, and applies a bucket policy for CloudFront read access.
- It is intended to replace direct public S3 access with CloudFront.

Before apply
------------
- If this bucket already has required policy statements, set variable existing_bucket_policy_json so they are preserved.
- If additional internal/cross-account roles need read access, set additional_read_principal_arns.
- If objects use SSE-KMS, confirm KMS key policy allows required principals.

After apply
-----------
- Update clients/apps to use the CloudFront domain output.
- Validate key object paths and monitor CloudFront 4xx/S3 AccessDenied/KMS AccessDenied.
"""


def _maybe_append_terraform_readme(
    result: PRBundleResult,
    risk_snapshot: dict[str, Any] | None = None,
    strategy_id: str | None = None,
) -> PRBundleResult:
    """Append README.txt to Terraform bundles so users see credential/risk instructions."""
    if result.get("format") != TERRAFORM_FORMAT or not result.get("files"):
        return result
    files = list(result["files"])
    readme = _terraform_readme_content()
    if any(f.get("path") == "s3_bucket_block_public_access.tf" for f in files):
        readme += _terraform_s3_bucket_block_guardrails_content()
    if any(f.get("path") == "s3_cloudfront_oac_private_s3.tf" for f in files):
        readme += _terraform_s3_cloudfront_oac_private_guardrails_content()
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
    return PRBundleResult(format=result["format"], files=files, steps=result["steps"])


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
        }
    return {
        "action_id": str(action.id),
        "action_title": (action.title or "Remediation").replace("\n", " ").strip()[:200],
        "account_id": action.account_id or "",
        "region": action.region or "N/A",
        "control_id": action.control_id or "",
        "target_id": (action.target_id or "").strip()[:512],
    }


def _s3_bucket_name_from_target_id(target_id: str) -> str:
    """
    Extract S3 bucket name from target_id.
    target_id may be: composite (account|region|arn:aws:s3:::bucketname|control) or plain ARN/bucket name.
    Returns the bucket name only (e.g. demomarcoss) or REPLACE_BUCKET_NAME if not parseable.
    """
    if not (target_id or "").strip():
        return "REPLACE_BUCKET_NAME"
    tid = (target_id or "").strip()
    if "arn:aws:s3:::" in tid:
        # Take the segment that contains the ARN (e.g. from composite or standalone)
        for part in tid.split("|"):
            part = part.strip()
            if "arn:aws:s3:::" in part:
                rest = part.split("arn:aws:s3:::")[-1]
                bucket = rest.split("/")[0].strip()
                if bucket:
                    return bucket
        rest = tid.split("arn:aws:s3:::")[-1]
        bucket = rest.split("/")[0].split("|")[0].strip()
        if bucket:
            return bucket
    if "|" in tid:
        return "REPLACE_BUCKET_NAME"
    return tid[:512] or "REPLACE_BUCKET_NAME"


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

    return "REPLACE_SECURITY_GROUP_ID"


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
      version = ">= 4.0"
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
# 9.2 S3 account-level: No native CF resource; valid YAML + CLI instructions.
# 9.3 Security Hub: AWS::SecurityHub::Hub. 9.4 GuardDuty: AWS::GuardDuty::Detector.
# 9.9 S3 bucket block: AWS::S3::Bucket + PublicAccessBlockConfiguration.
# 9.10 S3 bucket encryption: AWS::S3::Bucket + BucketEncryption.
# 9.11 SG restrict: AWS::EC2::SecurityGroupIngress (22/3389).
# 9.12 CloudTrail: AWS::CloudTrail::Trail. All templates valid YAML and applyable.
# ---------------------------------------------------------------------------


def _cloudformation_s3_content(meta: dict[str, str]) -> str:
    """Step 9.5: Valid CloudFormation template for S3 Block Public Access.

    CloudFormation does not support account-level S3 Block Public Access. This
    template is valid YAML with a placeholder resource and Description/Metadata
    instructing the user to use Terraform or the AWS CLI command.
    """
    account_id = meta["account_id"]
    return f"""# S3 Block Public Access (account-level) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {account_id}
# Control: {meta["control_id"]}
#
# NOTE: CloudFormation does not support account-level S3 Block Public Access.
# Use the Terraform bundle (s3_block_public_access.tf) or run the CLI command
# in the Description below.

AWSTemplateFormatVersion: "2010-09-09"
Description: |
  S3 Block Public Access (account-level) - Security Autopilot remediation.
  CloudFormation has no native resource for account-level S3 Block Public Access.
  Use Terraform (s3_block_public_access.tf) or run:
  aws s3control put-public-access-block --account-id {account_id or "<ACCOUNT_ID>"} --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  This stack creates a placeholder resource only; run the CLI command for remediation.
Metadata:
  SecurityAutopilot:
    ActionId: "{meta["action_id"]}"
    ControlId: "{meta["control_id"]}"
    RemediationCLI: "aws s3control put-public-access-block --account-id <ID> --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
Parameters:
  AccountId:
    Type: String
    Default: "{account_id or ""}"
    Description: AWS account ID (for reference; use in CLI command in Description).
Resources:
  PlaceholderNoOp:
    Type: AWS::CloudFormation::WaitConditionHandle
    Description: Placeholder so template is valid; account-level S3 block uses CLI or Terraform.
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
      version = ">= 4.0"
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
      version = ">= 4.0"
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


def _generate_for_s3_bucket_block_public_access(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for s3_bucket_block_public_access (per bucket, S3.2). Step 9.9."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="s3_bucket_block_public_access.yaml",
                content=_cloudformation_s3_bucket_block_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "IMPORTANT: this bundle is control hardening (Block Public Access), not a complete CloudFront+OAC migration.",
            "Inventory dependencies first (website hosting, log delivery, cross-account/service principals, KMS if SSE-KMS).",
            "Set Parameter BucketName to the target bucket (or use default).",
            "Validate the template and create/update the stack.",
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


def _generate_for_s3_cloudfront_oac_private(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """
    Generate IaC for real migration path: CloudFront + OAC + private S3 (S3.2).

    This variant is selected explicitly from the remediation flow and produces
    runnable Terraform for a safer public content pattern.
    """
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])

    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="README.yaml",
                content=(
                    f"# S3.2 migration variant requested for action {meta['action_id']}\n"
                    "# CloudFormation bundle is not implemented for this variant yet.\n"
                    "# Use Terraform format to generate CloudFront + OAC + private S3 resources.\n"
                ),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Regenerate this remediation in Terraform format.",
            "Apply Terraform resources (CloudFront + OAC + private S3 hardening).",
            "Recompute actions after validation.",
        ]
        return PRBundleResult(format=format, files=files, steps=steps)

    files = [
        PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
        PRBundleFile(
            path="s3_cloudfront_oac_private_s3.tf",
            content=_terraform_s3_cloudfront_oac_private_content(meta),
        ),
    ]
    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {region}.",
        f"Review variables in s3_cloudfront_oac_private_s3.tf (target bucket: {bucket_name}).",
        "If needed, set existing_bucket_policy_json and additional_read_principal_arns before apply.",
        "Run `terraform init` and `terraform plan`.",
        "Run `terraform apply` to create CloudFront+OAC and enforce private S3 access.",
        "Switch clients/apps to CloudFront domain output and validate traffic.",
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


def _terraform_s3_cloudfront_oac_private_content(meta: dict[str, str]) -> str:
    """Terraform for S3.2 migration variant: CloudFront + OAC + private S3."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3.2 migration variant (CloudFront + OAC + private S3) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

locals {{
  bucket_name = "{bucket}"
  oac_name    = substr("security-autopilot-oac-${{substr(md5(local.bucket_name), 0, 8)}}", 0, 64)
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

variable "additional_read_principal_arns" {{
  type        = list(string)
  description = "Optional IAM principal ARNs that still require direct S3 GetObject access."
  default     = []
}}

data "aws_s3_bucket" "target" {{
  bucket = local.bucket_name
}}

resource "aws_cloudfront_origin_access_control" "security_autopilot" {{
  name                              = local.oac_name
  description                       = "OAC for Security Autopilot remediation"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}}

resource "aws_cloudfront_distribution" "security_autopilot" {{
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Security Autopilot migration for ${{local.bucket_name}}"
  default_root_object = var.default_root_object
  price_class         = var.price_class

  origin {{
    domain_name              = data.aws_s3_bucket.target.bucket_regional_domain_name
    origin_id                = "s3-${{local.bucket_name}}"
    origin_access_control_id = aws_cloudfront_origin_access_control.security_autopilot.id
  }}

  default_cache_behavior {{
    target_origin_id       = "s3-${{local.bucket_name}}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true
    cache_policy_id        = var.cache_policy_id
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
  source_policy_documents = var.existing_bucket_policy_json == "" ? [] : [var.existing_bucket_policy_json]

  statement {{
    sid    = "AllowCloudFrontReadOnly"
    effect = "Allow"
    principals {{
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }}
    actions   = ["s3:GetObject"]
    resources = ["${{data.aws_s3_bucket.target.arn}}/*"]
    condition {{
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.security_autopilot.arn]
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
      resources = ["${{data.aws_s3_bucket.target.arn}}/*"]
    }}
  }}
}}

resource "aws_s3_bucket_policy" "security_autopilot" {{
  bucket = data.aws_s3_bucket.target.id
  policy = data.aws_iam_policy_document.bucket_policy.json
}}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {{
  bucket = data.aws_s3_bucket.target.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

output "cloudfront_distribution_id" {{
  value       = aws_cloudfront_distribution.security_autopilot.id
  description = "CloudFront distribution ID."
}}

output "cloudfront_domain_name" {{
  value       = aws_cloudfront_distribution.security_autopilot.domain_name
  description = "Use this domain in clients instead of direct S3 public URLs."
}}

output "bucket_name" {{
  value       = data.aws_s3_bucket.target.id
  description = "Target S3 bucket migrated to private access via CloudFront OAC."
}}
"""


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


def _generate_for_s3_bucket_access_logging(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for S3 bucket access logging (S3.9)."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="s3_bucket_access_logging.yaml",
                content=_cloudformation_s3_bucket_access_logging_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Set Parameter BucketName and LogBucketName for the target and log buckets.",
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_access_logging.tf",
                content=_terraform_s3_bucket_access_logging_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            f"Set bucket name (target: {bucket_name}) and logging target bucket variables.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable S3 server access logging.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_bucket_access_logging_content(meta: dict[str, str]) -> str:
    """Terraform for S3 bucket server access logging (S3.9)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket access logging - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

variable "log_bucket_name" {{
  type        = string
  description = "S3 bucket that will receive access logs"
}}

variable "log_prefix" {{
  type        = string
  description = "Prefix for delivered access logs"
  default     = "s3-access-logs/"
}}

resource "aws_s3_bucket_logging" "security_autopilot" {{
  bucket        = "{bucket}"
  target_bucket = var.log_bucket_name
  target_prefix = var.log_prefix
}}
"""


def _cloudformation_s3_bucket_access_logging_content(meta: dict[str, str]) -> str:
    """CloudFormation for S3 bucket server access logging (S3.9)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
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
    Description: Destination bucket receiving access logs
  LogPrefix:
    Type: String
    Default: s3-access-logs/
    Description: Prefix for delivered access logs
Resources:
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


def _generate_for_s3_bucket_lifecycle_configuration(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for S3 bucket lifecycle configuration (S3.11)."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="s3_bucket_lifecycle_configuration.yaml",
                content=_cloudformation_s3_bucket_lifecycle_configuration_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Set Parameter BucketName and optionally adjust AbortIncompleteMultipartDays.",
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_lifecycle_configuration.tf",
                content=_terraform_s3_bucket_lifecycle_configuration_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            f"Set bucket name (target: {bucket_name}) and lifecycle day threshold if needed.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to configure lifecycle policy.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_bucket_lifecycle_configuration_content(meta: dict[str, str]) -> str:
    """Terraform for S3 bucket lifecycle configuration (S3.11)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket lifecycle configuration - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

variable "abort_incomplete_multipart_days" {{
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {{
  bucket = "{bucket}"

  rule {{
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {{}}

    abort_incomplete_multipart_upload {{
      days_after_initiation = var.abort_incomplete_multipart_days
    }}
  }}
}}
"""


def _cloudformation_s3_bucket_lifecycle_configuration_content(meta: dict[str, str]) -> str:
    """CloudFormation for S3 bucket lifecycle configuration (S3.11)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket lifecycle configuration - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "Configure S3 lifecycle policy for a bucket."
Parameters:
  BucketName:
    Type: String
    Default: "{bucket}"
    Description: Target bucket for lifecycle configuration
  AbortIncompleteMultipartDays:
    Type: Number
    Default: 7
    Description: Days before aborting incomplete multipart uploads
Resources:
  BucketLifecycle:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BucketName
      LifecycleConfiguration:
        Rules:
          - Id: security-autopilot-abort-incomplete-multipart
            Status: Enabled
            AbortIncompleteMultipartUpload:
              DaysAfterInitiation: !Ref AbortIncompleteMultipartDays
"""


# ---------------------------------------------------------------------------
# S3 bucket SSE-KMS encryption (S3.15)
# ---------------------------------------------------------------------------


def _generate_for_s3_bucket_encryption_kms(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for S3 bucket SSE-KMS encryption (S3.15)."""
    meta = _action_meta(action)
    region = meta["region"]
    bucket_name = _s3_bucket_name_from_target_id(meta["target_id"])
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="s3_bucket_encryption_kms.yaml",
                content=_cloudformation_s3_bucket_encryption_kms_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Set Parameter BucketName and KmsKeyArn to the target bucket and approved KMS key.",
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_encryption_kms.tf",
                content=_terraform_s3_bucket_encryption_kms_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            f"Set bucket name (target: {bucket_name}) and kms_key_arn before apply.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enforce SSE-KMS default encryption.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_bucket_encryption_kms_content(meta: dict[str, str]) -> str:
    """Terraform for S3 bucket SSE-KMS encryption (S3.15)."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket SSE-KMS encryption - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

variable "kms_key_arn" {{
  type        = string
  description = "KMS key ARN to use for bucket default encryption"
}}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {{
  bucket = "{bucket}"

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }}
    bucket_key_enabled = true
  }}
}}
"""


def _cloudformation_s3_bucket_encryption_kms_content(meta: dict[str, str]) -> str:
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
    Description: KMS key ARN used for default bucket encryption
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
# Restrict 0.0.0.0/0 and optional ::/0 on 22/3389; optional allowlist (variables/parameters). User must remove existing public rules first.
# Terraform: aws_vpc_security_group_ingress_rule with parameterized CIDR. CloudFormation: AWS::EC2::SecurityGroupIngress.
# ---------------------------------------------------------------------------


def _generate_for_sg_restrict_public_ports(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for sg_restrict_public_ports (per security group, EC2.53). Step 9.11."""
    meta = _action_meta(action)
    region = meta["region"]
    sg_id = _security_group_id_from_target_id(meta["target_id"])
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="sg_restrict_public_ports.yaml",
                content=_cloudformation_sg_restrict_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Identify what is attached to this security group (EC2, ENIs, ALB/NLB, RDS, ECS/EKS) and treat production resources with extra caution.",
            "Review inbound rules and confirm which high-risk ports are open to 0.0.0.0/0 and/or ::/0. Public SSH/RDP and database ports are usually unnecessary.",
            "Confirm alternative admin access first (SSM Session Manager, bastion, or VPN). Optionally review VPC Flow Logs to confirm active source IPs.",
            "Do not delete broad rules blindly. Narrow sources incrementally to VPN CIDR, office IP, or source security group.",
            "Set Parameters SecurityGroupId and AllowedCidr (e.g. 10.0.0.0/8). Optionally set AllowedCidrIpv6 (e.g. fd00::/8).",
            "Validate the template and create/update the stack to add restricted ingress. Keep public 80/443 only where explicitly required.",
            "Test connectivity after each change and tighten in small steps.",
            "Avoid blind auto-remediation in production. If automation is enabled, prefer restrict-over-remove and use dev/test first.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="sg_restrict_public_ports.tf",
                content=_terraform_sg_restrict_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "Identify what is attached to this security group (EC2, ENIs, ALB/NLB, RDS, ECS/EKS) and treat production resources with extra caution.",
            "Review inbound rules and confirm which high-risk ports are open to 0.0.0.0/0 and/or ::/0. Public SSH/RDP and database ports are usually unnecessary.",
            "Confirm alternative admin access first (SSM Session Manager, bastion, or VPN). Optionally review VPC Flow Logs to confirm active source IPs.",
            "Do not delete broad rules blindly. Narrow sources incrementally to VPN CIDR, office IP, or source security group.",
            f"Set security_group_id and allowed_cidr in the Terraform file (target SG: {sg_id}).",
            "Optionally set allowed_cidr_ipv6 (e.g. fd00::/8) to add IPv6-restricted ingress.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to add restricted SSH/RDP ingress. Keep public 80/443 only where explicitly required.",
            "Test connectivity after each change and tighten in small steps.",
            "Avoid blind auto-remediation in production. If automation is enabled, prefer restrict-over-remove and use dev/test first.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_sg_restrict_content(meta: dict[str, str]) -> str:
    """Terraform for SG restrict public ports 22/3389 (EC2.53). Step 9.11: aws_vpc_security_group_ingress_rule with variables."""
    sg_id = _security_group_id_from_target_id(meta["target_id"])
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
  default     = "10.0.0.0/8"
  description = "CIDR allowed for SSH/RDP (e.g. VPN or bastion)"
}}

variable "allowed_cidr_ipv6" {{
  type        = string
  default     = ""
  description = "Optional IPv6 CIDR allowed for SSH/RDP (e.g. fd00::/8). Leave empty to skip IPv6 ingress."
}}

resource "aws_vpc_security_group_ingress_rule" "ssh_restricted" {{
  security_group_id = var.security_group_id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from allowed CIDR - Security Autopilot"
}}

resource "aws_vpc_security_group_ingress_rule" "rdp_restricted" {{
  security_group_id = var.security_group_id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 3389
  to_port           = 3389
  ip_protocol       = "tcp"
  description       = "RDP from allowed CIDR - Security Autopilot"
}}

resource "aws_vpc_security_group_ingress_rule" "ssh_restricted_ipv6" {{
  count             = var.allowed_cidr_ipv6 == "" ? 0 : 1
  security_group_id = var.security_group_id
  cidr_ipv6         = var.allowed_cidr_ipv6
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from allowed IPv6 CIDR - Security Autopilot"
}}

resource "aws_vpc_security_group_ingress_rule" "rdp_restricted_ipv6" {{
  count             = var.allowed_cidr_ipv6 == "" ? 0 : 1
  security_group_id = var.security_group_id
  cidr_ipv6         = var.allowed_cidr_ipv6
  from_port         = 3389
  to_port           = 3389
  ip_protocol       = "tcp"
  description       = "RDP from allowed IPv6 CIDR - Security Autopilot"
}}
"""


def _cloudformation_sg_restrict_content(meta: dict[str, str]) -> str:
    """CloudFormation for SG restrict public ports (EC2.53). Step 9.5 (all seven), 9.11."""
    sg_id = _security_group_id_from_target_id(meta["target_id"])
    return f"""# SG restrict public ports (22/3389) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "Restrict SSH/RDP to allowed CIDR - Security Autopilot. Use incremental tightening to avoid outages."
Metadata:
  SecurityAutopilotNotes:
    - "Identify SG attachments and active dependencies before tightening ingress."
    - "Replace broad sources incrementally (VPN CIDR, office IP, or source SG), then test connectivity."
    - "Avoid blind auto-remediation in production; prefer restrict-over-remove."
Parameters:
  SecurityGroupId:
    Type: AWS::EC2::SecurityGroup::Id
    Default: "{sg_id}"
    Description: Security group to add restricted ingress
  AllowedCidr:
    Type: String
    Default: "10.0.0.0/8"
    Description: CIDR allowed for SSH (22) and RDP (3389)
  AllowedCidrIpv6:
    Type: String
    Default: ""
    Description: Optional IPv6 CIDR allowed for SSH (22) and RDP (3389). Leave empty to skip IPv6 ingress.
Conditions:
  HasAllowedIpv6:
    Fn::Not:
      - Fn::Equals:
          - !Ref AllowedCidrIpv6
          - ""
Resources:
  IngressSSH:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 22
      ToPort: 22
      CidrIp: !Ref AllowedCidr
      Description: "SSH from allowed CIDR - Security Autopilot"
  IngressRDP:
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
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Ref SecurityGroupId
      IpProtocol: tcp
      FromPort: 3389
      ToPort: 3389
      CidrIpv6: !Ref AllowedCidrIpv6
      Description: "RDP from allowed IPv6 CIDR - Security Autopilot"
"""


# ---------------------------------------------------------------------------
# CloudTrail enabled — Step 9.12 (action_type: cloudtrail_enabled, control_id: CloudTrail.1)
# ---------------------------------------------------------------------------
# Scope: account-level or per region; region from action. Control CloudTrail.1 → cloudtrail_enabled (control_scope 9.8).
# Multi-region trail + S3 bucket for logs (variable/parameter).
# Terraform: aws_cloudtrail. CloudFormation: AWS::CloudTrail::Trail.
# ---------------------------------------------------------------------------


def _generate_for_cloudtrail_enabled(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for cloudtrail_enabled (multi-region trail, CloudTrail.1). Step 9.12."""
    meta = _action_meta(action)
    region = meta["region"]
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="cloudtrail_enabled.yaml",
                content=_cloudformation_cloudtrail_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']}.",
            "Create or identify an S3 bucket for CloudTrail logs; set parameter TrailBucketName.",
            "Validate the template and create/update the stack.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    else:
        files = [
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="cloudtrail_enabled.tf",
                content=_terraform_cloudtrail_content(meta),
            ),
        ]
        steps = [
            f"Configure AWS provider for account {meta['account_id']} and region {region}.",
            "Create an S3 bucket for trail logs and set trail_bucket_name in the Terraform file.",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable CloudTrail (multi-region).",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_regional_providers_content(meta: dict[str, str]) -> str:
    """Shared provider block with region for regional resources (9.9–9.12). Uses default credential chain (no profile)."""
    region = meta["region"]
    account_id = meta["account_id"]
    return f"""# Configure AWS provider for account {account_id} and region {region}.
# Credentials: default chain (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, or ~/.aws/credentials [default]).
# If you use a named profile, add: profile = "your-profile-name" (do not use account ID as profile name).

terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = ">= 4.0"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"
}}
"""


def _terraform_cloudtrail_content(meta: dict[str, str]) -> str:
    """Terraform for CloudTrail enabled (multi-region, CloudTrail.1). Step 9.12: aws_cloudtrail with variable trail_bucket_name."""
    return f"""# CloudTrail enabled - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]}
# Control: {meta["control_id"]}
# Create an S3 bucket for trail logs and set trail_bucket_name below.

variable "trail_bucket_name" {{
  type        = string
  description = "S3 bucket name for CloudTrail logs (create the bucket if it does not exist)"
}}

resource "aws_cloudtrail" "security_autopilot" {{
  name                          = "security-autopilot-trail"
  s3_bucket_name                = var.trail_bucket_name
  is_multi_region_trail          = true
  include_global_service_events = true
  enable_logging                = true
}}
"""


def _cloudformation_cloudtrail_content(meta: dict[str, str]) -> str:
    """CloudFormation for CloudTrail enabled (CloudTrail.1). Step 9.5 (all seven), 9.12."""
    return f"""# CloudTrail enabled - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "CloudTrail multi-region trail - Security Autopilot. Provide S3 bucket for logs."
Parameters:
  TrailBucketName:
    Type: String
    Description: S3 bucket name for CloudTrail logs
Resources:
  Trail:
    Type: AWS::CloudTrail::Trail
    Properties:
      TrailName: security-autopilot-trail
      S3BucketName: !Ref TrailBucketName
      IsMultiRegionTrail: true
      IncludeGlobalServiceEvents: true
"""


# ---------------------------------------------------------------------------
# Phase 1 strategy-based generators
# ---------------------------------------------------------------------------


def _generate_for_s3_bucket_strategy(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
) -> PRBundleResult:
    """Generate S3 bucket public-access remediation according to selected strategy."""
    normalized_strategy = (strategy_id or "").strip().lower()
    if normalized_strategy == "s3_migrate_cloudfront_oac_private":
        return _generate_for_s3_cloudfront_oac_private(action, format)
    if normalized_strategy == "s3_keep_public_exception":
        return _generate_for_exception_guidance(action, format, "Keep public S3 access (exception path)")
    return _generate_for_s3_bucket_block_public_access(action, format)


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
            "Validate the template and deploy the stack.",
            "Confirm AWS Config recorder is running and delivery channel is healthy.",
            "Recompute actions to verify remediation state.",
        ]
        return PRBundleResult(
            format=format,
            files=[PRBundleFile(path="aws_config_enabled.yaml", content=content)],
            steps=steps,
        )

    content = _terraform_aws_config_enabled_content(meta, strategy=strategy, strategy_inputs=inputs)
    steps = [
        f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
        "Adjust bucket/KMS variables as needed.",
        "Run `terraform init`, `terraform plan`, and `terraform apply`.",
        "Recompute actions to verify remediation state.",
    ]
    return PRBundleResult(
        format=format,
        files=[
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(path="aws_config_enabled.tf", content=content),
        ],
        steps=steps,
    )


def _generate_for_ssm_block_public_sharing(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate SSM document public-sharing block bundle."""
    meta = _action_meta(action)
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
                "Deploy the template to enforce SSM service setting for blocked public sharing.",
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
) -> PRBundleResult:
    """Generate S3 SSL enforcement bundle."""
    meta = _action_meta(action)
    strategy = (strategy_id or "s3_enforce_ssl_strict_deny").strip().lower()
    if strategy == "s3_keep_non_ssl_exception":
        return _generate_for_exception_guidance(action, format, "Keep non-SSL S3 access (exception path)")

    inputs = strategy_inputs or {}
    exempt_principals = inputs.get("exempt_principals")
    if not isinstance(exempt_principals, list):
        exempt_principals = []

    if format == CLOUDFORMATION_FORMAT:
        return PRBundleResult(
            format=format,
            files=[
                PRBundleFile(
                    path="s3_bucket_require_ssl.yaml",
                    content=_cloudformation_s3_bucket_require_ssl_content(
                        meta,
                        exempt_principals=exempt_principals,
                    ),
                )
            ],
            steps=[
                f"Configure AWS credentials for account {meta['account_id']}.",
                "Merge generated policy statements with any existing bucket policy.",
                "Deploy template and validate affected clients can use TLS.",
                "Recompute actions to verify remediation state.",
            ],
        )

    return PRBundleResult(
        format=format,
        files=[
            PRBundleFile(path="providers.tf", content=_terraform_regional_providers_content(meta)),
            PRBundleFile(
                path="s3_bucket_require_ssl.tf",
                content=_terraform_s3_bucket_require_ssl_content(
                    meta,
                    exempt_principals=exempt_principals,
                ),
            ),
        ],
        steps=[
            f"Configure AWS provider for account {meta['account_id']} and region {meta['region']}.",
            "Merge generated policy statements with any existing bucket policy.",
            "Run `terraform init`, `terraform plan`, and `terraform apply`.",
            "Validate impacted clients and recompute actions.",
        ],
    )


def _generate_for_iam_root_access_key_absent(
    action: ActionLike,
    format: PRBundleFormat,
    strategy_id: str | None,
) -> PRBundleResult:
    """Generate guided IAM root access key remediation bundle."""
    strategy = (strategy_id or "iam_root_key_disable").strip().lower()
    if strategy == "iam_root_key_keep_exception":
        return _generate_for_exception_guidance(action, format, "Keep root access key (exception path)")
    if strategy == "iam_root_key_delete":
        title = "Delete IAM root access key"
        step_action = "Delete root access key after validating fallback console MFA access."
    else:
        title = "Disable IAM root access key"
        step_action = "Disable root access key and validate that no automation relies on it."
    return _generate_for_guidance_bundle(action, format, title, [step_action])


def _generate_for_exception_guidance(
    action: ActionLike,
    format: PRBundleFormat,
    title: str,
) -> PRBundleResult:
    """Return a PR bundle that explicitly guides users into exception workflow."""
    return _generate_for_guidance_bundle(
        action,
        format,
        title,
        [
            "Create or update an exception with approval owner and expiry date.",
            "Document compensating controls and periodic review cadence.",
            "Recompute actions after exception approval to keep workflow consistent.",
        ],
    )


def _generate_for_guidance_bundle(
    action: ActionLike,
    format: PRBundleFormat,
    title: str,
    steps: list[str],
) -> PRBundleResult:
    """Create a guidance-only bundle for non-IaC exception/human-runbook paths."""
    meta = _action_meta(action)
    content = (
        f"# {title}\n"
        f"# Action: {meta['action_id']}\n"
        f"# Action type: {action.action_type}\n"
        f"# Account: {meta['account_id']} | Region: {meta['region']}\n"
    )
    path = "README.yaml" if format == CLOUDFORMATION_FORMAT else "README.tf"
    return PRBundleResult(format=format, files=[PRBundleFile(path=path, content=content)], steps=steps)


def _terraform_aws_config_enabled_content(
    meta: dict[str, str],
    strategy: str,
    strategy_inputs: dict[str, Any],
) -> str:
    bucket = str(strategy_inputs.get("delivery_bucket", "")).strip() or f"security-autopilot-config-{meta['account_id']}"
    kms_key_arn = str(strategy_inputs.get("kms_key_arn", "")).strip()
    if strategy == "config_enable_centralized_delivery":
        bucket_resource = ""
        bucket_name_expr = f"\"{bucket}\""
    else:
        bucket_resource = f"""
resource "aws_s3_bucket" "config_delivery" {{
  bucket = "{bucket}"
}}
"""
        bucket_name_expr = "aws_s3_bucket.config_delivery.id"

    kms_config = ""
    if kms_key_arn:
        kms_config = f'  s3_kms_key_arn = "{kms_key_arn}"\n'

    return f"""# AWS Config enablement - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]}
# Control: {meta["control_id"]}

{bucket_resource}
resource "aws_config_configuration_recorder" "security_autopilot" {{
  name     = "security-autopilot-recorder"
  role_arn = "arn:aws:iam::{meta["account_id"]}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig"
  recording_group {{
    all_supported = true
  }}
}}

resource "aws_config_delivery_channel" "security_autopilot" {{
  name           = "security-autopilot-delivery-channel"
  s3_bucket_name = {bucket_name_expr}
{kms_config}}}

resource "aws_config_configuration_recorder_status" "security_autopilot" {{
  name       = aws_config_configuration_recorder.security_autopilot.name
  is_enabled = true
  depends_on = [aws_config_delivery_channel.security_autopilot]
}}
"""


def _cloudformation_aws_config_enabled_content(
    meta: dict[str, str],
    strategy: str,
    strategy_inputs: dict[str, Any],
) -> str:
    bucket = str(strategy_inputs.get("delivery_bucket", "")).strip() or f"security-autopilot-config-{meta['account_id']}"
    kms_key_arn = str(strategy_inputs.get("kms_key_arn", "")).strip()
    create_bucket = strategy != "config_enable_centralized_delivery"
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
    parameter_block = ""
    if not create_bucket:
        parameter_block = f"""
  DeliveryBucketName:
    Type: String
    Default: "{bucket}"
    Description: Centralized S3 bucket for AWS Config delivery
"""
    return f"""AWSTemplateFormatVersion: "2010-09-09"
Description: "Enable AWS Config recording and delivery channel."
Parameters:{parameter_block if parameter_block else " {}"}
Resources:{bucket_resource}
  ConfigRecorder:
    Type: AWS::Config::ConfigurationRecorder
    Properties:
      Name: security-autopilot-recorder
      RoleARN: arn:aws:iam::{meta["account_id"]}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig
      RecordingGroup:
        AllSupported: true
  ConfigDeliveryChannel:
    Type: AWS::Config::DeliveryChannel
    Properties:
      Name: security-autopilot-delivery-channel
      S3BucketName: !Ref {bucket_ref}
{kms_line if kms_line else ""}
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


def _terraform_s3_bucket_require_ssl_content(meta: dict[str, str], exempt_principals: list[str]) -> str:
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    principal_block = ""
    if exempt_principals:
        quoted = ", ".join(f"\"{principal}\"" for principal in exempt_principals)
        principal_block = f"""
  statement {{
    sid = "AllowExemptPrincipals"
    effect = "Allow"
    principals {{
      type        = "AWS"
      identifiers = [{quoted}]
    }}
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::{bucket}",
      "arn:aws:s3:::{bucket}/*",
    ]
  }}
"""
    return f"""# Enforce SSL-only S3 requests - Action: {meta["action_id"]}
data "aws_iam_policy_document" "security_autopilot_ssl_enforcement" {{
  statement {{
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {{
      type        = "*"
      identifiers = ["*"]
    }}
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::{bucket}",
      "arn:aws:s3:::{bucket}/*",
    ]
    condition {{
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }}
  }}
{principal_block}
}}

resource "aws_s3_bucket_policy" "security_autopilot" {{
  bucket = "{bucket}"
  policy = data.aws_iam_policy_document.security_autopilot_ssl_enforcement.json
}}
"""


def _cloudformation_s3_bucket_require_ssl_content(meta: dict[str, str], exempt_principals: list[str]) -> str:
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    exemptions = ""
    if exempt_principals:
        items = "\n".join(f"                - {principal}" for principal in exempt_principals)
        exemptions = f"""
          - Sid: AllowExemptPrincipals
            Effect: Allow
            Principal:
              AWS:
{items}
            Action: "s3:*"
            Resource:
              - "arn:aws:s3:::{bucket}"
              - "arn:aws:s3:::{bucket}/*"
"""
    return f"""AWSTemplateFormatVersion: "2010-09-09"
Description: "Enforce SSL-only S3 requests."
Resources:
  S3BucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: "{bucket}"
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Sid: DenyInsecureTransport
            Effect: Deny
            Principal: "*"
            Action: "s3:*"
            Resource:
              - "arn:aws:s3:::{bucket}"
              - "arn:aws:s3:::{bucket}/*"
            Condition:
              Bool:
                aws:SecureTransport: "false"
{exemptions if exemptions else ""}
"""


# ---------------------------------------------------------------------------
# Unsupported / pr_only / fallback
# ---------------------------------------------------------------------------


def _generate_unsupported(
    action: ActionLike | None,
    format: PRBundleFormat,
) -> PRBundleResult:
    """
    Return a guidance placeholder for unsupported or missing action types.

    Used for pr_only, unmapped action_type, or when action is None.
    """
    action_type = (action.action_type or "pr_only").strip() if action else "pr_only"
    meta = _action_meta(action)
    guidance = (
        "This action type does not yet have IaC generation. "
        "Apply the fix manually in AWS Console or use direct fix if supported."
    )
    if format == CLOUDFORMATION_FORMAT:
        path = "README.yaml"
        content = f"""# Action type: {action_type}
# Action: {meta["action_id"] or "N/A"}
# {guidance}
"""
    else:
        path = "README.tf"
        content = f"""# Action type: {action_type}
# Action: {meta["action_id"] or "N/A"}
# {guidance}
"""

    steps = [
        "Review the finding and control in Security Hub.",
        "Apply the remediation manually in the AWS Console for this account/region.",
        "Use **Direct fix** from the action detail page if this control supports it.",
        "Return to the action and click **Recompute actions** after applying the fix.",
    ]

    return PRBundleResult(
        format=format,
        files=[PRBundleFile(path=path, content=content)],
        steps=steps,
    )


__all__ = [
    "ActionLike",
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
