#!/usr/bin/env python3
"""
Security Autopilot — S3 bucket lifecycle rollback restore.

Run to restore the exact lifecycle state that existed before the
apply-time merge helper executed.

Usage:
    python3 rollback/s3_lifecycle_restore.py

Reads: .s3-lifecycle-rollback/lifecycle_snapshot.json
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROLLBACK_DIR = ".s3-lifecycle-rollback"
SNAPSHOT_FILE = "lifecycle_snapshot.json"


def run_aws(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["aws", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "AWS CLI command failed"
        raise SystemExit(f"AWS CLI error: {message}")
    return result


def main() -> None:
    snapshot_path = Path(ROLLBACK_DIR) / SNAPSHOT_FILE
    if not snapshot_path.exists():
        raise SystemExit(
            f"Snapshot not found at {snapshot_path}. "
            "Was s3_lifecycle_merge.py run before apply?"
        )

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    bucket_name = str(snapshot.get("bucket_name") or "").strip()
    region = str(snapshot.get("region") or "").strip()
    lifecycle_exists = bool(snapshot.get("lifecycle_exists"))
    lifecycle_document = snapshot.get("lifecycle_document")

    if not bucket_name or not region:
        raise SystemExit("Snapshot is missing bucket_name or region.")

    if lifecycle_exists:
        if not isinstance(lifecycle_document, dict):
            raise SystemExit(
                "Snapshot says lifecycle configuration existed, but lifecycle_document is missing."
            )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(lifecycle_document, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            lifecycle_path = Path(handle.name)
        try:
            run_aws(
                "s3api",
                "put-bucket-lifecycle-configuration",
                "--bucket",
                bucket_name,
                "--region",
                region,
                "--lifecycle-configuration",
                f"file://{lifecycle_path}",
            )
        finally:
            lifecycle_path.unlink(missing_ok=True)
        print(f"Restored lifecycle configuration for {bucket_name} from {snapshot_path}.")
        return

    result = run_aws(
        "s3api",
        "delete-bucket-lifecycle",
        "--bucket",
        bucket_name,
        "--region",
        region,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0 or "NoSuchLifecycleConfiguration" in output:
        print(
            f"Original lifecycle configuration was absent; ensured {bucket_name} has no lifecycle configuration."
        )
        return

    message = result.stderr.strip() or result.stdout.strip() or "delete-bucket-lifecycle failed"
    raise SystemExit(f"AWS CLI error: {message}")


if __name__ == "__main__":
    main()
