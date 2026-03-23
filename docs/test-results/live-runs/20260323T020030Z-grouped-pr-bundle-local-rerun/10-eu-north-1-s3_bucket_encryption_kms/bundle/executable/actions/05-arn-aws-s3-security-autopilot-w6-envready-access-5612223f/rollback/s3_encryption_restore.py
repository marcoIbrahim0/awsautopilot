#!/usr/bin/env python3
"""
Security Autopilot — S3 bucket encryption rollback restore.

Run AFTER terraform destroy to restore the exact bucket encryption state
that was captured before apply.

Usage:
    python3 rollback/s3_encryption_restore.py

Reads: .s3-encryption-rollback/encryption_snapshot.json
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROLLBACK_DIR = ".s3-encryption-rollback"
SNAPSHOT_FILE = "encryption_snapshot.json"


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
            "Was s3_encryption_capture.py run before apply?"
        )

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    bucket_name = str(snapshot.get("bucket_name") or "").strip()
    region = str(snapshot.get("region") or "").strip()
    encryption_exists = bool(snapshot.get("encryption_exists"))
    configuration = snapshot.get("encryption_configuration")

    if not bucket_name or not region:
        raise SystemExit("Snapshot is missing bucket_name or region.")

    if encryption_exists:
        if not isinstance(configuration, dict) or not configuration:
            raise SystemExit(
                "Snapshot says bucket encryption existed, but encryption_configuration is missing."
            )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(configuration, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            config_path = Path(handle.name)
        try:
            run_aws(
                "s3api",
                "put-bucket-encryption",
                "--bucket",
                bucket_name,
                "--region",
                region,
                "--server-side-encryption-configuration",
                f"file://{config_path}",
            )
        finally:
            config_path.unlink(missing_ok=True)
        print(f"Restored bucket encryption for {bucket_name} from {snapshot_path}.")
        return

    result = run_aws(
        "s3api",
        "delete-bucket-encryption",
        "--bucket",
        bucket_name,
        "--region",
        region,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0 or "ServerSideEncryptionConfigurationNotFoundError" in output:
        print(
            f"Original bucket encryption was absent; ensured {bucket_name} has no default encryption."
        )
        return

    message = result.stderr.strip() or result.stdout.strip() or "delete-bucket-encryption failed"
    raise SystemExit(f"AWS CLI error: {message}")


if __name__ == "__main__":
    main()
