"""
Pytest tests for Step 7 components.

Covers: PR bundle scaffold, remediation_audit guards, SQS remediation_run payload,
worker handler registration. Does not require DB or SQS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

import pytest

from backend.models.enums import RemediationRunStatus
from backend.services.aws_cloudfront_bundle_support import (
    AWS_CLOUDFRONT_OAC_DISCOVERY_QUERY_PATH,
    AWS_CLOUDFRONT_OAC_DISCOVERY_SCRIPT_PATH,
    aws_cloudfront_oac_discovery_script_content,
)
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
from backend.services.remediation_strategy import list_strategies_for_action_type
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


def _bundle_file_content(bundle: dict[str, object], path: str) -> str:
    file_item = next(item for item in bundle["files"] if item["path"] == path)
    return str(file_item["content"])


def _write_bundle_files(bundle: dict[str, object], directory: Path) -> None:
    for item in bundle["files"]:
        path = directory / str(item["path"])
        path.write_text(str(item["content"]), encoding="utf-8")


def _terraform_env_with_mirror(temp_dir: Path) -> dict[str, str]:
    plugin_cache_dir = Path.home() / ".terraform.d" / "plugin-cache"
    plugin_cache_dir.mkdir(parents=True, exist_ok=True)
    tf_cli_config = temp_dir / "terraform.tfrc"
    tf_cli_config.write_text(
        'provider_installation {\n'
        '  filesystem_mirror {\n'
        f'    path    = "{plugin_cache_dir}"\n'
        '    include = ["registry.terraform.io/hashicorp/aws", "registry.terraform.io/hashicorp/null"]\n'
        "  }\n"
        "  direct {}\n"
        "}\n",
        encoding="utf-8",
    )
    terraform_env = dict(os.environ)
    terraform_env["TF_CLI_CONFIG_FILE"] = str(tf_cli_config)
    return terraform_env


def _run_cloudfront_oac_discovery_script(
    query: dict[str, str],
    responses: dict[str, object],
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        script_path = temp_dir / "cloudfront_oac_discovery.py"
        script_path.write_text(
            aws_cloudfront_oac_discovery_script_content(),
            encoding="utf-8",
        )
        script_path.chmod(0o755)

        aws_path = temp_dir / "aws"
        aws_path.write_text(
            (
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import os\n"
                "import sys\n"
                "\n"
                "responses = json.loads(os.environ['FAKE_AWS_RESPONSES'])\n"
                "args = sys.argv[1:]\n"
                "if args[-2:] == ['--output', 'json']:\n"
                "    args = args[:-2]\n"
                "key = ' '.join(args)\n"
                "payload = responses[key]\n"
                "if isinstance(payload, dict) and '__error__' in payload:\n"
                "    sys.stderr.write(str(payload['__error__']))\n"
                "    sys.exit(int(payload.get('__code__', 1)))\n"
                "json.dump(payload, sys.stdout)\n"
            ),
            encoding="utf-8",
        )
        aws_path.chmod(0o755)

        env = os.environ.copy()
        env["FAKE_AWS_RESPONSES"] = json.dumps(responses)
        env["PATH"] = f"{temp_dir}{os.pathsep}{env['PATH']}"
        return subprocess.run(
            ["python3", str(script_path)],
            input=json.dumps(query),
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )


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
    """Step 9.5: S3 CloudFormation uses a Lambda custom resource (no placeholder/no-op)."""
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
    assert "WaitConditionHandle" not in content
    assert "AWS::Lambda::Function" in content
    assert "Type: Custom::S3AccountPublicAccessBlock" in content
    assert "s3control.put_public_access_block(" in content
    assert '"BlockPublicAcls": True' in content
    assert '"IgnorePublicAcls": True' in content
    assert '"BlockPublicPolicy": True' in content
    assert '"RestrictPublicBuckets": True' in content
    assert 'if request_type == "Delete":' in content
    assert 'cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, "S3PublicAccessBlock")' in content
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
    strategy_inputs = None
    if action_type == ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING:
        strategy_inputs = {"log_bucket_name": "security-autopilot-log-bucket"}
    elif action_type == ACTION_TYPE_CLOUDTRAIL_ENABLED:
        strategy_inputs = {"trail_bucket_name": "security-autopilot-cloudtrail-logs"}
    elif action_type == ACTION_TYPE_S3_BUCKET_REQUIRE_SSL:
        strategy_inputs = {"existing_bucket_policy_json": '{"Version":"2012-10-17","Statement":[]}'}
    r = generate_pr_bundle(action, "terraform", strategy_inputs=strategy_inputs)
    paths = [f["path"] for f in r["files"]]
    assert expected_path in paths
    assert "README.tf" not in paths
    assert "README.yaml" not in paths


def test_pr_bundle_aws_config_enabled_uses_json_boolean_recording_group_payload() -> None:
    """Config.1 Terraform bundle uses JSON recorder payloads and overwrite toggle wiring."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform", strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs"})
    content = _bundle_file_content(r, "aws_config_enabled.tf")
    apply_script = _bundle_file_content(r, "scripts/aws_config_apply.py")

    assert 'variable "overwrite_recording_group"' in content
    assert "default     = false" in content
    assert 'export REGION="${var.remediation_region}"' in content
    assert 'export ROLLBACK_DIR=".aws-config-rollback"' in content
    assert "python3 ./scripts/aws_config_apply.py" in content
    assert "DEFAULT_REGION = 'eu-north-1'" in apply_script
    assert "DEFAULT_BUCKET = 'security-autopilot-config-111122223333-eu-north-1'" in apply_script
    assert "DEFAULT_ROLE_ARN = 'arn:aws:iam::111122223333:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig'" in apply_script
    assert "DEFAULT_CREATE_LOCAL_BUCKET = True" in apply_script
    assert "DEFAULT_OVERWRITE_RECORDING_GROUP = False" in apply_script
    assert "put-configuration-recorder" in apply_script
    assert '"allSupported": True' in apply_script
    assert '"includeGlobalResourceTypes": True' in apply_script
    assert 'put_structured_payload("put-configuration-recorder"' in apply_script
    assert 'create_bucket(bucket, region, object_lock_enabled=True)' in apply_script
    assert "put-bucket-versioning" in apply_script
    assert "put-bucket-notification-configuration" in apply_script
    assert "put-object-lock-configuration" in apply_script


def test_pr_bundle_aws_config_enabled_declares_null_provider_for_local_exec_bundle() -> None:
    """Config.1 bundle should pin the null provider used by its local-exec wrapper."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform", strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs"})
    providers = _bundle_file_content(r, "providers.tf")

    assert 'null = {' in providers
    assert 'source  = "hashicorp/null"' in providers
    assert 'version = "= 3.2.4"' in providers


def test_pr_bundle_aws_config_enabled_preserves_selective_recorder_by_default() -> None:
    """Recorder preflight should preserve selective mode unless overwrite is explicitly enabled."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    content = _bundle_file_content(r, "aws_config_enabled.tf")
    apply_script = _bundle_file_content(r, "scripts/aws_config_apply.py")

    assert 'default     = false' in content
    assert 'load_or_capture_snapshot(snapshot_dir, region=region, bucket=bucket)' in apply_script
    assert 'if not bool(summary.get("recorder_exists")) or overwrite_recording_group:' in apply_script
    assert "Preserving existing selective AWS Config recorder" in apply_script


def test_pr_bundle_aws_config_enabled_reuses_existing_recorder_name() -> None:
    """Config.1 preflight should reuse existing recorder name rather than creating duplicates."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    apply_script = _bundle_file_content(r, "scripts/aws_config_apply.py")

    assert 'pre_configuration_recorders.json' in apply_script
    assert 'recorder_name = str(summary.get("recorder_name") or "") or "security-autopilot-recorder"' in apply_script
    assert 'delivery_name = str(summary.get("delivery_channel_name") or "") or "security-autopilot-delivery-channel"' in apply_script
    assert 'target_bucket_created_by_apply' in apply_script
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/aws_config_restore.py",
        "runner": "python3",
    }


def test_pr_bundle_aws_config_enabled_delivery_bucket_mismatch_warning_surfaces_in_readme() -> None:
    """README should describe delivery-channel mismatch warning behavior."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    content = _bundle_file_content(r, "scripts/aws_config_apply.py")
    readme = _bundle_file_content(r, "README.txt")

    assert "WARNING: Existing AWS Config delivery channel" in content
    assert "Config.1 preflight safeguards" in readme
    assert "Delivery safety: if an existing delivery channel points to a different bucket" in readme
    assert "Delivery fail-closed" in readme
    assert "rollback/aws_config_restore.py" in readme


def test_pr_bundle_aws_config_enabled_uses_explicit_region_for_s3_bucket_create() -> None:
    """Config.1 local bucket create/check path should always pin AWS CLI region explicitly."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-central-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    content = _bundle_file_content(r, "scripts/aws_config_apply.py")

    assert '["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region]' in content
    assert 'args = ["aws", "s3api", "create-bucket", "--bucket", bucket, "--region", region]' in content
    assert 'f"LocationConstraint={region}"' in content


def test_pr_bundle_aws_config_enabled_centralized_delivery_fails_closed_on_unreachable_bucket() -> None:
    """Config.1 centralized delivery path should fail closed when delivery bucket is unreachable/stale."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-central-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="config_enable_centralized_delivery",
        strategy_inputs={"delivery_bucket": "centralized-config-bucket-111122223333"},
    )
    content = _bundle_file_content(r, "scripts/aws_config_apply.py")

    assert "create_local_bucket=false and delivery bucket" in content
    assert "create_local_bucket=false and delivery bucket '{bucket}' is unreachable" in content
    assert "points to unreachable bucket " in content
    assert "'{existing_delivery_bucket}' and create_local_bucket=false cannot repair it." in content
    assert "create_local_bucket=false cannot repair it" in content


def test_pr_bundle_aws_config_enabled_merges_bucket_policy_before_put() -> None:
    """Config.1 local bucket policy step should merge existing policy statements before write."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    content = _bundle_file_content(r, "scripts/aws_config_apply.py")

    assert "pre_target_bucket_state.json" in content
    assert "build_required_bucket_policy" in content
    assert "merge_bucket_policies" in content
    assert '"Sid": "AWSConfigBucketPermissionsCheck"' in content
    assert '"Sid": "AWSConfigBucketExistenceCheck"' in content
    assert '"Sid": "AWSConfigBucketDelivery"' in content
    assert '"AWS:SourceAccount": account_id' in content
    assert "put_bucket_policy(bucket, region, merged_policy)" in content


def test_pr_bundle_aws_config_enabled_captures_exact_pre_state_for_rollback() -> None:
    """Config.1 executable bundle snapshots exact pre-state before mutation."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    apply_script = _bundle_file_content(r, "scripts/aws_config_apply.py")

    assert "pre_configuration_recorders.json" in apply_script
    assert "pre_configuration_recorder_status.json" in apply_script
    assert "pre_delivery_channels.json" in apply_script
    assert "pre_target_bucket_state.json" in apply_script
    assert "pre_state_summary.json" in apply_script
    assert "Exact AWS Config rollback is unsupported when multiple configuration recorders exist." in apply_script
    assert "Exact AWS Config rollback is unsupported when multiple delivery channels exist." in apply_script


def test_pr_bundle_aws_config_enabled_restore_script_restores_prior_state_instead_of_deleting_it() -> None:
    """Config.1 rollback helper should restore captured state and fail closed on unsafe cleanup."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "terraform")
    restore_script = _bundle_file_content(r, "rollback/aws_config_restore.py")

    assert "DEFAULT_REGION = 'eu-north-1'" in restore_script
    assert 'os.environ.get("REGION", "").strip() or DEFAULT_REGION.strip()' in restore_script
    assert "pre_configuration_recorders.json" in restore_script
    assert "pre_delivery_channels.json" in restore_script
    assert "pre_target_bucket_state.json" in restore_script
    assert 'put_structured_payload("put-configuration-recorder", pre_recorder, region=region)' in restore_script
    assert 'put_structured_payload("put-delivery-channel", pre_delivery, region=region)' in restore_script
    assert '"delete-delivery-channel"' in restore_script
    assert '"delete-configuration-recorder"' in restore_script
    assert "Rollback would need to delete non-empty bucket" in restore_script
    assert "exact rollback is not guaranteed." in restore_script


def test_pr_bundle_aws_config_enabled_cloudformation_overwrite_toggle_defaults_safe() -> None:
    """Config.1 CloudFormation template should expose overwrite toggle with safe default."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(action, "cloudformation", strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs"})
    content = next(f for f in r["files"] if f["path"] == "aws_config_enabled.yaml")["content"]

    assert "OverwriteRecordingGroup:" in content
    assert 'Default: "false"' in content
    assert "ShouldOverwriteRecordingGroup" in content
    assert "RecordingGroup: !If" in content


