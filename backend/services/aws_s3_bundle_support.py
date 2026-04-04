"""Support helpers for S3.5 executable PR bundles."""
from __future__ import annotations

from textwrap import dedent
from typing import Any

AWS_S3_POLICY_CAPTURE_SCRIPT_PATH = "scripts/s3_policy_capture.py"
AWS_S3_POLICY_FETCH_SCRIPT_PATH = "scripts/s3_policy_fetch.py"
AWS_S3_POLICY_ROLLBACK_DIR = ".s3-rollback"
AWS_S3_POLICY_RESTORE_SCRIPT_PATH = "rollback/s3_policy_restore.py"


def aws_s3_bundle_rollback_metadata(action_id: str) -> dict[str, Any]:
    """Return rollback metadata for bundle-local S3 bucket policy restoration."""
    return {
        "bundle_rollback_entries": {
            action_id: {
                "path": AWS_S3_POLICY_RESTORE_SCRIPT_PATH,
                "runner": "python3",
            }
        }
    }


def aws_s3_policy_capture_script_content() -> str:
    """Return the pre-state capture helper run before terraform apply for S3.5 bundles."""
    return dedent(
        """\
        #!/usr/bin/env python3
        \"\"\"
        Security Autopilot — S3 bucket policy pre-state capture.

        Run BEFORE terraform apply to snapshot the current bucket policy so
        rollback can restore the exact pre-remediation policy after
        terraform destroy.

        Usage:
            BUCKET_NAME=my-bucket REGION=us-east-1 python3 scripts/s3_policy_capture.py

        Writes: .s3-rollback/policy_snapshot.json
        \"\"\"
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
            output = f"{result.stdout}\\n{result.stderr}"

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
            snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\\n", encoding="utf-8")
            if policy_exists:
                print(f"Captured existing bucket policy to {snapshot_path}")
            else:
                print(f"No existing bucket policy found; captured empty pre-state to {snapshot_path}")


        if __name__ == "__main__":
            main()
        """
    )


def aws_s3_policy_fetch_script_content() -> str:
    """Return the apply-time fetch helper for S3.5 policy merge bundles."""
    return dedent(
        """\
        #!/usr/bin/env python3
        \"\"\"
        Security Autopilot — S3 bucket policy fetch helper for Terraform external data.
        \"\"\"
        from __future__ import annotations

        import json
        import subprocess
        import sys


        def fail(message: str) -> None:
            raise SystemExit(message)


        def read_query() -> tuple[str, str]:
            query = json.load(sys.stdin)
            bucket_name = str(query.get("bucket_name") or "").strip()
            region = str(query.get("region") or "").strip()
            if not bucket_name or not region:
                fail("bucket_name and region are required")
            return bucket_name, region


        def run_aws(bucket_name: str, region: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    "aws",
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
                ],
                capture_output=True,
                text=True,
            )


        def main() -> None:
            bucket_name, region = read_query()
            result = run_aws(bucket_name, region)
            output = f"{result.stdout}\\n{result.stderr}"
            if result.returncode == 0:
                policy_json = (result.stdout or "").strip()
                if policy_json in {"", "None", "null"}:
                    policy_json = '{"Version":"2012-10-17","Statement":[]}'
                json.loads(policy_json)
                print(json.dumps({"policy_json": policy_json}))
                return
            if "NoSuchBucketPolicy" in output:
                print(json.dumps({"policy_json": '{"Version":"2012-10-17","Statement":[]}' }))
                return
            if "NoSuchBucket" in output or "Not Found" in output:
                fail(f"Target bucket '{bucket_name}' no longer exists.")
            message = result.stderr.strip() or result.stdout.strip() or "get-bucket-policy failed"
            fail(f"AWS CLI error: {message}")


        if __name__ == "__main__":
            main()
        """
    )


def aws_s3_policy_restore_script_content() -> str:
    """Return the rollback helper that restores captured S3 bucket policy state."""
    return dedent(
        """\
        #!/usr/bin/env python3
        \"\"\"
        Security Autopilot — S3 bucket policy rollback restore.

        Run AFTER terraform destroy to restore the exact bucket policy state that
        was captured before apply.

        Usage:
            python3 rollback/s3_policy_restore.py

        Reads: .s3-rollback/policy_snapshot.json
        \"\"\"
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
            output = f"{result.stdout}\\n{result.stderr}"
            if result.returncode == 0 or "NoSuchBucketPolicy" in output:
                print(f"Original bucket policy was absent; ensured {bucket_name} has no bucket policy.")
                return

            message = result.stderr.strip() or result.stdout.strip() or "delete-bucket-policy failed"
            raise SystemExit(f"AWS CLI error: {message}")


        if __name__ == "__main__":
            main()
        """
    )
