#!/usr/bin/env python3
"""
Fetch SQS queue URLs from the security-autopilot-sqs CloudFormation stack
and set key worker queue URLs in .env.

Run from project root. Idempotent: updates existing vars or appends if missing.
"""
from __future__ import annotations

import os
import re
import sys

import boto3

STACK_NAME = "security-autopilot-sqs"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
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


def main() -> None:
    cf = boto3.client("cloudformation")
    try:
        out = cf.describe_stacks(StackName=STACK_NAME)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    stacks = out.get("Stacks") or []
    if not stacks:
        print(f"Stack {STACK_NAME} not found.", file=sys.stderr)
        sys.exit(1)

    outputs = {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs") or []}
    missing = [k for k in OUTPUT_KEYS if k not in outputs]
    if missing:
        print(f"Missing outputs: {missing}", file=sys.stderr)
        sys.exit(1)

    values = {
        KEYS[index]: outputs[OUTPUT_KEYS[index]]
        for index in range(len(KEYS))
    }

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

    print("Updated .env with SQS queue URLs from stack outputs.")


if __name__ == "__main__":
    main()