def test_config_1_strategy_schema_guided_choice_fields() -> None:
    """Task 4: Config.1 strategy exposes guided schema fields for scope, delivery, and KMS toggles."""
    strategies = {
        strategy["strategy_id"]: strategy
        for strategy in list_strategies_for_action_type(ACTION_TYPE_AWS_CONFIG_ENABLED)
    }
    strategy = strategies["config_enable_centralized_delivery"]
    fields = {field["key"]: field for field in strategy["input_schema"]["fields"]}
    account_local_fields = {
        field["key"]: field
        for field in strategies["config_enable_account_local_delivery"]["input_schema"]["fields"]
    }

    recording_scope = fields["recording_scope"]
    assert recording_scope["type"] == "select"
    assert [option["value"] for option in recording_scope.get("options", [])] == [
        "all_resources",
        "keep_existing",
    ]
    assert account_local_fields["recording_scope"]["type"] == "select"
    assert [option["value"] for option in account_local_fields["recording_scope"].get("options", [])] == [
        "all_resources",
        "keep_existing",
    ]

    delivery_bucket_mode = fields["delivery_bucket_mode"]
    assert delivery_bucket_mode["type"] == "select"
    assert [option["value"] for option in delivery_bucket_mode.get("options", [])] == [
        "create_new",
        "use_existing",
    ]

    existing_bucket_name = fields["existing_bucket_name"]
    assert existing_bucket_name["type"] == "string"
    assert existing_bucket_name["visible_when"] == {
        "field": "delivery_bucket_mode",
        "equals": "use_existing",
    }

    encrypt_with_kms = fields["encrypt_with_kms"]
    assert encrypt_with_kms["type"] == "boolean"

    kms_key_arn = fields["kms_key_arn"]
    assert kms_key_arn["type"] == "string"
    assert kms_key_arn["visible_when"] == {
        "field": "encrypt_with_kms",
        "equals": True,
    }


def test_pr_bundle_aws_config_enabled_guided_inputs_drive_terraform_defaults() -> None:
    """Task 4: Config.1 Terraform wiring should honor guided strategy input defaults."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="config_enable_account_local_delivery",
        strategy_inputs={
            "recording_scope": "all_resources",
            "delivery_bucket_mode": "use_existing",
            "existing_bucket_name": "shared-config-bucket-111122223333",
            "encrypt_with_kms": True,
            "kms_key_arn": "arn:aws:kms:eu-north-1:111122223333:key/1234abcd",
        },
    )
    content = next(f for f in r["files"] if f["path"] == "aws_config_enabled.tf")["content"]

    assert 'variable "delivery_bucket_name"' in content
    assert 'default     = "shared-config-bucket-111122223333"' in content
    assert 'variable "create_local_bucket"' in content
    assert 'default     = false' in content
    assert 'variable "overwrite_recording_group"' in content
    assert 'default     = true' in content
    assert 'variable "kms_key_arn"' in content
    assert 'default     = "arn:aws:kms:eu-north-1:111122223333:key/1234abcd"' in content


def test_pr_bundle_aws_config_enabled_guidance_describes_auto_promoted_selective_recorders() -> None:
    """Config.1 bundle guidance should describe the auto-promotion executable path."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="config_enable_account_local_delivery",
        strategy_inputs={"recording_scope": "all_resources"},
    )
    readme = _bundle_file_content(r, "README.txt")

    assert "resolver auto-promotes `recording_scope=all_resources`" in readme
    assert any(
        "selective/custom recorders should resolve to all-supported recording" in step
        for step in r["steps"]
    )


def test_pr_bundle_aws_config_enabled_guided_inputs_drive_cloudformation_defaults() -> None:
    """Task 4: Config.1 CloudFormation wiring should honor guided strategy input defaults."""
    action = _make_action(
        action_type=ACTION_TYPE_AWS_CONFIG_ENABLED,
        account_id="111122223333",
        region="eu-north-1",
        control_id="Config.1",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_id="config_enable_account_local_delivery",
        strategy_inputs={
            "recording_scope": "all_resources",
            "delivery_bucket_mode": "use_existing",
            "existing_bucket_name": "shared-config-bucket-111122223333",
            "encrypt_with_kms": True,
            "kms_key_arn": "arn:aws:kms:eu-north-1:111122223333:key/1234abcd",
        },
    )
    content = next(f for f in r["files"] if f["path"] == "aws_config_enabled.yaml")["content"]

    assert "DeliveryBucketName:" in content
    assert 'Default: "shared-config-bucket-111122223333"' in content
    assert 'Default: "true"' in content
    assert "S3KmsKeyArn: arn:aws:kms:eu-north-1:111122223333:key/1234abcd" in content
    assert "ConfigDeliveryBucket:" not in content


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
    assert "S3.2 post-fix access guidance" in readme
    assert "NOT a full CloudFront + OAC + private S3 migration" in readme
    assert "What changes" in readme
    assert "How to access now" in readme


def test_pr_bundle_s3_bucket_block_public_policy_scrub_review_bundle_contains_apply_time_filtering() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="public-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    result = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_bucket_block_public_access_standard",
        resolution={
            "strategy_id": "s3_bucket_block_public_access_standard",
            "profile_id": "s3_bucket_block_public_access_review_public_policy_scrub",
            "support_tier": "review_required_bundle",
            "blocked_reasons": [
                "Bucket policy is currently public; generated Terraform will scrub unconditional public Allow statements before enabling Block Public Access."
            ],
            "preservation_summary": {
                "public_policy_scrub_available": True,
                "public_policy_scrub_reason": "review bundle will remove unconditional public Allow statements",
                "manual_preservation_required": False,
            },
            "decision_rationale": "Review bundle required for public policy scrub.",
        },
    )

    content = _bundle_file_content(result, "s3_bucket_block_public_access.tf")
    readme = _bundle_file_content(result, "README.txt")
    assert 'data "aws_s3_bucket_policy" "existing"' in content
    assert 'resource "aws_s3_bucket_policy" "security_autopilot"' in content
    assert 'count  = length(local.preserved_policy_statements) > 0 ? 1 : 0' in content
    assert 'resource "terraform_data" "delete_bucket_policy"' in content
    assert 'count = length(local.preserved_policy_statements) == 0 ? 1 : 0' in content
    assert 'aws s3api delete-bucket-policy --bucket "public-bucket"' in content
    assert 'resource "aws_s3_bucket_public_access_block" "security_autopilot"' in content
    assert "removed_statement_count" in content
    assert "removed_statement_identifiers" in content
    assert 'lower(trimspace(try(tostring(statement.Effect), ""))) == "allow"' in content
    assert "!can(statement.Condition)" in content
    assert 'trimspace(try(tostring(statement.Principal), "")) == "*"' in content
    assert "depends_on = [" in content
    assert "aws_s3_bucket_policy.security_autopilot" in content
    assert "terraform_data.delete_bucket_policy" in content
    assert "public-policy scrub branches remove unconditional public Allow statements" in readme


def test_pr_bundle_s3_bucket_block_public_policy_scrub_cloudformation_raises_error() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="public-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "cloudformation",
            strategy_id="s3_bucket_block_public_access_standard",
            resolution={
                "strategy_id": "s3_bucket_block_public_access_standard",
                "profile_id": "s3_bucket_block_public_access_review_public_policy_scrub",
                "support_tier": "review_required_bundle",
                "blocked_reasons": [
                    "Bucket policy is currently public; generated Terraform will scrub unconditional public Allow statements before enabling Block Public Access."
                ],
                "preservation_summary": {
                    "public_policy_scrub_available": True,
                    "manual_preservation_required": False,
                },
                "decision_rationale": "Review bundle required for public policy scrub.",
            },
        )
    assert exc_info.value.as_dict()["code"] == "unsupported_variant_format"


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
    assert "S3.2 post-fix access guidance" not in readme


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


@pytest.mark.parametrize(
    ("action_type", "target_id", "control_id", "risk_snapshot", "expected_snippets"),
    [
        (
            ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
            "my-bucket",
            "S3.2",
            None,
            [
                "S3.2 post-fix access guidance",
                "CloudFront usage note",
                "curl -I https://<cloudfront-domain>/<object-key>",
                "aws s3api get-public-access-block --bucket <bucket-name>",
            ],
        ),
        (
            ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
            "sg-0abc1234def567890",
            "EC2.53",
            None,
            [
                "EC2.53 post-fix access guidance",
                "aws ssm start-session --target <instance-id> --region <region>",
                "describe-security-group-rules --region <region>",
                "authorize-security-group-ingress --region <region>",
            ],
        ),
        (
            ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
            "my-bucket",
            "S3.5",
            {"evidence": {"existing_bucket_policy_statement_count": 0}},
            [
                "S3.5 post-fix access guidance",
                "HTTPS requirement",
                "curl -I http://<bucket-name>.s3.<region>.amazonaws.com/<object-key>",
                "get-bucket-policy --bucket <bucket-name> --query Policy --output text > pre-remediation-policy.json",
                "put-bucket-policy --bucket <bucket-name> --policy file://pre-remediation-policy.json",
            ],
        ),
        (
            ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING,
            "account-ssm",
            "SSM.7",
            None,
            [
                "SSM.7 post-fix access guidance",
                "modify-document-permission --name <document-name>",
                "get-service-setting --setting-id arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/documents/console/public-sharing-permission",
                "update-service-setting --setting-id arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/documents/console/public-sharing-permission --setting-value Enable",
            ],
        ),
    ],
)
def test_pr_bundle_terraform_readme_includes_post_fix_access_guidance(
    action_type: str,
    target_id: str,
    control_id: str,
    risk_snapshot: dict[str, object] | None,
    expected_snippets: list[str],
) -> None:
    """Terraform README appends post-fix access guidance for high-risk controls."""
    action = _make_action(
        action_type=action_type,
        target_id=target_id,
        region="us-east-1",
        control_id=control_id,
    )
    bundle = generate_pr_bundle(action, "terraform", risk_snapshot=risk_snapshot)
    readme = next(f for f in bundle["files"] if f["path"] == "README.txt")["content"]
    for snippet in expected_snippets:
        assert snippet in readme


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
    assert AWS_CLOUDFRONT_OAC_DISCOVERY_SCRIPT_PATH in paths
    assert AWS_CLOUDFRONT_OAC_DISCOVERY_QUERY_PATH in paths
    assert "README.txt" in paths

    providers = _bundle_file_content(r, "providers.tf")
    content = next(f for f in r["files"] if f["path"] == "s3_cloudfront_oac_private_s3.tf")["content"]
    assert 'external = {' not in providers
    assert 'source  = "hashicorp/external"' not in providers
    assert "aws_cloudfront_origin_access_control" in content
    assert "aws_cloudfront_distribution" in content
    assert "aws_s3_bucket_policy" in content
    assert "aws_s3_bucket_public_access_block" in content
    assert 'data "external" "cloudfront_reuse"' not in content
    assert 'variable "cloudfront_reuse_mode"' in content
    assert 'variable "reuse_oac_id"' in content
    assert 'variable "reuse_distribution_id"' in content
    assert 'variable "reuse_distribution_arn"' in content
    assert 'variable "reuse_distribution_domain_name"' in content
    assert "effective_oac_id = (" in content
    assert "effective_distribution_id = (" in content
    assert 'count                             = local.reuse_oac ? 0 : 1' in content
    assert 'count               = local.reuse_distribution ? 0 : 1' in content
    assert 'bucket_name                         = "my-bucket"' in content
    assert 'cloudfront_reuse_mode = var.cloudfront_reuse_mode' in content


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
    query = json.loads(_bundle_file_content(result, AWS_CLOUDFRONT_OAC_DISCOVERY_QUERY_PATH))
    assert 'oac_name                            = "security-autopilot-oac-' in content
    assert query["expected_oac_name"].startswith("security-autopilot-oac-")
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


