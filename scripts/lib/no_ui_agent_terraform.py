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
