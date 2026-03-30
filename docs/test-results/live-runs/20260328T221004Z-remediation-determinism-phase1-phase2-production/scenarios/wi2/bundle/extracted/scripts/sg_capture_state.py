#!/usr/bin/env python3
"""
Security Autopilot — EC2.53 SG ingress pre-state capture.

Run BEFORE terraform apply to snapshot the current public 22/3389 ingress
rules for the target security group so they can be restored on rollback.

Usage:
    SECURITY_GROUP_ID=sg-xxx REGION=eu-north-1 python3 scripts/sg_capture_state.py

Writes: .sg-rollback/sg_ingress_snapshot.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SNAPSHOT_VERSION = 1
ROLLBACK_DIR = ".sg-rollback"
SNAPSHOT_FILE = "sg_ingress_snapshot.json"


def env_text(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def run_aws(*args: str) -> dict:
    result = subprocess.run(
        ["aws", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"AWS CLI error: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def is_public_cidr(cidr: str) -> bool:
    return cidr in {"0.0.0.0/0", "::/0"}


def ip_range_entry(*, cidr_key: str, cidr_value: str, description: str) -> dict[str, str]:
    entry = {cidr_key: cidr_value}
    if description:
        entry["Description"] = description
    return entry


def main() -> None:
    sg_id = env_text("SECURITY_GROUP_ID")
    region = env_text("REGION")

    resp = run_aws(
        "ec2", "describe-security-group-rules",
        "--region", region,
        "--filters", f"Name=group-id,Values={sg_id}",
        "--output", "json",
    )
    rules = resp.get("SecurityGroupRules", [])

    # Capture only public admin-port rules that will be revoked by the apply script
    captured = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if bool(rule.get("IsEgress")):
            continue
        protocol = str(rule.get("IpProtocol", "")).lower()
        from_port = rule.get("FromPort")
        to_port = rule.get("ToPort")
        cidr_ipv4 = str(rule.get("CidrIpv4") or "").strip()
        cidr_ipv6 = str(rule.get("CidrIpv6") or "").strip()
        description = str(rule.get("Description") or "").strip()

        if protocol not in {"tcp", "-1"}:
            continue
        if from_port is None or to_port is None:
            if protocol != "-1":
                continue

        # Only capture public-admin-port rules we will revoke
        is_admin_port = (
            protocol == "-1"
            or (isinstance(from_port, int) and isinstance(to_port, int)
                and from_port <= 22 <= to_port)
            or (isinstance(from_port, int) and isinstance(to_port, int)
                and from_port <= 3389 <= to_port)
        )
        if not is_admin_port:
            continue

        if cidr_ipv4 and is_public_cidr(cidr_ipv4):
            captured.append({
                "IpProtocol": protocol,
                "FromPort": from_port,
                "ToPort": to_port,
                "IpRanges": [ip_range_entry(cidr_key="CidrIp", cidr_value=cidr_ipv4, description=description)],
            })
        if cidr_ipv6 and is_public_cidr(cidr_ipv6):
            captured.append({
                "IpProtocol": protocol,
                "FromPort": from_port,
                "ToPort": to_port,
                "Ipv6Ranges": [ip_range_entry(cidr_key="CidrIpv6", cidr_value=cidr_ipv6, description=description)],
            })

    rollback_dir = Path(ROLLBACK_DIR)
    rollback_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "version": SNAPSHOT_VERSION,
        "security_group_id": sg_id,
        "region": region,
        "captured_rules": captured,
    }
    snapshot_path = rollback_dir / SNAPSHOT_FILE
    snapshot_path.write_text(json.dumps(snapshot, indent=2))
    print(f"Captured {len(captured)} public ingress rule(s) to {snapshot_path}")


if __name__ == "__main__":
    main()
