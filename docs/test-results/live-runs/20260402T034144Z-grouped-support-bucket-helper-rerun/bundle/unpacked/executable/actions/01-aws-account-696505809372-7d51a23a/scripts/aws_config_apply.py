#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SNAPSHOT_VERSION = 1
DEFAULT_REGION = 'eu-north-1'
DEFAULT_BUCKET = 'security-autopilot-config-696505809372-eu-north-1'
DEFAULT_ROLE_ARN = 'arn:aws:iam::696505809372:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig'
DEFAULT_KMS_ARN = ''
DEFAULT_ACCOUNT_ID = '696505809372'
DEFAULT_CREATE_LOCAL_BUCKET = True
DEFAULT_OVERWRITE_RECORDING_GROUP = False

def env_text(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    fallback = default.strip()
    if fallback:
        return fallback
    raise SystemExit(f"{name} is required")


def env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name, "").strip().lower()
    if not raw_value:
        return default
    if raw_value not in {"true", "false"}:
        raise SystemExit(f"{name} must be 'true' or 'false'")
    return raw_value == "true"


def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise SystemExit(f"{' '.join(args)}: {message}")
    return result


def run_json(args: list[str]) -> dict[str, Any]:
    result = run_command(args)
    return json.loads(result.stdout or "{}")


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        dir=path.parent,
        encoding="utf-8",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def bucket_exists(bucket: str, region: str) -> bool:
    result = run_command(
        ["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region],
        check=False,
    )
    return result.returncode == 0


def create_bucket(bucket: str, region: str, *, object_lock_enabled: bool = False) -> None:
    args = ["aws", "s3api", "create-bucket", "--bucket", bucket, "--region", region]
    if region != "us-east-1":
        args.extend(
            [
                "--create-bucket-configuration",
                f"LocationConstraint={region}",
            ]
        )
    if object_lock_enabled:
        args.append("--object-lock-enabled-for-bucket")
    run_command(args)


def get_bucket_policy_json(bucket: str, region: str) -> dict[str, Any] | None:
    result = run_command(
        [
            "aws",
            "s3api",
            "get-bucket-policy",
            "--bucket",
            bucket,
            "--region",
            region,
            "--query",
            "Policy",
            "--output",
            "text",
        ],
        check=False,
    )
    if result.returncode != 0:
        output = f"{result.stdout}\n{result.stderr}"
        if "NoSuchBucketPolicy" in output or "NoSuchBucket" in output:
            return None
        message = result.stderr.strip() or result.stdout.strip() or "get-bucket-policy failed"
        raise SystemExit(message)
    text = (result.stdout or "").strip()
    if text in {"", "None", "null"}:
        return None
    return json.loads(text)


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


def build_required_bucket_policy(bucket: str, account_id: str) -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AWSConfigBucketPermissionsCheck",
                "Effect": "Allow",
                "Principal": {"Service": "config.amazonaws.com"},
                "Action": "s3:GetBucketAcl",
                "Resource": f"arn:aws:s3:::{bucket}",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceAccount": account_id,
                    }
                },
            },
            {
                "Sid": "AWSConfigBucketExistenceCheck",
                "Effect": "Allow",
                "Principal": {"Service": "config.amazonaws.com"},
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::{bucket}",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceAccount": account_id,
                    }
                },
            },
            {
                "Sid": "AWSConfigBucketDelivery",
                "Effect": "Allow",
                "Principal": {"Service": "config.amazonaws.com"},
                "Action": "s3:PutObject",
                "Resource": f"arn:aws:s3:::{bucket}/AWSLogs/{account_id}/Config/*",
                "Condition": {
                    "StringEquals": {
                        "s3:x-amz-acl": "bucket-owner-full-control",
                        "AWS:SourceAccount": account_id,
                    }
                },
            },
        ],
    }


def statement_key(statement: dict[str, Any]) -> tuple[str, str]:
    sid = statement.get("Sid")
    if isinstance(sid, str) and sid.strip():
        return ("sid", sid.strip())
    return ("json", json.dumps(statement, sort_keys=True, separators=(",", ":")))


