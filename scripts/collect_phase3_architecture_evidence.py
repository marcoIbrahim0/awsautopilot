#!/usr/bin/env python3
"""
Collect Phase 3 architecture evidence snapshots from AWS and optional readiness endpoint.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import ClientError


DEFAULT_DR_STACK = "security-autopilot-dr-backup-controls"
DEFAULT_OUT_DIR = "docs/audit-remediation/evidence"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Phase 3 architecture evidence artifacts.")
    parser.add_argument("--region", default="", help="AWS region override (defaults to env/profile region).")
    parser.add_argument("--dr-stack", default=DEFAULT_DR_STACK)
    parser.add_argument("--readiness-url", default="", help="Optional /ready endpoint URL.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser


def _describe_stack(cf: Any, stack_name: str) -> dict[str, Any] | None:
    try:
        response = cf.describe_stacks(StackName=stack_name)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"ValidationError", "ResourceNotFoundException"}:
            return None
        raise
    stacks = response.get("Stacks") or []
    if not stacks:
        return None
    return stacks[0]


def _stack_outputs(stack: dict[str, Any] | None) -> dict[str, str]:
    if not stack:
        return {}
    outputs = stack.get("Outputs") or []
    return {str(item.get("OutputKey") or ""): str(item.get("OutputValue") or "") for item in outputs}


def _stack_parameters(stack: dict[str, Any] | None) -> dict[str, str]:
    if not stack:
        return {}
    params = stack.get("Parameters") or []
    return {str(item.get("ParameterKey") or ""): str(item.get("ParameterValue") or "") for item in params}


def _backup_job_statuses(backup: Any, vault_name: str, since: datetime) -> dict[str, int]:
    counters: dict[str, int] = {}
    paginator = backup.get_paginator("list_backup_jobs")
    for page in paginator.paginate(ByCreatedAfter=since):
        for item in page.get("BackupJobs") or []:
            if vault_name and str(item.get("BackupVaultName") or "") != vault_name:
                continue
            state = str(item.get("State") or "UNKNOWN")
            counters[state] = counters.get(state, 0) + 1
    return counters


def _restore_job_statuses(backup: Any, since: datetime) -> dict[str, int]:
    counters: dict[str, int] = {}
    paginator = backup.get_paginator("list_restore_jobs")
    for page in paginator.paginate(ByCreatedAfter=since):
        for item in page.get("RestoreJobs") or []:
            state = str(item.get("Status") or "UNKNOWN")
            counters[state] = counters.get(state, 0) + 1
    return counters


def _recovery_points(backup: Any, vault_name: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if not vault_name:
        return points
    paginator = backup.get_paginator("list_recovery_points_by_backup_vault")
    for page in paginator.paginate(BackupVaultName=vault_name):
        for item in page.get("RecoveryPoints") or []:
            points.append(
                {
                    "arn": str(item.get("RecoveryPointArn") or ""),
                    "resource_arn": str(item.get("ResourceArn") or ""),
                    "status": str(item.get("Status") or ""),
                    "created_at": str(item.get("CreationDate") or ""),
                    "delete_after": str(item.get("CalculatedLifecycle", {}).get("DeleteAt") or ""),
                }
            )
    points.sort(key=lambda p: p["created_at"], reverse=True)
    return points


def _fetch_readiness(url: str) -> dict[str, Any]:
    if not url:
        return {"checked": False}
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=10) as resp:
            status = int(resp.status)
            body = resp.read().decode("utf-8")
        payload = json.loads(body)
        return {
            "checked": True,
            "url": url,
            "http_status": status,
            "ready": bool(payload.get("ready")),
            "status": payload.get("status"),
        }
    except HTTPError as exc:
        return {"checked": True, "url": url, "http_status": int(exc.code), "error": str(exc)}
    except URLError as exc:
        return {"checked": True, "url": url, "error": str(exc.reason)}
    except Exception as exc:  # pragma: no cover - defensive path
        return {"checked": True, "url": url, "error": str(exc)}


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Phase 3 Architecture Evidence Snapshot")
    lines.append("")
    lines.append(f"Generated at: `{payload['generated_at']}`")
    lines.append(f"Region: `{payload['region']}`")
    identity = payload.get("identity") or {}
    lines.append(f"AWS Account: `{identity.get('account', 'unknown')}`")
    lines.append(f"AWS Arn: `{identity.get('arn', 'unknown')}`")
    lines.append("")

    stack = payload.get("stack") or {}
    lines.append("## DR Stack Status")
    lines.append("")
    lines.append(f"- Name: `{stack.get('name', '')}`")
    lines.append(f"- Status: `{stack.get('status', 'NOT_FOUND')}`")
    lines.append(f"- Last Updated: `{stack.get('last_updated', '')}`")
    lines.append("")

    backup = payload.get("backup") or {}
    lines.append("## Backup Summary")
    lines.append("")
    lines.append(f"- Vault: `{backup.get('backup_vault_name', '')}`")
    lines.append(f"- Recovery points: `{backup.get('recovery_points_count', 0)}`")
    lines.append(f"- Backup jobs (24h): `{backup.get('backup_jobs_24h', {})}`")
    lines.append(f"- Restore jobs (24h): `{backup.get('restore_jobs_24h', {})}`")
    lines.append("")

    readiness = payload.get("readiness") or {}
    lines.append("## Readiness Gate")
    lines.append("")
    if readiness.get("checked"):
        lines.append(f"- URL: `{readiness.get('url', '')}`")
        lines.append(f"- HTTP status: `{readiness.get('http_status', 'n/a')}`")
        lines.append(f"- Ready: `{readiness.get('ready', False)}`")
        if readiness.get("error"):
            lines.append(f"- Error: `{readiness.get('error')}`")
    else:
        lines.append("- Readiness URL not provided.")
    lines.append("")

    lines.append("## Artifact Files")
    lines.append("")
    lines.append(f"- JSON: `{payload['json_artifact_path']}`")
    lines.append(f"- Markdown: `{payload['markdown_artifact_path']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _build_parser().parse_args()

    session_kwargs: dict[str, Any] = {}
    if args.region:
        session_kwargs["region_name"] = args.region
    session = boto3.session.Session(**session_kwargs)
    region = session.region_name or "unknown"

    cf = session.client("cloudformation")
    backup = session.client("backup")
    sts = session.client("sts")

    identity_raw = sts.get_caller_identity()
    identity = {
        "account": str(identity_raw.get("Account") or ""),
        "arn": str(identity_raw.get("Arn") or ""),
        "user_id": str(identity_raw.get("UserId") or ""),
    }

    stack_raw = _describe_stack(cf, args.dr_stack)
    outputs = _stack_outputs(stack_raw)
    params = _stack_parameters(stack_raw)

    backup_vault_name = str(params.get("BackupVaultName") or "")
    if not backup_vault_name:
        backup_vault_name = str(outputs.get("BackupVaultArn") or "").split(":")[-1]

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    backup_jobs_24h = _backup_job_statuses(backup, backup_vault_name, since)
    restore_jobs_24h = _restore_job_statuses(backup, since)
    recovery_points = _recovery_points(backup, backup_vault_name)

    readiness = _fetch_readiness(str(args.readiness_url or "").strip())

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"phase3-architecture-{timestamp}.json"
    md_path = out_dir / f"phase3-architecture-{timestamp}.md"

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": region,
        "identity": identity,
        "stack": {
            "name": args.dr_stack,
            "status": str(stack_raw.get("StackStatus") if stack_raw else "NOT_FOUND"),
            "last_updated": str(
                (stack_raw.get("LastUpdatedTime") or stack_raw.get("CreationTime") or "")
                if stack_raw
                else ""
            ),
        },
        "stack_outputs": outputs,
        "stack_parameters": params,
        "backup": {
            "backup_vault_name": backup_vault_name,
            "recovery_points_count": len(recovery_points),
            "latest_recovery_points": recovery_points[:10],
            "backup_jobs_24h": backup_jobs_24h,
            "restore_jobs_24h": restore_jobs_24h,
        },
        "readiness": readiness,
        "json_artifact_path": str(json_path),
        "markdown_artifact_path": str(md_path),
    }

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")

    print(f"Wrote: {md_path}")
    print(f"Wrote: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
