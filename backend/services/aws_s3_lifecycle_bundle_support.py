"""Support helpers for S3.11 executable apply-time lifecycle bundles."""
from __future__ import annotations

from textwrap import dedent
from typing import Any

AWS_S3_LIFECYCLE_APPLY_SCRIPT_PATH = "scripts/s3_lifecycle_merge.py"
AWS_S3_LIFECYCLE_ROLLBACK_DIR = ".s3-lifecycle-rollback"
AWS_S3_LIFECYCLE_RESTORE_SCRIPT_PATH = "rollback/s3_lifecycle_restore.py"


def aws_s3_lifecycle_bundle_rollback_metadata(action_id: str) -> dict[str, Any]:
    """Return rollback metadata for bundle-local S3 lifecycle restoration."""
    return {
        "bundle_rollback_entries": {
            action_id: {
                "path": AWS_S3_LIFECYCLE_RESTORE_SCRIPT_PATH,
                "runner": "python3",
            }
        }
    }


def aws_s3_lifecycle_merge_script_content(*, bucket_name: str, region: str, abort_days: int) -> str:
    """Return the apply-time lifecycle merge helper for S3.11 bundles."""
    template = dedent(
        """\
        #!/usr/bin/env python3
        \"\"\"
        Security Autopilot — S3 bucket lifecycle apply-time merge.

        Run via terraform apply to fetch the current lifecycle configuration,
        preserve existing non-managed rules, and enforce the managed abort rule.

        Usage:
            python3 scripts/s3_lifecycle_merge.py

        Optional overrides:
            BUCKET_NAME=my-bucket REGION=us-east-1 ABORT_INCOMPLETE_MULTIPART_DAYS=7 python3 scripts/s3_lifecycle_merge.py

        Writes: .s3-lifecycle-rollback/lifecycle_snapshot.json
        \"\"\"
        from __future__ import annotations

        import json
        import os
        import subprocess
        from pathlib import Path

        SNAPSHOT_VERSION = 1
        ROLLBACK_DIR = ".s3-lifecycle-rollback"
        SNAPSHOT_FILE = "lifecycle_snapshot.json"
        MANAGED_RULE_ID = "security-autopilot-abort-incomplete-multipart"
        DEFAULT_BUCKET_NAME = <<DEFAULT_BUCKET_NAME>>
        DEFAULT_REGION = <<DEFAULT_REGION>>
        DEFAULT_ABORT_DAYS = <<DEFAULT_ABORT_DAYS>>


        def env_text(name: str, default: str) -> str:
            value = os.environ.get(name, "").strip()
            if value:
                return value
            fallback = default.strip()
            if fallback:
                return fallback
            raise SystemExit(f"{name} is required")


        def env_int(name: str, default: int) -> int:
            value = os.environ.get(name, "").strip()
            if not value:
                return default
            try:
                parsed = int(value)
            except ValueError as exc:
                raise SystemExit(f"{name} must be an integer.") from exc
            if parsed <= 0:
                raise SystemExit(f"{name} must be greater than zero.")
            return parsed


        def run_aws(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
            result = subprocess.run(["aws", *args], capture_output=True, text=True)
            if check and result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip() or "AWS CLI command failed"
                raise SystemExit(f"AWS CLI error: {message}")
            return result


        def is_equivalent_abort_rule(rule: object, abort_days: int) -> bool:
            if not isinstance(rule, dict):
                return False
            if str(rule.get("Status") or "").strip().lower() != "enabled":
                return False
            if any(
                rule.get(field)
                for field in (
                    "Expiration",
                    "Transitions",
                    "NoncurrentVersionExpiration",
                    "NoncurrentVersionTransitions",
                )
            ):
                return False
            abort_block = rule.get("AbortIncompleteMultipartUpload")
            if not isinstance(abort_block, dict):
                return False
            try:
                days = int(abort_block.get("DaysAfterInitiation"))
            except (TypeError, ValueError):
                return False
            if days != abort_days:
                return False
            if rule.get("Prefix") not in (None, ""):
                return False
            filter_value = rule.get("Filter")
            if filter_value is None:
                return True
            if not isinstance(filter_value, dict):
                return False
            if not filter_value:
                return True
            return filter_value.get("Prefix") == "" and len(filter_value) == 1


        def managed_abort_rule(abort_days: int) -> dict[str, object]:
            return {
                "ID": MANAGED_RULE_ID,
                "Status": "Enabled",
                "Filter": {},
                "AbortIncompleteMultipartUpload": {
                    "DaysAfterInitiation": abort_days,
                },
            }


        def lifecycle_state(bucket_name: str, region: str) -> tuple[bool, dict[str, object]]:
            result = run_aws(
                "s3api",
                "get-bucket-lifecycle-configuration",
                "--bucket",
                bucket_name,
                "--region",
                region,
                "--output",
                "json",
                check=False,
            )
            output = f"{result.stdout}\\n{result.stderr}"
            if result.returncode == 0:
                payload = json.loads(result.stdout or "{}")
                rules = payload.get("Rules")
                if rules is None:
                    payload["Rules"] = []
                elif not isinstance(rules, list):
                    raise SystemExit("AWS CLI returned a lifecycle document without a valid Rules list.")
                return True, payload
            if "NoSuchLifecycleConfiguration" in output:
                return False, {"Rules": []}
            message = result.stderr.strip() or result.stdout.strip() or "get-bucket-lifecycle-configuration failed"
            raise SystemExit(f"AWS CLI error: {message}")


        def write_snapshot_once(
            *,
            bucket_name: str,
            region: str,
            lifecycle_exists: bool,
            lifecycle_document: dict[str, object] | None,
        ) -> Path:
            rollback_dir = Path(ROLLBACK_DIR)
            rollback_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = rollback_dir / SNAPSHOT_FILE
            if snapshot_path.exists():
                existing = json.loads(snapshot_path.read_text(encoding="utf-8"))
                existing_bucket = str(existing.get("bucket_name") or "").strip()
                existing_region = str(existing.get("region") or "").strip()
                if existing_bucket != bucket_name or existing_region != region:
                    raise SystemExit(
                        f"Snapshot at {snapshot_path} belongs to {existing_bucket or '<unknown>'}/{existing_region or '<unknown>'}, "
                        f"not {bucket_name}/{region}."
                    )
                return snapshot_path

            snapshot = {
                "version": SNAPSHOT_VERSION,
                "bucket_name": bucket_name,
                "region": region,
                "lifecycle_exists": lifecycle_exists,
                "lifecycle_document": lifecycle_document,
            }
            snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\\n", encoding="utf-8")
            return snapshot_path


        def main() -> None:
            bucket_name = env_text("BUCKET_NAME", DEFAULT_BUCKET_NAME)
            region = env_text("REGION", DEFAULT_REGION)
            abort_days = env_int("ABORT_INCOMPLETE_MULTIPART_DAYS", DEFAULT_ABORT_DAYS)

            lifecycle_exists, lifecycle_document = lifecycle_state(bucket_name, region)
            snapshot_path = write_snapshot_once(
                bucket_name=bucket_name,
                region=region,
                lifecycle_exists=lifecycle_exists,
                lifecycle_document=lifecycle_document if lifecycle_exists else None,
            )

            existing_rules = lifecycle_document.get("Rules", [])
            if not isinstance(existing_rules, list):
                raise SystemExit("Lifecycle Rules must be a list.")

            merged_rules = [
                rule
                for rule in existing_rules
                if not is_equivalent_abort_rule(rule, abort_days)
            ]
            merged_rules.append(managed_abort_rule(abort_days))

            payload = {"Rules": merged_rules}
            run_aws(
                "s3api",
                "put-bucket-lifecycle-configuration",
                "--bucket",
                bucket_name,
                "--region",
                region,
                "--lifecycle-configuration",
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )
            print(
                f"Merged lifecycle configuration for {bucket_name}. "
                f"Rollback snapshot retained at {snapshot_path}."
            )


        if __name__ == "__main__":
            main()
        """
    )
    return (
        template.replace("<<DEFAULT_BUCKET_NAME>>", repr(bucket_name))
        .replace("<<DEFAULT_REGION>>", repr(region))
        .replace("<<DEFAULT_ABORT_DAYS>>", str(abort_days))
    )


def aws_s3_lifecycle_restore_script_content() -> str:
    """Return the rollback helper that restores captured S3 lifecycle state."""
    return dedent(
        """\
        #!/usr/bin/env python3
        \"\"\"
        Security Autopilot — S3 bucket lifecycle rollback restore.

        Run to restore the exact lifecycle state that existed before the
        apply-time merge helper executed.

        Usage:
            python3 rollback/s3_lifecycle_restore.py

        Reads: .s3-lifecycle-rollback/lifecycle_snapshot.json
        \"\"\"
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
            output = f"{result.stdout}\\n{result.stderr}"
            if result.returncode == 0 or "NoSuchLifecycleConfiguration" in output:
                print(
                    f"Original lifecycle configuration was absent; ensured {bucket_name} has no lifecycle configuration."
                )
                return

            message = result.stderr.strip() or result.stdout.strip() or "delete-bucket-lifecycle failed"
            raise SystemExit(f"AWS CLI error: {message}")


        if __name__ == "__main__":
            main()
        """
    )
