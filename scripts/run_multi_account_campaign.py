#!/usr/bin/env python3
"""
Run the single-account campaign script across all validated accounts.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running from project root or scripts/
try:
    from scripts.lib.no_ui_agent_client import SaaSApiClient
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.lib.no_ui_agent_client import SaaSApiClient


DEFAULT_API_BASE = "https://api.valensjewelry.com"
DEFAULT_REGION = "eu-north-1"
DEFAULT_CONTROLS = "Config.1,SSM.7,EC2.7,EC2.182"
DEFAULT_CLIENT_TIMEOUT_SEC = 30
DEFAULT_CLIENT_RETRIES = 8
DEFAULT_CLIENT_RETRY_BACKOFF_SEC = 1.5
DEFAULT_MAX_READINESS_WAIT_SEC = 300
DEFAULT_READINESS_POLL_INTERVAL_SEC = 15
DEFAULT_STAGE0_MAX_ATTEMPTS = 3
DEFAULT_STAGE0_RETRY_SLEEP_SEC = 5

CAMPAIGN_SCRIPT = Path(__file__).resolve().parent / "run_s3_controls_campaign.py"


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-account campaign runner")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="SaaS API base URL")
    parser.add_argument("--region", default=DEFAULT_REGION, help="Default AWS region for accounts missing region")
    parser.add_argument("--controls", default=DEFAULT_CONTROLS, help="Comma-separated control IDs")
    parser.add_argument(
        "--output-dir",
        help="Cross-account campaign output directory. Default: artifacts/no-ui-agent/multi-account-campaign-<UTC_TIMESTAMP>",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip terraform apply in campaign runs")
    parser.add_argument("--stage0-only", action="store_true", help="Run readiness gate only in each account run")
    parser.add_argument(
        "--reconcile-after-apply",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Trigger reconcile during refresh after terraform apply (default: true).",
    )
    parser.add_argument(
        "--client-timeout-sec",
        type=int,
        default=DEFAULT_CLIENT_TIMEOUT_SEC,
        help="HTTP timeout seconds for campaign API requests.",
    )
    parser.add_argument(
        "--client-retries",
        type=int,
        default=DEFAULT_CLIENT_RETRIES,
        help="Retry count for transient campaign API failures.",
    )
    parser.add_argument(
        "--client-retry-backoff-sec",
        type=float,
        default=DEFAULT_CLIENT_RETRY_BACKOFF_SEC,
        help="Initial exponential backoff seconds for API retries.",
    )
    parser.add_argument(
        "--max-readiness-wait-sec",
        type=int,
        default=DEFAULT_MAX_READINESS_WAIT_SEC,
        help="Max seconds to poll readiness per attempt.",
    )
    parser.add_argument(
        "--readiness-poll-interval-sec",
        type=int,
        default=DEFAULT_READINESS_POLL_INTERVAL_SEC,
        help="Readiness poll interval seconds.",
    )
    parser.add_argument(
        "--stage0-max-attempts",
        type=int,
        default=DEFAULT_STAGE0_MAX_ATTEMPTS,
        help="Bounded attempts for stage0 canary->readiness loop.",
    )
    parser.add_argument(
        "--stage0-retry-sleep-sec",
        type=int,
        default=DEFAULT_STAGE0_RETRY_SLEEP_SEC,
        help="Sleep between stage0 attempts.",
    )
    return parser.parse_args(argv)


def _prompt_credentials() -> tuple[str, str]:
    email = os.environ.get("SAAS_EMAIL", "").strip()
    password = os.environ.get("SAAS_PASSWORD", "").strip()
    if not email:
        email = input("SaaS email: ").strip()
    if not password:
        password = getpass.getpass("SaaS password: ").strip()
    if not email or not password:
        raise SystemExit("ERROR: Both SAAS_EMAIL and SAAS_PASSWORD are required")
    return email, password


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _fetch_accounts(client: SaaSApiClient) -> list[dict[str, Any]]:
    payload = client._request_bytes("GET", "/api/aws/accounts")
    if not payload:
        return []
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, list):
        return []
    return [row for row in decoded if isinstance(row, dict)]


def _list_validated_accounts(client: SaaSApiClient) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for row in _fetch_accounts(client):
        status = str(row.get("status") or "").strip().lower()
        if status == "validated":
            validated.append(row)
    return validated


def _resolve_account_region(account: dict[str, Any], default_region: str) -> str:
    region = str(account.get("region") or "").strip()
    if region:
        return region
    regions = account.get("regions")
    if isinstance(regions, list):
        for item in regions:
            value = str(item or "").strip()
            if value:
                return value
    return default_region


def _build_campaign_command(
    args: argparse.Namespace,
    account_id: str,
    region: str,
    account_output_dir: Path,
) -> list[str]:
    cmd = [
        sys.executable,
        str(CAMPAIGN_SCRIPT),
        "--api-base",
        str(args.api_base),
        "--account-id",
        account_id,
        "--region",
        region,
        "--controls",
        str(args.controls),
        "--output-dir",
        str(account_output_dir),
        "--client-timeout-sec",
        str(args.client_timeout_sec),
        "--client-retries",
        str(args.client_retries),
        "--client-retry-backoff-sec",
        str(args.client_retry_backoff_sec),
        "--max-readiness-wait-sec",
        str(args.max_readiness_wait_sec),
        "--readiness-poll-interval-sec",
        str(args.readiness_poll_interval_sec),
        "--stage0-max-attempts",
        str(args.stage0_max_attempts),
        "--stage0-retry-sleep-sec",
        str(args.stage0_retry_sleep_sec),
    ]
    cmd.append("--reconcile-after-apply" if args.reconcile_after_apply else "--no-reconcile-after-apply")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.stage0_only:
        cmd.append("--stage0-only")
    return cmd


def _extract_control_outcomes(summary: dict[str, Any]) -> dict[str, str]:
    controls = summary.get("controls")
    if not isinstance(controls, dict):
        return {}
    outcomes: dict[str, str] = {}
    for control_id, row in controls.items():
        if not isinstance(row, dict):
            continue
        outcomes[str(control_id)] = str(row.get("outcome_type") or "")
    return outcomes


def _extract_error(account_dir: Path, campaign_exit_code: int) -> str | None:
    campaign_summary = _read_json(account_dir / "campaign_summary.json")
    if not campaign_summary:
        return f"Missing campaign_summary.json (campaign_exit_code={campaign_exit_code})"
    results = campaign_summary.get("results")
    if isinstance(results, list):
        for row in reversed(results):
            if not isinstance(row, dict):
                continue
            errors = row.get("errors")
            if isinstance(errors, list) and errors:
                message = errors[-1].get("message") if isinstance(errors[-1], dict) else str(errors[-1])
                if str(message).strip():
                    return str(message)
    return f"Campaign failed with exit_code={campaign_exit_code}"


def _summarize_account_run(
    account_id: str,
    region: str,
    account_output_dir: Path,
    campaign_exit_code: int,
) -> dict[str, Any]:
    final_summary = _read_json(account_output_dir / "final_campaign_summary.json")
    has_summary = bool(final_summary)
    remediated = int(final_summary.get("remediated_count") or 0) if has_summary else 0
    noop = int(final_summary.get("already_compliant_noop_count") or 0) if has_summary else 0
    failed = int(final_summary.get("failed_count") or 0) if has_summary else 1
    overall = bool(final_summary.get("overall_passed")) if has_summary else (campaign_exit_code == 0)
    return {
        "account_id": account_id,
        "region": region,
        "campaign_exit_code": campaign_exit_code,
        "overall_passed": overall,
        "remediated_count": remediated,
        "already_compliant_noop_count": noop,
        "failed_count": failed,
        "control_outcomes": _extract_control_outcomes(final_summary),
        "output_dir": str(account_output_dir),
        "error": None if overall else _extract_error(account_output_dir, campaign_exit_code),
    }


def _build_cross_account_summary(
    output_dir: Path,
    controls: list[str],
    accounts: list[dict[str, Any]],
) -> dict[str, Any]:
    accounts_total = len(accounts)
    accounts_passed = sum(1 for row in accounts if bool(row.get("overall_passed")))
    accounts_failed = accounts_total - accounts_passed
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "controls": controls,
        "accounts_total": accounts_total,
        "accounts_passed": accounts_passed,
        "accounts_failed": accounts_failed,
        "overall_passed": bool(accounts_total > 0 and accounts_failed == 0),
        "accounts": accounts,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    controls = [item.strip() for item in str(args.controls or "").split(",") if item.strip()]
    if not controls:
        print("ERROR: No controls provided via --controls", file=sys.stderr)
        return 2

    email, password = _prompt_credentials()
    campaign_ts = _utc_ts()
    root_dir = (
        Path(str(args.output_dir)).expanduser()
        if str(args.output_dir or "").strip()
        else Path("artifacts/no-ui-agent") / f"multi-account-campaign-{campaign_ts}"
    )
    root_dir.mkdir(parents=True, exist_ok=True)

    client = SaaSApiClient(
        str(args.api_base),
        timeout_sec=max(5, int(args.client_timeout_sec)),
        retries=max(0, int(args.client_retries)),
        retry_backoff_sec=max(0.1, float(args.client_retry_backoff_sec)),
    )
    client.login(email, password)

    validated_accounts = _list_validated_accounts(client)
    if not validated_accounts:
        summary = _build_cross_account_summary(root_dir, controls, [])
        summary["error"] = "No validated accounts returned by /api/aws/accounts"
        (root_dir / "cross_account_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("ERROR: No validated accounts found")
        print(f"Summary: {root_dir / 'cross_account_summary.json'}")
        return 1

    env = os.environ.copy()
    env["SAAS_EMAIL"] = email
    env["SAAS_PASSWORD"] = password

    account_results: list[dict[str, Any]] = []
    for account in validated_accounts:
        account_id = str(account.get("account_id") or "").strip()
        if not account_id:
            account_results.append(
                {
                    "account_id": "",
                    "region": str(args.region),
                    "campaign_exit_code": 1,
                    "overall_passed": False,
                    "remediated_count": 0,
                    "already_compliant_noop_count": 0,
                    "failed_count": 1,
                    "control_outcomes": {},
                    "output_dir": "",
                    "error": "Account row missing account_id",
                }
            )
            continue

        region = _resolve_account_region(account, str(args.region))
        account_dir = root_dir / account_id
        account_dir.mkdir(parents=True, exist_ok=True)
        cmd = _build_campaign_command(args, account_id, region, account_dir)

        print(f"[{account_id}] Running campaign in region={region}")
        completed = subprocess.run(cmd, env=env, check=False)
        account_results.append(_summarize_account_run(account_id, region, account_dir, completed.returncode))

    summary = _build_cross_account_summary(root_dir, controls, account_results)
    summary_path = root_dir / "cross_account_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Cross-account summary: {summary_path}")
    print(
        f"Accounts total={summary['accounts_total']} passed={summary['accounts_passed']} "
        f"failed={summary['accounts_failed']} overall_passed={summary['overall_passed']}"
    )
    return 0 if bool(summary.get("overall_passed")) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
