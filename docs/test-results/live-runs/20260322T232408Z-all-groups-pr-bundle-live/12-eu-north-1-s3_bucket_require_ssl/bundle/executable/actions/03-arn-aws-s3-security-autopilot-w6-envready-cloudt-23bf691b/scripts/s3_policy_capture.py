#!/usr/bin/env python3
"""
Security Autopilot — S3 bucket policy pre-state capture.

Run BEFORE terraform apply to snapshot the current bucket policy so
rollback can restore the exact pre-remediation policy after
terraform destroy.

Usage:
    BUCKET_NAME=my-bucket REGION=us-east-1 python3 scripts/s3_policy_capture.py

Writes: .s3-rollback/policy_snapshot.json
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SNAPSHOT_VERSION = 1
ROLLBACK_DIR = ".s3-rollback"
SNAPSHOT_FILE = "policy_snapshot.json"


def env_text(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def run_aws(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["aws", *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "AWS CLI command failed"
        raise SystemExit(f"AWS CLI error: {message}")
    return result


def main() -> None:
    bucket_name = env_text("BUCKET_NAME")
    region = env_text("REGION")

    result = run_aws(
        "s3api",
        "get-bucket-policy",
        "--bucket",
        bucket_name,
        "--region",
        region,
        "--query",
        "Policy",
        "--output",
        "text",
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"

    policy_exists = False
    policy_json: str | None = None
    if result.returncode == 0:
        candidate = (result.stdout or "").strip()
        if candidate not in {"", "None", "null"}:
            json.loads(candidate)
            policy_exists = True
            policy_json = candidate
    elif "NoSuchBucketPolicy" not in output:
        message = result.stderr.strip() or result.stdout.strip() or "get-bucket-policy failed"
        raise SystemExit(f"AWS CLI error: {message}")

    rollback_dir = Path(ROLLBACK_DIR)
    rollback_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = rollback_dir / SNAPSHOT_FILE
    snapshot = {
        "version": SNAPSHOT_VERSION,
        "bucket_name": bucket_name,
        "region": region,
        "policy_exists": policy_exists,
        "policy_json": policy_json,
    }
    snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    if policy_exists:
        print(f"Captured existing bucket policy to {snapshot_path}")
    else:
        print(f"No existing bucket policy found; captured empty pre-state to {snapshot_path}")


if __name__ == "__main__":
    main()
