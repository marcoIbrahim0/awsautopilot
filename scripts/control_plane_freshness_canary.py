#!/usr/bin/env python3
"""
Emit supported security-group management events to keep control-plane freshness warm.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

DEFAULT_INTERVAL_SECONDS = 8 * 60
DEFAULT_CIDR = "203.0.113.10/32"
DEFAULT_DESCRIPTION = "autopilot-warmup"
DEFAULT_PORT = 22


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control-plane freshness canary.")
    parser.add_argument("--region", default="", help="AWS region (defaults to AWS SDK resolution).")
    parser.add_argument("--sg-id", default="", help="Security group ID to use for warm-up.")
    parser.add_argument("--cidr", default=DEFAULT_CIDR, help="CIDR used for temporary ingress rule.")
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION, help="Rule description.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port used for warm-up.")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS, help="Loop interval.")
    parser.add_argument("--iterations", type=int, default=0, help="0 means run forever.")
    parser.add_argument("--once", action="store_true", help="Run once and exit.")
    return parser


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "ClientError")
    return type(exc).__name__


def _build_permission(cidr: str, description: str, port: int) -> dict[str, Any]:
    return {
        "IpProtocol": "tcp",
        "FromPort": port,
        "ToPort": port,
        "IpRanges": [{"CidrIp": cidr, "Description": description}],
    }


def _pick_first_group(groups: list[dict[str, Any]]) -> str | None:
    for group in groups:
        group_id = str(group.get("GroupId") or "").strip()
        if group_id.startswith("sg-"):
            return group_id
    return None


def _resolve_security_group_id(ec2: Any, explicit_group_id: str) -> str:
    group_id = explicit_group_id.strip()
    if group_id:
        return group_id

    default_vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}]).get("Vpcs", [])
    if default_vpcs:
        default_vpc_id = str(default_vpcs[0].get("VpcId") or "").strip()
        if default_vpc_id:
            groups = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [default_vpc_id]}]).get(
                "SecurityGroups", []
            )
            chosen = _pick_first_group(groups)
            if chosen:
                return chosen

    groups = ec2.describe_security_groups().get("SecurityGroups", [])
    chosen = _pick_first_group(groups)
    if chosen:
        return chosen
    raise RuntimeError("No usable security group found; provide --sg-id explicitly.")


def _authorize_ingress(ec2: Any, group_id: str, permission: dict[str, Any]) -> str:
    try:
        ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=[permission])
        return "added"
    except ClientError as exc:
        if _error_code(exc) == "InvalidPermission.Duplicate":
            return "already_present"
        raise


def _revoke_ingress(ec2: Any, group_id: str, permission: dict[str, Any]) -> str:
    try:
        ec2.revoke_security_group_ingress(GroupId=group_id, IpPermissions=[permission])
        return "removed"
    except ClientError as exc:
        if _error_code(exc) == "InvalidPermission.NotFound":
            return "already_absent"
        raise


def _run_once(ec2: Any, group_id: str, cidr: str, description: str, port: int) -> dict[str, Any]:
    permission = _build_permission(cidr=cidr, description=description, port=port)
    result = {
        "timestamp": _utc_now_iso(),
        "security_group_id": group_id,
        "cidr": cidr,
        "port": port,
        "description": description,
        "authorize": "not_attempted",
        "revoke": "not_attempted",
        "status": "success",
    }
    cleanup_needed = False

    try:
        result["authorize"] = _authorize_ingress(ec2, group_id, permission)
        cleanup_needed = result["authorize"] in {"added", "already_present"}
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"authorize_failed:{_error_code(exc)}"

    if cleanup_needed:
        try:
            result["revoke"] = _revoke_ingress(ec2, group_id, permission)
        except Exception as exc:
            result["status"] = "failed"
            result["cleanup_error"] = f"revoke_failed:{_error_code(exc)}"

    return result


def _should_continue(iterations: int, completed: int) -> bool:
    if iterations <= 0:
        return True
    return completed < iterations


def main() -> int:
    args = _build_parser().parse_args()
    iterations = 1 if args.once else args.iterations
    region = args.region.strip() or None
    ec2 = boto3.client("ec2", region_name=region)

    try:
        group_id = _resolve_security_group_id(ec2, args.sg_id)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"resolve_sg_failed:{_error_code(exc)}"}))
        return 1

    completed = 0
    all_success = True
    while _should_continue(iterations, completed):
        completed += 1
        result = _run_once(ec2, group_id, args.cidr, args.description, args.port)
        print(json.dumps(result))
        if result.get("status") != "success":
            all_success = False
        if _should_continue(iterations, completed):
            time.sleep(max(args.interval_seconds, 1))
    return 0 if all_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted"}))
        sys.exit(130)

