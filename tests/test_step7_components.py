"""
Pytest tests for Step 7 components.

Covers: PR bundle scaffold, remediation_audit guards, SQS remediation_run payload,
worker handler registration. Does not require DB or SQS.
"""
from __future__ import annotations

import json
import uuid

import pytest

from backend.models.enums import RemediationRunStatus
from backend.services.pr_bundle import (
    ACTION_TYPE_AWS_CONFIG_ENABLED,
    ACTION_TYPE_CLOUDTRAIL_ENABLED,
    ACTION_TYPE_EBS_DEFAULT_ENCRYPTION,
    ACTION_TYPE_EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_ENABLE_GUARDDUTY,
    ACTION_TYPE_ENABLE_SECURITY_HUB,
    ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT,
    ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
    ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
    ACTION_TYPE_S3_BUCKET_ENCRYPTION,
    ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
    ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
    ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
    ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
    ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING,
    CLOUDFORMATION_FORMAT,
    PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3,
    PRBundleGenerationError,
    SUPPORTED_ACTION_TYPES,
    TERRAFORM_FORMAT,
    generate_pr_bundle,
    _s3_bucket_name_from_target_id,
)
from backend.services.remediation_audit import (
    allow_update_outcome,
    is_run_completed,
)
from backend.utils.sqs import (
    REMEDIATION_RUN_JOB_TYPE,
    build_remediation_run_job_payload,
)


# ---------------------------------------------------------------------------
# PR bundle (Step 9.1: load action, dispatch by action_type)
# ---------------------------------------------------------------------------


def _make_action(
    action_type: str = "s3_block_public_access",
    action_id: uuid.UUID | None = None,
    account_id: str = "123456789012",
    region: str | None = "us-east-1",
    target_id: str = "target-1",
    title: str = "Remediation",
    control_id: str | None = "control-1",
) -> object:
    """Minimal action-like object for tests (ActionLike protocol)."""
    return type("ActionLike", (), {
        "id": action_id or uuid.uuid4(),
        "action_type": action_type,
        "account_id": account_id,
        "region": region,
        "target_id": target_id,
        "title": title,
        "control_id": control_id,
    })()


def test_pr_bundle_returns_dict_with_format_files_steps() -> None:
    """generate_pr_bundle returns format, files, steps."""
    action = _make_action(action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS)
    r = generate_pr_bundle(action, "terraform")
    assert isinstance(r, dict)
    assert "format" in r
    assert "files" in r
    assert "steps" in r
    assert r["format"] == "terraform"
    assert len(r["files"]) >= 1
    assert len(r["steps"]) >= 2


def test_pr_bundle_terraform_file_shape() -> None:
    """Terraform bundle for s3_block_public_access has providers.tf + resource .tf (Step 9.2)."""
    action = _make_action(action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS)
    r = generate_pr_bundle(action, "terraform")
    paths = [f["path"] for f in r["files"]]
    assert "providers.tf" in paths
    assert "s3_block_public_access.tf" in paths
    assert "README.txt" in paths
    assert len(r["files"]) == 3
    resource_file = next(f for f in r["files"] if f["path"] == "s3_block_public_access.tf")
    assert "aws_s3_account_public_access_block" in resource_file["content"]


def test_pr_bundle_cloudformation_file_shape() -> None:
    """CloudFormation bundle for s3 has .yaml file."""
    action = _make_action(action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS)
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"].endswith(".yaml")