def test_pr_bundle_s3_cloudfront_oac_private_strips_previous_managed_cloudfront_statement() -> None:
    """Preloaded S3.2 policy JSON should drop the prior managed AllowCloudFrontReadOnly statement."""
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
                "Sid": "AllowCloudFrontReadOnly",
                "Effect": "Allow",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::my-bucket/*",
            },
            {
                "Sid": "KeepDirectRead",
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::my-bucket/*",
            },
        ],
    }

    result = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_cloudfront_oac_private",
        risk_snapshot={
            "evidence": {
                "existing_bucket_policy_statement_count": 2,
                "existing_bucket_policy_json": json.dumps(existing_policy),
            }
        },
    )

    tfvars = json.loads(_bundle_file_content(result, "terraform.auto.tfvars.json"))
    preserved_policy = json.loads(tfvars["existing_bucket_policy_json"])
    preserved_sids = [stmt.get("Sid") for stmt in preserved_policy["Statement"]]
    assert preserved_sids == ["KeepDirectRead"]


def test_pr_bundle_s3_cloudfront_oac_private_apply_time_merge_uses_resolution_summary() -> None:
    """CloudFront+OAC variant can fetch and merge the live bucket policy at apply time."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.2",
    )

    result = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_cloudfront_oac_private",
        resolution={
            "strategy_id": "s3_migrate_cloudfront_oac_private",
            "profile_id": "s3_migrate_cloudfront_oac_private",
            "support_tier": "deterministic_bundle",
            "blocked_reasons": [],
            "preservation_summary": {
                "apply_time_merge": True,
                "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
            },
            "decision_rationale": "Apply-time merge is allowed.",
        },
    )

    paths = [f["path"] for f in result["files"]]
    providers = _bundle_file_content(result, "providers.tf")
    content = next(f for f in result["files"] if f["path"] == "s3_cloudfront_oac_private_s3.tf")["content"]

    assert 'external = {' not in providers
    assert 'data "aws_s3_bucket_policy" "existing"' in content
    assert 'data "external" "cloudfront_reuse"' not in content
    assert "effective_oac_id = (" in content
    assert "filtered_existing_policy_statements" in content
    assert 'data "aws_iam_policy_document" "bucket_policy"' in content
    assert 'resource "aws_s3_bucket_policy" "security_autopilot"' in content
    assert "terraform.auto.tfvars.json" not in paths
    assert any("fetched and merged at terraform plan/apply time" in step for step in result["steps"])


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


def test_pr_bundle_s3_website_cloudfront_private_generates_real_iac() -> None:
    """Website migration variant emits CloudFront, Route53, website removal, and BPA resources."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="website-bucket",
        region="us-east-1",
        control_id="S3.2",
    )

    result = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_website_cloudfront_private",
        strategy_inputs={
            "aliases": ["www.example.com"],
            "route53_hosted_zone_id": "Z123456ABCDEFG",
            "acm_certificate_arn": "arn:aws:acm:us-east-1:123456789012:certificate/abc",
        },
        risk_snapshot={
            "evidence": {
                "existing_bucket_policy_statement_count": 0,
                "existing_bucket_website_configuration_json": json.dumps(
                    {
                        "IndexDocument": {"Suffix": "index.html"},
                        "ErrorDocument": {"Key": "error.html"},
                    }
                ),
            }
        },
    )

    paths = [f["path"] for f in result["files"]]
    assert "providers.tf" in paths
    assert "s3_website_cloudfront_private.tf" in paths
    assert "terraform.auto.tfvars.json" in paths
    assert "README.txt" in paths

    content = _bundle_file_content(result, "s3_website_cloudfront_private.tf")
    tfvars = json.loads(_bundle_file_content(result, "terraform.auto.tfvars.json"))
    assert "aws_cloudfront_origin_access_control" in content
    assert "aws_cloudfront_distribution" in content
    assert 'resource "aws_route53_record" "website_ipv4"' in content
    assert 'resource "aws_route53_record" "website_ipv6"' in content
    assert 'resource "null_resource" "disable_bucket_website"' in content
    assert 'resource "aws_s3_bucket_public_access_block" "security_autopilot"' in content
    assert "default_root_object = var.default_root_object" in content
    assert "acm_certificate_arn      = var.acm_certificate_arn" in content
    assert "aliases             = var.aliases" in content
    assert tfvars["existing_bucket_website_configuration_json"]


def test_pr_bundle_s3_website_cloudfront_private_apply_time_merge_uses_resolution_summary() -> None:
    """Website migration variant can merge the live bucket policy at apply time."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="website-bucket",
        region="us-east-1",
        control_id="S3.2",
    )

    result = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_website_cloudfront_private",
        strategy_inputs={
            "aliases": ["www.example.com"],
            "route53_hosted_zone_id": "Z123456ABCDEFG",
            "acm_certificate_arn": "arn:aws:acm:us-east-1:123456789012:certificate/abc",
        },
        risk_snapshot={
            "evidence": {
                "existing_bucket_website_configuration_json": json.dumps(
                    {"IndexDocument": {"Suffix": "index.html"}}
                ),
            }
        },
        resolution={
            "strategy_id": "s3_migrate_website_cloudfront_private",
            "profile_id": "s3_migrate_website_cloudfront_private",
            "support_tier": "deterministic_bundle",
            "blocked_reasons": [],
            "preservation_summary": {
                "apply_time_merge": True,
                "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
            },
            "decision_rationale": "Apply-time merge is allowed.",
        },
    )

    content = _bundle_file_content(result, "s3_website_cloudfront_private.tf")
    tfvars = json.loads(_bundle_file_content(result, "terraform.auto.tfvars.json"))
    assert 'data "aws_s3_bucket_policy" "existing"' in content
    assert "filtered_existing_policy_statements" in content
    assert "existing_bucket_policy_json" not in tfvars
    assert "existing_bucket_website_configuration_json" in tfvars


def test_pr_bundle_s3_website_cloudfront_private_cloudformation_raises_error() -> None:
    """Website migration variant is Terraform-only."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="website-bucket",
        region="us-east-1",
        control_id="S3.2",
    )

    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "cloudformation",
            strategy_id="s3_migrate_website_cloudfront_private",
            strategy_inputs={
                "aliases": ["www.example.com"],
                "route53_hosted_zone_id": "Z123456ABCDEFG",
                "acm_certificate_arn": "arn:aws:acm:us-east-1:123456789012:certificate/abc",
            },
            risk_snapshot={
                "evidence": {
                    "existing_bucket_website_configuration_json": json.dumps(
                        {"IndexDocument": {"Suffix": "index.html"}}
                    ),
                }
            },
        )

    assert exc_info.value.as_dict()["code"] == "unsupported_variant_format"


def test_pr_bundle_s3_website_cloudfront_private_rejects_routing_rules() -> None:
    """Complex S3 website routing rules stay fail-closed in bundle generation."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="website-bucket",
        region="us-east-1",
        control_id="S3.2",
    )

    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "terraform",
            strategy_id="s3_migrate_website_cloudfront_private",
            strategy_inputs={
                "aliases": ["www.example.com"],
                "route53_hosted_zone_id": "Z123456ABCDEFG",
                "acm_certificate_arn": "arn:aws:acm:us-east-1:123456789012:certificate/abc",
            },
            risk_snapshot={
                "evidence": {
                    "existing_bucket_website_configuration_json": json.dumps(
                        {
                            "IndexDocument": {"Suffix": "index.html"},
                            "RoutingRules": [{"Condition": {"KeyPrefixEquals": "docs/"}}],
                        }
                    ),
                }
            },
        )

    assert exc_info.value.as_dict()["code"] == "unsupported_website_configuration"


def test_pr_bundle_s3_website_cloudfront_private_has_specific_readme_section() -> None:
    """README includes website cutover-specific guidance."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="website-bucket",
        region="us-east-1",
        control_id="S3.2",
    )

    result = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_website_cloudfront_private",
        strategy_inputs={
            "aliases": ["www.example.com"],
            "route53_hosted_zone_id": "Z123456ABCDEFG",
            "acm_certificate_arn": "arn:aws:acm:us-east-1:123456789012:certificate/abc",
        },
        risk_snapshot={
            "evidence": {
                "existing_bucket_policy_statement_count": 0,
                "existing_bucket_website_configuration_json": json.dumps(
                    {"IndexDocument": {"Suffix": "index.html"}}
                ),
            }
        },
    )

    readme = _bundle_file_content(result, "README.txt")
    assert "S3 website migration variant (CloudFront + private S3 + Route53)" in readme
    assert "existing_bucket_website_configuration_json" in readme


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform is not installed")
def test_pr_bundle_s3_website_cloudfront_private_terraform_validate() -> None:
    """Website migration Terraform bundle should pass terraform validate in a temp dir."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="website-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    bundle = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_website_cloudfront_private",
        strategy_inputs={
            "aliases": ["www.example.com"],
            "route53_hosted_zone_id": "Z123456ABCDEFG",
            "acm_certificate_arn": "arn:aws:acm:us-east-1:123456789012:certificate/abc",
        },
        risk_snapshot={
            "evidence": {
                "existing_bucket_policy_statement_count": 0,
                "existing_bucket_website_configuration_json": json.dumps(
                    {
                        "IndexDocument": {"Suffix": "index.html"},
                        "ErrorDocument": {"Key": "error.html"},
                    }
                ),
            }
        },
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        bundle_dir = Path(temp_dir)
        _write_bundle_files(bundle, bundle_dir)
        terraform_env = _terraform_env_with_mirror(bundle_dir)
        init_result = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=bundle_dir,
            capture_output=True,
            text=True,
            check=False,
            env=terraform_env,
            timeout=120,
        )
        assert init_result.returncode == 0, init_result.stdout + init_result.stderr

        validate_result = subprocess.run(
            ["terraform", "validate", "-no-color"],
            cwd=bundle_dir,
            capture_output=True,
            text=True,
            check=False,
            env=terraform_env,
            timeout=120,
        )
        assert validate_result.returncode == 0, validate_result.stdout + validate_result.stderr


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform is not installed")
def test_pr_bundle_s3_bucket_block_public_policy_scrub_terraform_validate() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="public-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    bundle = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_bucket_block_public_access_standard",
        resolution={
            "strategy_id": "s3_bucket_block_public_access_standard",
            "profile_id": "s3_bucket_block_public_access_review_public_policy_scrub",
            "support_tier": "review_required_bundle",
            "blocked_reasons": [
                "Bucket policy is currently public; generated Terraform will scrub unconditional public Allow statements before enabling Block Public Access."
            ],
            "preservation_summary": {
                "public_policy_scrub_available": True,
                "manual_preservation_required": False,
            },
            "decision_rationale": "Review bundle required for public policy scrub.",
        },
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        bundle_dir = Path(temp_dir)
        _write_bundle_files(bundle, bundle_dir)
        terraform_env = _terraform_env_with_mirror(bundle_dir)
        init_result = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=bundle_dir,
            capture_output=True,
            text=True,
            check=False,
            env=terraform_env,
            timeout=120,
        )
        assert init_result.returncode == 0, init_result.stdout + init_result.stderr

        validate_result = subprocess.run(
            ["terraform", "validate", "-no-color"],
            cwd=bundle_dir,
            capture_output=True,
            text=True,
            check=False,
            env=terraform_env,
            timeout=120,
        )
        assert validate_result.returncode == 0, validate_result.stdout + validate_result.stderr


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform is not installed")
def test_s3_public_policy_scrub_single_statement_shape_plans() -> None:
    config = """
terraform {
  required_version = ">= 1.0"
}

locals {
  existing_policy_statements_candidate = [
    {
      Sid       = "AllowPublicRead"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "arn:aws:s3:::example-bucket/*"
    }
  ]
  existing_policy_statements = jsondecode(
    local.existing_policy_statements_candidate == null ? "[]" : (
      can(local.existing_policy_statements_candidate.Effect) ? format(
        "[%s]",
        jsonencode(local.existing_policy_statements_candidate)
      ) : jsonencode(local.existing_policy_statements_candidate)
    )
  )
}

output "existing_policy_statements_len" {
  value = length(local.existing_policy_statements)
}
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        bundle_dir = Path(temp_dir)
        (bundle_dir / "main.tf").write_text(config)

        init_result = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=bundle_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert init_result.returncode == 0, init_result.stdout + init_result.stderr

        plan_result = subprocess.run(
            ["terraform", "plan", "-no-color"],
            cwd=bundle_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert plan_result.returncode == 0, plan_result.stdout + plan_result.stderr
        assert "existing_policy_statements_len = 1" in plan_result.stdout


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


def test_pr_bundle_s3_bucket_access_logging_fails_when_log_bucket_unset() -> None:
    """S3.9 fails closed when log bucket is unresolved."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="log-source-bucket",
        region="us-east-1",
        control_id="S3.9",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(action, "terraform")
    payload = exc_info.value.as_dict()
    assert payload["code"] == "unresolved_placeholder_token"
    assert "REPLACE_LOG_BUCKET_NAME" in payload["detail"]


def test_pr_bundle_s3_bucket_access_logging_terraform_with_separate_log_bucket_override() -> None:
    """S3.9 Terraform bundle succeeds when log bucket is explicitly set to a separate bucket."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="log-source-bucket",
        region="us-east-1",
        control_id="S3.9",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"log_bucket_name": "dedicated-access-log-bucket"},
    )
    assert r["format"] == "terraform"
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_access_logging.tf")["content"]
    assert 'resource "aws_s3_bucket_logging" "security_autopilot"' in content
    assert 'variable "source_bucket_name"' in content
    assert 'default     = "log-source-bucket"' in content
    assert "bucket        = local.source_bucket_name" in content
    assert 'variable "log_bucket_name"' in content
    assert 'default     = "dedicated-access-log-bucket"' in content
    assert "REPLACE_LOG_BUCKET_NAME" not in content
    assert "target_bucket = var.log_bucket_name" in content
    assert "Do not use the source bucket as the log destination." in r["steps"]
    assert "S3.9" in content or "Control:" in content


def test_pr_bundle_s3_bucket_access_logging_terraform_creates_missing_source_bucket_when_requested() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="source-bucket",
        region="us-east-1",
        control_id="S3.9",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "log_bucket_name": "dedicated-access-log-bucket",
            "create_bucket_if_missing": True,
        },
    )
    content = _bundle_file_content(r, "s3_bucket_access_logging.tf")

    assert 'variable "create_bucket_if_missing"' in content
    assert "default     = true" in content
    assert 'resource "aws_s3_bucket" "source_bucket"' in content
    assert "source_bucket_name" in content
    assert "var.create_bucket_if_missing ? aws_s3_bucket.source_bucket[0].bucket : var.source_bucket_name" in content
    assert "bucket        = local.source_bucket_name" in content
    assert any("create the missing source bucket" in step for step in r["steps"])


def test_pr_bundle_s3_bucket_access_logging_terraform_can_adopt_existing_log_bucket() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="source-bucket",
        region="us-east-1",
        control_id="S3.9",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "log_bucket_name": "dedicated-access-log-bucket",
            "create_log_bucket": True,
        },
    )
    content = _bundle_file_content(r, "s3_bucket_access_logging.tf")

    assert 'variable "adopt_existing_log_bucket"' in content
    assert "manage_log_bucket_baseline = var.create_log_bucket || var.adopt_existing_log_bucket" in content
    assert 'log_bucket_id              = var.create_log_bucket ? aws_s3_bucket.access_logs[0].id : var.log_bucket_name' in content
    assert "local.manage_log_bucket_baseline ? 1 : 0" in content
    assert "If the destination bucket already exists and is already owned" in " ".join(r["steps"])


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
    assert 'bucket = local.target_bucket_name' in content
    assert "abort_incomplete_multipart_upload" in content
    assert 'variable "abort_incomplete_multipart_days"' in content
    assert "S3.11" in content or "Control:" in content


def test_pr_bundle_s3_bucket_lifecycle_configuration_terraform_creates_missing_bucket_when_requested() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"create_bucket_if_missing": True},
    )
    content = _bundle_file_content(r, "s3_bucket_lifecycle_configuration.tf")
    paths = [f["path"] for f in r["files"]]

    assert 'variable "create_bucket_if_missing"' in content
    assert 'resource "aws_s3_bucket" "target_bucket"' in content
    assert 'resource "aws_s3_bucket_server_side_encryption_configuration" "target_bucket"' in content
    assert 'depends_on = [aws_s3_bucket_ownership_controls.target_bucket]' in content
    assert "scripts/s3_lifecycle_merge.py" not in paths
    assert "rollback/s3_lifecycle_restore.py" not in paths
    assert any("create the missing target bucket" in step for step in r["steps"])


def test_pr_bundle_s3_bucket_lifecycle_configuration_terraform_preserves_renderable_rules() -> None:
    """S3.11 additive merge preserves captured lifecycle rules in Terraform output."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    lifecycle_document = {
        "Rules": [
            {
                "ID": "expire-logs",
                "Status": "Enabled",
                "Filter": {"Prefix": "logs/"},
                "Expiration": {"Days": 30},
            },
            {
                "ID": "AbortMultipartUploads",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            },
        ]
    }

    r = generate_pr_bundle(
        action,
        "terraform",
        risk_snapshot={
            "evidence": {
                "existing_lifecycle_configuration_json": json.dumps(lifecycle_document),
            }
        },
    )

    content = _bundle_file_content(r, "s3_bucket_lifecycle_configuration.tf")
    assert 'id     = "expire-logs"' in content
    assert 'prefix = "logs/"' in content
    assert "days = 30" in content
    assert content.count('id     = "security-autopilot-abort-incomplete-multipart"') == 1
    assert 'id     = "AbortMultipartUploads"' not in content


def test_pr_bundle_s3_bucket_lifecycle_configuration_terraform_preserves_noncurrent_rules() -> None:
    """S3.11 additive merge keeps renderable noncurrent-version lifecycle rules intact."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    lifecycle_document = {
        "Rules": [
            {
                "ID": "expire-noncurrent",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
            }
        ]
    }

    r = generate_pr_bundle(
        action,
        "terraform",
        risk_snapshot={
            "evidence": {
                "existing_lifecycle_configuration_json": json.dumps(lifecycle_document),
            }
        },
    )

    content = _bundle_file_content(r, "s3_bucket_lifecycle_configuration.tf")
    assert 'id     = "expire-noncurrent"' in content
    assert "noncurrent_version_expiration" in content
    assert "noncurrent_days = 30" in content
    assert content.count('id     = "security-autopilot-abort-incomplete-multipart"') == 1


def test_pr_bundle_s3_11_terraform_apply_time_merge_uses_resolution_summary() -> None:
    """S3.11 Terraform can fetch and merge the live lifecycle document at apply time."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="123456789012|us-east-1|arn:aws:s3:::lifecycle-bucket|S3.11",
        region="us-east-1",
        control_id="S3.11",
    )
    action.resource_id = "arn:aws:s3:::lifecycle-bucket"

    r = generate_pr_bundle(
        action,
        "terraform",
        resolution={
            "strategy_id": "s3_enable_abort_incomplete_uploads",
            "profile_id": "s3_enable_abort_incomplete_uploads",
            "support_tier": "deterministic_bundle",
            "blocked_reasons": [],
            "preservation_summary": {
                "apply_time_merge": True,
                "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
            },
            "decision_rationale": "Apply-time lifecycle merge is allowed.",
        },
    )

    content = _bundle_file_content(r, "s3_bucket_lifecycle_configuration.tf")
    paths = [f["path"] for f in r["files"]]

    assert 'resource "terraform_data" "security_autopilot"' in content
    assert 'python3 ./scripts/s3_lifecycle_merge.py' in content
    assert "triggers_replace" in content
    assert "scripts/s3_lifecycle_merge.py" in paths
    assert "rollback/s3_lifecycle_restore.py" in paths
    assert any("fetch the current lifecycle configuration at apply time" in step for step in r["steps"])
    assert any("python3 rollback/s3_lifecycle_restore.py" in step for step in r["steps"])
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/s3_lifecycle_restore.py",
        "runner": "python3",
    }


def test_pr_bundle_s3_11_apply_time_merge_helpers_snapshot_and_restore_exact_lifecycle() -> None:
    """S3.11 apply-time fallback should ship exact capture and restore helpers."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="123456789012|us-east-1|arn:aws:s3:::lifecycle-bucket|S3.11",
        region="us-east-1",
        control_id="S3.11",
    )
    action.resource_id = "arn:aws:s3:::lifecycle-bucket"

    r = generate_pr_bundle(
        action,
        "terraform",
        resolution={
            "strategy_id": "s3_enable_abort_incomplete_uploads",
            "profile_id": "s3_enable_abort_incomplete_uploads",
            "support_tier": "deterministic_bundle",
            "blocked_reasons": [],
            "preservation_summary": {"apply_time_merge": True},
            "decision_rationale": "Apply-time lifecycle merge is allowed.",
        },
    )

    apply_script = _bundle_file_content(r, "scripts/s3_lifecycle_merge.py")
    restore_script = _bundle_file_content(r, "rollback/s3_lifecycle_restore.py")

    assert '"get-bucket-lifecycle-configuration"' in apply_script
    assert '"put-bucket-lifecycle-configuration"' in apply_script
    assert ".s3-lifecycle-rollback/lifecycle_snapshot.json" in apply_script
    assert '"delete-bucket-lifecycle"' in restore_script
    assert '"put-bucket-lifecycle-configuration"' in restore_script


def test_pr_bundle_s3_bucket_lifecycle_configuration_cloudformation_custom_resource() -> None:
    """S3.11: CloudFormation uses Lambda custom resource PutLifecycleConfiguration with delete no-op."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    r = generate_pr_bundle(action, "cloudformation")
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"] == "s3_bucket_lifecycle_configuration.yaml"
    content = r["files"][0]["content"]
    assert "AWS::S3::Bucket" not in content
    assert "AWS::Lambda::Function" in content
    assert "Type: Custom::S3BucketLifecycleConfiguration" in content
    assert "s3:PutLifecycleConfiguration" in content
    assert "s3.put_bucket_lifecycle_configuration(" in content
    assert 'if request_type == "Delete":' in content
    assert 'cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, "S3BucketLifecycle")' in content
    assert "Delete path is no-op and does NOT remove existing lifecycle rules." in content


def test_pr_bundle_s3_bucket_lifecycle_configuration_cloudformation_rejects_additive_merge() -> None:
    """S3.11 CloudFormation stays fail-closed when additive merge would be required."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    lifecycle_document = {
        "Rules": [
            {
                "ID": "expire-logs",
                "Status": "Enabled",
                "Filter": {"Prefix": "logs/"},
                "Expiration": {"Days": 30},
            }
        ]
    }

    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "cloudformation",
            risk_snapshot={
                "evidence": {
                    "existing_lifecycle_configuration_json": json.dumps(lifecycle_document),
                }
            },
        )

    assert exc_info.value.as_dict()["code"] == "cloudformation_lifecycle_additive_merge_unsupported"


def test_pr_bundle_s3_bucket_lifecycle_configuration_cloudformation_rejects_apply_time_merge() -> None:
    """S3.11 CloudFormation stays fail-closed for apply-time lifecycle merge fallback."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="123456789012|us-east-1|arn:aws:s3:::lifecycle-bucket|S3.11",
        region="us-east-1",
        control_id="S3.11",
    )
    action.resource_id = "arn:aws:s3:::lifecycle-bucket"

    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "cloudformation",
            resolution={
                "strategy_id": "s3_enable_abort_incomplete_uploads",
                "profile_id": "s3_enable_abort_incomplete_uploads",
                "support_tier": "deterministic_bundle",
                "blocked_reasons": [],
                "preservation_summary": {"apply_time_merge": True},
                "decision_rationale": "Apply-time lifecycle merge is allowed.",
            },
        )

    assert exc_info.value.as_dict()["code"] == "cloudformation_lifecycle_additive_merge_unsupported"


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
    assert 'bucket = local.target_bucket_name' in content
    assert 'sse_algorithm     = "aws:kms"' in content
    assert 'variable "kms_key_arn"' in content
    assert 'default     = "arn:aws:kms:us-east-1:123456789012:alias/aws/s3"' in content
    assert "S3.15" in content or "Control:" in content


def test_pr_bundle_s3_bucket_encryption_kms_terraform_creates_missing_bucket_when_requested() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="kms-bucket",
        region="us-east-1",
        control_id="S3.15",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"create_bucket_if_missing": True},
    )
    content = _bundle_file_content(r, "s3_bucket_encryption_kms.tf")
    paths = [f["path"] for f in r["files"]]

    assert 'variable "create_bucket_if_missing"' in content
    assert 'resource "aws_s3_bucket" "target_bucket"' in content
    assert content.count('resource "aws_s3_bucket_server_side_encryption_configuration"') == 1
    assert 'depends_on = [aws_s3_bucket_ownership_controls.target_bucket]' in content
    assert "scripts/s3_encryption_capture.py" not in paths
    assert "rollback/s3_encryption_restore.py" not in paths
    assert any("create the missing target bucket" in step for step in r["steps"])


def test_pr_bundle_s3_bucket_encryption_kms_includes_exact_capture_and_restore_helpers() -> None:
    """S3.15 Terraform bundle should ship exact bucket-encryption capture/restore helpers."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="kms-bucket",
        region="us-east-1",
        control_id="S3.15",
    )
    r = generate_pr_bundle(action, "terraform", strategy_inputs={"kms_key_mode": "aws_managed"})

    capture_script = _bundle_file_content(r, "scripts/s3_encryption_capture.py")
    restore_script = _bundle_file_content(r, "rollback/s3_encryption_restore.py")
    readme = _bundle_file_content(r, "README.txt")

    assert '"get-bucket-encryption"' in capture_script
    assert ".s3-encryption-rollback/encryption_snapshot.json" in capture_script
    assert "DEFAULT_BUCKET_NAME = 'kms-bucket'" in capture_script
    assert "DEFAULT_REGION = 'us-east-1'" in capture_script
    assert '"put-bucket-encryption"' in restore_script
    assert '"delete-bucket-encryption"' in restore_script
    assert ".s3-encryption-rollback/" in readme
    assert "python3 scripts/s3_encryption_capture.py" in readme
    assert "optional overrides only" in readme
    assert "python3 rollback/s3_encryption_restore.py" in readme
    assert any("python3 scripts/s3_encryption_capture.py" in step for step in r["steps"])
    assert any("python3 rollback/s3_encryption_restore.py" in step for step in r["steps"])
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/s3_encryption_restore.py",
        "runner": "python3",
    }


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
    strategy_inputs = None
    if action_type == ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING:
        strategy_inputs = {"log_bucket_name": "cloudformation-log-bucket"}
    r = generate_pr_bundle(action, "cloudformation", strategy_inputs=strategy_inputs)
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
    assert "IMPORTANT: review remove_existing_public_rules before applying." in r["steps"]
    assert 'variable "security_group_id"' in content
    assert 'variable "allowed_cidr"' in content
    assert 'variable "allowed_cidr_ipv6"' in content
    assert 'variable "remove_existing_public_rules"' in content
    assert "type        = bool" in content
    assert "default     = false" in content
    assert '"sg-abc123"' in content
    assert '"10.0.0.0/8"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "ssh_restricted"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "rdp_restricted"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "ssh_restricted_ipv6"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "rdp_restricted_ipv6"' in content
    assert 'resource "null_resource" "revoke_public_admin_ingress"' in content
    assert "var.remove_existing_public_rules == true ? 1 : 0" in content
    assert "IpRanges=[{CidrIp=${var.allowed_cidr}}]" in content
    assert "Ipv6Ranges=[{CidrIpv6=${var.allowed_cidr_ipv6}}]" in content
    assert 'from_port         = 22' in content
    assert 'to_port           = 22' in content
    assert 'from_port         = 3389' in content
    assert 'to_port           = 3389' in content
    assert 'ip_protocol       = "tcp"' in content
    assert "cidr_ipv6" in content
    assert "EC2.53" in content or "Control:" in content


def test_ec2_53_strategy_schema_guided_choice_fields() -> None:
    """Task 2: EC2.53 strategy exposes guided access-mode schema with impact text."""
    strategies = list_strategies_for_action_type(ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS)
    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy["strategy_id"] == "sg_restrict_public_ports_guided"
    assert strategy["requires_inputs"] is True

    fields = {field["key"]: field for field in strategy["input_schema"]["fields"]}
    access_mode = fields["access_mode"]
    assert access_mode["type"] == "select"
    option_values = [option["value"] for option in access_mode.get("options", [])]
    assert option_values == [
        "close_public",
        "close_and_revoke",
        "restrict_to_ip",
        "restrict_to_cidr",
        "ssm_only",
        "bastion_sg_reference",
    ]
    for option in access_mode.get("options", []):
        assert option.get("impact_text")

    allowed_cidr = fields["allowed_cidr"]
    assert allowed_cidr["type"] == "cidr"
    assert allowed_cidr["visible_when"] == {
        "field": "access_mode",
        "equals": ["restrict_to_ip", "restrict_to_cidr"],
    }

    allowed_cidr_ipv6 = fields["allowed_cidr_ipv6"]
    assert allowed_cidr_ipv6["type"] == "cidr"
    assert allowed_cidr_ipv6["visible_when"] == {
        "field": "access_mode",
        "equals": ["restrict_to_ip", "restrict_to_cidr"],
    }


def test_pr_bundle_sg_restrict_terraform_strategy_inputs_map_defaults() -> None:
    """Task 2: SG Terraform bundle uses access-mode and CIDR strategy inputs as defaults."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-0abc1234def567890",
        region="us-east-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "access_mode": "close_and_revoke",
            "allowed_cidr": "203.0.113.99/32",
            "allowed_cidr_ipv6": "2001:db8::123/64",
        },
    )
    content = next(f for f in r["files"] if f["path"] == "sg_restrict_public_ports.tf")["content"]
    assert 'default     = "203.0.113.99/32"' in content
    assert 'default     = "2001:db8::/64"' in content
    assert 'variable "remove_existing_public_rules"' in content
    assert "default     = true" in content


def test_pr_bundle_sg_restrict_remove_existing_true_only_for_close_and_revoke() -> None:
    """Task 2: remove_existing_public_rules default is true only for access_mode=close_and_revoke."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-0abc1234def567890",
        region="us-east-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "access_mode": "restrict_to_cidr",
            "remove_existing_public_rules": True,
            "allowed_cidr": "198.51.100.0/24",
        },
    )
    content = next(f for f in r["files"] if f["path"] == "sg_restrict_public_ports.tf")["content"]
    assert 'default     = "198.51.100.0/24"' in content
    assert "default     = false" in content


def test_pr_bundle_sg_restrict_close_and_revoke_includes_exact_state_capture_and_restore() -> None:
    """EC2.53 close_and_revoke bundles should ship exact-state capture/restore helpers."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-0abc1234def567890",
        region="eu-north-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"access_mode": "close_and_revoke"},
    )

    apply_script = _bundle_file_content(r, "scripts/sg_capture_state.py")
    restore_script = _bundle_file_content(r, "rollback/sg_restore.py")
    readme = _bundle_file_content(r, "README.txt")

    assert "--filters\", f\"Name=group-id,Values={sg_id}\"" in apply_script
    assert "Name=is-egress,Values=false" not in apply_script
    assert 'if bool(rule.get("IsEgress")):' in apply_script
    assert 'description = str(rule.get("Description") or "").strip()' in apply_script
    assert 'entry["Description"] = description' in apply_script
    assert '"IpRanges": [ip_range_entry(cidr_key="CidrIp", cidr_value=cidr_ipv4, description=description)]' in apply_script
    assert '"Ipv6Ranges": [ip_range_entry(cidr_key="CidrIpv6", cidr_value=cidr_ipv6, description=description)]' in apply_script
    assert 'permissions_json = json.dumps([rule])' in restore_script
    assert "including rule descriptions" in readme
    assert ".sg-rollback/sg_ingress_snapshot.json" in readme
    assert "python3 rollback/sg_restore.py" in readme
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/sg_restore.py",
        "runner": "python3",
    }


def test_pr_bundle_sg_restrict_ssm_only_terraform_is_revoke_only() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-0abc1234def567890",
        region="eu-north-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"access_mode": "ssm_only"},
    )

    content = _bundle_file_content(r, "sg_restrict_public_ports.tf")
    readme = _bundle_file_content(r, "README.txt")
    assert 'variable "security_group_id"' in content
    assert 'resource "null_resource" "revoke_public_admin_ingress"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule"' not in content
    assert 'variable "allowed_cidr"' not in content
    assert 'variable "allowed_cidr_ipv6"' not in content
    assert 'remove_existing_public_rules' not in content
    assert "CidrIp=0.0.0.0/0" in content
    assert "CidrIpv6=::/0" in content
    assert "does not add replacement SSH/RDP rules" in content
    assert "Confirm SSM Session Manager access is already working" in " ".join(r["steps"])
    assert "scripts/sg_capture_state.py" in readme
    assert "`ssm_only` removes public SSH/RDP ingress" in readme
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/sg_restore.py",
        "runner": "python3",
    }


def test_pr_bundle_sg_restrict_ssm_only_cloudformation_is_revoke_only() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-xyz789",
        region="us-east-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={"access_mode": "ssm_only"},
    )

    content = r["files"][0]["content"]
    assert r["format"] == "cloudformation"
    assert "Confirm SSM Session Manager access is already working" in " ".join(r["steps"])
    assert "Type: Custom::SecurityGroupIngressRevoke" in content
    assert "AWS::EC2::SecurityGroupIngress" not in content
    assert "AllowedCidr:" not in content
    assert "AllowedCidrIpv6:" not in content
    assert "does not add replacement ingress rules" in content
    assert '"CidrIp": "0.0.0.0/0"' in content
    assert '"CidrIpv6": "::/0"' in content


def test_pr_bundle_sg_restrict_bastion_reference_terraform_replaces_public_ingress() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-0abc1234def567890",
        region="eu-north-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "access_mode": "bastion_sg_reference",
            "approved_bastion_security_group_ids": ["sg-bastion-1", "sg-bastion-2"],
        },
    )

    content = _bundle_file_content(r, "sg_restrict_public_ports.tf")
    readme = _bundle_file_content(r, "README.txt")
    assert 'variable "approved_bastion_security_group_ids"' in content
    assert 'resource "null_resource" "revoke_public_admin_ingress"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "bastion_ssh"' in content
    assert 'resource "aws_vpc_security_group_ingress_rule" "bastion_rdp"' in content
    assert "referenced_security_group_id = each.value" in content
    assert 'default     = ["sg-bastion-1", "sg-bastion-2"]' in content
    assert "CidrIp=0.0.0.0/0" in content
    assert "CidrIpv6=::/0" in content
    assert "approved bastion SG list" in readme
    assert "scripts/sg_capture_state.py" in readme
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/sg_restore.py",
        "runner": "python3",
    }


def test_pr_bundle_sg_restrict_bastion_reference_cloudformation_replaces_public_ingress() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-xyz789",
        region="us-east-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={
            "access_mode": "bastion_sg_reference",
            "approved_bastion_security_group_ids": ["sg-bastion-1", "sg-bastion-2"],
        },
    )

    content = r["files"][0]["content"]
    assert r["format"] == "cloudformation"
    assert "approved bastion security groups are correct" in " ".join(r["steps"])
    assert "Type: Custom::SecurityGroupIngressRevoke" in content
    assert 'SourceSecurityGroupId: "sg-bastion-1"' in content
    assert 'SourceSecurityGroupId: "sg-bastion-2"' in content
    assert "CidrIp:" not in content
    assert "AllowedCidr:" not in content
    assert '"CidrIp": "0.0.0.0/0"' in content
    assert '"CidrIpv6": "::/0"' in content


def test_pr_bundle_sg_restrict_cloudformation_step_9_11() -> None:
    """Step 9.11: CloudFormation for EC2.53 includes revoke custom resource + ordered restricted ingress."""
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
    assert "IMPORTANT: review revoke-before-add behavior before applying." in r["steps"]
    assert "AWS::EC2::SecurityGroupIngress" in content
    assert "AWS::Lambda::Function" in content
    assert "Type: Custom::SecurityGroupIngressRevoke" in content
    assert "RevokeSecurityGroupIngress" in content
    assert "SecurityGroupId:" in content
    assert "AllowedCidr:" in content
    assert "AllowedCidrIpv6:" in content
    assert "HasAllowedIpv6" in content
    assert "ec2.revoke_security_group_ingress(" in content
    assert '"CidrIp": "0.0.0.0/0"' in content
    assert '"CidrIpv6": "::/0"' in content
    assert 'if request_type == "Delete":' in content
    assert 'cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, "RevokePublicIngress")' in content
    assert content.count("DependsOn: RevokePublicAdminIngress") == 4
    assert "CidrIpv6:" in content
    assert "FromPort: 22" in content
    assert "ToPort: 22" in content
    assert "FromPort: 3389" in content
    assert "ToPort: 3389" in content
    assert "IpProtocol: tcp" in content
    assert "10.0.0.0/8" in content
    assert "Delete path is no-op and does NOT re-add public ingress rules." in content
    assert "authorize-security-group-ingress" not in content
    assert "authorize_security_group_ingress" not in content
    assert "EC2.53" in content or "Control:" in content


def test_pr_bundle_sg_restrict_cloudformation_strategy_inputs_map_defaults() -> None:
    """Task 2: SG CloudFormation bundle maps CIDR strategy inputs into parameter defaults."""
    action = _make_action(
        action_type=ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
        target_id="sg-0abc1234def567890",
        region="us-east-1",
        control_id="EC2.53",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={
            "access_mode": "restrict_to_ip",
            "allowed_cidr": "198.51.100.44/32",
            "allowed_cidr_ipv6": "2001:db8::abcd/64",
        },
    )
    content = next(f for f in r["files"] if f["path"] == "sg_restrict_public_ports.yaml")["content"]
    assert 'Default: "198.51.100.44/32"' in content
    assert 'Default: "2001:db8::/64"' in content


@pytest.mark.parametrize(
    ("action_type", "target_id", "control_id", "risk_snapshot", "expected_step_snippets"),
    [
        (
            ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
            "my-bucket",
            "S3.2",
            None,
            [
                "What changes: sets Bucket PublicAccessBlockConfiguration",
                "CloudFront usage note - serve traffic through CloudFront HTTPS endpoints",
                "aws s3api get-public-access-block --bucket <bucket-name>",
                "Rollback: emergency-only unblock command",
            ],
        ),
        (
            ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS,
            "sg-0abc1234def567890",
            "EC2.53",
            None,
            [
                "What changes: custom resource revokes 0.0.0.0/0 and ::/0 SSH/RDP ingress (22/3389)",
                "aws ssm start-session --target <instance-id> --region <region>",
                "describe-security-group-rules --region <region>",
                "Rollback: re-authorize only temporary scoped admin ingress",
            ],
        ),
        (
            ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
            "my-bucket",
            "S3.5",
            {"evidence": {"existing_bucket_policy_statement_count": 0}},
            [
                "What changes: merges existing bucket policy statements and adds DenyInsecureTransport",
                "How to access now: HTTPS requirement",
                "curl -I https://my-bucket.s3.us-east-1.amazonaws.com/<object-key>",
                "put-bucket-policy --bucket my-bucket --policy file://pre-remediation-policy.json",
            ],
        ),
        (
            ACTION_TYPE_SSM_BLOCK_PUBLIC_SHARING,
            "account-ssm",
            "SSM.7",
            None,
            [
                "What changes: sets the SSM public-sharing service setting to Disable.",
                "modify-document-permission --name <document-name> --permission-type Share --account-ids-to-add <account-id>",
                "get-service-setting --setting-id arn:aws:ssm:us-east-1:123456789012:servicesetting/ssm/documents/console/public-sharing-permission",
                "update-service-setting --setting-id arn:aws:ssm:us-east-1:123456789012:servicesetting/ssm/documents/console/public-sharing-permission --setting-value Enable",
            ],
        ),
    ],
)
def test_pr_bundle_cloudformation_steps_include_post_fix_access_guidance(
    action_type: str,
    target_id: str,
    control_id: str,
    risk_snapshot: dict[str, object] | None,
    expected_step_snippets: list[str],
) -> None:
    """CloudFormation instructions include post-fix access guidance strings per control."""
    action = _make_action(
        action_type=action_type,
        target_id=target_id,
        region="us-east-1",
        control_id=control_id,
    )
    bundle = generate_pr_bundle(action, "cloudformation", risk_snapshot=risk_snapshot)
    step_text = "\n".join(bundle["steps"])
    for snippet in expected_step_snippets:
        assert snippet in step_text


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


def test_cloudtrail_1_strategy_schema_guided_choice_fields() -> None:
    """Task 5: CloudTrail.1 strategy exposes guided fields and defaults."""
    strategies = list_strategies_for_action_type(ACTION_TYPE_CLOUDTRAIL_ENABLED)
    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy["strategy_id"] == "cloudtrail_enable_guided"
    assert strategy["requires_inputs"] is True

    fields = {field["key"]: field for field in strategy["input_schema"]["fields"]}
    trail_name = fields["trail_name"]
    assert trail_name["type"] == "string"
    assert trail_name["default_value"] == "security-autopilot-trail"

    trail_bucket_name = fields["trail_bucket_name"]
    assert trail_bucket_name["type"] == "string"
    assert trail_bucket_name["safe_default_value"] == "security-autopilot-trail-logs-{{account_id}}-{{region}}"
    assert trail_bucket_name["safe_default_label"] == "Auto-generate a dedicated CloudTrail log bucket"

    create_bucket_if_missing = fields["create_bucket_if_missing"]
    assert create_bucket_if_missing["type"] == "boolean"
    assert create_bucket_if_missing["default_value"] is True

    create_bucket_policy = fields["create_bucket_policy"]
    assert create_bucket_policy["type"] == "boolean"
    assert create_bucket_policy["default_value"] is True

    multi_region = fields["multi_region"]
    assert multi_region["type"] == "boolean"
    assert multi_region["default_value"] is True


def test_pr_bundle_dispatch_cloudtrail_terraform_step_9_12() -> None:
    """Step 9.12: cloudtrail_enabled returns Terraform with aws_cloudtrail."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
    )
    r = generate_pr_bundle(action, "terraform", strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs"})
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
    r = generate_pr_bundle(action, "terraform", strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs"})
    content = next(f for f in r["files"] if f["path"] == "cloudtrail_enabled.tf")["content"]
    assert 'variable "trail_bucket_name"' in content
    assert 'variable "trail_name"' in content
    assert 'default     = "security-autopilot-trail"' in content
    assert 'variable "create_bucket_if_missing"' in content
    assert "default     = false" in content
    assert 'variable "multi_region"' in content
    assert "default     = true" in content
    assert 'variable "create_bucket_policy"' in content
    assert 'resource "aws_cloudtrail" "security_autopilot"' in content
    assert "name                          = var.trail_name" in content
    assert "s3_bucket_name                = local.cloudtrail_bucket_name" in content
    assert "is_multi_region_trail          = var.multi_region" in content
    assert "include_global_service_events" in content
    assert "enable_logging" in content
    assert 'resource "null_resource" "cloudtrail_bucket_policy"' in content
    assert 'resource "aws_s3_bucket" "cloudtrail_logs"' in content
    assert 'resource "aws_s3_bucket_policy" "cloudtrail_logs"' in content
    assert "python3 - <<'PY'" in content
    assert "get-bucket-policy" in content
    assert "put-bucket-policy" in content
    assert "NoSuchBucketPolicy" in content
    assert "depends_on                    = [aws_s3_bucket_policy.cloudtrail_logs, null_resource.cloudtrail_bucket_policy]" in content
    assert "cloudtrail.amazonaws.com" in content
    assert "s3:GetBucketAcl" in content
    assert "s3:PutObject" in content
    assert '"/AWSLogs/" + account_id + "/CloudTrail/*"' in content
    assert "s3:x-amz-acl" in content
    assert "bucket-owner-full-control" in content
    assert "CloudTrail.1" in content or "Control:" in content


def test_pr_bundle_cloudtrail_cloudformation_step_9_12() -> None:
    """Step 9.12: CloudFormation for CloudTrail.1 (cloudtrail_enabled) has AWS::CloudTrail::Trail, IsMultiRegionTrail, S3BucketName."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(action, "cloudformation", strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs"})
    assert r["format"] == "cloudformation"
    assert r["files"][0]["path"] == "cloudtrail_enabled.yaml"
    content = r["files"][0]["content"]
    assert "AWS::CloudTrail::Trail" in content
    assert "TrailName:" in content
    assert 'Default: "security-autopilot-trail"' in content
    assert "TrailBucketName:" in content or "TrailBucketName" in content
    assert "CreateBucketIfMissing:" in content
    assert "MultiRegion:" in content
    assert 'Default: "true"' in content
    assert "CreateBucketPolicy:" in content
    assert 'IsMultiRegionTrail: !Equals [!Ref MultiRegion, "true"]' in content
    assert "IncludeGlobalServiceEvents" in content or "S3BucketName:" in content
    assert "AWS::S3::Bucket" in content
    assert "AWS::S3::BucketPolicy" in content
    assert "cloudtrail.amazonaws.com" in content
    assert "s3:GetBucketAcl" in content
    assert "s3:PutObject" in content
    assert "/AWSLogs/123456789012/CloudTrail/*" in content
    assert "bucket-owner-full-control" in content
    assert "CloudTrail.1" in content or "Control:" in content


def test_pr_bundle_cloudtrail_terraform_opt_out_bucket_policy() -> None:
    """CloudTrail Terraform opt-out removes bucket policy resources from generated file."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs", "create_bucket_policy": False},
    )
    content = next(f for f in r["files"] if f["path"] == "cloudtrail_enabled.tf")["content"]

    assert 'variable "create_bucket_policy"' in content
    assert "default     = false" in content
    assert 'resource "null_resource" "cloudtrail_bucket_policy"' in content
    assert "count  = var.create_bucket_policy && !var.create_bucket_if_missing ? 1 : 0" in content


def test_pr_bundle_cloudtrail_cloudformation_opt_out_bucket_policy() -> None:
    """CloudTrail CloudFormation opt-out removes bucket policy resource from template."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={"trail_bucket_name": "security-autopilot-cloudtrail-logs", "create_bucket_policy": False},
    )
    content = r["files"][0]["content"]

    assert "CreateBucketPolicy:" in content
    assert 'Default: "false"' in content
    assert "CreateBucketPolicy:" in content


def test_pr_bundle_cloudtrail_terraform_strategy_inputs_map_defaults() -> None:
    """Task 5: CloudTrail Terraform bundle honors guided strategy input defaults."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "trail_name": "org-audit-trail",
            "trail_bucket_name": "org-cloudtrail-logs",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/cloudtrail",
            "multi_region": False,
            "create_bucket_policy": False,
        },
    )
    content = next(f for f in r["files"] if f["path"] == "cloudtrail_enabled.tf")["content"]

    assert 'variable "trail_bucket_name"' in content
    assert 'default     = "org-cloudtrail-logs"' in content
    assert 'variable "trail_name"' in content
    assert 'default     = "org-audit-trail"' in content
    assert 'variable "create_bucket_if_missing"' in content
    assert "default     = false" in content
    assert 'variable "kms_key_arn"' in content
    assert 'default     = "arn:aws:kms:us-east-1:123456789012:key/cloudtrail"' in content
    assert 'variable "multi_region"' in content
    assert "default     = false" in content
    assert "name                          = var.trail_name" in content
    assert 'kms_key_id                    = var.kms_key_arn != "" ? var.kms_key_arn : null' in content
    assert "is_multi_region_trail          = var.multi_region" in content
    assert 'resource "null_resource" "cloudtrail_bucket_policy"' in content


def test_pr_bundle_cloudtrail_cloudformation_strategy_inputs_map_defaults() -> None:
    """Task 5: CloudTrail CloudFormation bundle honors guided strategy input defaults."""
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={
            "trail_name": "org-audit-trail",
            "trail_bucket_name": "org-cloudtrail-logs",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/cloudtrail",
            "create_bucket_if_missing": True,
            "multi_region": False,
            "create_bucket_policy": False,
        },
    )
    content = r["files"][0]["content"]

    assert "TrailName:" in content
    assert 'Default: "org-audit-trail"' in content
    assert "TrailBucketName:" in content
    assert 'Default: "org-cloudtrail-logs"' in content
    assert "CreateBucketIfMissing:" in content
    assert 'Default: "true"' in content
    assert "KmsKeyArn:" in content
    assert 'Default: "arn:aws:kms:us-east-1:123456789012:key/cloudtrail"' in content
    assert "HasKmsKeyArn" in content
    assert "KMSKeyId: !If [HasKmsKeyArn, !Ref KmsKeyArn, !Ref AWS::NoValue]" in content
    assert "MultiRegion:" in content
    assert 'Default: "false"' in content
    assert 'IsMultiRegionTrail: !Equals [!Ref MultiRegion, "true"]' in content
    assert "AWS::S3::BucketPolicy" in content


def test_pr_bundle_cloudtrail_terraform_create_if_missing_includes_bucket_resources() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_CLOUDTRAIL_ENABLED,
        region="us-east-1",
        control_id="CloudTrail.1",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "trail_bucket_name": "new-cloudtrail-logs",
            "create_bucket_if_missing": True,
        },
    )
    content = next(f for f in r["files"] if f["path"] == "cloudtrail_enabled.tf")["content"]

    assert content.count('resource "aws_s3_bucket" "cloudtrail_logs"') == 1
    assert 'resource "aws_s3_bucket_public_access_block" "cloudtrail_logs"' in content
    assert 'resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs"' in content
    assert 'resource "aws_s3_bucket_versioning" "cloudtrail_logs"' in content
    assert 'resource "aws_s3_bucket_policy" "cloudtrail_logs"' in content
    assert 'kms_master_key_id = "alias/aws/s3"' in content
    assert 'sid     = "DenyInsecureTransport"' in content
    assert "local.arn_prefix_cloudtrail_logs" in content
    assert "${arn_prefix_cloudtrail_logs}" not in content
    assert 'default     = true' in content
    assert 'resource "aws_s3_bucket_policy" "cloudtrail_managed"' not in content
    assert 'sse_algorithm = "AES256"' not in content


def test_pr_bundle_s3_9_cloudformation_create_log_bucket_uses_support_bucket_baseline() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9",
        region="us-east-1",
        control_id="S3.9",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={
            "log_bucket_name": "new-access-log-bucket",
            "create_log_bucket": True,
        },
    )
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_access_logging.yaml")["content"]

    assert "CreateLogBucket:" in content
    assert 'Default: "true"' in content
    assert "AccessLogBucketPolicy:" in content
    assert "DenyInsecureTransport" in content
    assert "KMSMasterKeyID: alias/aws/s3" in content
    assert "AbortIncompleteMultipartUpload:" in content


def test_pr_bundle_s3_9_terraform_create_log_bucket_uses_local_support_bucket_arns() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9",
        region="us-east-1",
        control_id="S3.9",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "log_bucket_name": "new-access-log-bucket",
            "create_log_bucket": True,
        },
    )
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_access_logging.tf")["content"]

    assert "local.arn_prefix_access_logs" in content
    assert "${arn_prefix_access_logs}" not in content
    assert 'bucket = local.log_bucket_id' in content


def test_pr_bundle_s3_cloudfront_oac_private_terraform_creates_missing_bucket_when_requested() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="123456789012|us-east-1|arn:aws:s3:::oac-bucket|S3.2",
        region="us-east-1",
        control_id="S3.2",
    )
    action.resource_id = "arn:aws:s3:::oac-bucket"

    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_migrate_cloudfront_oac_private",
        strategy_inputs={"create_bucket_if_missing": True},
    )
    content = _bundle_file_content(r, "s3_cloudfront_oac_private_s3.tf")

    assert 'variable "create_bucket_if_missing"' in content
    assert 'resource "aws_s3_bucket" "target_bucket"' in content
    assert 'data "aws_s3_bucket" "existing_target"' in content
    assert 'data "external" "cloudfront_reuse"' not in content
    assert 'count  = var.create_bucket_if_missing ? 0 : 1' in content
    assert content.count('resource "aws_s3_bucket_public_access_block"') == 1
    assert "data \"aws_s3_bucket_policy\" \"existing\"" not in content
    assert any("create the missing target bucket" in step for step in r["steps"])


def test_cloudfront_oac_discovery_script_reuses_matching_distribution_and_oac() -> None:
    query = {
        "bucket_name": "my-bucket",
        "expected_bucket_regional_domain_name": "my-bucket.s3.us-east-1.amazonaws.com",
        "expected_distribution_comment": "Security Autopilot migration for my-bucket",
        "expected_oac_name": "security-autopilot-oac-123456789abc",
        "expected_origin_id": "s3-my-bucket",
    }
    responses = {
        "cloudfront list-distributions": {
            "DistributionList": {
                "Items": [
                    {
                        "Id": "E123DIST",
                        "ARN": "arn:aws:cloudfront::123456789012:distribution/E123DIST",
                        "DomainName": "d123.cloudfront.net",
                        "Comment": "Security Autopilot migration for my-bucket",
                        "Origins": {
                            "Items": [
                                {
                                    "Id": "s3-my-bucket",
                                    "DomainName": "my-bucket.s3.us-east-1.amazonaws.com",
                                    "OriginAccessControlId": "OAC123",
                                }
                            ]
                        },
                    }
                ]
            }
        },
        "cloudfront list-origin-access-controls": {
            "OriginAccessControlList": {
                "Items": [
                    {
                        "Id": "OAC123",
                        "Name": "security-autopilot-oac-123456789abc",
                        "OriginAccessControlOriginType": "s3",
                        "SigningBehavior": "always",
                        "SigningProtocol": "sigv4",
                    }
                ]
            }
        },
    }

    completed = _run_cloudfront_oac_discovery_script(query, responses)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload == {
        "cloudfront_reuse_mode": "reuse_distribution",
        "reuse_distribution_id": "E123DIST",
        "reuse_distribution_arn": "arn:aws:cloudfront::123456789012:distribution/E123DIST",
        "reuse_distribution_domain_name": "d123.cloudfront.net",
        "reuse_oac_id": "OAC123",
    }


def test_cloudfront_oac_discovery_script_reuses_safe_standalone_oac() -> None:
    query = {
        "bucket_name": "my-bucket",
        "expected_bucket_regional_domain_name": "my-bucket.s3.us-east-1.amazonaws.com",
        "expected_distribution_comment": "Security Autopilot migration for my-bucket",
        "expected_oac_name": "security-autopilot-oac-123456789abc",
        "expected_origin_id": "s3-my-bucket",
    }
    responses = {
        "cloudfront list-distributions": {
            "DistributionList": {
                "Items": [
                    {
                        "Id": "EUNRELATED",
                        "ARN": "arn:aws:cloudfront::123456789012:distribution/EUNRELATED",
                        "DomainName": "other.cloudfront.net",
                        "Comment": "Security Autopilot migration for other-bucket",
                        "Origins": {
                            "Items": [
                                {
                                    "Id": "s3-other-bucket",
                                    "DomainName": "other-bucket.s3.us-east-1.amazonaws.com",
                                    "OriginAccessControlId": "OTHEROAC",
                                }
                            ]
                        },
                    }
                ]
            }
        },
        "cloudfront list-origin-access-controls": {
            "OriginAccessControlList": {
                "Items": [
                    {
                        "Id": "OAC123",
                        "Name": "security-autopilot-oac-123456789abc",
                        "OriginAccessControlOriginType": "s3",
                        "SigningBehavior": "always",
                        "SigningProtocol": "sigv4",
                    },
                    {
                        "Id": "OTHEROAC",
                        "Name": "other-oac",
                        "OriginAccessControlOriginType": "s3",
                        "SigningBehavior": "always",
                        "SigningProtocol": "sigv4",
                    },
                ]
            }
        },
    }

    completed = _run_cloudfront_oac_discovery_script(query, responses)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload == {
        "cloudfront_reuse_mode": "reuse_oac_only",
        "reuse_oac_id": "OAC123",
    }


@pytest.mark.parametrize(
    ("responses", "expected_error"),
    [
        (
            {
                "cloudfront list-distributions": {
                    "DistributionList": {
                        "Items": [
                            {
                                "Id": "E1",
                                "ARN": "arn:aws:cloudfront::123456789012:distribution/E1",
                                "DomainName": "d1.cloudfront.net",
                                "Comment": "Security Autopilot migration for my-bucket",
                                "Origins": {
                                    "Items": [
                                        {
                                            "Id": "s3-my-bucket",
                                            "DomainName": "my-bucket.s3.us-east-1.amazonaws.com",
                                            "OriginAccessControlId": "OAC123",
                                        }
                                    ]
                                },
                            },
                            {
                                "Id": "E2",
                                "ARN": "arn:aws:cloudfront::123456789012:distribution/E2",
                                "DomainName": "d2.cloudfront.net",
                                "Comment": "Security Autopilot migration for other-bucket",
                                "Origins": {
                                    "Items": [
                                        {
                                            "Id": "s3-my-bucket",
                                            "DomainName": "my-bucket.s3.us-east-1.amazonaws.com",
                                            "OriginAccessControlId": "OAC456",
                                        }
                                    ]
                                },
                            },
                        ]
                    }
                },
                "cloudfront list-origin-access-controls": {
                    "OriginAccessControlList": {
                        "Items": [
                            {
                                "Id": "OAC123",
                                "Name": "security-autopilot-oac-123456789abc",
                                "OriginAccessControlOriginType": "s3",
                                "SigningBehavior": "always",
                                "SigningProtocol": "sigv4",
                            },
                            {
                                "Id": "OAC456",
                                "Name": "other-safe-oac",
                                "OriginAccessControlOriginType": "s3",
                                "SigningBehavior": "always",
                                "SigningProtocol": "sigv4",
                            },
                        ]
                    }
                },
            },
            "Multiple existing Security Autopilot CloudFront distributions appear to target this bucket",
        ),
        (
            {
                "cloudfront list-distributions": {"DistributionList": {"Items": []}},
                "cloudfront list-origin-access-controls": {
                    "OriginAccessControlList": {
                        "Items": [
                            {
                                "Id": "OAC123",
                                "Name": "security-autopilot-oac-123456789abc",
                                "OriginAccessControlOriginType": "s3",
                                "SigningBehavior": "never",
                                "SigningProtocol": "sigv4",
                            }
                        ]
                    }
                },
            },
            "does not use signing_behavior=always",
        ),
    ],
)
def test_cloudfront_oac_discovery_script_fails_closed_for_ambiguous_or_incompatible_matches(
    responses: dict[str, object],
    expected_error: str,
) -> None:
    query = {
        "bucket_name": "my-bucket",
        "expected_bucket_regional_domain_name": "my-bucket.s3.us-east-1.amazonaws.com",
        "expected_distribution_comment": "Security Autopilot migration for my-bucket",
        "expected_oac_name": "security-autopilot-oac-123456789abc",
        "expected_origin_id": "s3-my-bucket",
    }

    completed = _run_cloudfront_oac_discovery_script(query, responses)

    assert completed.returncode != 0
    assert expected_error in completed.stderr


def test_task_6_s3_impact_text_present_for_s3_1_s3_2_s3_4() -> None:
    """Task 6: S3.1/S3.2/S3.4 strategies expose impact_text for guided UX."""
    for action_type in (
        ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS,
        ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        ACTION_TYPE_S3_BUCKET_ENCRYPTION,
    ):
        strategies = list_strategies_for_action_type(action_type)
        assert strategies
        for strategy in strategies:
            assert strategy.get("impact_text")


def test_task_6_s3_5_strategy_schema_preserve_existing_policy_with_impact_text() -> None:
    """Task 6: S3.5 strategies include preserve_existing_policy boolean with impact_text."""
    strategies = list_strategies_for_action_type(ACTION_TYPE_S3_BUCKET_REQUIRE_SSL)
    strategy_by_id = {strategy["strategy_id"]: strategy for strategy in strategies}

    for strategy_id in (
        "s3_enforce_ssl_strict_deny",
        "s3_enforce_ssl_with_principal_exemptions",
    ):
        strategy = strategy_by_id[strategy_id]
        fields = {field["key"]: field for field in strategy["input_schema"]["fields"]}
        preserve = fields["preserve_existing_policy"]
        assert preserve["type"] == "boolean"
        assert preserve["default_value"] is True
        assert preserve.get("impact_text")
        assert strategy.get("impact_text")


def test_task_6_s3_9_strategy_schema_log_bucket_required_with_impact_text() -> None:
    """Task 6: S3.9 strategy includes required log_bucket_name with impact text."""
    strategies = list_strategies_for_action_type(ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING)
    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy["strategy_id"] == "s3_enable_access_logging_guided"
    fields = {field["key"]: field for field in strategy["input_schema"]["fields"]}
    log_bucket_name = fields["log_bucket_name"]
    assert log_bucket_name["type"] == "string"
    assert log_bucket_name["required"] is True
    assert log_bucket_name.get("impact_text")
    assert "source bucket" in log_bucket_name["safe_default_label"].lower()
    assert strategy.get("impact_text")


def test_task_6_s3_11_strategy_schema_abort_days_bounds_and_impact_text() -> None:
    """Task 6: S3.11 strategy includes abort_days bounds/default and impact text."""
    strategies = list_strategies_for_action_type(ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION)
    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy["strategy_id"] == "s3_enable_abort_incomplete_uploads"
    fields = {field["key"]: field for field in strategy["input_schema"]["fields"]}
    abort_days = fields["abort_days"]
    assert abort_days["type"] == "number"
    assert abort_days["default_value"] == 7
    assert abort_days["min"] == 1
    assert abort_days["max"] == 365
    assert abort_days.get("impact_text")
    assert strategy.get("impact_text")


def test_task_6_s3_15_strategy_schema_kms_mode_and_conditional_kms_arn() -> None:
    """Task 6: S3.15 strategy includes key mode select and conditional KMS ARN field."""
    strategies = list_strategies_for_action_type(ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS)
    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy["strategy_id"] == "s3_enable_sse_kms_guided"
    fields = {field["key"]: field for field in strategy["input_schema"]["fields"]}

    kms_key_mode = fields["kms_key_mode"]
    assert kms_key_mode["type"] == "select"
    assert kms_key_mode["default_value"] == "aws_managed"
    assert [option["value"] for option in kms_key_mode.get("options", [])] == [
        "aws_managed",
        "custom",
    ]

    kms_key_arn = fields["kms_key_arn"]
    assert kms_key_arn["type"] == "string"
    assert kms_key_arn["visible_when"] == {
        "field": "kms_key_mode",
        "equals": "custom",
    }
    assert strategy.get("impact_text")


def test_pr_bundle_s3_11_terraform_strategy_inputs_map_defaults() -> None:
    """Task 6: S3.11 Terraform bundle uses strategy_inputs.abort_days default."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"abort_days": 30},
    )
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_lifecycle_configuration.tf")["content"]
    assert 'variable "abort_incomplete_multipart_days"' in content
    assert "default     = 30" in content


def test_pr_bundle_s3_11_cloudformation_strategy_inputs_map_defaults() -> None:
    """Task 6: S3.11 CloudFormation bundle uses strategy_inputs.abort_days default."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={"abort_days": 30},
    )
    content = r["files"][0]["content"]
    assert "AbortIncompleteMultipartDays:" in content
    assert "Default: 30" in content


def test_pr_bundle_s3_11_terraform_rejects_unsupported_captured_rule_shape() -> None:
    """S3.11 additive merge fails closed when the captured lifecycle rule uses unsupported fields."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    lifecycle_document = {
        "Rules": [
            {
                "ID": "unsupported-shape",
                "Status": "Enabled",
                "Filter": {"Prefix": "logs/"},
                "Expiration": {"Days": 30},
                "UnsupportedField": "value",
            }
        ]
    }

    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "terraform",
            risk_snapshot={
                "evidence": {
                    "existing_lifecycle_configuration_json": json.dumps(lifecycle_document),
                    "existing_lifecycle_rule_count": 1,
                }
            },
        )

    payload = exc_info.value.as_dict()
    assert payload["code"] == "lifecycle_additive_merge_unsupported"
    assert "unsupported fields" in payload["detail"]


def test_pr_bundle_s3_15_terraform_strategy_inputs_map_defaults() -> None:
    """Task 6: S3.15 Terraform bundle maps custom key inputs."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="kms-bucket",
        region="us-east-1",
        control_id="S3.15",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={
            "kms_key_mode": "custom",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
        },
    )
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_encryption_kms.tf")["content"]
    assert 'default     = "arn:aws:kms:us-east-1:123456789012:key/custom-key-id"' in content


def test_pr_bundle_s3_15_cloudformation_strategy_inputs_map_defaults() -> None:
    """Task 6: S3.15 CloudFormation bundle maps custom key inputs."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="kms-bucket",
        region="us-east-1",
        control_id="S3.15",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={
            "kms_key_mode": "custom",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
        },
    )
    content = r["files"][0]["content"]
    assert "KmsKeyArn:" in content
    assert 'Default: "arn:aws:kms:us-east-1:123456789012:key/custom-key-id"' in content


def test_pr_bundle_s3_15_custom_mode_requires_kms_key_arn() -> None:
    """Task 6: S3.15 custom key mode fails closed when kms_key_arn is missing."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="kms-bucket",
        region="us-east-1",
        control_id="S3.15",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "terraform",
            strategy_inputs={"kms_key_mode": "custom"},
        )
    payload = exc_info.value.as_dict()
    assert payload["code"] == "missing_kms_key_arn"
    assert payload["action_type"] == ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS


def test_pr_bundle_s3_9_review_required_resolution_returns_guidance_bundle() -> None:
    """Wave 6: downgraded S3.9 branches stay metadata-only once destination safety is unproven."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ACCESS_LOGGING,
        target_id="log-source-bucket",
        region="us-east-1",
        control_id="S3.9",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"log_bucket_name": "dedicated-access-log-bucket"},
        resolution={
            "strategy_id": "s3_enable_access_logging_guided",
            "profile_id": "s3_enable_access_logging_review_destination_safety",
            "support_tier": "review_required_bundle",
            "blocked_reasons": [
                "Destination safety could not be proven for the selected S3 access-log bucket."
            ],
            "preservation_summary": {"destination_safety_proven": False},
            "decision_rationale": "Destination safety is under-proven.",
        },
    )

    assert r["metadata"]["non_executable_bundle"] is True
    assert [f["path"] for f in r["files"]] == ["decision.json", "README.txt"]
    decision = json.loads(next(f for f in r["files"] if f["path"] == "decision.json")["content"])
    assert decision["profile_id"] == "s3_enable_access_logging_review_destination_safety"


def test_pr_bundle_s3_15_review_required_resolution_returns_guidance_bundle() -> None:
    """Wave 6: downgraded S3.15 customer-managed branches stay metadata-only."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_ENCRYPTION_KMS,
        target_id="kms-bucket",
        region="us-east-1",
        control_id="S3.15",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        strategy_inputs={
            "kms_key_mode": "custom",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
        },
        resolution={
            "strategy_id": "s3_enable_sse_kms_guided",
            "profile_id": "s3_enable_sse_kms_customer_managed",
            "support_tier": "review_required_bundle",
            "blocked_reasons": [
                "Customer-managed KMS key policy/grant evidence is under-specified."
            ],
            "preservation_summary": {"customer_managed_dependency_proven": False},
            "decision_rationale": "Customer-managed KMS safety is under-proven.",
        },
    )

    assert r["metadata"]["non_executable_bundle"] is True
    assert [f["path"] for f in r["files"]] == ["decision.json", "README.txt"]
    decision = json.loads(next(f for f in r["files"] if f["path"] == "decision.json")["content"])
    assert decision["profile_id"] == "s3_enable_sse_kms_customer_managed"


def test_pr_bundle_s3_2_non_executable_resolution_returns_guidance_bundle() -> None:
    """Wave 6: downgraded S3.2 branches render metadata-only guidance instead of runnable IaC."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_BLOCK_PUBLIC_ACCESS,
        target_id="website-bucket",
        region="us-east-1",
        control_id="S3.2",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_bucket_block_public_access_standard",
        resolution={
            "strategy_id": "s3_bucket_block_public_access_standard",
            "profile_id": "s3_bucket_block_public_access_manual_preservation",
            "support_tier": "manual_guidance_only",
            "blocked_reasons": [
                "Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access."
            ],
            "preservation_summary": {"manual_preservation_required": True},
            "decision_rationale": "Manual preservation is required.",
        },
    )
    assert r["metadata"]["non_executable_bundle"] is True
    paths = [f["path"] for f in r["files"]]
    assert paths == ["decision.json", "README.txt"]
    assert all(not path.endswith((".tf", ".yaml")) for path in paths)
    assert "manual_guidance_only" in next(f for f in r["files"] if f["path"] == "README.txt")["content"]
    decision = json.loads(next(f for f in r["files"] if f["path"] == "decision.json")["content"])
    assert decision["profile_id"] == "s3_bucket_block_public_access_manual_preservation"


def test_pr_bundle_s3_ssl_preserve_existing_policy_false_returns_guidance_bundle_when_resolver_downgrades() -> None:
    """Wave 6: unsafe S3.5 overwrite requests stay non-executable once the resolver downgrades them."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"preserve_existing_policy": False},
        risk_snapshot={"evidence": {"existing_bucket_policy_statement_count": 2}},
        resolution={
            "strategy_id": "s3_enforce_ssl_strict_deny",
            "profile_id": "s3_enforce_ssl_strict_deny",
            "support_tier": "manual_guidance_only",
            "blocked_reasons": [
                "Unsafe bucket policy overwrite is not executable in Wave 6; preserve_existing_policy must remain true."
            ],
            "preservation_summary": {"unsafe_overwrite_requested": True},
            "decision_rationale": "Unsafe overwrite stays manual-only.",
        },
    )
    paths = [f["path"] for f in r["files"]]
    assert paths == ["decision.json", "README.txt"]
    assert "s3_bucket_require_ssl.tf" not in paths
    assert "terraform.auto.tfvars.json" not in paths
    assert r["metadata"]["non_executable_bundle"] is True


def test_pr_bundle_s3_ssl_review_required_resolution_returns_guidance_bundle() -> None:
    """Wave 6: under-proven S3.5 merge safety returns review metadata only."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    r = generate_pr_bundle(
        action,
        "cloudformation",
        risk_snapshot={"evidence": {"existing_bucket_policy_statement_count": 2}},
        resolution={
            "strategy_id": "s3_enforce_ssl_strict_deny",
            "profile_id": "s3_enforce_ssl_strict_deny",
            "support_tier": "review_required_bundle",
            "blocked_reasons": [
                "Existing bucket policy statements were detected, but their JSON was not captured for safe merge."
            ],
            "preservation_summary": {"merge_safe_policy_available": False},
            "decision_rationale": "Policy capture is incomplete.",
        },
    )
    assert r["metadata"]["non_executable_bundle"] is True
    paths = [f["path"] for f in r["files"]]
    assert paths == ["decision.json", "README.txt"]
    decision = json.loads(next(f for f in r["files"] if f["path"] == "decision.json")["content"])
    assert decision["support_tier"] == "review_required_bundle"


def test_pr_bundle_s3_11_review_required_resolution_returns_guidance_bundle() -> None:
    """Wave 6: S3.11 additive-merge uncertainty renders metadata-only guidance."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_LIFECYCLE_CONFIGURATION,
        target_id="lifecycle-bucket",
        region="us-east-1",
        control_id="S3.11",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        resolution={
            "strategy_id": "s3_enable_abort_incomplete_uploads",
            "profile_id": "s3_enable_abort_incomplete_uploads",
            "support_tier": "review_required_bundle",
            "blocked_reasons": [
                "Existing lifecycle rules were detected, but the lifecycle document was not captured for additive review."
            ],
            "preservation_summary": {"additive_merge_safe": False},
            "decision_rationale": "Lifecycle capture is incomplete.",
        },
    )
    assert r["metadata"]["non_executable_bundle"] is True
    paths = [f["path"] for f in r["files"]]
    assert paths == ["decision.json", "README.txt"]
    assert "s3_bucket_lifecycle_configuration.tf" not in paths


def test_pr_bundle_s3_ssl_fails_closed_when_policy_count_present_without_policy_json() -> None:
    """S3.5 should fail closed when runtime evidence says policy statements exist but JSON is missing."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "terraform",
            risk_snapshot={"evidence": {"existing_bucket_policy_statement_count": 2}},
        )
    payload = exc_info.value.as_dict()
    assert payload["code"] == "bucket_policy_preservation_evidence_missing"


def test_pr_bundle_s3_ssl_fails_closed_when_policy_evidence_is_missing() -> None:
    """S3.5 should fail closed when preservation evidence is entirely missing."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "terraform",
            risk_snapshot={"evidence": {}},
        )
    payload = exc_info.value.as_dict()
    assert payload["code"] == "bucket_policy_preservation_evidence_missing"


def test_pr_bundle_s3_ssl_terraform_apply_time_merge_uses_resolution_summary() -> None:
    """S3.5 Terraform can fetch and merge the live bucket policy when the resolver approved apply-time merge."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        resolution={
            "strategy_id": "s3_enforce_ssl_strict_deny",
            "profile_id": "s3_enforce_ssl_strict_deny",
            "support_tier": "deterministic_bundle",
            "blocked_reasons": [],
            "preservation_summary": {
                "apply_time_merge": True,
                "apply_time_merge_reason": "Runtime capture failed (AccessDenied).",
            },
            "decision_rationale": "Apply-time merge is allowed.",
        },
    )

    content = _bundle_file_content(r, "s3_bucket_require_ssl.tf")
    paths = [f["path"] for f in r["files"]]

    assert 'data "external" "existing_policy"' in content
    assert 'program = ["python3", "${path.module}/scripts/s3_policy_fetch.py"]' in content
    assert "filtered_existing_policy_statements" in content
    assert 'data "aws_iam_policy_document" "merged_policy"' in content
    assert 'resource "aws_s3_bucket_policy" "security_autopilot"' in content
    assert "terraform.auto.tfvars.json" not in paths
    assert "scripts/s3_policy_fetch.py" in paths
    assert "scripts/s3_policy_capture.py" in paths
    assert "rollback/s3_policy_restore.py" in paths
    assert any("fetched and merged at terraform plan/apply time" in step for step in r["steps"])
    assert any("python3 scripts/s3_policy_capture.py" in step for step in r["steps"])
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/s3_policy_restore.py",
        "runner": "python3",
    }


def test_pr_bundle_s3_ssl_apply_time_merge_filters_existing_ssl_deny_statement() -> None:
    """Apply-time merge should filter existing SSL deny statements before adding the managed deny."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        resolution={
            "strategy_id": "s3_enforce_ssl_strict_deny",
            "profile_id": "s3_enforce_ssl_strict_deny",
            "support_tier": "deterministic_bundle",
            "blocked_reasons": [],
            "preservation_summary": {"apply_time_merge": True},
            "decision_rationale": "Apply-time merge is allowed.",
        },
    )

    content = _bundle_file_content(r, "s3_bucket_require_ssl.tf")
    assert 'lower(try(tostring(stmt.Sid), "")) == "denyinsecuretransport"' in content
    assert 'stmt.Condition.Bool["aws:SecureTransport"]' in content
    assert 'lookup(data.external.existing_policy.result, "policy_json", "")' in content


def test_pr_bundle_s3_ssl_terraform_preloads_policy_json_for_merge() -> None:
    """S3.5 Terraform should preload existing policy JSON for merge-safe policy generation."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "KeepAppRead",
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::111122223333:role/app-role"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::my-bucket/*",
            }
        ],
    }
    r = generate_pr_bundle(
        action,
        "terraform",
        risk_snapshot={
            "evidence": {
                "existing_bucket_policy_statement_count": 1,
                "existing_bucket_policy_json": json.dumps(existing_policy),
            }
        },
    )
    content = next(f for f in r["files"] if f["path"] == "s3_bucket_require_ssl.tf")["content"]
    tfvars = next(f for f in r["files"] if f["path"] == "terraform.auto.tfvars.json")
    parsed_tfvars = json.loads(tfvars["content"])
    preserved_policy = json.loads(parsed_tfvars["existing_bucket_policy_json"])

    assert 'data "aws_iam_policy_document" "merged_policy"' in content
    assert "source_policy_documents" in content
    assert "override_policy_documents" in content
    assert 'resource "aws_s3_bucket_policy" "security_autopilot"' in content
    assert "local-exec" not in content
    assert "KeepAppRead" in json.dumps(preserved_policy)
    assert "DenyInsecureTransport" in content


def test_pr_bundle_s3_ssl_terraform_creates_missing_bucket_when_requested() -> None:
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="ssl-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_id="s3_enforce_ssl_strict_deny",
        strategy_inputs={"create_bucket_if_missing": True},
    )
    content = _bundle_file_content(r, "s3_bucket_require_ssl.tf")
    paths = [f["path"] for f in r["files"]]

    assert 'variable "create_bucket_if_missing"' in content
    assert 'resource "aws_s3_bucket" "target_bucket"' in content
    assert "terraform.auto.tfvars.json" not in paths
    assert "scripts/s3_policy_capture.py" not in paths
    assert "rollback/s3_policy_restore.py" not in paths
    assert any("create the missing target bucket" in step for step in r["steps"])


def test_pr_bundle_s3_ssl_cloudformation_apply_time_merge_stays_fail_closed() -> None:
    """CloudFormation S3.5 still requires captured policy JSON even when Terraform can merge at apply time."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    with pytest.raises(PRBundleGenerationError) as exc_info:
        generate_pr_bundle(
            action,
            "cloudformation",
            resolution={
                "strategy_id": "s3_enforce_ssl_strict_deny",
                "profile_id": "s3_enforce_ssl_strict_deny",
                "support_tier": "deterministic_bundle",
                "blocked_reasons": [],
                "preservation_summary": {"apply_time_merge": True},
                "decision_rationale": "Apply-time merge is allowed.",
            },
        )
    payload = exc_info.value.as_dict()
    assert payload["code"] == "bucket_policy_preservation_evidence_missing"


def test_pr_bundle_s3_ssl_terraform_includes_exact_policy_capture_and_restore_helpers() -> None:
    """S3.5 Terraform should ship exact policy capture/restore helpers when preserving a bucket policy."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "KeepAppRead",
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::111122223333:role/app-role"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::my-bucket/*",
            }
        ],
    }
    r = generate_pr_bundle(
        action,
        "terraform",
        risk_snapshot={
            "evidence": {
                "existing_bucket_policy_statement_count": 1,
                "existing_bucket_policy_json": json.dumps(existing_policy),
            }
        },
    )

    apply_script = _bundle_file_content(r, "scripts/s3_policy_capture.py")
    restore_script = _bundle_file_content(r, "rollback/s3_policy_restore.py")

    assert '"get-bucket-policy"' in apply_script
    assert ".s3-rollback/policy_snapshot.json" in apply_script
    assert '"put-bucket-policy"' in restore_script
    assert '"delete-bucket-policy"' in restore_script
    assert any(
        "python3 scripts/s3_policy_capture.py" in step
        for step in r["steps"]
    )
    assert any(
        "python3 rollback/s3_policy_restore.py" in step
        for step in r["steps"]
    )
    assert r["metadata"]["bundle_rollback_entries"][str(action.id)] == {
        "path": "rollback/s3_policy_restore.py",
        "runner": "python3",
    }


def test_pr_bundle_s3_ssl_terraform_zero_policy_path_skips_tfvars_preload() -> None:
    """S3.5 Terraform should not emit tfvars preload file when no policy statements exist."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        risk_snapshot={"evidence": {"existing_bucket_policy_statement_count": 0}},
    )

    paths = [f["path"] for f in r["files"]]
    assert "s3_bucket_require_ssl.tf" in paths
    assert "terraform.auto.tfvars.json" not in paths


def test_pr_bundle_s3_ssl_accepts_explicit_preservation_evidence_inputs() -> None:
    """Grouped S3 bundles can rely on persisted strategy inputs without a risk snapshot."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    r = generate_pr_bundle(
        action,
        "terraform",
        strategy_inputs={"existing_bucket_policy_statement_count": 0},
    )

    paths = [f["path"] for f in r["files"]]
    assert "s3_bucket_require_ssl.tf" in paths
    assert "terraform.auto.tfvars.json" not in paths


def test_pr_bundle_s3_ssl_cloudformation_uses_merge_custom_resource() -> None:
    """S3.5 CloudFormation should merge existing policy via custom resource instead of overwrite resource."""
    action = _make_action(
        action_type=ACTION_TYPE_S3_BUCKET_REQUIRE_SSL,
        target_id="my-bucket",
        region="us-east-1",
        control_id="S3.5",
    )
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "KeepAnalyticsRead",
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::111122223333:role/analytics-role"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::my-bucket/*",
            }
        ],
    }
    r = generate_pr_bundle(
        action,
        "cloudformation",
        risk_snapshot={
            "evidence": {
                "existing_bucket_policy_statement_count": 1,
                "existing_bucket_policy_json": json.dumps(existing_policy),
            }
        },
    )
    content = r["files"][0]["content"]
    assert "Custom::S3SslPolicyMerge" in content
    assert "S3SslPolicyMergeFunction" in content
    assert "get_bucket_policy" in content
    assert "put_bucket_policy" in content
    assert "ExistingBucketPolicyJson" in content
    assert "AWS::S3::BucketPolicy" not in content


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
        strategy_inputs = None
        if action_type == ACTION_TYPE_SG_RESTRICT_PUBLIC_PORTS:
            target_id = "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0123456789abcdef0"
        if action_type == ACTION_TYPE_CLOUDTRAIL_ENABLED:
            strategy_inputs = {"trail_bucket_name": "security-autopilot-cloudtrail-logs"}
        action = _make_action(action_type=action_type, target_id=target_id, region="us-east-1")
        r = generate_pr_bundle(action, "cloudformation", strategy_inputs=strategy_inputs)
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
