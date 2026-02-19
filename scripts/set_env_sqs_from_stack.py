#!/usr/bin/env python3
"""
Fetch SQS queue URLs from the security-autopilot SQS CloudFormation stack
and set key worker queue URLs in config/.env.ops.

Run from project root. Idempotent: updates existing vars or appends if missing.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import boto3
from botocore.exceptions import ClientError

DEFAULT_STACK_CANDIDATES = (
    "security-autopilot-sqs-queues",
    "security-autopilot-sqs",
)
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".env.ops")
KEYS = (
    "SQS_INGEST_QUEUE_URL",
    "SQS_INGEST_DLQ_URL",
    "SQS_EVENTS_FAST_LANE_QUEUE_URL",
    "SQS_EVENTS_FAST_LANE_DLQ_URL",
    "SQS_INVENTORY_RECONCILE_QUEUE_URL",
    "SQS_INVENTORY_RECONCILE_DLQ_URL",
    "SQS_EXPORT_REPORT_QUEUE_URL",
    "SQS_EXPORT_REPORT_DLQ_URL",
    "SQS_CONTRACT_QUARANTINE_QUEUE_URL",
)
OUTPUT_KEYS = (
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync SQS queue URLs from CloudFormation outputs into config/.env.ops.",
    )
    parser.add_argument(
        "--stack-name",
        default="",
        help=(
            "CloudFormation stack name to use. "
            "If omitted, script auto-detects one of: "
            f"{', '.join(DEFAULT_STACK_CANDIDATES)}"
        ),
    )
    parser.add_argument(
        "--region",
        default="",
        help="AWS region override (defaults to current AWS CLI/boto3 config).",
    )
    return parser


def _describe_stack(cf, stack_name: str) -> dict | None:
    try:
        out = cf.describe_stacks(StackName=stack_name)
    except ClientError:
        return None
    stacks = out.get("Stacks") or []
    return stacks[0] if stacks else None


def _resolve_stack(cf, requested_stack_name: str) -> tuple[str, dict]:
    requested = (requested_stack_name or "").strip()
    if requested:
        stack = _describe_stack(cf, requested)
        if stack is None:
            print(f"Error: stack '{requested}' not found.", file=sys.stderr)
            sys.exit(1)
        return requested, stack

    for candidate in DEFAULT_STACK_CANDIDATES:
        stack = _describe_stack(cf, candidate)
        if stack is not None:
            return candidate, stack

    print(
        "Error: no matching SQS stack found. Tried: "
        + ", ".join(DEFAULT_STACK_CANDIDATES),
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    args = _build_parser().parse_args()
    client_kwargs = {}
    if args.region:
        client_kwargs["region_name"] = args.region
    cf = boto3.client("cloudformation", **client_kwargs)
    stack_name, stack = _resolve_stack(cf, args.stack_name)

    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs") or []}
    missing = [k for k in OUTPUT_KEYS if k not in outputs]
    if missing:
        print(f"Missing outputs: {missing}", file=sys.stderr)
        sys.exit(1)

    values = {
        KEYS[index]: outputs[OUTPUT_KEYS[index]]
        for index in range(len(KEYS))
    }

    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)

    if not os.path.isfile(ENV_PATH):
        with open(ENV_PATH, "w") as f:
            for k in KEYS:
                f.write(f'{k}="{values[k]}"\n')
        print(f"Created {ENV_PATH} with SQS vars.")
        return

    with open(ENV_PATH) as f:
        lines = f.readlines()

    updated = {k: False for k in KEYS}
    out_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("#"):
            out_lines.append(line)
            continue
        m = re.match(rf"^({'|'.join(KEYS)})=(.*)$", line.strip())
        if m:
            k = m.group(1)
            out_lines.append(f'{k}="{values[k]}"\n')
            updated[k] = True
        else:
            out_lines.append(line)

    for k in KEYS:
        if not updated[k]:
            out_lines.append(f'{k}="{values[k]}"\n')

    with open(ENV_PATH, "w") as f:
        f.writelines(out_lines)

    print(f"Updated {ENV_PATH} with SQS queue URLs from stack '{stack_name}'.")


if __name__ == "__main__":
    main()
