from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.lib.no_ui_agent_terraform import TerraformError, run_terraform_apply


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_sg_bundle(workdir: Path) -> None:
    (workdir / "providers.tf").write_text('provider "aws" { region = "eu-north-1" }\n', encoding="utf-8")
    (workdir / "sg_restrict_public_ports.tf").write_text(
        '\n'.join(
            [
                'variable "security_group_id" { default = "sg-1234567890" }',
                'variable "allowed_cidr" { default = "10.0.0.0/8" }',
                'variable "allowed_cidr_ipv6" { default = "" }',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_s3_logging_bundle_missing_log_bucket(workdir: Path) -> None:
    (workdir / "providers.tf").write_text('provider "aws" { region = "eu-north-1" }\n', encoding="utf-8")
    (workdir / "s3_bucket_access_logging.tf").write_text(
        '\n'.join(
            [
                '# Account: 029037611564 | Region: eu-north-1 | Bucket: demo-bucket',
                'variable "log_bucket_name" { type = string }',
                'resource "aws_s3_bucket_logging" "security_autopilot" {',
                '  bucket        = "demo-bucket"',
                "  target_bucket = var.log_bucket_name",
                '  target_prefix = "logs/"',
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_s3_kms_bundle_missing_key(workdir: Path) -> None:
    (workdir / "providers.tf").write_text('provider "aws" { region = "eu-north-1" }\n', encoding="utf-8")
    (workdir / "s3_bucket_encryption_kms.tf").write_text(
        '\n'.join(
            [
                '# Account: 029037611564 | Region: eu-north-1 | Bucket: secure-bucket',
                'variable "kms_key_arn" { type = string }',
                'resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {',
                '  bucket = "secure-bucket"',
                "  rule {",
                "    apply_server_side_encryption_by_default {",
                '      sse_algorithm     = "aws:kms"',
                "      kms_master_key_id = var.kms_key_arn",
                "    }",
                "  }",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_terraform_apply_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del cwd, env, capture_output, text, check, timeout
        calls.append(command)
        return _Completed(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transcript = run_terraform_apply(tmp_path, timeout_sec=30)

    assert len(transcript) == 3
    assert calls[0][:2] == ["terraform", "init"]
    assert transcript[-1]["exit_code"] == 0


def test_run_terraform_apply_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del cwd, env, capture_output, text, check, timeout
        if command[1] == "plan":
            return _Completed(1, stderr="plan failed")
        return _Completed(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(TerraformError) as exc:
        run_terraform_apply(tmp_path, timeout_sec=30)

    assert len(exc.value.transcript) == 2
    assert exc.value.transcript[-1]["stderr"] == "plan failed"


def test_run_terraform_apply_sg_preflight_revokes_target_rules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_sg_bundle(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del cwd, env, capture_output, text, check, timeout
        calls.append(command)
        if command[:3] == ["aws", "ec2", "describe-security-group-rules"]:
            payload = {
                "SecurityGroupRules": [
                    {
                        "SecurityGroupRuleId": "sgr-public",
                        "IsEgress": False,
                        "FromPort": 22,
                        "ToPort": 22,
                        "CidrIpv4": "0.0.0.0/0",
                    },
                    {
                        "SecurityGroupRuleId": "sgr-duplicate",
                        "IsEgress": False,
                        "FromPort": 3389,
                        "ToPort": 3389,
                        "CidrIpv4": "10.0.0.0/8",
                    },
                    {
                        "SecurityGroupRuleId": "sgr-ignore",
                        "IsEgress": False,
                        "FromPort": 443,
                        "ToPort": 443,
                        "CidrIpv4": "0.0.0.0/0",
                    },
                ]
            }
            return _Completed(0, stdout=json.dumps(payload))
        return _Completed(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transcript = run_terraform_apply(tmp_path, timeout_sec=30)

    assert calls[0][:3] == ["aws", "ec2", "describe-security-group-rules"]
    assert calls[1][:3] == ["aws", "ec2", "revoke-security-group-ingress"]
    assert "sgr-public" in calls[1]
    assert "sgr-duplicate" in calls[1]
    assert len(transcript) == 5


def test_run_terraform_apply_sg_preflight_noop_when_no_target_rules(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_sg_bundle(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del cwd, env, capture_output, text, check, timeout
        calls.append(command)
        if command[:3] == ["aws", "ec2", "describe-security-group-rules"]:
            return _Completed(0, stdout=json.dumps({"SecurityGroupRules": []}))
        return _Completed(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transcript = run_terraform_apply(tmp_path, timeout_sec=30)

    assert calls[0][:3] == ["aws", "ec2", "describe-security-group-rules"]
    assert all(cmd[:3] != ["aws", "ec2", "revoke-security-group-ingress"] for cmd in calls)
    assert transcript[1]["command"] == "sg_preflight_noop"


def test_run_terraform_apply_autofills_s3_logging_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_s3_logging_bundle_missing_log_bucket(tmp_path)

    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del command, cwd, env, capture_output, text, check, timeout
        return _Completed(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transcript = run_terraform_apply(tmp_path, timeout_sec=30)

    tfvars_path = tmp_path / "security_autopilot.auto.tfvars.json"
    payload = json.loads(tfvars_path.read_text(encoding="utf-8"))
    assert payload["log_bucket_name"] == "demo-bucket"
    assert any(item.get("command") == "autofill_tfvars" for item in transcript)


def test_run_terraform_apply_autofills_s3_kms_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_s3_kms_bundle_missing_key(tmp_path)

    def fake_run(command, cwd, env, capture_output, text, check, timeout):
        del command, cwd, env, capture_output, text, check, timeout
        return _Completed(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_terraform_apply(tmp_path, timeout_sec=30)

    tfvars_path = tmp_path / "security_autopilot.auto.tfvars.json"
    payload = json.loads(tfvars_path.read_text(encoding="utf-8"))
    assert payload["kms_key_arn"] == "arn:aws:kms:eu-north-1:029037611564:alias/aws/s3"