def merge_bucket_policies(
    existing: dict[str, Any] | None,
    required: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for statement in (existing or {}).get("Statement", []):
        if isinstance(statement, dict):
            merged[statement_key(statement)] = statement
    for statement in required.get("Statement", []):
        if isinstance(statement, dict):
            merged[statement_key(statement)] = statement
    version = (existing or {}).get("Version") or "2012-10-17"
    return {"Version": version, "Statement": list(merged.values())}

def apply_support_bucket_baseline(bucket: str, region: str, helper_bucket_role: str | None = None) -> None:
    """Apply the canonical support-bucket baseline via AWS CLI (idempotent).

    Applies in order: public-access block → SSE-KMS → lifecycle
    → helper-bucket tags → SSL-only policy merged with any existing statements.
    """
    import json as _json
    import subprocess
    import tempfile
    from pathlib import Path

    def _run(args: list) -> None:
        r = subprocess.run(args, text=True, capture_output=True)
        if r.returncode != 0:
            raise SystemExit(f"{' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")

    # 1. Public-access block
    _run([
        "aws", "s3api", "put-public-access-block",
        "--bucket", bucket, "--region", region,
        "--public-access-block-configuration",
        "BlockPublicAcls=true,IgnorePublicAcls=true,"
        "BlockPublicPolicy=true,RestrictPublicBuckets=true",
    ])

    # 2. SSE-KMS with AWS-managed S3 key (alias/aws/s3 avoids S3.15 drift)
    sse = _json.dumps({
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "aws:kms",
                "KMSMasterKeyID": "alias/aws/s3",
            },
            "BucketKeyEnabled": True,
        }]
    })
    _run([
        "aws", "s3api", "put-bucket-encryption",
        "--bucket", bucket, "--region", region,
        "--server-side-encryption-configuration", sse,
    ])

    # 3. Lifecycle: abort-incomplete-multipart (7 days)
    # NOTE: this replaces any existing lifecycle configuration.
    # Callers that need to preserve existing rules must read + merge first.
    lc = _json.dumps({
        "Rules": [{
            "ID": "abort-incomplete-multipart",
            "Status": "Enabled",
            "Filter": {},
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
        }]
    })
    _run([
        "aws", "s3api", "put-bucket-lifecycle-configuration",
        "--bucket", bucket, "--region", region,
        "--lifecycle-configuration", lc,
    ])

    # 4. Role-specific baseline extensions
    if helper_bucket_role in ("cloudtrail-logs", "aws-config-delivery"):
        _run([
            "aws", "s3api", "put-bucket-versioning",
            "--bucket", bucket, "--region", region,
            "--versioning-configuration", "Status=Enabled",
        ])

    if helper_bucket_role == "aws-config-delivery":
        notifications = _json.dumps({"EventBridgeConfiguration": {}})
        _run([
            "aws", "s3api", "put-bucket-notification-configuration",
            "--bucket", bucket, "--region", region,
            "--notification-configuration", notifications,
        ])
        object_lock = _json.dumps({"ObjectLockEnabled": "Enabled"})
        _run([
            "aws", "s3api", "put-object-lock-configuration",
            "--bucket", bucket, "--region", region,
            "--object-lock-configuration", object_lock,
        ])

    # 5. Product-managed helper tags — only when the caller declares a helper role
    if helper_bucket_role:
        tagging = _json.dumps({
            "TagSet": [
                {
                    "Key": "security-autopilot:managed-support-bucket",
                    "Value": "true",
                },
                {
                    "Key": "security-autopilot:support-bucket-role",
                    "Value": helper_bucket_role,
                },
            ]
        })
        _run([
            "aws", "s3api", "put-bucket-tagging",
            "--bucket", bucket, "--region", region,
            "--tagging", tagging,
        ])

    # 6. SSL-only deny policy — merged with any existing statements
    get_r = subprocess.run(
        ["aws", "s3api", "get-bucket-policy",
         "--bucket", bucket, "--region", region,
         "--query", "Policy", "--output", "text"],
        text=True, capture_output=True,
    )
    existing_stmts: list = []
    if get_r.returncode == 0:
        raw = (get_r.stdout or "").strip()
        if raw and raw not in ("None", "null"):
            try:
                existing_stmts = _json.loads(raw).get("Statement", [])
            except (ValueError, AttributeError):
                pass
    ssl_stmt = {
        "Sid": "DenyInsecureTransport",
        "Effect": "Deny",
        "Principal": "*",
        "Action": "s3:*",
        "Resource": [
            f"arn:aws:s3:::{bucket}",
            f"arn:aws:s3:::{bucket}/*",
        ],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }
    merged_stmts = [
        s for s in existing_stmts if s.get("Sid") != "DenyInsecureTransport"
    ] + [ssl_stmt]
    policy = _json.dumps({"Version": "2012-10-17", "Statement": merged_stmts})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(policy)
        tmp = f.name
    try:
        _run([
            "aws", "s3api", "put-bucket-policy",
            "--bucket", bucket, "--region", region,
            "--policy", f"file://{tmp}",
        ])
    finally:
        Path(tmp).unlink(missing_ok=True)

