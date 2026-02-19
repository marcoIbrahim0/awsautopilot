#!/usr/bin/env python3
"""
Collect Phase 2 architecture evidence snapshots from AWS and write markdown/json artifacts.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

DEFAULT_SQS_STACK = "security-autopilot-sqs-queues"
DEFAULT_FORWARDER_STACK = "security-autopilot-control-plane-forwarder"
DEFAULT_RECONCILE_STACK = "security-autopilot-reconcile-scheduler"
FORWARDER_STACK_FALLBACK = "SecurityAutopilotControlPlaneForwarder"
DEFAULT_OUT_DIR = "docs/audit-remediation/evidence"

STACKS = (
    ("sqs", DEFAULT_SQS_STACK),
    ("forwarder", DEFAULT_FORWARDER_STACK),
    ("reconcile", DEFAULT_RECONCILE_STACK),
)

QUEUE_OUTPUT_KEYS = (
    "IngestQueueURL",
    "IngestDLQURL",
    "EventsFastLaneQueueURL",
    "EventsFastLaneDLQURL",
    "InventoryReconcileQueueURL",
    "InventoryReconcileDLQURL",
    "ExportReportQueueURL",
    "ExportReportDLQURL",
    "ContractQuarantineQueueURL",
)

ALARM_PREFIXES = (
    "security-autopilot-ingest-",
    "security-autopilot-events-",
    "security-autopilot-inventory-",
    "security-autopilot-export-report-",
    "security-autopilot-contract-quarantine-",
    "security-autopilot-control-plane-",
    "security-autopilot-reconcile-scheduler-",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Phase 2 architecture evidence artifacts.")
    parser.add_argument("--region", default="", help="AWS region override (defaults to env/profile region).")
    parser.add_argument("--sqs-stack", default=DEFAULT_SQS_STACK)
    parser.add_argument("--forwarder-stack", default=DEFAULT_FORWARDER_STACK)
    parser.add_argument("--reconcile-stack", default=DEFAULT_RECONCILE_STACK)
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


def _resolve_existing_stack(cf: Any, candidates: list[str]) -> tuple[str, dict[str, Any] | None]:
    for name in candidates:
        stack = _describe_stack(cf, name)
        if stack:
            return name, stack
    return candidates[0], None


def _stack_outputs(stack: dict[str, Any] | None) -> dict[str, str]:
    if not stack:
        return {}
    outputs = stack.get("Outputs") or []
    return {str(item.get("OutputKey") or ""): str(item.get("OutputValue") or "") for item in outputs}


def _queue_snapshot(sqs: Any, queue_url: str) -> dict[str, Any]:
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
            "CreatedTimestamp",
            "LastModifiedTimestamp",
        ],
    ).get("Attributes") or {}
    return {
        "queue_url": queue_url,
        "visible": int(attrs.get("ApproximateNumberOfMessages", "0")),
        "not_visible": int(attrs.get("ApproximateNumberOfMessagesNotVisible", "0")),
        "delayed": int(attrs.get("ApproximateNumberOfMessagesDelayed", "0")),
        "created_timestamp": attrs.get("CreatedTimestamp"),
        "last_modified_timestamp": attrs.get("LastModifiedTimestamp"),
    }


def _collect_alarms(cw: Any) -> list[dict[str, Any]]:
    paginator = cw.get_paginator("describe_alarms")
    alarms: list[dict[str, Any]] = []
    for page in paginator.paginate():
        for item in page.get("MetricAlarms") or []:
            name = str(item.get("AlarmName") or "")
            if not name:
                continue
            if any(name.startswith(prefix) for prefix in ALARM_PREFIXES):
                alarms.append(
                    {
                        "name": name,
                        "state": str(item.get("StateValue") or "UNKNOWN"),
                        "metric": str(item.get("MetricName") or ""),
                        "namespace": str(item.get("Namespace") or ""),
                    }
                )
    alarms.sort(key=lambda alarm: alarm["name"])
    return alarms


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Phase 2 Architecture Evidence Snapshot")
    lines.append("")
    lines.append(f"Generated at: `{payload['generated_at']}`")
    lines.append(f"Region: `{payload['region']}`")
    identity = payload.get("identity") or {}
    lines.append(f"AWS Account: `{identity.get('account', 'unknown')}`")
    lines.append(f"AWS Arn: `{identity.get('arn', 'unknown')}`")
    lines.append("")

    lines.append("## Stack Status")
    lines.append("")
    lines.append("| Stack | Name | Status |")
    lines.append("| --- | --- | --- |")
    for label, item in payload.get("stacks", {}).items():
        lines.append(
            f"| {label} | {item.get('name', '')} | {item.get('status', 'NOT_FOUND')} |"
        )
    lines.append("")

    lines.append("## Queue Snapshot")
    lines.append("")
    lines.append("| Queue Output Key | Visible | Not Visible | Delayed |")
    lines.append("| --- | --- | --- | --- |")
    queue_snapshots = payload.get("queue_snapshots", {})
    if queue_snapshots:
        for key, item in queue_snapshots.items():
            lines.append(
                f"| {key} | {item.get('visible', 0)} | {item.get('not_visible', 0)} | {item.get('delayed', 0)} |"
            )
    else:
        lines.append("| (none) |  |  |  |")
    lines.append("")

    lines.append("## Alarm Inventory")
    lines.append("")
    alarms = payload.get("alarms", [])
    lines.append(f"Total alarms matched: `{len(alarms)}`")
    lines.append("")
    for alarm in alarms:
        lines.append(f"- `{alarm['name']}` ({alarm['state']}) [{alarm['namespace']}:{alarm['metric']}]")

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
    cw = session.client("cloudwatch")
    sts = session.client("sts")

    identity_raw = sts.get_caller_identity()
    identity = {
        "account": str(identity_raw.get("Account") or ""),
        "arn": str(identity_raw.get("Arn") or ""),
        "user_id": str(identity_raw.get("UserId") or ""),
    }

    stack_candidates = {
        "sqs": [args.sqs_stack],
        "forwarder": [args.forwarder_stack],
        "reconcile": [args.reconcile_stack],
    }
    if FORWARDER_STACK_FALLBACK not in stack_candidates["forwarder"]:
        stack_candidates["forwarder"].append(FORWARDER_STACK_FALLBACK)

    stacks: dict[str, dict[str, Any]] = {}
    stack_outputs: dict[str, dict[str, str]] = {}
    for label, candidates in stack_candidates.items():
        resolved_name, stack = _resolve_existing_stack(cf, candidates)
        stacks[label] = {
            "name": resolved_name,
            "status": str(stack.get("StackStatus") if stack else "NOT_FOUND"),
            "last_updated": str(
                (stack.get("LastUpdatedTime") or stack.get("CreationTime") or "")
                if stack
                else ""
            ),
        }
        stack_outputs[label] = _stack_outputs(stack)

    queue_snapshots: dict[str, dict[str, Any]] = {}
    sqs_client_cache: dict[str, Any] = {}
    sqs_outputs = stack_outputs.get("sqs", {})
    for output_key in QUEUE_OUTPUT_KEYS:
        queue_url = str(sqs_outputs.get(output_key) or "").strip()
        if not queue_url:
            continue
        queue_region = queue_url.split(".")[1] if queue_url.startswith("https://sqs.") else (session.region_name or "eu-north-1")
        sqs_client = sqs_client_cache.get(queue_region)
        if sqs_client is None:
            sqs_client = session.client("sqs", region_name=queue_region)
            sqs_client_cache[queue_region] = sqs_client
        queue_snapshots[output_key] = _queue_snapshot(sqs_client, queue_url)

    alarms = _collect_alarms(cw)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"phase2-architecture-{timestamp}.json"
    md_path = out_dir / f"phase2-architecture-{timestamp}.md"

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": region,
        "identity": identity,
        "stacks": stacks,
        "stack_outputs": stack_outputs,
        "queue_snapshots": queue_snapshots,
        "alarms": alarms,
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
