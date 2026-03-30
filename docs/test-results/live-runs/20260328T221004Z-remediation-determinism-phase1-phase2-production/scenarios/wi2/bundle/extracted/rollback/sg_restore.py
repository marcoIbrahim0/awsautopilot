#!/usr/bin/env python3
"""
Security Autopilot — EC2.53 SG ingress rollback restore.

Run AFTER terraform destroy to re-add the original public 22/3389 ingress
rules that were captured before apply.

Usage:
    python3 rollback/sg_restore.py

Reads: .sg-rollback/sg_ingress_snapshot.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROLLBACK_DIR = ".sg-rollback"
SNAPSHOT_FILE = "sg_ingress_snapshot.json"


def run_aws(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["aws", *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise SystemExit(f"AWS CLI error: {result.stderr.strip()}")
    return result


def main() -> None:
    snapshot_path = Path(ROLLBACK_DIR) / SNAPSHOT_FILE
    if not snapshot_path.exists():
        raise SystemExit(
            f"Snapshot not found at {snapshot_path}. "
            "Was sg_capture_state.py run before apply?"
        )

    snapshot = json.loads(snapshot_path.read_text())
    sg_id = snapshot["security_group_id"]
    region = snapshot["region"]
    rules = snapshot.get("captured_rules", [])

    if not rules:
        print("No public ingress rules were captured; nothing to restore.")
        return

    restored = 0
    errors = 0
    for rule in rules:
        permissions_json = json.dumps([rule])
        result = run_aws(
            "ec2", "authorize-security-group-ingress",
            "--region", region,
            "--group-id", sg_id,
            "--ip-permissions", permissions_json,
            check=False,
        )
        if result.returncode == 0:
            restored += 1
        else:
            err = result.stderr.strip()
            # Duplicate rule is not an error
            if "InvalidPermission.Duplicate" in err:
                print(f"  Rule already present (skipped): {rule}")
                restored += 1
            else:
                print(f"  ERROR restoring rule {rule}: {err}", file=sys.stderr)
                errors += 1

    print(f"Restored {restored}/{len(rules)} ingress rule(s) to {sg_id}.")
    if errors:
        raise SystemExit(f"{errors} rule(s) failed to restore — check stderr above.")


if __name__ == "__main__":
    main()
