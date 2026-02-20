from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any


class TerraformError(Exception):
    def __init__(self, message: str, transcript: list[dict[str, Any]]):
        super().__init__(message)
        self.transcript = transcript


def run_terraform_apply(
    workdir: Path,
    timeout_sec: int,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    transcript: list[dict[str, Any]] = []
    _run_sg_preflight(workdir, timeout_sec, merged_env, transcript)
    _write_bundle_auto_tfvars(workdir, merged_env, transcript)
    commands = [
        ["terraform", "init", "-input=false"],
        ["terraform", "plan", "-input=false", "-out=tfplan"],
        ["terraform", "apply", "-auto-approve", "tfplan"],
    ]
    for command in commands:
        _run_or_raise(command, workdir, timeout_sec, merged_env, transcript, "Terraform command failed")

    return transcript


def _run_sg_preflight(
    workdir: Path,
    timeout_sec: int,
    env: dict[str, str],
    transcript: list[dict[str, Any]],
) -> None:
    config = _load_sg_bundle_config(workdir, env)
    if config is None:
        return

    describe = _sg_describe_command(config)
    describe_record = run_command(describe, workdir, timeout_sec, env)
    transcript.append(describe_record)
    if int(describe_record["exit_code"]) != 0:
        raise TerraformError("Preflight command failed: aws ec2 describe-security-group-rules", transcript)

    rule_ids = _extract_revoke_rule_ids(describe_record.get("stdout"), config)
    if not rule_ids:
        transcript.append(_note_record("sg_preflight_noop", "No matching SG rules to revoke before Terraform"))
        return

    revoke = _sg_revoke_command(config, rule_ids)
    _run_or_raise(revoke, workdir, timeout_sec, env, transcript, "Preflight command failed")


def _write_bundle_auto_tfvars(
    workdir: Path,
    env: dict[str, str],
    transcript: list[dict[str, Any]],
) -> None:
    inferred = {}
    inferred.update(_infer_s3_access_logging_vars(workdir))
    inferred.update(_infer_s3_kms_vars(workdir, env))
    if not inferred:
        return

    path = workdir / "security_autopilot.auto.tfvars.json"
    existing = _parse_existing_tfvars(path)
    existing.update(inferred)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    keys = ", ".join(sorted(inferred.keys()))
    transcript.append(_note_record("autofill_tfvars", f"Wrote {path.name} with inferred vars: {keys}"))


def _parse_existing_tfvars(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _infer_s3_access_logging_vars(workdir: Path) -> dict[str, str]:
    tf_path = workdir / "s3_bucket_access_logging.tf"
    if not tf_path.exists():
        return {}

    tf_text = tf_path.read_text(encoding="utf-8")
    if not _variable_requires_value(tf_text, "log_bucket_name"):
        return {}
    bucket_name = _extract_logging_source_bucket(tf_text)
    return {"log_bucket_name": bucket_name} if bucket_name else {}


def _infer_s3_kms_vars(workdir: Path, env: dict[str, str]) -> dict[str, str]:
    tf_path = workdir / "s3_bucket_encryption_kms.tf"
    if not tf_path.exists():
        return {}

    tf_text = tf_path.read_text(encoding="utf-8")
    if not _variable_requires_value(tf_text, "kms_key_arn"):
        return {}

    region = _bundle_region(workdir, env)
    account_id = _bundle_account_id(tf_text, env)
    if not region or not account_id:
        return {}
    return {"kms_key_arn": f"arn:aws:kms:{region}:{account_id}:alias/aws/s3"}


def _variable_requires_value(tf_text: str, variable_name: str) -> bool:
    pattern = rf'variable\s+"{re.escape(variable_name)}"\s*\{{(.*?)\}}'
    match = re.search(pattern, tf_text, flags=re.DOTALL)
    if not match:
        return False
    block = str(match.group(1) or "")
    return re.search(r"^\s*default\s*=", block, flags=re.MULTILINE) is None


def _extract_logging_source_bucket(tf_text: str) -> str:
    resource_pattern = r'resource\s+"aws_s3_bucket_logging"\s+"[^"]+"\s*\{(.*?)\}'
    resource_match = re.search(resource_pattern, tf_text, flags=re.DOTALL)
    resource_block = str(resource_match.group(1) or "") if resource_match else ""
    bucket_match = re.search(r'^\s*bucket\s*=\s*"([^"]+)"', resource_block, flags=re.MULTILINE)
    if bucket_match:
        return str(bucket_match.group(1) or "").strip()
    comment_match = re.search(r"\|\s*Bucket:\s*([A-Za-z0-9._:-]+)", tf_text)
    return str(comment_match.group(1) or "").strip() if comment_match else ""


def _bundle_region(workdir: Path, env: dict[str, str]) -> str:
    providers = (workdir / "providers.tf")
    providers_text = providers.read_text(encoding="utf-8") if providers.exists() else ""
    region = _extract_provider_region(providers_text)
    if region:
        return region
    return str(env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION") or "").strip()


def _bundle_account_id(tf_text: str, env: dict[str, str]) -> str:
    env_account = str(env.get("AWS_ACCOUNT_ID") or "").strip()
    if env_account:
        return env_account
    comment_match = re.search(r"Account:\s*(\d{12})", tf_text)
    if comment_match:
        return str(comment_match.group(1) or "").strip()
    return _caller_account_id(env)


def _caller_account_id(env: dict[str, str]) -> str:
    try:
        completed = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--output", "json"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except Exception:
        return ""
    if int(completed.returncode) != 0:
        return ""
    payload = _parse_json(completed.stdout)
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("Account") or "").strip()


def _sg_describe_command(config: dict[str, str]) -> list[str]:
    return [
        "aws",
        "ec2",
        "describe-security-group-rules",
        "--region",
        config["region"],
        "--filters",
        f"Name=group-id,Values={config['security_group_id']}",
        "--output",
        "json",
    ]


def _sg_revoke_command(config: dict[str, str], rule_ids: list[str]) -> list[str]:
    return [
        "aws",
        "ec2",
        "revoke-security-group-ingress",
        "--region",
        config["region"],
        "--group-id",
        config["security_group_id"],
        "--security-group-rule-ids",
        *rule_ids,
    ]


def _run_or_raise(
    command: list[str],
    workdir: Path,
    timeout_sec: int,
    env: dict[str, str],
    transcript: list[dict[str, Any]],
    message: str,
) -> None:
    record = run_command(command, workdir, timeout_sec, env)
    transcript.append(record)
    if int(record["exit_code"]) != 0:
        raise TerraformError(f"{message}: {' '.join(command)}", transcript)


def _load_sg_bundle_config(workdir: Path, env: dict[str, str]) -> dict[str, str] | None:
    sg_path = workdir / "sg_restrict_public_ports.tf"
    if not sg_path.exists():
        return None

    sg_text = sg_path.read_text(encoding="utf-8")
    providers_text = (workdir / "providers.tf").read_text(encoding="utf-8") if (workdir / "providers.tf").exists() else ""
    security_group_id = _extract_tf_var_default(sg_text, "security_group_id")
    region = _extract_provider_region(providers_text) or env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION") or ""
    if not security_group_id or not region:
        return None

    return {
        "region": str(region),
        "security_group_id": security_group_id,
        "allowed_cidr": _extract_tf_var_default(sg_text, "allowed_cidr"),
        "allowed_cidr_ipv6": _extract_tf_var_default(sg_text, "allowed_cidr_ipv6"),
    }


def _extract_tf_var_default(tf_text: str, variable_name: str) -> str:
    pattern = rf'variable\s+"{re.escape(variable_name)}"\s*\{{.*?default\s*=\s*"([^"]*)"'
    match = re.search(pattern, tf_text, flags=re.DOTALL)
    return str(match.group(1)).strip() if match else ""


def _extract_provider_region(providers_text: str) -> str:
    match = re.search(r'region\s*=\s*"([^"]+)"', providers_text)
    return str(match.group(1)).strip() if match else ""


def _extract_revoke_rule_ids(stdout: Any, config: dict[str, str]) -> list[str]:
    payload = _parse_json(stdout)
    if not isinstance(payload, dict):
        return []
    rules = payload.get("SecurityGroupRules") if isinstance(payload.get("SecurityGroupRules"), list) else []
    selected = [
        _rule_id(rule)
        for rule in rules
        if _is_target_ingress(rule)
        and _is_target_cidr(rule, config.get("allowed_cidr", ""), config.get("allowed_cidr_ipv6", ""))
    ]
    return [x for x in selected if x]


def _parse_json(value: Any) -> Any:
    try:
        return json.loads(str(value or "").strip() or "{}")
    except json.JSONDecodeError:
        return {}


def _rule_id(rule: Any) -> str:
    if not isinstance(rule, dict):
        return ""
    return str(rule.get("SecurityGroupRuleId") or "").strip()


def _is_target_ingress(rule: Any) -> bool:
    if not isinstance(rule, dict):
        return False
    if bool(rule.get("IsEgress")):
        return False
    from_port = int(rule.get("FromPort")) if isinstance(rule.get("FromPort"), int) else -1
    to_port = int(rule.get("ToPort")) if isinstance(rule.get("ToPort"), int) else -1
    return from_port in {22, 3389} and to_port in {22, 3389}


def _is_target_cidr(rule: Any, allowed_cidr: str, allowed_cidr_ipv6: str) -> bool:
    if not isinstance(rule, dict):
        return False
    cidr4 = str(rule.get("CidrIpv4") or "").strip()
    cidr6 = str(rule.get("CidrIpv6") or "").strip()
    allowed4 = {x for x in {"0.0.0.0/0", allowed_cidr} if x}
    allowed6 = {x for x in {"::/0", allowed_cidr_ipv6} if x}
    return cidr4 in allowed4 or cidr6 in allowed6


def _note_record(command: str, message: str) -> dict[str, Any]:
    now = _utc_epoch_seconds()
    return {
        "command": command,
        "exit_code": 0,
        "stdout": message,
        "stderr": "",
        "duration_sec": 0.0,
        "started_at_epoch": now,
        "finished_at_epoch": now,
    }


def run_command(
    command: list[str],
    workdir: Path,
    timeout_sec: int,
    env: dict[str, str],
) -> dict[str, Any]:
    started = time.monotonic()
    started_at = _utc_epoch_seconds()
    completed = subprocess.run(
        command,
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_sec,
    )
    duration_sec = round(time.monotonic() - started, 3)

    return {
        "command": " ".join(command),
        "exit_code": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_sec": duration_sec,
        "started_at_epoch": started_at,
        "finished_at_epoch": _utc_epoch_seconds(),
    }


def _utc_epoch_seconds() -> float:
    return time.time()