def test_pr_bundle_cloudformation_s3_step_9_5_valid_template() -> None:
    """Step 9.5: S3 CloudFormation is valid YAML with placeholder + CLI instructions."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS,
        account_id="111122223333",
        control_id="S3.1",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    content = r["files"][0]["content"]
    assert "AWSTemplateFormatVersion" in content
    assert "Resources:" in content
    assert "PlaceholderNoOp" in content or "WaitConditionHandle" in content
    assert "put-public-access-block" in content or "s3control" in content
    assert "CloudFormation does not support" in content or "no native resource" in content
    assert "111122223333" in content


def test_pr_bundle_cloudformation_security_hub_step_9_5() -> None:
    """Step 9.5: Security Hub CloudFormation is valid, applyable YAML."""
    action = _make_action(
        action_type=ACTION_TYPE_ENABLE_SECURITY_HUB,
        region="eu-west-1",
        account_id="222233334444",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    content = r["files"][0]["content"]
    assert "AWSTemplateFormatVersion" in content
    assert "AWS::SecurityHub::Hub" in content
    assert "SecurityAutopilotHub" in content
    assert "eu-west-1" in content


def test_pr_bundle_cloudformation_guardduty_step_9_5() -> None:
    """Step 9.5: GuardDuty CloudFormation is valid, applyable YAML with Enable: true."""
    action = _make_action(
        action_type=ACTION_TYPE_ENABLE_GUARDDUTY,
        region="ap-southeast-1",
        account_id="333344445555",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    content = r["files"][0]["content"]
    assert "AWSTemplateFormatVersion" in content
    assert "AWS::GuardDuty::Detector" in content
    assert "Enable: true" in content
    assert "SecurityAutopilotDetector" in content
    assert "ap-southeast-1" in content


def test_pr_bundle_invalid_format_defaults_terraform() -> None:
    """Invalid format falls back to terraform."""
    action = _make_action(action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS)
    r = generate_pr_bundle(action, "invalid")
    assert r["format"] == "terraform"


def test_pr_bundle_unsupported_action_type_raises_structured_error() -> None:
    """Unsupported action types fail with structured errors (no README placeholder bundle)."""
    action = _make_action(action_type="pr_only")
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(action, "terraform")
    payload = exc_info.value.as_dict()
    assert payload["code"] == "pr_only_action_type_unsupported"
    assert payload["action_type"] == "pr_only"


def test_pr_bundle_none_action_raises_structured_error() -> None:
    """None action fails with a structured error payload."""
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(None, "terraform")
    payload = exc_info.value.as_dict()
    assert payload["code"] == "missing_action_context"
    assert payload["format"] == TERRAFORM_FORMAT


def test_pr_bundle_dispatch_s3_terraform() -> None:
    """s3_block_public_access produces S3 Terraform content (Step 9.2)."""
    action = _make_action(action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS)
    r = generate_pr_bundle(action, "terraform")
    resource_file = next(f for f in r["files"] if "s3_block_public_access" in f["path"])
    assert "aws_s3_account_public_access_block" in resource_file["content"]
    assert "block_public_acls" in resource_file["content"]
    assert "restrict_public_buckets" in resource_file["content"]
    providers_file = next(f for f in r["files"] if f["path"] == "providers.tf")
    assert "hashicorp/aws" in providers_file["content"]
    assert "required_providers" in providers_file["content"]


def test_pr_bundle_s3_terraform_step_9_2_exact_structure() -> None:
    """Step 9.2: Terraform S3 bundle has exact HCL structure and four steps."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS,
        account_id="111122223333",
        title="Enable S3 Block Public Access",
        control_id="S3.1",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    assert len(r["steps"]) == 4
    assert "Ensure AWS provider is configured for account 111122223333" in r["steps"][0]
    assert "terraform init" in r["steps"][1]
    assert "terraform apply" in r["steps"][2]
    assert "Recompute actions" in r["steps"][3]
    resource_file = next(f for f in r["files"] if f["path"] == "s3_block_public_access.tf")
    content = resource_file["content"]
    assert 'resource "aws_s3_account_public_access_block" "security_autopilot"' in content
    assert "block_public_acls       = true" in content
    assert "block_public_policy     = true" in content
    assert "ignore_public_acls      = true" in content
    assert "restrict_public_buckets = true" in content
    assert "Action:" in content and "111122223333" in content


