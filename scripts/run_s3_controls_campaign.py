#!/usr/bin/env python3
"""
Campaign runner: validate PR bundles for all 4 S3 controls end-to-end.

Execution model (gated):
  Stage 0: Readiness gate (must pass before any control execution)
  Stage 1+: Per-control runs (S3.9, S3.5, S3.11, S3.15)

Usage:
  export SAAS_EMAIL=<email>
  export SAAS_PASSWORD=<password>

  # Full campaign
  python scripts/run_s3_controls_campaign.py

  # Stage 0 only
  python scripts/run_s3_controls_campaign.py --stage0-only

  # Dry-run campaign (skips terraform apply inside agent)
  python scripts/run_s3_controls_campaign.py --dry-run
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running from project root or scripts/
try:
    from scripts.run_no_ui_pr_bundle_agent import NoUiPrBundleAgent
    from scripts.lib.no_ui_agent_client import SaaSApiClient
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.run_no_ui_pr_bundle_agent import NoUiPrBundleAgent
    from scripts.lib.no_ui_agent_client import SaaSApiClient


TARGET_CONTROLS = ["S3.9", "S3.5", "S3.11", "S3.15"]

DEFAULT_API_BASE = "https://api.valensjewelry.com"
DEFAULT_ACCOUNT_ID = "029037611564"
DEFAULT_REGION = "eu-north-1"

CANARY_SCRIPT = Path(__file__).resolve().parent / "control_plane_freshness_canary.py"
DEFAULT_MAX_READINESS_WAIT_SEC = 300
DEFAULT_READINESS_POLL_INTERVAL_SEC = 15
DEFAULT_STAGE0_MAX_ATTEMPTS = 3
DEFAULT_STAGE0_RETRY_SLEEP_SEC = 5
DEFAULT_CLIENT_TIMEOUT_SEC = 30
DEFAULT_CLIENT_RETRIES = 8
DEFAULT_CLIENT_RETRY_BACKOFF_SEC = 1.5


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="S3 control campaign runner")
    parser.add_argument("--dry-run", action="store_true", help="Skip terraform apply in no-UI agent")
    parser.add_argument("--stage0-only", action="store_true", help="Run readiness gate only and exit")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="SaaS API base URL")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID, help="AWS account ID")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    parser.add_argument(
        "--output-dir",
        help=(
            "Campaign artifact output directory. "
            "Default: artifacts/no-ui-agent/s3-campaign-<UTC_TIMESTAMP>"
        ),
    )
    parser.add_argument(
        "--reconcile-after-apply",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Trigger reconcile during refresh after terraform apply (default: true).",
    )
    parser.add_argument(
        "--max-readiness-wait-sec",
        type=int,
        default=DEFAULT_MAX_READINESS_WAIT_SEC,
        help="Max seconds to poll readiness per attempt",
    )
    parser.add_argument(
        "--readiness-poll-interval-sec",
        type=int,
        default=DEFAULT_READINESS_POLL_INTERVAL_SEC,
        help="Readiness poll interval seconds",
    )
    parser.add_argument(
        "--stage0-max-attempts",
        type=int,
        default=DEFAULT_STAGE0_MAX_ATTEMPTS,
        help="Bounded attempts for stage0 canary->readiness loop",
    )
    parser.add_argument(
        "--stage0-retry-sleep-sec",
        type=int,
        default=DEFAULT_STAGE0_RETRY_SLEEP_SEC,
        help="Sleep between stage0 attempts",
    )
    parser.add_argument(
        "--controls",
        default=",".join(TARGET_CONTROLS),
        help="Comma-separated control IDs to execute in order (default: S3 campaign controls).",
    )
    parser.add_argument(
        "--client-timeout-sec",
        type=int,
        default=DEFAULT_CLIENT_TIMEOUT_SEC,
        help="HTTP timeout seconds for no-UI agent API requests.",
    )
    parser.add_argument(
        "--client-retries",
        type=int,
        default=DEFAULT_CLIENT_RETRIES,
        help="Retry count for transient no-UI agent API failures.",
    )
    parser.add_argument(
        "--client-retry-backoff-sec",
        type=float,
        default=DEFAULT_CLIENT_RETRY_BACKOFF_SEC,
        help="Initial exponential backoff seconds for API retries.",
    )
    return parser.parse_args(argv)


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _prompt_credentials() -> tuple[str, str]:
    email = os.environ.get("SAAS_EMAIL", "").strip()
    password = os.environ.get("SAAS_PASSWORD", "").strip()
    if not email:
        email = input("SaaS email: ").strip()
    if not password:
        password = getpass.getpass("SaaS password: ").strip()
    if not email or not password:
        print("ERROR: Both email and password are required", file=sys.stderr)
        sys.exit(2)
    return email, password


def _run_canary(region: str) -> dict[str, Any]:
    """Run freshness canary once to emit qualifying SG management events."""
    cmd = [sys.executable, str(CANARY_SCRIPT), "--once", "--region", region]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        output = completed.stdout.strip()
        if completed.returncode == 0 and output:
            return json.loads(output.splitlines()[-1])
        return {
            "status": "failed",
            "exit_code": completed.returncode,
            "stdout": output[-1000:],
            "stderr": completed.stderr[-1000:],
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _target_region_row(readiness: dict[str, Any], region: str) -> dict[str, Any] | None:
    rows = readiness.get("regions") if isinstance(readiness.get("regions"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("region") or "") == region:
            return row
    return None


def _readiness_diagnostics(readiness: dict[str, Any], region: str) -> dict[str, Any]:
    row = _target_region_row(readiness, region)
    return {
        "overall_ready": bool(readiness.get("overall_ready")),
        "missing_regions": readiness.get("missing_regions") if isinstance(readiness.get("missing_regions"), list) else [],
        "target_region": region,
        "target_region_present": bool(row),
        "target_is_recent": bool(row.get("is_recent")) if row else False,
        "target_last_event_time": row.get("last_event_time") if row else None,
        "target_last_intake_time": row.get("last_intake_time") if row else None,
        "target_age_minutes": row.get("age_minutes") if row else None,
    }


def _is_region_ready(readiness: dict[str, Any], region: str) -> bool:
    if not bool(readiness.get("overall_ready")):
        return False
    row = _target_region_row(readiness, region)
    return bool(row and row.get("is_recent"))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _wait_for_readiness(
    client: SaaSApiClient,
    account_id: str,
    region: str,
    max_wait_sec: int,
    poll_interval_sec: int,
) -> tuple[bool, dict[str, Any], int]:
    """Poll readiness until target region is recent or timeout."""
    started = time.monotonic()
    last_readiness: dict[str, Any] = {}

    while (time.monotonic() - started) < max_wait_sec:
        try:
            payload = client.check_control_plane_readiness(account_id, stale_after_minutes=30)
            if isinstance(payload, dict):
                last_readiness = payload
            if _is_region_ready(last_readiness, region):
                return True, last_readiness, int(time.monotonic() - started)
        except Exception as exc:
            last_readiness = {"overall_ready": False, "error": str(exc)}
        time.sleep(max(1, poll_interval_sec))

    return False, last_readiness, int(time.monotonic() - started)


def _run_stage0_readiness_gate(
    client: SaaSApiClient,
    campaign_dir: Path,
    account_id: str,
    region: str,
    max_attempts: int,
    retry_sleep_sec: int,
    max_wait_sec: int,
    poll_interval_sec: int,
) -> dict[str, Any]:
    """Stage 0 gate: bounded canary->readiness loop with artifact logging."""
    stage0_dir = campaign_dir / "stage0"
    stage0_dir.mkdir(parents=True, exist_ok=True)
    attempts_jsonl = stage0_dir / "readiness_attempts.jsonl"

    attempts: list[dict[str, Any]] = []
    total_attempts = max(1, max_attempts)

    for attempt in range(1, total_attempts + 1):
        canary = _run_canary(region)
        ready, readiness, waited_sec = _wait_for_readiness(
            client=client,
            account_id=account_id,
            region=region,
            max_wait_sec=max_wait_sec,
            poll_interval_sec=poll_interval_sec,
        )
        diagnostics = _readiness_diagnostics(readiness, region)
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempt": attempt,
            "canary": canary,
            "ready": ready,
            "waited_sec": waited_sec,
            "diagnostics": diagnostics,
            "readiness": readiness,
        }
        attempts.append(row)
        _append_jsonl(attempts_jsonl, row)

        if ready:
            summary = {
                "passed": True,
                "attempts_used": attempt,
                "max_attempts": total_attempts,
                "region": region,
                "account_id": account_id,
                "diagnostics": diagnostics,
                "attempts_jsonl": str(attempts_jsonl),
            }
            (stage0_dir / "readiness_gate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary

        if attempt < total_attempts:
            time.sleep(max(1, retry_sleep_sec))

    last = attempts[-1] if attempts else {}
    summary = {
        "passed": False,
        "attempts_used": total_attempts,
        "max_attempts": total_attempts,
        "region": region,
        "account_id": account_id,
        "diagnostics": last.get("diagnostics", {}),
        "attempts_jsonl": str(attempts_jsonl),
    }
    (stage0_dir / "readiness_gate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _build_settings(
    control_id: str,
    output_dir: str,
    dry_run: bool,
    reconcile_after_apply: bool,
    api_base: str,
    account_id: str,
    region: str,
    client_timeout_sec: int,
    client_retries: int,
    client_retry_backoff_sec: float,
) -> dict[str, Any]:
    return {
        "api_base": api_base,
        "account_id": account_id,
        "region": region,
        "output_dir": output_dir,
        "control_preference": [control_id],
        "poll_interval_sec": 10,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 1800,
        "verify_timeout_sec": 900,
        "terraform_timeout_sec": 900,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": dry_run,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": max(5, int(client_timeout_sec)),
        "client_retries": max(0, int(client_retries)),
        "client_retry_backoff_sec": max(0.1, float(client_retry_backoff_sec)),
        "reconcile_after_apply": bool(reconcile_after_apply),
        "reconcile_timeout_sec": 900,
        "reconcile_poll_interval_sec": 10,
    }


def _run_single_control(
    control_id: str,
    campaign_dir: Path,
    email: str,
    password: str,
    dry_run: bool,
    reconcile_after_apply: bool,
    api_base: str,
    account_id: str,
    region: str,
    client_timeout_sec: int,
    client_retries: int,
    client_retry_backoff_sec: float,
) -> dict[str, Any]:
    """Run the full agent flow for one control. Returns a result dict."""
    control_dir = campaign_dir / control_id.replace(".", "_")
    control_dir.mkdir(parents=True, exist_ok=True)

    settings = _build_settings(
        control_id,
        str(control_dir),
        dry_run,
        reconcile_after_apply,
        api_base,
        account_id,
        region,
        client_timeout_sec,
        client_retries,
        client_retry_backoff_sec,
    )
    started = datetime.now(timezone.utc).isoformat()

    try:
        agent = NoUiPrBundleAgent(
            settings=settings,
            output_dir=control_dir,
            email=email,
            password=password,
        )
        exit_code = agent.run()
    except Exception as exc:
        return {
            "control_id": control_id,
            "status": "error",
            "exit_code": 1,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "output_dir": str(control_dir),
        }

    checkpoint_path = control_dir / "checkpoint.json"
    checkpoint: dict[str, Any] = {}
    if checkpoint_path.exists():
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            checkpoint = {}

    report_path = control_dir / "final_report.json"
    report: dict[str, Any] = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            report = {}

    delta = report.get("delta") if isinstance(report.get("delta"), dict) else {}
    kpis = delta.get("kpis") if isinstance(delta.get("kpis"), dict) else {}

    return {
        "control_id": control_id,
        "status": checkpoint.get("status", "unknown"),
        "exit_code": exit_code,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "target_finding_id": checkpoint.get("context", {}).get("target_finding_id", ""),
        "target_action_id": checkpoint.get("context", {}).get("target_action_id", ""),
        "run_id": checkpoint.get("context", {}).get("run_id", ""),
        "open_drop": kpis.get("open_drop", "N/A"),
        "resolved_gain": kpis.get("resolved_gain", "N/A"),
        "tested_control_delta": kpis.get("tested_control_delta", "N/A"),
        "output_dir": str(control_dir),
        "errors": checkpoint.get("errors", []),
    }


def _write_coverage_table(path: Path, results: list[dict[str, Any]]) -> None:
    rows: list[str] = []
    for result in results:
        status_tag = "pass" if result.get("passed") else "fail"
        error_msg = ""
        if result.get("errors"):
            error_msg = result["errors"][-1].get("message", "")
        elif result.get("error"):
            error_msg = str(result.get("error"))
        rows.append(
            f"{result.get('control_id','')}\t{status_tag}\t{result.get('exit_code','')}"
            f"\t{result.get('output_dir','')}\t{error_msg}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _terraform_apply_exit_code(control_dir: Path) -> int | None:
    transcript_path = control_dir / "terraform_transcript.json"
    if not transcript_path.exists():
        return None
    try:
        payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    for row in payload:
        if not isinstance(row, dict):
            continue
        command = str(row.get("command") or "")
        if command.startswith("terraform apply"):
            code = row.get("exit_code")
            return int(code) if isinstance(code, int) else None
    return None


def _build_final_campaign_summary(
    campaign_dir: Path,
    results: list[dict[str, Any]],
    controls: list[str],
) -> dict[str, Any]:
    result_by_control = {str(row.get("control_id") or ""): row for row in results}
    control_summaries: dict[str, Any] = {}

    for control_id in controls:
        row = result_by_control.get(control_id, {})
        output_dir_raw = str(row.get("output_dir") or "").strip()
        control_dir = Path(output_dir_raw) if output_dir_raw else (campaign_dir / control_id.replace(".", "_"))
        report = _read_json(control_dir / "final_report.json")

        report_status = str(report.get("status") or row.get("status") or "").lower()
        run_id = str(row.get("run_id") or report.get("run_id") or "")
        target_finding_id = str(row.get("target_finding_id") or report.get("target_finding_id") or "")
        target_action_id = str(row.get("target_action_id") or report.get("target_action_id") or "")
        outcome_type = str(report.get("outcome_type") or "failed").strip().lower() or "failed"
        gate_evaluated = report.get("gate_evaluated")
        gate_skip_reason = report.get("gate_skip_reason")

        delta = report.get("delta") if isinstance(report.get("delta"), dict) else {}
        kpis = delta.get("kpis") if isinstance(delta.get("kpis"), dict) else {}
        tested_control_delta = kpis.get("tested_control_delta")
        resolved_gain = kpis.get("resolved_gain")
        tested_control_delta_lt_0 = isinstance(tested_control_delta, (int, float)) and tested_control_delta < 0
        resolved_gain_gt_0 = isinstance(resolved_gain, (int, float)) and resolved_gain > 0

        apply_exit_code = _terraform_apply_exit_code(control_dir)
        if outcome_type == "already_compliant_noop":
            checks = {
                "final_report_status_success": report_status == "success",
                "outcome_type_already_compliant_noop": True,
                "gate_evaluated_false": gate_evaluated is False,
                "gate_skip_reason_pre_already_compliant": str(gate_skip_reason or "") == "pre_already_compliant",
            }
        elif outcome_type == "remediated":
            checks = {
                "final_report_status_success": report_status == "success",
                "run_id_non_empty": bool(run_id),
                "target_finding_id_non_empty": bool(target_finding_id),
                "target_action_id_non_empty": bool(target_action_id),
                "terraform_apply_exit_code_0": apply_exit_code == 0,
                "resolved_state_verification_passed": report_status == "success",
                "tested_control_delta_lt_0": tested_control_delta_lt_0,
                "resolved_gain_gt_0": resolved_gain_gt_0,
            }
        else:
            checks = {
                "final_report_status_success": report_status == "success",
                "known_failure_outcome": outcome_type == "failed",
            }
        definition_of_done_passed = all(bool(v) for v in checks.values())

        control_summaries[control_id] = {
            "control_id": control_id,
            "run_id": run_id,
            "target_finding_id": target_finding_id,
            "target_action_id": target_action_id,
            "status": report_status or str(row.get("status") or ""),
            "exit_code": row.get("exit_code"),
            "tested_control_delta": tested_control_delta,
            "resolved_gain": resolved_gain,
            "outcome_type": outcome_type,
            "gate_evaluated": gate_evaluated,
            "gate_skip_reason": gate_skip_reason,
            "definition_of_done_checks": checks,
            "definition_of_done_passed": definition_of_done_passed,
            "output_dir": str(control_dir),
        }

    overall_passed = all(
        bool(control_summaries.get(control_id, {}).get("definition_of_done_passed")) for control_id in controls
    )
    outcome_counts = {"remediated": 0, "already_compliant_noop": 0, "failed": 0}
    for control_id in controls:
        token = str(control_summaries.get(control_id, {}).get("outcome_type") or "failed")
        if token not in outcome_counts:
            token = "failed"
        outcome_counts[token] += 1

    return {
        "controls": control_summaries,
        "overall_passed": overall_passed,
        "remediated_count": outcome_counts["remediated"],
        "already_compliant_noop_count": outcome_counts["already_compliant_noop"],
        "failed_count": outcome_counts["failed"],
    }


def main() -> int:
    args = parse_args(sys.argv[1:])
    target_controls = [c.strip() for c in str(args.controls or "").split(",") if c.strip()]
    if not target_controls:
        print("ERROR: No controls provided in --controls", file=sys.stderr)
        return 2
    email, password = _prompt_credentials()

    campaign_ts = _utc_ts()
    campaign_dir = (
        Path(str(args.output_dir)).expanduser()
        if str(args.output_dir or "").strip()
        else Path("artifacts/no-ui-agent") / f"s3-campaign-{campaign_ts}"
    )
    campaign_dir.mkdir(parents=True, exist_ok=True)

    print(f"Campaign started at {campaign_ts}")
    print(f"Output directory: {campaign_dir}")
    print(f"Target controls: {target_controls}")
    print(f"Dry-run: {args.dry_run}")
    print(f"Reconcile after apply: {args.reconcile_after_apply}")
    print(f"Stage0 only: {args.stage0_only}")
    print(f"Region: {args.region}")
    print()

    print("Validating credentials...")
    client = SaaSApiClient(args.api_base)
    try:
        client.login(email, password)
    except Exception as exc:
        print(f"ERROR: Login failed: {exc}", file=sys.stderr)
        return 2

    print("Stage 0: readiness gate (canary -> readiness poll)...")
    stage0 = _run_stage0_readiness_gate(
        client=client,
        campaign_dir=campaign_dir,
        account_id=args.account_id,
        region=args.region,
        max_attempts=args.stage0_max_attempts,
        retry_sleep_sec=args.stage0_retry_sleep_sec,
        max_wait_sec=args.max_readiness_wait_sec,
        poll_interval_sec=args.readiness_poll_interval_sec,
    )
    if not stage0.get("passed"):
        print("ERROR: Stage 0 readiness gate failed. Hard-aborting campaign before control execution.")
        print(f"Diagnostics: {json.dumps(stage0.get('diagnostics', {}), indent=2)}")
        print(f"Artifacts: {campaign_dir / 'stage0'}")

        summary = {
            "campaign_timestamp": campaign_ts,
            "dry_run": args.dry_run,
            "all_passed": False,
            "controls_targeted": len(target_controls),
            "controls_executed": 0,
            "controls_passed": 0,
            "stage0": stage0,
            "results": [],
        }
        (campaign_dir / "campaign_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        _write_coverage_table(campaign_dir / "coverage_table.tsv", [])
        return 1

    print("Stage 0 PASS: readiness gate satisfied.")
    print(f"Stage 0 artifacts: {campaign_dir / 'stage0'}")

    if args.stage0_only:
        summary = {
            "campaign_timestamp": campaign_ts,
            "dry_run": args.dry_run,
            "all_passed": True,
            "controls_targeted": len(target_controls),
            "controls_executed": 0,
            "controls_passed": 0,
            "stage0": stage0,
            "results": [],
        }
        (campaign_dir / "campaign_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        _write_coverage_table(campaign_dir / "coverage_table.tsv", [])
        print("Stage 0 only requested. Exiting cleanly.")
        return 0

    results: list[dict[str, Any]] = []
    all_passed = True

    for index, control_id in enumerate(target_controls):
        print(f"\n{'=' * 60}")
        print(f"[{index + 1}/{len(target_controls)}] Control: {control_id}")
        print(f"{'=' * 60}")

        print(f"  Running readiness canary for {args.region}...")
        canary_result = _run_canary(args.region)
        print(f"  Canary result: {canary_result.get('status', 'unknown')}")

        print(f"  Waiting for readiness (max {args.max_readiness_wait_sec}s)...")
        ready, readiness, waited_sec = _wait_for_readiness(
            client=client,
            account_id=args.account_id,
            region=args.region,
            max_wait_sec=args.max_readiness_wait_sec,
            poll_interval_sec=args.readiness_poll_interval_sec,
        )

        if not ready:
            diagnostics = _readiness_diagnostics(readiness, args.region)
            result = {
                "control_id": control_id,
                "status": "failed",
                "exit_code": 1,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "target_finding_id": "",
                "target_action_id": "",
                "run_id": "",
                "open_drop": "N/A",
                "resolved_gain": "N/A",
                "tested_control_delta": "N/A",
                "output_dir": "",
                "errors": [
                    {
                        "phase": "readiness",
                        "message": (
                            "Readiness gate failed before control execution: "
                            f"missing_regions={diagnostics.get('missing_regions')} "
                            f"target_last_intake={diagnostics.get('target_last_intake_time')} "
                            f"target_age_minutes={diagnostics.get('target_age_minutes')}"
                        ),
                    }
                ],
                "readiness": readiness,
                "waited_sec": waited_sec,
            }
            result["passed"] = False
            results.append(result)
            all_passed = False
            print("  ERROR: Readiness gate failed during control loop. Hard-aborting remaining controls.")
            print(f"  Diagnostics: {json.dumps(diagnostics, indent=2)}")
            break

        print(f"  Running agent for {control_id}...")
        result = _run_single_control(
            control_id=control_id,
            campaign_dir=campaign_dir,
            email=email,
            password=password,
            dry_run=args.dry_run,
            reconcile_after_apply=args.reconcile_after_apply,
            api_base=args.api_base,
            account_id=args.account_id,
            region=args.region,
            client_timeout_sec=args.client_timeout_sec,
            client_retries=args.client_retries,
            client_retry_backoff_sec=args.client_retry_backoff_sec,
        )
        result["passed"] = result["exit_code"] == 0 and result["status"] == "success"
        results.append(result)

        if not result["passed"]:
            all_passed = False

        print(f"  Result: {'PASS' if result['passed'] else 'FAIL'}")
        print(f"  Exit code: {result['exit_code']}")
        print(f"  Status: {result['status']}")
        if result.get("open_drop") != "N/A":
            print(f"  KPIs: open_drop={result['open_drop']}, resolved_gain={result['resolved_gain']}")
        if result.get("errors"):
            for err in result["errors"]:
                print(f"  Error: {err.get('message', str(err))}")
        if not result["passed"]:
            print("  Gate failure: stopping campaign at first failed control.")
            break

    summary = {
        "campaign_timestamp": campaign_ts,
        "dry_run": args.dry_run,
        "all_passed": all_passed,
        "controls_targeted": len(target_controls),
        "controls_executed": len(results),
        "controls_passed": sum(1 for row in results if row.get("passed")),
        "stage0": stage0,
        "results": results,
    }
    summary_path = campaign_dir / "campaign_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    tsv_path = campaign_dir / "coverage_table.tsv"
    _write_coverage_table(tsv_path, results)

    final_campaign_summary = _build_final_campaign_summary(campaign_dir, results, target_controls)
    final_campaign_summary_path = campaign_dir / "final_campaign_summary.json"
    final_campaign_summary_path.write_text(json.dumps(final_campaign_summary, indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print("CAMPAIGN SUMMARY")
    print(f"{'=' * 60}")
    print(
        f"Targeted: {len(target_controls)} | Executed: {len(results)} | "
        f"Passed: {summary['controls_passed']} | Failed: {len(results) - summary['controls_passed']}"
    )
    print(f"All passed: {all_passed}")
    print(f"Summary: {summary_path}")
    print(f"Coverage: {tsv_path}")
    print(f"Final summary: {final_campaign_summary_path}")
    for row in results:
        tag = "PASS" if row.get("passed") else "FAIL"
        print(f"  {tag} {row.get('control_id','')}: exit_code={row.get('exit_code')}, status={row.get('status')}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCampaign interrupted by user")
        sys.exit(130)
