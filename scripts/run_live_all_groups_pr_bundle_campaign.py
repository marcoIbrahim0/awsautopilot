#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.lib.no_ui_agent_client import ApiError, SaaSApiClient, redact_payload
    from scripts.lib.no_ui_agent_terraform import run_command
    from scripts.run_no_ui_pr_bundle_agent import extract_zip_safe
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.lib.no_ui_agent_client import ApiError, SaaSApiClient, redact_payload
    from scripts.lib.no_ui_agent_terraform import run_command
    from scripts.run_no_ui_pr_bundle_agent import extract_zip_safe


RETRIABLE_CREATE_REASONS = {
    "missing_strategy_id",
    "dependency_check_failed",
    "invalid_strategy_inputs",
    "invalid_override_strategy",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all live grouped PR bundles for one account.")
    parser.add_argument("--api-base", default="https://api.ocypheris.com")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--aws-profile")
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--poll-interval-sec", type=int, default=10)
    parser.add_argument("--run-timeout-sec", type=int, default=1800)
    parser.add_argument("--terraform-timeout-sec", type=int, default=2400)
    parser.add_argument("--client-timeout-sec", type=int, default=30)
    parser.add_argument("--client-retries", type=int, default=4)
    parser.add_argument("--client-retry-backoff-sec", type=float, default=1.5)
    return parser.parse_args()


def prompt_credentials() -> tuple[str, str]:
    email = str(os.environ.get("SAAS_EMAIL") or "").strip()
    password = str(os.environ.get("SAAS_PASSWORD") or "").strip()
    if not email:
        email = input("SaaS email: ").strip()
    if not password:
        password = getpass.getpass("SaaS password: ").strip()
    if not email or not password:
        raise SystemExit("Both SAAS_EMAIL and SAAS_PASSWORD are required.")
    return email, password


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def resolve_output_dir(args: argparse.Namespace, run_id: str) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser().resolve()
    return (Path("docs/test-results/live-runs") / run_id).resolve()


def build_client(args: argparse.Namespace, token: str | None = None) -> SaaSApiClient:
    client = SaaSApiClient(
        args.api_base,
        timeout_sec=args.client_timeout_sec,
        retries=args.client_retries,
        retry_backoff_sec=args.client_retry_backoff_sec,
    )
    if token:
        client.set_access_token(token)
    return client


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def list_all_action_groups(client: SaaSApiClient, *, account_id: str, page_size: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    offset = 0
    while True:
        payload = client.list_action_groups(account_id=account_id, limit=page_size, offset=offset)
        page = payload.get("items") if isinstance(payload.get("items"), list) else []
        items.extend(item for item in page if isinstance(item, dict))
        if len(page) < page_size:
            return items
        offset += page_size


def refresh_regions(client: SaaSApiClient, *, account_id: str, regions: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for region in regions:
        results.append(
            {
                "region": region,
                "compute": client.trigger_compute_actions(account_id, region),
            }
        )
    return results


def group_folder_name(index: int, group: dict[str, Any]) -> str:
    region = str(group.get("region") or "global").lower()
    action_type = slugify(str(group.get("action_type") or "group"))
    return f"{index:02d}-{region}-{action_type}"


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "group"


def representative_action_id(detail: dict[str, Any]) -> str:
    members = detail.get("members") if isinstance(detail.get("members"), list) else []
    for member in members:
        if isinstance(member, dict) and str(member.get("action_id") or "").strip():
            return str(member["action_id"])
    raise RuntimeError(f"No member action_id found for group {detail.get('id')}")


def build_request_candidates(
    options_payload: dict[str, Any],
    *,
    action_type: str,
    run_id: str,
    folder: str,
) -> list[dict[str, Any]]:
    strategies = options_payload.get("strategies") if isinstance(options_payload.get("strategies"), list) else []
    ordered = sorted(
        (item for item in strategies if isinstance(item, dict)),
        key=lambda item: (0 if item.get("recommended") else 1, str(item.get("strategy_id") or "")),
    )
    candidates: list[dict[str, Any]] = []
    for item in ordered:
        strategy_id = str(item.get("strategy_id") or "").strip()
        if not strategy_id:
            continue
        body = {
            "strategy_id": strategy_id,
            "strategy_inputs": safe_default_strategy_inputs(item),
            "risk_acknowledged": True,
            "bucket_creation_acknowledged": action_type == "cloudtrail_enabled",
            "repo_target": unique_repo_target(run_id=run_id, folder=folder, strategy_id=strategy_id),
        }
        candidates.append(compact_body(body))
    if not candidates:
        raise RuntimeError("No remediation strategies available.")
    return candidates


def safe_default_strategy_inputs(strategy: dict[str, Any]) -> dict[str, Any]:
    input_schema = strategy.get("input_schema") if isinstance(strategy.get("input_schema"), dict) else {}
    fields = input_schema.get("fields") if isinstance(input_schema.get("fields"), list) else []
    resolved: dict[str, Any] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "").strip()
        if not key or not field.get("required") or "safe_default_value" not in field:
            continue
        value = field.get("safe_default_value")
        if isinstance(value, str) and "{{" in value:
            continue
        if value in (None, ""):
            continue
        resolved[key] = value
    return resolved


def unique_repo_target(*, run_id: str, folder: str, strategy_id: str) -> dict[str, str]:
    head = slugify(f"{run_id}-{folder}-{strategy_id}")[:120]
    return {
        "provider": "github",
        "repository": "example/security-autopilot-remediations",
        "base_branch": "main",
        "head_branch": head,
    }


def compact_body(body: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in body.items():
        if value in (None, "", []):
            continue
        compact[key] = value
    return compact


def extract_reason(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    detail = payload.get("detail")
    if not isinstance(detail, dict):
        return None
    reason = detail.get("reason")
    return str(reason).strip() if isinstance(reason, str) and reason.strip() else None


def extract_existing_run_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    detail = payload.get("detail")
    if not isinstance(detail, dict):
        return None
    run_id = detail.get("existing_run_id")
    return str(run_id).strip() if isinstance(run_id, str) and run_id.strip() else None


def create_group_bundle_run(
    client: SaaSApiClient,
    *,
    group_id: str,
    request_candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any] | None]:
    attempts: list[dict[str, Any]] = []
    for body in request_candidates:
        try:
            return client.create_action_group_bundle_run(group_id, body), attempts, body
        except ApiError as exc:
            reason = extract_reason(exc.payload)
            attempts.append(
                {
                    "request_body": redact_payload(body),
                    "status_code": exc.status_code,
                    "reason": reason,
                    "payload": redact_payload(exc.payload),
                    "existing_run_id": extract_existing_run_id(exc.payload),
                }
            )
            if exc.status_code == 400 and reason in RETRIABLE_CREATE_REASONS:
                continue
            return None, attempts, body
    return None, attempts, None


def poll_remediation_run(
    client: SaaSApiClient,
    run_id: str,
    *,
    timeout_sec: int,
    poll_sec: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.monotonic()
    history: list[dict[str, Any]] = []
    latest: dict[str, Any] = {}
    while True:
        latest = client.get_remediation_run(run_id)
        history.append({"polled_at": now_utc().isoformat(), "payload": redact_payload(latest)})
        status = str(latest.get("status") or "").lower()
        if status in {"success", "failed", "cancelled"}:
            return latest, history
        if time.monotonic() - started >= timeout_sec:
            raise RuntimeError(f"Timed out waiting for remediation run {run_id}")
        time.sleep(max(1, poll_sec))


def download_and_extract_bundle(client: SaaSApiClient, run_id: str, group_dir: Path) -> Path:
    zip_path = group_dir / "pr-bundle.zip"
    bundle_dir = group_dir / "bundle"
    write_bytes(zip_path, client.download_pr_bundle_zip(run_id))
    bundle_dir.mkdir(parents=True, exist_ok=True)
    extract_zip_safe(zip_path, bundle_dir)
    return bundle_dir


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def inspect_bundle(bundle_dir: Path) -> dict[str, Any]:
    manifest = read_json(bundle_dir / "bundle_manifest.json")
    actions = manifest.get("actions") if isinstance(manifest.get("actions"), list) else []
    executable = [item for item in actions if isinstance(item, dict) and item.get("tier") == "executable"]
    review = [item for item in actions if isinstance(item, dict) and item.get("tier") == "review_required"]
    manual = [item for item in actions if isinstance(item, dict) and item.get("tier") == "manual_guidance"]
    reasons = bundle_non_runnable_reasons(review, manual)
    return {
        "manifest": manifest,
        "runnable_action_count": len(executable),
        "review_required_action_count": len(review),
        "manual_guidance_action_count": len(manual),
        "has_run_all": (bundle_dir / "run_all.sh").exists(),
        "non_runnable_reasons": reasons,
    }


def bundle_non_runnable_reasons(review: list[dict[str, Any]], manual: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for item in review + manual:
        decision = read_reason_fields(item)
        reasons.append(decision)
    return reasons


def read_reason_fields(item: dict[str, Any]) -> dict[str, Any]:
    blocked = item.get("blocked_reasons") if isinstance(item.get("blocked_reasons"), list) else []
    return {
        "action_id": item.get("action_id"),
        "tier": item.get("tier"),
        "title": item.get("title"),
        "outcome": item.get("outcome"),
        "support_tier": item.get("support_tier"),
        "blocked_reasons": blocked,
        "decision_summary": item.get("decision_summary") or item.get("decision_rationale"),
    }


def execute_group_bundle(
    bundle_dir: Path,
    *,
    aws_profile: str | None,
    region: str | None,
    timeout_sec: int,
) -> tuple[bool, list[dict[str, Any]]]:
    env = os.environ.copy()
    if aws_profile:
        env["AWS_PROFILE"] = aws_profile
    if region:
        env["AWS_REGION"] = region
        env.setdefault("AWS_DEFAULT_REGION", region)
    records = [run_command(["chmod", "+x", "run_all.sh"], bundle_dir, 30, env)]
    for name in ("run_actions.sh", "replay_group_run_reports.sh"):
        if (bundle_dir / name).exists():
            records.append(run_command(["chmod", "+x", name], bundle_dir, 30, env))
    records.append(run_command(["bash", "./run_all.sh"], bundle_dir, timeout_sec, env))
    success = int(records[-1].get("exit_code") or 1) == 0
    return success, records


def poll_group_run(
    client: SaaSApiClient,
    *,
    group_id: str,
    group_run_id: str,
    timeout_sec: int,
    poll_sec: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.monotonic()
    history: list[dict[str, Any]] = []
    latest: dict[str, Any] = {}
    while True:
        latest = client.get_action_group_run(group_id, group_run_id)
        history.append({"polled_at": now_utc().isoformat(), "payload": redact_payload(latest)})
        status = str(latest.get("status") or "").lower()
        if status in {"finished", "failed", "cancelled"}:
            return latest, history
        if time.monotonic() - started >= timeout_sec:
            return latest, history
        time.sleep(max(1, poll_sec))


def classify_result(result: dict[str, Any]) -> str:
    if result.get("generation_status") != "success":
        return "GENERATION NOT SUCCESSFUL"
    if result.get("apply_status") == "failed":
        return "APPLY NOT SUCCESSFUL"
    if result.get("apply_status") == "success" and result.get("review_required_action_count", 0) > 0:
        return "APPLIED WITH REVIEW-REQUIRED LEFTOVERS"
    if result.get("apply_status") == "success":
        return "APPLY SUCCESSFUL"
    if result.get("runnable_action_count", 0) == 0 and result.get("review_required_action_count", 0) > 0:
        return "Needs review before apply"
    return "No runnable fix here"


def process_group(
    args: argparse.Namespace,
    *,
    token: str,
    run_id: str,
    group: dict[str, Any],
    index: int,
    output_dir: Path,
) -> dict[str, Any]:
    client = build_client(args, token)
    folder = group_folder_name(index, group)
    group_dir = output_dir / folder
    group_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "folder": folder,
        "group_id": group.get("id"),
        "action_type": group.get("action_type"),
        "account_id": group.get("account_id"),
        "region": group.get("region"),
        "generation_status": "not_started",
        "apply_status": "not_started",
    }
    try:
        detail = client.get_action_group_detail(str(group["id"]))
        write_json(group_dir / "group_detail.json", redact_payload(detail))
        action_id = representative_action_id(detail)
        options = client.get_remediation_options(action_id)
        write_json(group_dir / "options.json", redact_payload(options))
        candidates = build_request_candidates(options, action_type=str(group.get("action_type") or ""), run_id=run_id, folder=folder)
        write_json(group_dir / "request_candidates.json", redact_payload(candidates))
        created, attempts, selected = create_group_bundle_run(client, group_id=str(group["id"]), request_candidates=candidates)
        write_json(group_dir / "create_attempts.json", attempts)
        if created is None:
            result["generation_status"] = "failed"
            result["failure_reason"] = attempts[-1] if attempts else {"reason": "create_failed"}
            return finalize_group_result(group_dir, result)
        write_json(group_dir / "bundle_run_create.json", redact_payload(created))
        result["selected_request"] = redact_payload(selected)
        result["remediation_run_id"] = created.get("remediation_run_id")
        result["group_run_id"] = created.get("group_run_id")
        final_run, poll_history = poll_remediation_run(
            client,
            str(created["remediation_run_id"]),
            timeout_sec=args.run_timeout_sec,
            poll_sec=args.poll_interval_sec,
        )
        write_json(group_dir / "remediation_run_poll_history.json", poll_history)
        write_json(group_dir / "remediation_run_final.json", redact_payload(final_run))
        if str(final_run.get("status") or "").lower() != "success":
            result["generation_status"] = "failed"
            result["failure_reason"] = redact_payload(final_run)
            return finalize_group_result(group_dir, result)
        result["generation_status"] = "success"
        bundle_dir = download_and_extract_bundle(client, str(created["remediation_run_id"]), group_dir)
        inspection = inspect_bundle(bundle_dir)
        write_json(group_dir / "bundle_inspection.json", inspection)
        result.update(
            {
                "runnable_action_count": inspection["runnable_action_count"],
                "review_required_action_count": inspection["review_required_action_count"],
                "manual_guidance_action_count": inspection["manual_guidance_action_count"],
                "non_runnable_reasons": inspection["non_runnable_reasons"],
            }
        )
        if inspection["runnable_action_count"] == 0 or not inspection["has_run_all"]:
            result["apply_status"] = "skipped"
            return finalize_group_result(group_dir, result)
        apply_ok, transcript = execute_group_bundle(
            bundle_dir,
            aws_profile=args.aws_profile,
            region=str(group.get("region") or "") or None,
            timeout_sec=args.terraform_timeout_sec,
        )
        write_json(group_dir / "bundle_execution_transcript.json", transcript)
        result["apply_status"] = "success" if apply_ok else "failed"
        if created.get("group_run_id"):
            post_run, post_history = poll_group_run(
                client,
                group_id=str(group["id"]),
                group_run_id=str(created["group_run_id"]),
                timeout_sec=args.run_timeout_sec,
                poll_sec=args.poll_interval_sec,
            )
            write_json(group_dir / "group_run_poll_history.json", post_history)
            write_json(group_dir / "group_run_final.json", redact_payload(post_run))
        return finalize_group_result(group_dir, result)
    except Exception as exc:
        result["generation_status"] = result.get("generation_status") or "failed"
        if result["generation_status"] == "success" and result["apply_status"] == "not_started":
            result["apply_status"] = "failed"
        result["exception"] = str(exc)
        return finalize_group_result(group_dir, result)


def finalize_group_result(group_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    result["summary_status"] = classify_result(result)
    write_json(group_dir / "result.json", result)
    return result


def build_summary(run_id: str, account_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in results:
        label = str(item.get("summary_status") or "UNKNOWN")
        counts[label] = counts.get(label, 0) + 1
    return {
        "run_id": run_id,
        "account_id": account_id,
        "generated_at": now_utc().isoformat(),
        "group_count": len(results),
        "status_counts": counts,
        "results": results,
    }


def build_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Final Summary",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Account: `{summary['account_id']}`",
        f"- Groups processed: `{summary['group_count']}`",
        "",
        "## Status Counts",
        "",
    ]
    for key, value in sorted(summary.get("status_counts", {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Per-Group Results", ""])
    for item in summary.get("results", []):
        lines.append(f"### {item.get('folder')} — {item.get('summary_status')}")
        lines.append(f"- Group: `{item.get('group_id')}`")
        lines.append(f"- Action type: `{item.get('action_type')}`")
        lines.append(f"- Region: `{item.get('region')}`")
        if item.get("remediation_run_id"):
            lines.append(f"- Remediation run: `{item.get('remediation_run_id')}`")
        if item.get("group_run_id"):
            lines.append(f"- Group run: `{item.get('group_run_id')}`")
        lines.append(f"- Runnable actions: `{item.get('runnable_action_count', 0)}`")
        lines.append(f"- Review-required actions: `{item.get('review_required_action_count', 0)}`")
        if item.get("failure_reason"):
            lines.append(f"- Failure detail: `{json.dumps(item['failure_reason'], sort_keys=True)[:400]}`")
        if item.get("exception"):
            lines.append(f"- Exception: `{item.get('exception')}`")
        for reason in item.get("non_runnable_reasons", []):
            blocked = reason.get("blocked_reasons") or []
            if blocked:
                lines.append(f"- Why not runnable: `{'; '.join(str(x) for x in blocked)}`")
            elif reason.get("decision_summary"):
                lines.append(f"- Why not runnable: `{reason.get('decision_summary')}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    run_id = f"{utc_stamp()}-all-groups-pr-bundle-live"
    output_dir = resolve_output_dir(args, run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    email, password = prompt_credentials()
    client = build_client(args)
    login = client.login(email, password)
    token = str(login.get("access_token") or "").strip()
    write_json(output_dir / "login_response.json", redact_payload(login))
    me = client.get_me()
    write_json(output_dir / "auth_me.json", redact_payload(me))
    initial_groups = list_all_action_groups(client, account_id=args.account_id, page_size=args.page_size)
    write_json(output_dir / "groups_index_before_refresh.json", {"items": initial_groups, "total": len(initial_groups)})
    regions = sorted({str(item.get("region")) for item in initial_groups if item.get("region")})
    refresh = refresh_regions(client, account_id=args.account_id, regions=regions)
    write_json(output_dir / "refresh_state.json", redact_payload(refresh))
    groups = list_all_action_groups(client, account_id=args.account_id, page_size=args.page_size)
    write_json(output_dir / "groups_index.json", {"items": groups, "total": len(groups)})
    manifest = [
        {
            "folder": group_folder_name(index, group),
            "group_id": group.get("id"),
            "action_type": group.get("action_type"),
            "region": group.get("region"),
        }
        for index, group in enumerate(groups, start=1)
    ]
    write_json(output_dir / "grouped_execution_manifest.json", manifest)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as executor:
        futures = {
            executor.submit(
                process_group,
                args,
                token=token,
                run_id=run_id,
                group=group,
                index=index,
                output_dir=output_dir,
            ): str(group.get("id"))
            for index, group in enumerate(groups, start=1)
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: str(item.get("folder") or ""))
    summary = build_summary(run_id, args.account_id, results)
    write_json(output_dir / "summary.json", summary)
    write_text(output_dir / "notes/README.md", "# Notes\n\n- [Final summary](final-summary.md)\n")
    write_text(output_dir / "notes/final-summary.md", build_summary_markdown(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