def test_pr_bundle_security_hub_terraform_step_9_3_exact_structure() -> None:
    """Step 9.3: Terraform Security Hub bundle has region-scoped provider and four steps."""
    action = _make_action(
        action_type=ACTION_TYPE_ENABLE_SECURITY_HUB,
        account_id="111122223333",
        region="eu-west-1",
        title="Enable Security Hub",
        control_id="SH.1",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    paths = [f["path"] for f in r["files"]]
    assert "README.txt" in paths
    assert len(r["files"]) == 3
    assert len(r["steps"]) == 4
    assert "Configure AWS provider for account 111122223333 and region eu-west-1" in r["steps"][0]
    assert "terraform init" in r["steps"][1]
    assert "terraform apply" in r["steps"][2]
    assert "Recompute actions" in r["steps"][3]
    providers_file = next(f for f in r["files"] if f["path"] == "providers.tf")
    assert 'region = "eu-west-1"' in providers_file["content"]
    assert "hashicorp/aws" in providers_file["content"]
    resource_file = next(f for f in r["files"] if f["path"] == "enable_security_hub.tf")
    content = resource_file["content"]
    assert 'resource "aws_securityhub_account" "security_autopilot"' in content
    assert "Account:" in content and "111122223333" in content
    assert "Region: eu-west-1" in content


def test_pr_bundle_guardduty_terraform_step_9_4_exact_structure() -> None:
    """Step 9.4: Terraform GuardDuty bundle has region-scoped provider and four steps."""
    action = _make_action(
        action_type=ACTION_TYPE_ENABLE_GUARDDUTY,
        account_id="444455556666",
        region="ap-southeast-1",
        title="Enable GuardDuty",
        control_id="GD.1",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    paths = [f["path"] for f in r["files"]]
    assert "README.txt" in paths
    assert len(r["files"]) == 3
    assert len(r["steps"]) == 4
    assert "Configure AWS provider for account 444455556666 and region ap-southeast-1" in r["steps"][0]
    assert "terraform init" in r["steps"][1]
    assert "terraform apply" in r["steps"][2]
    assert "Recompute actions" in r["steps"][3]
    providers_file = next(f for f in r["files"] if f["path"] == "providers.tf")
    assert 'region = "ap-southeast-1"' in providers_file["content"]
    assert "hashicorp/aws" in providers_file["content"]
    resource_file = next(f for f in r["files"] if f["path"] == "enable_guardduty.tf")
    content = resource_file["content"]
    assert 'resource "aws_guardduty_detector" "security_autopilot"' in content
    assert "enable = true" in content
    assert "Account:" in content and "444455556666" in content
    assert "Region: ap-southeast-1" in content


def test_pr_bundle_supported_action_types_all_sixteen() -> None:
    """Phase 1: SUPPORTED_ACTION_TYPES contains all mapped action types."""
    assert len(SUPPORTED_ACTION_TYPES) == 16
    assert ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_ENABLE_SECURITY_HUB in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_ENABLE_GUARDDUTY in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_S3_BUCKET_ENCRYPTION in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_CLOUDTRAIL_ENABLED in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_AWS_CONFIG_ENABLED in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_EBS_DEFAULT_ENCRYPTION in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_S3_BUCKET_REQUIRE_SSL in SUPPORTED_ACTION_TYPES
    assert ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT in SUPPORTED_ACTION_TYPES


@pytest.mark.parametrize(
    ("action_type", "target_id", "expected_path"),
    [
        (ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS, "account-target", "s3_block_public_access.tf"),
        (ACTION_TYPE_ENABLE_SECURITY_HUB, "regional-target", "enable_security_hub.tf"),
        (ACTION_TYPE_ENABLE_GUARDDUTY, "regional-target", "enable_guardduty.tf"),
        (ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS, "bucket-one", "s3_bucket_block_public_access.tf"),
        (ACTION_TYPE_S3_BUCKET_ENCRYPTION, "bucket-two", "s3_bucket_encryption.tf"),
        (ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING, "bucket-three", "s3_bucket_access_logging.tf"),
        (ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION, "bucket-four", "s3_bucket_lifecycle_configuration.tf"),
        (ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS, "bucket-five", "s3_bucket_encryption_kms.tf"),
        (ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS, "sg-0123456789abcdef0", "sg_restrict_public_ports.tf"),
        (ACTION_TYPE_CLOUDTRAIL_ENABLED, "trail-target", "cloudtrail_enabled.tf"),
        (ACTION_TYPE_AWS_CONFIG_ENABLED, "config-target", "aws_config_enabled.tf"),
        (ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING, "ssm-target", "ssm_block_public_sharing.tf"),
        (ACTION_TYPE_EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS, "ebs-snapshot-target", "ebs_snapshot_block_public_access.tf"),
        (ACTION_TYPE_EBS_DEFAULT_ENCRYPTION, "ebs-default-target", "ebs_default_encryption.tf"),
        (ACTION_TYPE_S3_BUCKET_REQUIRE_SSL, "bucket-six", "s3_bucket_require_ssl.tf"),
        (ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT, "root-target", "iam_root_access_key_absent.tf"),
    ],
)
def test_pr_bundle_supported_action_type_generates_executable_terraform_artifact(
    action_type: str,
    target_id: str,
    expected_path: str,
) -> None:
    """Every supported action type emits executable Terraform files (no README-only placeholder bundles)."""
    action = _make_action(action_type=action_type, target_id=target_id, region="us-east-1")
    r = generate_pr_bundle(action, "terraform")
    paths = [f["path"] for f in r["files"]]
    assert expected_path in paths
    assert "README.tf" not in paths
    assert "README.yaml" not in paths


def test_pr_bundle_aws_config_enabled_uses_json_boolean_recording_group_payload() -> None:
    """Config.1 Terraform bundle sets recorder booleans and Config delivery bucket policy payloads."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    content = next(f for f in r["files"] if f["path"] == "aws_config_enabled.tf")["content"]

    assert 'RECORDER_PAYLOAD=$(cat <<JSON' in content
    assert '"recordingGroup":{"allSupported":true,"includeGlobalResourceTypes":true}' in content
    assert '--configuration-recorder "$RECORDER_PAYLOAD"' in content
    assert 'recordingGroup={allSupported=true,includeGlobalResourceTypes=true}' not in content
    assert 'CONFIG_BUCKET_POLICY=$(cat <<JSON' in content
    assert '"Sid":"AWSConfigBucketPermissionsCheck"' in content
    assert '"Sid":"AWSConfigBucketDelivery"' in content
    assert '--policy "$CONFIG_BUCKET_POLICY"' in content


def test_pr_bundle_dispatch_s3_bucket_block_terraform_step_9_9() -> None:
    """Step 9.9: s3_bucket_block_public_access returns Terraform with aws_s3_bucket_public_access_block."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket-name",
        region="us-east-1",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    paths = [f["path"] for f in r["files"]]
    assert "providers.tf" in paths
    assert "s3_bucket_block_public_access.tf" in paths
    assert "README.txt" in paths
    assert len(r["files"]) == 3
    resource_file = next(f for f in r["files"] if f["path"] == "s3_bucket_block_public_access.tf")
    assert "aws_s3_bucket_public_access_block" in resource_file["content"]
    assert "my-bucket-name" in resource_file["content"]
    assert "block_public_acls" in resource_file["content"]


def test_pr_bundle_s3_bucket_block_terraform_step_9_9_exact_structure() -> None:
    """Step 9.9: Terraform for S3.2 (s3_bucket_block_public_access) has exact structure: aws_s3_bucket_public_access_block, block_public_*."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    r = generate_pr_bundle(action, "terraform")
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_block_public_access.tf")["content"]
    assert 'resource "aws_s3_bucket_public_access_block" "security_autopilot"' in content
    assert 'bucket = "my-bucket"' in content
    assert "block_public_acls       = true" in content or "block_public_acls" in content
    assert "block_public_policy" in content
    assert "ignore_public_acls" in content
    assert "restrict_public_buckets" in content
    assert "S3.2" in content or "Control:" in content


def test_pr_bundle_s3_bucket_block_terraform_readme_has_guardrails() -> None:
    """S3.2 Terraform bundle README includes explicit non-migration guardrails."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    r = generate_pr_bundle(action, "terraform")
    readme = next(f for f in r["files"] if f["path"] == "README.txt")["content"]
    assert "S3.2 guardrail (read before apply)" in readme
    assert "NOT a full CloudFront + OAC + private S3 migration" in readme
    assert "Pre-apply checks (required)" in readme
    assert "Apply sequence (recommended)" in readme
    assert "Rollback plan" in readme


def test_pr_bundle_non_s3_terraform_readme_excludes_s3_guardrails() -> None:
    """Guardrail block is only appended for S3.2 Terraform bundles."""
    action = _make_action(
        action_type=ACTION_TYPE_ENABLE_SECURITY_HUB,
        target_id="target-1",
        region="us-east-1",
        control_id="SecurityHub.1",
    )
    r = generate_pr_bundle(action, "terraform")
    readme = next(f for f in r["files"] if f["path"] == "README.txt")["content"]
    assert "S3.2 guardrail (read before apply)" not in readme


def test_pr_bundle_terraform_readme_includes_c2_c5_proof_fields() -> None:
    """Terraform README includes plan timestamp metadata and preservation statement."""
    action = _make_action(
        action_type=ACTION_TYPE_ENABLE_SECURITY_HUB,
        target_id="target-1",
        region="us-east-1",
        control_id="SecurityHub.1",
    )
    r = generate_pr_bundle(action, "terraform")
    readme = next(f for f in r["files"] if f["path"] == "README.txt")["content"]
    assert "terraform_plan_timestamp_utc:" in readme
    assert "preserved_configuration_statement:" in readme


def test_pr_bundle_s3_cloudfront_oac_private_variant_generates_real_iac() -> None:
    """S3.2 variant cloudfront_oac_private_s3 returns runnable CloudFront+OAC+private S3 Terraform."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        variant=PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3,
        risk_snapshot={"evidence": {"existing_bucket_policy_statement_count": 0}},
    )
    assert r["format"] == "terraform"
    paths = [f["path"] for f in r["files"]]
    assert "providers.tf" in paths
    assert "s3_cloudfront_oac_private_s3.tf" in paths
    assert "README.txt" in paths

    content = next(f for f in r["files"] if f["path"] == "s3_cloudfront_oac_private_s3.tf")["content"]
    assert "aws_cloudfront_origin_access_control" in content
    assert "aws_cloudfront_distribution" in content
    assert "aws_s3_bucket_policy" in content
    assert "aws_s3_bucket_public_access_block" in content
    assert 'bucket_name = "my-bucket"' in content


def test_pr_bundle_s3_cloudfront_oac_private_variant_uses_unique_oac_name_seed() -> None:
    """CloudFront+OAC variant should avoid static bucket-only OAC names that collide on reruns."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    result = generate_pr_bundle(
        action,
        "terraform",
        variant=PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3,
        risk_snapshot={"evidence": {"existing_bucket_policy_statement_count": 0}},
    )
    content = next(f for f in result["files"] if f["path"] == "s3_cloudfront_oac_private_s3.tf")["content"]
    assert "oac_name_seed" in content
    assert "security-autopilot-oac-${substr(md5(local.oac_name_seed)" in content
    assert "substr(md5(local.bucket_name), 0, 8)" not in content


def test_pr_bundle_s3_cloudfront_oac_private_variant_has_specific_readme_section() -> None:
    """Variant README includes migration-specific section."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        variant=PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3,
        risk_snapshot={"evidence": {"existing_bucket_policy_statement_count": 0}},
    )
    readme = next(f for f in r["files"] if f["path"] == "README.txt")["content"]
    assert "S3.2 migration variant (CloudFront + OAC + private S3)" in readme
    assert "additional_read_principal_arns" in readme


def test_pr_bundle_s3_cloudfront_oac_private_variant_cloudformation_raises_error() -> None:
    """CloudFormation for CloudFront/OAC S3 variant is rejected with a structured error."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "cloudformation",
            variant=PR_BUNDLE_VARIANT_CLOUDFRONT_OAC_PRIVATE_S3,
        )
    payload = exc_info.value.as_dict()
    assert payload["code"] == "unsupported_variant_format"


