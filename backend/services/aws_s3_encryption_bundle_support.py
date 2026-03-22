"""Support helpers for S3.15 executable PR bundles."""
from __future__ import annotations

from textwrap import dedent
from typing import Any

AWS_S3_ENCRYPTION_CAPTURE_SCRIPT_PATH = "scripts/s3_encryption_capture.py"
AWS_S3_ENCRYPTION_ROLLBACK_DIR = ".s3-encryption-rollback"
AWS_S3_ENCRYPTION_RESTORE_SCRIPT_PATH = "rollback/s3_encryption_restore.py"


def aws_s3_encryption_bundle_rollback_metadata(action_id: str) -> dict[str, Any]:
    """Return rollback metadata for bundle-local S3 encryption restoration."""
    return {
        "bundle_rollback_entries": {
            action_id: {
                "path": AWS_S3_ENCRYPTION_RESTORE_SCRIPT_PATH,
                "runner": "python3",
            }
        }
    }


def aws_s3_encryption_capture_script_content(*, bucket_name: str, region: str) -> str:
    """Return the pre-state capture helper run before terraform apply for S3.15 bundles."""
    template = dedent(
        """\
        #!/usr/bin/env python3
        \"\"\"
        Security Autopilot — S3 bucket encryption pre-state capture.

        Run BEFORE terraform apply to snapshot the current bucket encryption so
        rollback can restore the exact pre-remediation encryption after
        terraform destroy.

        Usage:
            python3 scripts/s3_encryption_capture.py

        Optional overrides:
            BUCKET_NAME=my-bucket REGION=us-east-1 python3 scripts/s3_encryption_capture.py

        Writes: .s3-encryption-rollback/encryption_snapshot.json
        \"\"\"
        from __future__ import annotations

        import json
        import os
        import subprocess
        from pathlib import Path

        SNAPSHOT_VERSION = 1
        ROLLBACK_DIR = ".s3-encryption-rollback"
        SNAPSHOT_FILE = "encryption_snapshot.json"
        DEFAULT_BUCKET_NAME = <<DEFAULT_BUCKET_NAME>>
        DEFAULT_REGION = <<DEFAULT_REGION>>


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
            output = f"{result.stdout}\\n{result.stderr}"

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
            snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\\n", encoding="utf-8")
            if encryption_exists:
                print(f"Captured existing bucket encryption to {snapshot_path}")
            else:
                print(f"No existing bucket encryption found; captured empty pre-state to {snapshot_path}")


        if __name__ == "__main__":
            main()
        """
    )
    return template.replace("<<DEFAULT_BUCKET_NAME>>", repr(bucket_name)).replace(
        "<<DEFAULT_REGION>>",
        repr(region),
    )


def aws_s3_encryption_restore_script_content() -> str:
    """Return the rollback helper that restores captured S3 bucket encryption state."""
    return dedent(
        """\
        #!/usr/bin/env python3
        \"\"\"
        Security Autopilot — S3 bucket encryption rollback restore.

        Run AFTER terraform destroy to restore the exact bucket encryption state
        that was captured before apply.

        Usage:
            python3 rollback/s3_encryption_restore.py

        Reads: .s3-encryption-rollback/encryption_snapshot.json
        \"\"\"
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
            output = f"{result.stdout}\\n{result.stderr}"
            if result.returncode == 0 or "ServerSideEncryptionConfigurationNotFoundError" in output:
                print(
                    f"Original bucket encryption was absent; ensured {bucket_name} has no default encryption."
                )
                return

            message = result.stderr.strip() or result.stdout.strip() or "delete-bucket-encryption failed"
            raise SystemExit(f"AWS CLI error: {message}")


        if __name__ == "__main__":
            main()
        """
    )
