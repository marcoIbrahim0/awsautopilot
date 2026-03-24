#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_REGION = 'us-east-1'

def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise SystemExit(f"{' '.join(args)}: {message}")
    return result


def run_json(args: list[str]) -> dict[str, Any]:
    result = run_command(args)
    return json.loads(result.stdout or "{}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def bucket_exists(bucket: str, region: str) -> bool:
    result = run_command(
        ["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region],
        check=False,
    )
    return result.returncode == 0


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_payload(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value if item is not None]
    return value


def put_structured_payload(option: str, payload: dict[str, Any], *, region: str) -> None:
    cleaned = sanitize_payload(payload)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        json.dump(cleaned, handle, sort_keys=True, separators=(",", ":"))
        payload_path = Path(handle.name)
    try:
        run_command(
            [
                "aws",
                "configservice",
                option,
                "--region",
                region,
                f"--{option.replace('put-', '')}",
                f"file://{payload_path}",
            ]
        )
    finally:
        payload_path.unlink(missing_ok=True)


def put_bucket_policy(bucket: str, region: str, policy: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        json.dump(policy, handle, sort_keys=True, separators=(",", ":"))
        policy_path = Path(handle.name)
    try:
        run_command(
            [
                "aws",
                "s3api",
                "put-bucket-policy",
                "--bucket",
                bucket,
                "--region",
                region,
                "--policy",
                f"file://{policy_path}",
            ]
        )
    finally:
        policy_path.unlink(missing_ok=True)


def delete_bucket_policy(bucket: str, region: str) -> None:
    result = run_command(
        ["aws", "s3api", "delete-bucket-policy", "--bucket", bucket, "--region", region],
        check=False,
    )
    if result.returncode != 0:
        output = f"{result.stdout}\n{result.stderr}"
        if "NoSuchBucketPolicy" not in output and "NoSuchBucket" not in output:
            message = result.stderr.strip() or result.stdout.strip() or "delete-bucket-policy failed"
            raise SystemExit(message)


def ensure_singletons(payload: dict[str, Any], key: str, description: str) -> list[dict[str, Any]]:
    items = list(payload.get(key) or [])
    if len(items) > 1:
        raise SystemExit(f"Exact AWS Config rollback is unsupported when multiple {description} exist.")
    return items


def current_config_state(region: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    recorders = ensure_singletons(
        run_json(["aws", "configservice", "describe-configuration-recorders", "--region", region, "--output", "json"]),
        "ConfigurationRecorders",
        "configuration recorders",
    )
    deliveries = ensure_singletons(
        run_json(["aws", "configservice", "describe-delivery-channels", "--region", region, "--output", "json"]),
        "DeliveryChannels",
        "delivery channels",
    )
    return recorders, deliveries


def bucket_is_empty(bucket: str, region: str) -> bool:
    current = run_json(
        ["aws", "s3api", "list-objects-v2", "--bucket", bucket, "--region", region, "--max-items", "1", "--output", "json"]
    )
    if current.get("Contents"):
        return False
    versions = run_json(
        ["aws", "s3api", "list-object-versions", "--bucket", bucket, "--region", region, "--max-items", "1", "--output", "json"]
    )
    return not versions.get("Versions") and not versions.get("DeleteMarkers")


def allowed_name(current_name: str, expected_names: set[str]) -> bool:
    return not current_name or current_name in expected_names

def main() -> int:
    region = os.environ.get("REGION", "").strip() or DEFAULT_REGION.strip()
    if not region:
        raise SystemExit("REGION is required")
    rollback_dir = Path(os.environ.get("ROLLBACK_DIR") or ".aws-config-rollback")
    snapshot_dir = rollback_dir / "snapshot"
    ready_path = snapshot_dir / ".snapshot-ready"
    if not ready_path.exists():
        raise SystemExit("No AWS Config rollback snapshot exists for this bundle.")

    summary = load_json(snapshot_dir / "pre_state_summary.json")
    bucket_state = load_json(snapshot_dir / "pre_target_bucket_state.json")
    apply_context = load_json(rollback_dir / "apply_context.json")
    pre_recorders = ensure_singletons(
        load_json(snapshot_dir / "pre_configuration_recorders.json"),
        "ConfigurationRecorders",
        "configuration recorders",
    )
    pre_deliveries = ensure_singletons(
        load_json(snapshot_dir / "pre_delivery_channels.json"),
        "DeliveryChannels",
        "delivery channels",
    )
    current_recorders, current_deliveries = current_config_state(region)
    pre_recorder = pre_recorders[0] if pre_recorders else None
    pre_delivery = pre_deliveries[0] if pre_deliveries else None
    expected_recorder_names = {
        str(name).strip()
        for name in [
            summary.get("recorder_name"),
            apply_context.get("applied_recorder_name"),
        ]
        if str(name).strip()
    }
    expected_delivery_names = {
        str(name).strip()
        for name in [
            summary.get("delivery_channel_name"),
            apply_context.get("applied_delivery_channel_name"),
        ]
        if str(name).strip()
    }

    current_recorder_name = str((current_recorders[0] if current_recorders else {}).get("name") or "")
    current_delivery_name = str((current_deliveries[0] if current_deliveries else {}).get("name") or "")
    if current_recorders and not allowed_name(current_recorder_name, expected_recorder_names):
        raise SystemExit(
            "Current AWS Config recorder does not match the bundle's recorded mutation target; "
            "exact rollback is not guaranteed."
        )
    if current_deliveries and not allowed_name(current_delivery_name, expected_delivery_names):
        raise SystemExit(
            "Current AWS Config delivery channel does not match the bundle's recorded mutation target; "
            "exact rollback is not guaranteed."
        )

    if current_recorder_name:
        run_command(
            [
                "aws",
                "configservice",
                "stop-configuration-recorder",
                "--region",
                region,
                "--configuration-recorder-name",
                current_recorder_name,
            ],
            check=False,
        )

    if pre_recorder is not None:
        put_structured_payload("put-configuration-recorder", pre_recorder, region=region)

    if pre_delivery is not None:
        put_structured_payload("put-delivery-channel", pre_delivery, region=region)
    elif current_delivery_name:
        run_command(
            [
                "aws",
                "configservice",
                "delete-delivery-channel",
                "--region",
                region,
                "--delivery-channel-name",
                current_delivery_name,
            ]
        )

    if pre_recorder is not None:
        pre_recorder_name = str(pre_recorder.get("name") or "")
        if bool(summary.get("recording_before")):
            run_command(
                [
                    "aws",
                    "configservice",
                    "start-configuration-recorder",
                    "--region",
                    region,
                    "--configuration-recorder-name",
                    pre_recorder_name,
                ]
            )
        else:
            run_command(
                [
                    "aws",
                    "configservice",
                    "stop-configuration-recorder",
                    "--region",
                    region,
                    "--configuration-recorder-name",
                    pre_recorder_name,
                ],
                check=False,
            )
    elif current_recorder_name:
        run_command(
            [
                "aws",
                "configservice",
                "delete-configuration-recorder",
                "--region",
                region,
                "--configuration-recorder-name",
                current_recorder_name,
            ]
        )

    target_bucket_name = str(bucket_state.get("bucket_name") or "")
    if bool(bucket_state.get("bucket_existed_before")):
        if not bucket_exists(target_bucket_name, region):
            raise SystemExit(
                f"Original AWS Config delivery bucket '{target_bucket_name}' is now unreachable; "
                "exact rollback is not guaranteed."
            )
        original_policy = bucket_state.get("policy_json")
        if isinstance(original_policy, dict):
            put_bucket_policy(target_bucket_name, region, original_policy)
        else:
            delete_bucket_policy(target_bucket_name, region)
    elif bucket_exists(target_bucket_name, region):
        if not bool(apply_context.get("target_bucket_created_by_apply")):
            raise SystemExit(
                "Rollback cannot prove that the target bucket was created by this bundle; "
                "exact cleanup is not guaranteed."
            )
        if not bucket_is_empty(target_bucket_name, region):
            raise SystemExit(
                f"Rollback would need to delete non-empty bucket '{target_bucket_name}'. "
                "Exact restoration is not guaranteed."
            )
        delete_bucket_policy(target_bucket_name, region)
        run_command(["aws", "s3api", "delete-bucket", "--bucket", target_bucket_name, "--region", region])

    receipt = {
        "restored": True,
        "target_bucket_name": target_bucket_name,
        "recorder_name": "" if pre_recorder is None else str(pre_recorder.get("name") or ""),
        "delivery_channel_name": "" if pre_delivery is None else str(pre_delivery.get("name") or ""),
    }
    (rollback_dir / "rollback_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