def test_pr_bundle_s3_cloudfront_oac_private_auto_preserves_existing_policy_from_risk_evidence() -> None:
    """CloudFront+OAC variant should preload existing non-risk bucket policy statements."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowCrossAccountRead",
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::my-bucket/*",
            },
            {
                "Sid": "AllowVpcScopedReadPath",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::my-bucket/*",
                "Condition": {"StringEquals": {"aws:SourceVpc": "vpc-0123456789abcdef0"}},
            },
        ],
    }
    risk_snapshot = {
        "evidence": {
            "existing_bucket_policy_statement_count": 2,
            "existing_bucket_policy_json": json.dumps(existing_policy),
        }
    }

    result = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_cloudfront_oac_private",
        risk_snapshot=risk_snapshot,
    )
    tfvars = next(f for f in result["files"] if f["path"] == "terraform.auto.tfvars.json")
    parsed_tfvars = json.loads(tfvars["content"])
    preserved_policy = json.loads(parsed_tfvars["existing_bucket_policy_json"])
    preserved_sids = sorted(stmt.get("Sid") for stmt in preserved_policy.get("Statement", []))
    assert preserved_sids == ["AllowCrossAccountRead", "AllowVpcScopedReadPath"]


def test_pr_bundle_s3_cloudfront_oac_private_fails_when_policy_exists_but_preservation_input_missing() -> None:
    """CloudFront+OAC variant fails closed when policy exists but preservation cannot be guaranteed."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    risk_snapshot = {"evidence": {"existing_bucket_policy_statement_count": 3}}

    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "terraform",
            strategy_id="s3_migrate_cloudfront_oac_private",
            risk_snapshot=risk_snapshot,
        )

    payload = exc_info.value.as_dict()
    assert payload["code"] == "existing_bucket_policy_preservation_required"


