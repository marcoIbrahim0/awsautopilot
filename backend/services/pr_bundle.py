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

import uuid
from typing import Literal, Protocol, TypedDict

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
ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS = "sg_restrict_public_ports" # 9.11
ACTION_TYPE_CLOUDTRAIL_ENABLED = "cloudtrail_enabled"             # 9.12
ACTION_TYPE_PR_ONLY = "pr_only"

SUPPORTED_ACTION_TYPES = frozenset({
    ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_ENABLE_SECURITY_HUB,
    ACTION_TYPE_ENABLE_GUARDDUTY,
    ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_S3_BUCKET_ENCRYPTION,
    ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
    ACTION_TYPE_CLOUDTRAIL_ENABLED,
})


def generate_pr_bundle(
    action: ActionLike | None,
    format: str = "terraform",
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
    if action_type == ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS:
        return _maybe_append_terraform_readme(_generate_for_s3(action, normalized_format))
    if action_type == ACTION_TYPE_ENABLE_SECURITY_HUB:
        return _maybe_append_terraform_readme(_generate_for_security_hub(action, normalized_format))
    if action_type == ACTION_TYPE_ENABLE_GUARDDUTY:
        return _maybe_append_terraform_readme(_generate_for_guardduty(action, normalized_format))
    if action_type == ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS:
        return _maybe_append_terraform_readme(
            _generate_for_s3_bucket_block_public_access(action, normalized_format)
        )
    if action_type == ACTION_TYPE_S3_BUCKET_ENCRYPTION:
        return _maybe_append_terraform_readme(
            _generate_for_s3_bucket_encryption(action, normalized_format)
        )
    if action_type == ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS:
        return _maybe_append_terraform_readme(
            _generate_for_sg_restrict_public_ports(action, normalized_format)
        )
    if action_type == ACTION_TYPE_CLOUDTRAIL_ENABLED:
        return _maybe_append_terraform_readme(
            _generate_for_cloudtrail_enabled(action, normalized_format)
        )

    return _maybe_append_terraform_readme(_generate_unsupported(action, normalized_format))


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


def _maybe_append_terraform_readme(result: PRBundleResult) -> PRBundleResult:
    """Append README.txt to Terraform bundles so users see credential instructions."""
    if result.get("format") != TERRAFORM_FORMAT or not result.get("files"):
        return result
    files = list(result["files"])
    files.append(PRBundleFile(path="README.txt", content=_terraform_readme_content()))
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
            f"Set bucket name in the Terraform file (target: {bucket_name}).",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to enable block public access on the bucket.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_s3_bucket_block_content(meta: dict[str, str]) -> str:
    """Terraform for per-bucket S3 block public access (S3.2). Step 9.9: aws_s3_bucket_public_access_block."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket-level block public access - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {{
  bucket = "{bucket}"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}
"""


def _cloudformation_s3_bucket_block_content(meta: dict[str, str]) -> str:
    """CloudFormation for per-bucket S3 block public access (S3.2). Step 9.5 (all seven), 9.9."""
    bucket = _s3_bucket_name_from_target_id(meta.get("target_id", ""))
    return f"""# S3 bucket-level block public access - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Bucket: {bucket}
# Control: {meta["control_id"]}
# For existing buckets, prefer Terraform (aws_s3_bucket_public_access_block). This template creates/updates a bucket with block.

AWSTemplateFormatVersion: "2010-09-09"
Description: "S3 bucket block public access - Security Autopilot. Set BucketName parameter."
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
# SG restrict public ports (22/3389) — Step 9.11 (action_type: sg_restrict_public_ports, control_id: EC2.18)
# ---------------------------------------------------------------------------
# Scope: per security group; target_id = SG ID. Control EC2.18 → sg_restrict_public_ports (control_scope 9.8).
# Restrict 0.0.0.0/0 on 22/3389; optional allowlist (variables/parameters). User must remove existing 0.0.0.0/0 rules first.
# Terraform: aws_vpc_security_group_ingress_rule with parameterized CIDR. CloudFormation: AWS::EC2::SecurityGroupIngress.
# ---------------------------------------------------------------------------


def _generate_for_sg_restrict_public_ports(action: ActionLike, format: PRBundleFormat) -> PRBundleResult:
    """Generate IaC for sg_restrict_public_ports (per security group, EC2.18). Step 9.11."""
    meta = _action_meta(action)
    region = meta["region"]
    sg_id = meta["target_id"] or "REPLACE_SECURITY_GROUP_ID"
    if format == CLOUDFORMATION_FORMAT:
        files = [
            PRBundleFile(
                path="sg_restrict_public_ports.yaml",
                content=_cloudformation_sg_restrict_content(meta),
            )
        ]
        steps = [
            f"Configure AWS credentials for account {meta['account_id']} and region {region}.",
            "Remove existing rules allowing 0.0.0.0/0 on ports 22 and 3389 in the AWS Console or via CLI.",
            "Set Parameters SecurityGroupId and AllowedCidr (e.g. 10.0.0.0/8).",
            "Validate the template and create/update the stack to add restricted ingress.",
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
            "Remove existing 0.0.0.0/0 rules for ports 22 and 3389 (Console or Terraform).",
            f"Set security_group_id and allowed_cidr in the Terraform file (target SG: {sg_id}).",
            "Run `terraform init` and `terraform plan`.",
            "Run `terraform apply` to add restricted SSH/RDP ingress.",
            "Return to the action and click **Recompute actions** or trigger ingest to verify.",
        ]
    return PRBundleResult(format=format, files=files, steps=steps)


def _terraform_sg_restrict_content(meta: dict[str, str]) -> str:
    """Terraform for SG restrict public ports 22/3389 (EC2.18). Step 9.11: aws_vpc_security_group_ingress_rule with variables."""
    sg_id = meta["target_id"] or "REPLACE_SECURITY_GROUP_ID"
    return f"""# SG restrict public ports (22/3389) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}
# Remove existing 0.0.0.0/0 rules for 22 and 3389 before applying; this adds restricted ingress.

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
"""


def _cloudformation_sg_restrict_content(meta: dict[str, str]) -> str:
    """CloudFormation for SG restrict public ports (EC2.18). Step 9.5 (all seven), 9.11."""
    sg_id = meta["target_id"] or "REPLACE_SECURITY_GROUP_ID"
    return f"""# SG restrict public ports (22/3389) - Action: {meta["action_id"]}
# Remediation for: {meta["action_title"]}
# Account: {meta["account_id"]} | Region: {meta["region"]} | Security group: {sg_id}
# Control: {meta["control_id"]}

AWSTemplateFormatVersion: "2010-09-09"
Description: "Restrict SSH/RDP to allowed CIDR - Security Autopilot. Remove 0.0.0.0/0 rules for 22/3389 first."
Parameters:
  SecurityGroupId:
    Type: AWS::EC2::SecurityGroup::Id
    Default: "{sg_id}"
    Description: Security group to add restricted ingress
  AllowedCidr:
    Type: String
    Default: "10.0.0.0/8"
    Description: CIDR allowed for SSH (22) and RDP (3389)
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
    "ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS",
    "ACTION_TYPE_CLOUDTRAIL_ENABLED",
    "ACTION_TYPE_PR_ONLY",
    "SUPPORTED_ACTION_TYPES",
    "generate_pr_bundle",
]
