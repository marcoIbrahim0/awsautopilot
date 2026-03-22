#!/usr/bin/env python3
"""
Security Autopilot — S3 bucket encryption pre-state capture.

Run BEFORE terraform apply to snapshot the current bucket encryption so
rollback can restore the exact pre-remediation encryption after
terraform destroy.

Usage:
    python3 scripts/s3_encryption_capture.py

Optional overrides:
    BUCKET_NAME=my-bucket REGION=us-east-1 python3 scripts/s3_encryption_capture.py

Writes: .s3-encryption-rollback/encryption_snapshot.json
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SNAPSHOT_VERSION = 1
ROLLBACK_DIR = ".s3-encryption-rollback"
SNAPSHOT_FILE = "encryption_snapshot.json"
DEFAULT_BUCKET_NAME = 'security-autopilot-w6-strict-s315-exec-696505809372'
DEFAULT_REGION = 'eu-north-1'


def env_text(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    fallback = default.strip()
    if fallback:
        return fallback
    raise SystemExit(f"{{name}} is required")


def run_aws(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["aws", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "AWS CLI command failed"
        raise SystemExit(f"AWS CLI error: {message}")
    return result


def main() -> None:
    bucket_name = env_text("BUCKET_NAME", DEFAULT_BUCKET_NAME)
    region = env_text("REGION", DEFAULT_REGION)
    result = run_aws(
        "s3api",
        "get-bucket-encryption",
        "--bucket",
        bucket_name,
        "--region",
        region,
        "--output",
        "json",
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"

    encryption_exists = False
    encryption_configuration = None
    if result.returncode == 0:
        payload = json.loads(result.stdout or "{}")
        configuration = payload.get("ServerSideEncryptionConfiguration")
        if not isinstance(configuration, dict) and isinstance(payload.get("Rules"), list):
            configuration = payload
        if isinstance(configuration, dict):
            encryption_exists = True
            encryption_configuration = configuration
    elif "ServerSideEncryptionConfigurationNotFoundError" not in output:
        message = result.stderr.strip() or result.stdout.strip() or "get-bucket-encryption failed"
        raise SystemExit(f"AWS CLI error: {message}")

    rollback_dir = Path(ROLLBACK_DIR)
    rollback_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = rollback_dir / SNAPSHOT_FILE
    snapshot = {
        "version": SNAPSHOT_VERSION,
        "bucket_name": bucket_name,
        "region": region,
        "encryption_exists": encryption_exists,
        "encryption_configuration": encryption_configuration,
    }
    snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    if encryption_exists:
        print(f"Captured existing bucket encryption to {snapshot_path}")
    else:
        print(f"No existing bucket encryption found; captured empty pre-state to {snapshot_path}")


if __name__ == "__main__":
    main()