def test_s3_bucket_name_from_target_id() -> None:
    """_s3_bucket_name_from_target_id extracts bucket name from composite or plain target_id."""
    assert _s3_bucket_name_from_target_id("") == "REPLACE_BUCKET_NAME"
    assert _s3_bucket_name_from_target_id("my-bucket") == "my-bucket"
    assert _s3_bucket_name_from_target_id("arn:aws:s3:::demomarcoss") == "demomarcoss"
    composite = "029037611564|eu-north-1|arn:aws:s3:::demomarcoss|S3.2"
    assert _s3_bucket_name_from_target_id(composite) == "demomarcoss"
    assert _s3_bucket_name_from_target_id("029037611564|eu-north-1|no-arn-here|S3.2") == "no-arn-here"
    assert (
        _s3_bucket_name_from_target_id("029037611564|eu-north-1|AWS::::Account:029037611564|S3.15")
        == "REPLACE_BUCKET_NAME"
    )


def test_pr_bundle_bucket_actions_fail_on_unresolved_bucket_placeholder() -> None:
    """Bucket-scoped bundles must fail instead of shipping REPLACE_BUCKET_NAME placeholders."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="029037611564|eu-north-1|AWS::::Account:029037611564|S3.15",
        region="eu-north-1",
        control_id="S3.15",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(action, "terraform")
    payload = exc_info.value.as_dict()
    assert payload["code"] == "unresolved_placeholder_token"
    assert "REPLACE_BUCKET_NAME" in payload["detail"]


def test_pr_bundle_s3_bucket_block_cloudformation_step_9_9() -> None:
    """Step 9.9: CloudFormation for S3.2 (s3_bucket_block_public_access) has PublicAccessBlockConfiguration."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="blocked-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"] == "s3_bucket_block_public_access.yaml"
    content = r["files"][0]["content"]
    assert "AWS::S3::Bucket" in content
    assert "PublicAccessBlockConfiguration:" in content
    assert "BlockPublicAcls: true" in content or "BlockPublicAcls:" in content
    assert "BlockPublicPolicy" in content
    assert "IgnorePublicAcls" in content
    assert "RestrictPublicBuckets" in content
    assert "BucketName:" in content
    assert "S3.2" in content or "Control:" in content


def test_pr_bundle_dispatch_s3_bucket_encryption_terraform_step_9_10() -> None:
    """Step 9.10: s3_bucket_encryption returns Terraform with aws_s3_bucket_server_side_encryption_configuration."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION,
        target_id="encrypt-this-bucket",
        region="eu-west-1",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    resource_file = next(f for f in r["files"] if f["path"] == "s3_bucket_encryption.tf")
    assert "aws_s3_bucket_server_side_encryption_configuration" in resource_file["content"]
    assert "encrypt-this-bucket" in resource_file["content"]
    assert "AES256" in resource_file["content"]


def test_pr_bundle_s3_bucket_encryption_terraform_step_9_10_exact_structure() -> None:
    """Step 9.10: Terraform for S3.4 (s3_bucket_encryption) has exact structure: rule, AES256, bucket_key_enabled."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.4",
    )
    r = generate_pr_bundle(action, "terraform")
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_encryption.tf")["content"]
    assert 'resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot"' in content
    assert 'bucket = "my-bucket"' in content
    assert "rule {" in content
    assert "apply_server_side_encryption_by_default" in content
    assert 'sse_algorithm = "AES256"' in content
    assert "bucket_key_enabled = true" in content
    assert "S3.4" in content or "Control:" in content