def recorder_status_map(status_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in status_payload.get("ConfigurationRecordersStatus", []):
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                mapping[name] = item
    return mapping


def build_pre_state_summary(
    recorders_payload: dict[str, Any],
    status_payload: dict[str, Any],
    deliveries_payload: dict[str, Any],
    *,
    target_bucket_name: str,
    target_bucket_existed_before: bool,
) -> dict[str, Any]:
    recorders = list(recorders_payload.get("ConfigurationRecorders") or [])
    deliveries = list(deliveries_payload.get("DeliveryChannels") or [])
    if len(recorders) > 1:
        raise SystemExit("Exact AWS Config rollback is unsupported when multiple configuration recorders exist.")
    if len(deliveries) > 1:
        raise SystemExit("Exact AWS Config rollback is unsupported when multiple delivery channels exist.")
    recorder = recorders[0] if recorders else None
    delivery = deliveries[0] if deliveries else None
    status = None
    if recorder is not None:
        status = recorder_status_map(status_payload).get(str(recorder.get("name") or ""))
    return {
        "version": SNAPSHOT_VERSION,
        "recorder_exists": recorder is not None,
        "recorder_name": "" if recorder is None else str(recorder.get("name") or ""),
        "recorder_all_supported": bool((recorder or {}).get("recordingGroup", {}).get("allSupported")),
        "recording_before": None if status is None else bool(status.get("recording")),
        "delivery_channel_exists": delivery is not None,
        "delivery_channel_name": "" if delivery is None else str(delivery.get("name") or ""),
        "delivery_bucket_name": "" if delivery is None else str(delivery.get("s3BucketName") or ""),
        "target_bucket_name": target_bucket_name,
        "target_bucket_existed_before": target_bucket_existed_before,
    }


def capture_snapshot(snapshot_dir: Path, *, region: str, bucket: str) -> dict[str, Any]:
    recorders_payload = run_json(
        ["aws", "configservice", "describe-configuration-recorders", "--region", region, "--output", "json"]
    )
    status_payload = run_json(
        [
            "aws",
            "configservice",
            "describe-configuration-recorder-status",
            "--region",
            region,
            "--output",
            "json",
        ]
    )
    deliveries_payload = run_json(
        ["aws", "configservice", "describe-delivery-channels", "--region", region, "--output", "json"]
    )
    bucket_existed_before = bucket_exists(bucket, region)
    bucket_state = {
        "version": SNAPSHOT_VERSION,
        "bucket_name": bucket,
        "bucket_existed_before": bucket_existed_before,
        "policy_json": None if not bucket_existed_before else get_bucket_policy_json(bucket, region),
    }
    summary = build_pre_state_summary(
        recorders_payload,
        status_payload,
        deliveries_payload,
        target_bucket_name=bucket,
        target_bucket_existed_before=bucket_existed_before,
    )
    atomic_write_json(snapshot_dir / "pre_configuration_recorders.json", recorders_payload)
    atomic_write_json(snapshot_dir / "pre_configuration_recorder_status.json", status_payload)
    atomic_write_json(snapshot_dir / "pre_delivery_channels.json", deliveries_payload)
    atomic_write_json(snapshot_dir / "pre_target_bucket_state.json", bucket_state)
    atomic_write_json(snapshot_dir / "pre_state_summary.json", summary)
    (snapshot_dir / ".snapshot-ready").write_text("ready\n", encoding="utf-8")
    return summary


def load_or_capture_snapshot(snapshot_dir: Path, *, region: str, bucket: str) -> dict[str, Any]:
    ready_path = snapshot_dir / ".snapshot-ready"
    if ready_path.exists():
        summary_path = snapshot_dir / "pre_state_summary.json"
        if not summary_path.exists():
            raise SystemExit("Existing AWS Config rollback snapshot is incomplete.")
        return load_json(summary_path)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return capture_snapshot(snapshot_dir, region=region, bucket=bucket)

def main() -> int:
    region = env_text("REGION", DEFAULT_REGION)
    bucket = env_text("BUCKET", DEFAULT_BUCKET)
    role_arn = env_text("ROLE_ARN", DEFAULT_ROLE_ARN)
    kms_arn = os.environ.get("KMS_ARN", DEFAULT_KMS_ARN).strip()
    account_id = env_text("ACCOUNT_ID", DEFAULT_ACCOUNT_ID)
    create_local_bucket = env_bool("CREATE_LOCAL_BUCKET", DEFAULT_CREATE_LOCAL_BUCKET)
    overwrite_recording_group = env_bool(
        "OVERWRITE_RECORDING_GROUP",
        DEFAULT_OVERWRITE_RECORDING_GROUP,
    )
    rollback_dir = Path(os.environ.get("ROLLBACK_DIR") or ".aws-config-rollback")
    snapshot_dir = rollback_dir / "snapshot"

    summary = load_or_capture_snapshot(snapshot_dir, region=region, bucket=bucket)
    if create_local_bucket:
        if not bucket_exists(bucket, region):
            create_bucket(bucket, region, object_lock_enabled=True)
        apply_support_bucket_baseline(
            bucket,
            region,
            helper_bucket_role="aws-config-delivery",
        )
        original_policy = load_json(snapshot_dir / "pre_target_bucket_state.json").get("policy_json")
        merged_policy = merge_bucket_policies(
            original_policy,
            build_required_bucket_policy(bucket, account_id),
        )
        put_bucket_policy(bucket, region, merged_policy)
    elif not bucket_exists(bucket, region):
        raise SystemExit(
            f"create_local_bucket=false and delivery bucket '{bucket}' is unreachable. "
            "Provide a reachable delivery_bucket_name or set create_local_bucket=true."
        )

    recorders_payload = load_json(snapshot_dir / "pre_configuration_recorders.json")
    recorder = next(iter(recorders_payload.get("ConfigurationRecorders") or []), None)
    recorder_name = str(summary.get("recorder_name") or "") or "security-autopilot-recorder"
    if not bool(summary.get("recorder_exists")) or overwrite_recording_group:
        recorder_payload = sanitize_payload(recorder or {"name": recorder_name})
        recorder_payload["name"] = recorder_name
        recorder_payload["roleARN"] = role_arn
        recorder_payload["recordingGroup"] = {
            "allSupported": True,
            "includeGlobalResourceTypes": True,
        }
        put_structured_payload("put-configuration-recorder", recorder_payload, region=region)
    elif not bool(summary.get("recorder_all_supported")):
        print(
            f"Preserving existing selective AWS Config recorder '{recorder_name}' "
            "(overwrite_recording_group=false).",
            file=sys.stderr,
        )
    else:
        print(
            f"Preserving existing AWS Config recorder '{recorder_name}' recording group "
            "(overwrite_recording_group=false).",
            file=sys.stderr,
        )

    deliveries_payload = load_json(snapshot_dir / "pre_delivery_channels.json")
    delivery = next(iter(deliveries_payload.get("DeliveryChannels") or []), None)
    delivery_name = str(summary.get("delivery_channel_name") or "") or "security-autopilot-delivery-channel"
    existing_delivery_bucket = str(summary.get("delivery_bucket_name") or "")
    existing_delivery_bucket_stale = bool(existing_delivery_bucket) and not bucket_exists(existing_delivery_bucket, region)
    if existing_delivery_bucket_stale and not create_local_bucket and existing_delivery_bucket == bucket:
        raise SystemExit(
            f"Existing AWS Config delivery channel '{delivery_name}' points to unreachable bucket "
            f"'{existing_delivery_bucket}' and create_local_bucket=false cannot repair it. "
            "Provide a reachable delivery_bucket_name or set create_local_bucket=true."
        )
    if existing_delivery_bucket and existing_delivery_bucket != bucket:
        warning = (
            f"WARNING: Existing AWS Config delivery channel '{delivery_name}' currently targets "
            f"{'unreachable ' if existing_delivery_bucket_stale else ''}bucket "
            f"'{existing_delivery_bucket}'. This bundle will redirect delivery to '{bucket}'."
        )
        print(warning, file=sys.stderr)
    delivery_payload = sanitize_payload(delivery or {"name": delivery_name})
    delivery_payload["name"] = delivery_name
    delivery_payload["s3BucketName"] = bucket
    if kms_arn:
        delivery_payload["s3KmsKeyArn"] = kms_arn
    else:
        delivery_payload.pop("s3KmsKeyArn", None)
    put_structured_payload("put-delivery-channel", delivery_payload, region=region)
    run_command(
        [
            "aws",
            "configservice",
            "start-configuration-recorder",
            "--region",
            region,
            "--configuration-recorder-name",
            recorder_name,
        ],
        check=False,
    )

    apply_context = {
        "version": SNAPSHOT_VERSION,
        "target_bucket_name": bucket,
        "target_bucket_created_by_apply": (
            not bool(summary.get("target_bucket_existed_before")) and bucket_exists(bucket, region)
        ),
        "applied_recorder_name": recorder_name,
        "applied_delivery_channel_name": delivery_name,
    }
    atomic_write_json(rollback_dir / "apply_context.json", apply_context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
