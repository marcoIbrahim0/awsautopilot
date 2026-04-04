#!/usr/bin/env python3
"""
Security Autopilot — S3 bucket policy rollback restore.

Run AFTER terraform destroy to restore the exact bucket policy state that
was captured before apply.

Usage:
    python3 rollback/s3_policy_restore.py

Reads: .s3-rollback/policy_snapshot.json
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROLLBACK_DIR = ".s3-rollback"
SNAPSHOT_FILE = "policy_snapshot.json"


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
    snapshot_path = Path(ROLLBACK_DIR) / SNAPSHOT_FILE
    if not snapshot_path.exists():
        raise SystemExit(
            f"Snapshot not found at {snapshot_path}. "
            "Was s3_policy_capture.py run before apply?"
        )

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    bucket_name = str(snapshot.get("bucket_name") or "").strip()
    region = str(snapshot.get("region") or "").strip()
    policy_exists = bool(snapshot.get("policy_exists"))
    policy_json = snapshot.get("policy_json")

    if not bucket_name or not region:
        raise SystemExit("Snapshot is missing bucket_name or region.")

    if policy_exists:
        if not isinstance(policy_json, str) or not policy_json.strip():
            raise SystemExit("Snapshot says a policy existed, but policy_json is missing.")
        json.loads(policy_json)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(policy_json)
            handle.flush()
            policy_path = Path(handle.name)
        try:
            run_aws(
                "s3api",
                "put-bucket-policy",
                "--bucket",
                bucket_name,
                "--region",
                region,
                "--policy",
                f"file://{policy_path}",
            )
        finally:
            policy_path.unlink(missing_ok=True)
        print(f"Restored bucket policy for {bucket_name} from {snapshot_path}.")
        return

    result = run_aws(
        "s3api",
        "delete-bucket-policy",
        "--bucket",
        bucket_name,
        "--region",
        region,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0 or "NoSuchBucketPolicy" in output:
        print(f"Original bucket policy was absent; ensured {bucket_name} has no bucket policy.")
        return

    message = result.stderr.strip() or result.stdout.strip() or "delete-bucket-policy failed"
    raise SystemExit(f"AWS CLI error: {message}")


if __name__ == "__main__":
    main()