def test_pr_bundle_s3_bucket_encryption_cloudformation_step_9_10() -> None:
    """Step 9.10: CloudFormation for S3.4 (s3_bucket_encryption) has BucketEncryption, AES256, BucketKeyEnabled."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION,
        target_id="encrypted-bucket",
        region="us-east-1",
        control_id="S3.4",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"] == "s3_bucket_encryption.yaml"
    content = r["files"][0]["content"]
    assert "AWS::S3::Bucket" in content
    assert "BucketEncryption:" in content
    assert "ServerSideEncryptionConfiguration:" in content
    assert "ServerSideEncryptionByDefault:" in content
    assert "SSEAlgorithm: AES256" in content
    assert "BucketKeyEnabled: true" in content
    assert "BucketName:" in content
    assert "S3.4" in content or "Control:" in content


def test_pr_bundle_s3_bucket_access_logging_terraform() -> None:
    """S3.9: access logging bundle uses aws_s3_bucket_logging and configurable log destination."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="log-source-bucket",
        region="us-east-1",
        control_id="S3.9",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_access_logging.tf")["content"]
    assert 'resource "aws_s3_bucket_logging" "security_autopilot"' in content
    assert 'variable "source_bucket_name"' in content
    assert 'default     = "log-source-bucket"' in content
    assert "bucket        = var.source_bucket_name" in content
    assert 'variable "log_bucket_name"' in content
    assert content.count('default     = "log-source-bucket"') >= 2
    assert "target_bucket = var.log_bucket_name" in content
    assert "S3.9" in content or "Control:" in content


def test_pr_bundle_s3_bucket_lifecycle_configuration_terraform() -> None:
    """S3.11: lifecycle bundle configures abort-incomplete-multipart lifecycle policy."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    content = next(
        f for f in r["files"] if f["path"] == "s3_bucket_lifecycle_configuration.tf"
    )["content"]
    assert 'resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot"' in content
    assert 'bucket = "lifecycle-bucket"' in content
    assert "abort_incomplete_multipart_upload" in content
    assert 'variable "abort_incomplete_multipart_days"' in content
    assert "S3.11" in content or "Control:" in content


def test_pr_bundle_s3_bucket_encryption_kms_terraform() -> None:
    """S3.15: encryption bundle configures SSE-KMS with safe default AWS-managed key."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="kms-bucket",
        region="us-east-1",
        control_id="S3.15",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_encryption_kms.tf")["content"]
    assert 'resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot"' in content
    assert 'bucket = "kms-bucket"' in content
    assert 'sse_algorithm     = "aws:kms"' in content
    assert 'variable "kms_key_arn"' in content
    assert 'default     = "arn:aws:kms:us-east-1:123456789012:alias/aws/s3"' in content
    assert "S3.15" in content or "Control:" in content


@pytest.mark.parametrize(
    ("action_type", "expected_path", "expected_snippet"),
    [
        (ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING, "s3_bucket_access_logging.yaml", "LoggingConfiguration"),
        (ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION, "s3_bucket_lifecycle_configuration.yaml", "LifecycleConfiguration"),
        (ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS, "s3_bucket_encryption_kms.yaml", "SSEAlgorithm: aws:kms"),
    ],
)
def test_pr_bundle_new_s3_controls_cloudformation(
    action_type: str,
    expected_path: str,
    expected_snippet: str,
) -> None:
    """New S3 controls render CloudFormation templates with expected resources/settings."""
    action = _make_action(
        action_type=action_type,
        target_id="example-bucket",
        region="us-east-1",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"] == expected_path
    assert expected_snippet in r["files"][0]["content"]


def test_pr_bundle_dispatch_sg_restrict_terraform_step_9_11() -> None:
    """Step 9.11: sg_restrict_public_ports returns Terraform with aws_vpc_security_group_ingress_rule."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-0123456789abcdef0",
        region="us-east-1",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    resource_file = next(f for f in r["files"] if f["path"] == "sg_restrict_public_ports.tf")
    assert "aws_vpc_security_group_ingress_rule" in resource_file["content"]
    assert "sg-0123456789abcdef0" in resource_file["content"]
    assert "22" in resource_file["content"] and "3389" in resource_file["content"]


def test_pr_bundle_sg_restrict_terraform_step_9_11_exact_structure() -> None:
    """Step 9.11: Terraform for EC2.53 (sg_restrict_public_ports) has exact structure: variables, SSH (22), RDP (3389), optional IPv6."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-abc123",
        region="us-east-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(action, "terraform")
    content = next(f for f in r["files"] if f["path"] == "sg_restrict_public_ports.tf")["content"]
    assert 'variable "security_group_id"' in content
    assert 'variable "allowed_cidr"' in content
    assert 'variable "allowed_cidr_ipv6"' in content
    assert '"sg-abc123"' in content
    assert '"10.0.0.0/8"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "ssh_restricted"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "rdp_restricted"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "ssh_restricted_ipv6"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "rdp_restricted_ipv6"' in content
    assert 'resource "null_resource" "revoke_public_admin_ingress"' in content
    assert "IpRanges=[{CidrIp=${var.allowed_cidr}}]" in content
    assert "Ipv6Ranges=[{CidrIpv6=${var.allowed_cidr_ipv6}}]" in content
    assert 'from_port         = 22' in content
    assert 'to_port           = 22' in content
    assert 'from_port         = 3389' in content
    assert 'to_port           = 3389' in content
    assert 'ip_protocol       = "tcp"' in content
    assert "cidr_ipv6" in content
    assert "EC2.53" in content or "Control:" in content


def test_pr_bundle_sg_restrict_cloudformation_step_9_11() -> None:
    """Step 9.11: CloudFormation for EC2.53 (sg_restrict_public_ports) has SecurityGroupIngress, SSH (22), RDP (3389), optional IPv6."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-xyz789",
        region="us-east-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"] == "sg_restrict_public_ports.yaml"
    content = r["files"][0]["content"]
    assert "AWS::EC2::SecurityGroupIngress" in content
    assert "SecurityGroupId:" in content
    assert "AllowedCidr:" in content
    assert "AllowedCidrIpv6:" in content
    assert "HasAllowedIpv6" in content
    assert "CidrIpv6:" in content
    assert "FromPort: 22" in content
    assert "ToPort: 22" in content
    assert "FromPort: 3389" in content
    assert "ToPort: 3389" in content
    assert "IpProtocol: tcp" in content
    assert "10.0.0.0/8" in content
    assert "EC2.53" in content or "Control:" in content


def test_pr_bundle_sg_restrict_target_id_composite_extracts_sg_id() -> None:
    """Composite target_id strings should normalize SecurityGroupId/security_group_id to plain sg-*."""
    composite_target_id = (
        "029037611564|eu-north-1|"
        "arn:aws:ec2:eu-north-1:029037611564:security-group/sg-0de002382892023f5|EC2.53"
    )
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id=composite_target_id,
        region="eu-north-1",
        control_id="EC2.53",
    )

    tf_bundle = generate_pr_bundle(action, "terraform")
    tf_content = next(f for f in tf_bundle["files"] if f["path"] == "sg_restrict_public_ports.tf")["content"]
    assert 'default     = "sg-0de002382892023f5"' in tf_content
    assert composite_target_id not in tf_content

    cfn_bundle = generate_pr_bundle(action, "cloudformation")
    cfn_content = next(f for f in cfn_bundle["files"] if f["path"] == "sg_restrict_public_ports.yaml")["content"]
    assert 'Default: "sg-0de002382892023f5"' in cfn_content
    assert composite_target_id not in cfn_content


def test_pr_bundle_sg_restrict_uses_resource_id_when_target_id_not_parseable() -> None:
    """SG bundle falls back to action.resource_id when target_id is account-scoped/stale."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="029037611564|eu-north-1|aws-account:029037611564|EC2.53",
        region="eu-north-1",
        control_id="EC2.53",
    )
    action.resource_id = "arn:aws:ec2:eu-north-1:029037611564:security-group/sg-0de002382892023f5"

    tf_bundle = generate_pr_bundle(action, "terraform")
    tf_content = next(f for f in tf_bundle["files"] if f["path"] == "sg_restrict_public_ports.tf")["content"]
    assert 'default     = "sg-0de002382892023f5"' in tf_content

    cfn_bundle = generate_pr_bundle(action, "cloudformation")
    cfn_content = next(f for f in cfn_bundle["files"] if f["path"] == "sg_restrict_public_ports.yaml")["content"]
    assert 'Default: "sg-0de002382892023f5"' in cfn_content


def test_pr_bundle_sg_restrict_unparseable_target_raises_structured_error() -> None:
    """When SG ID cannot be resolved, generation fails with explicit error payload."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="029037611564|eu-north-1|aws-account:029037611564|EC2.53",
        region="eu-north-1",
        control_id="EC2.53",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(action, "terraform")
    payload = exc_info.value.as_dict()
    assert payload["code"] == "missing_security_group_id"
    assert payload["action_type"] == ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS


def test_pr_bundle_iam_root_cloudformation_raises_structured_error() -> None:
    """IAM root access key remediation supports Terraform only."""
    action = _make_action(
        action_type=ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT,
        region="us-east-1",
        control_id="IAM.9",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(action, CLOUDFORMATION_FORMAT)
    payload = exc_info.value.as_dict()
    assert payload["code"] == "unsupported_format_for_action_type"
    assert payload["action_type"] == ACTION_TYPE_IAM_ROOT_ACCESS_KEY_ABSENT


def test_pr_bundle_dispatch_cloudtrail_terraform_step_9_12() -> None:
    """Step 9.12: cloudtrail_enabled returns Terraform with aws_cloudtrail."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
    )
    r = generate_pr_bundle(action, "terraform")
    assert r["format"] == "terraform"
    resource_file = next(f for f in r["files"] if f["path"] == "cloudtrail_enabled.tf")
    assert "aws_cloudtrail" in resource_file["content"]
    assert "is_multi_region_trail" in resource_file["content"]


def test_pr_bundle_cloudtrail_terraform_step_9_12_exact_structure() -> None:
    """Step 9.12: Terraform for CloudTrail.1 (cloudtrail_enabled) has exact structure: variable, aws_cloudtrail, multi-region."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(action, "terraform")
    content = next(f for f in r["files"] if f["path"] == "cloudtrail_enabled.tf")["content"]
    assert 'variable "trail_bucket_name"' in content
    assert 'resource "aws_cloudtrail" "security_autopilot"' in content
    assert "s3_bucket_name" in content
    assert "is_multi_region_trail" in content
    assert "include_global_service_events" in content
    assert "enable_logging" in content
    assert "CloudTrail.1" in content or "Control:" in content


def test_pr_bundle_cloudtrail_cloudformation_step_9_12() -> None:
    """Step 9.12: CloudFormation for CloudTrail.1 (cloudtrail_enabled) has AWS::CloudTrail::Trail, IsMultiRegionTrail, S3BucketName."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"] == "cloudtrail_enabled.yaml"
    content = r["files"][0]["content"]
    assert "AWS::CloudTrail::Trail" in content
    assert "TrailBucketName:" in content or "TrailBucketName" in content
    assert "IsMultiRegionTrail: true" in content or "IsMultiRegionTrail:" in content
    assert "IncludeGlobalServiceEvents" in content or "S3BucketName:" in content
    assert "CloudTrail.1" in content or "Control:" in content


def test_pr_bundle_dispatch_all_seven_cloudformation() -> None:
    """Step 9.5 / 9.9–9.12: All 7 types produce CloudFormation YAML (valid structure)."""
    types_and_paths = [
        (ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS, "s3_block_public_access.yaml"),
        (ACTION_TYPE_ENABLE_SECURITY_HUB, "enable_security_hub.yaml"),
        (ACTION_TYPE_ENABLE_GUARDDUTY, "enable_guardduty.yaml"),
        (ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS, "s3_bucket_block_public_access.yaml"),
        (ACTION_TYPE_S3_BUCKET_ENCRYPTION, "s3_bucket_encryption.yaml"),
        (ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS, "sg_restrict_public_ports.yaml"),
        (ACTION_TYPE_CLOUDTRAIL_ENABLED, "cloudtrail_enabled.yaml"),
    ]
    for action_type, expected_path in types_and_paths:
        target_id = "test-target"
        if action_type == ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS:
            target_id = "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0123456789abcdef0"
        action = _make_action(action_type=action_type, target_id=target_id, region="us-east-1")
        r = generate_pr_bundle(action, "cloudformation")
        assert r["format"] == "cloudformation"
        assert len(r["files"]) == 1
        assert r["files"][0]["path"] == expected_path
        content = r["files"][0]["content"]
        assert "AWSTemplateFormatVersion" in content or "Resources:" in content or "Description" in content


# ---------------------------------------------------------------------------
# Remediation audit (7.5)
# ---------------------------------------------------------------------------

def test_is_run_completed_success() -> None:
    """status success is completed."""
    assert is_run_completed(RemediationRunStatus.success) is True
    assert is_run_completed("success") is True


def test_is_run_completed_failed() -> None:
    """status failed is completed."""
    assert is_run_completed(RemediationRunStatus.failed) is True
    assert is_run_completed("failed") is True


def test_is_run_completed_pending_not_completed() -> None:
    """status pending is not completed."""
    assert is_run_completed(RemediationRunStatus.pending) is False
    assert is_run_completed("pending") is False


def test_allow_update_outcome_pending() -> None:
    """Pending run allows update."""
    class Run:
        status = RemediationRunStatus.pending
    assert allow_update_outcome(Run()) is True


def test_allow_update_outcome_success() -> None:
    """Completed run (success) does not allow update."""
    class Run:
        status = RemediationRunStatus.success
    assert allow_update_outcome(Run()) is False


def test_allow_update_outcome_failed() -> None:
    """Completed run (failed) does not allow update."""
    class Run:
        status = RemediationRunStatus.failed
    assert allow_update_outcome(Run()) is False


# ---------------------------------------------------------------------------
# SQS remediation_run payload (7.2 / 7.3)
# ---------------------------------------------------------------------------

def test_build_remediation_run_job_payload_shape() -> None:
    """Payload has job_type, run_id, tenant_id, action_id, mode, created_at."""
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    action_id = uuid.uuid4()
    created_at = "2026-02-02T12:00:00Z"
    payload = build_remediation_run_job_payload(run_id, tenant_id, action_id, "pr_only", created_at)
    assert payload["job_type"] == REMEDIATION_RUN_JOB_TYPE
    assert payload["run_id"] == str(run_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["action_id"] == str(action_id)
    assert payload["mode"] == "pr_only"
    assert payload["created_at"] == created_at


def test_build_remediation_run_job_payload_direct_fix() -> None:
    """Payload supports mode direct_fix."""
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    action_id = uuid.uuid4()
    payload = build_remediation_run_job_payload(run_id, tenant_id, action_id, "direct_fix", "2026-02-02T12:00:00Z")
    assert payload["mode"] == "direct_fix"


def test_build_remediation_run_job_payload_with_variant() -> None:
    """Payload includes optional pr_bundle_variant when provided."""
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    action_id = uuid.uuid4()
    payload = build_remediation_run_job_payload(
        run_id,
        tenant_id,
        action_id,
        "pr_only",
        "2026-02-02T12:00:00Z",
        pr_bundle_variant="cloudfront_oac_private_s3",
    )
    assert payload["mode"] == "pr_only"
    assert payload["pr_bundle_variant"] == "cloudfront_oac_private_s3"


# ---------------------------------------------------------------------------
# Worker handler registration (7.3)
# ---------------------------------------------------------------------------

def test_remediation_run_handler_registered() -> None:
    """Worker has a handler for remediation_run job type."""
    from backend.workers.jobs import get_job_handler
    handler = get_job_handler(REMEDIATION_RUN_JOB_TYPE)
    assert handler is not None
    assert callable(handler)
