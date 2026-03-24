#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

try:
    from backend.config import settings
    from backend.services.database_failover import build_sync_connect_args, resolve_database_urls
    from scripts.lib.no_ui_agent_client import ApiError, SaaSApiClient
    from scripts.lib.no_ui_agent_terraform import TerraformError, run_command, run_terraform_apply
    from scripts.run_no_ui_pr_bundle_agent import extract_zip_safe, _find_reconciliation_run, _reconcile_services_for_control
    from backend.utils.sqs import (
        REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
        build_reconcile_inventory_shard_job_payload,
        build_remediation_run_job_payload,
    )
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.config import settings
    from backend.services.database_failover import build_sync_connect_args, resolve_database_urls
    from scripts.lib.no_ui_agent_client import ApiError, SaaSApiClient
    from scripts.lib.no_ui_agent_terraform import TerraformError, run_command, run_terraform_apply
    from scripts.run_no_ui_pr_bundle_agent import extract_zip_safe, _find_reconciliation_run, _reconcile_services_for_control
    from backend.utils.sqs import (
        REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
        build_reconcile_inventory_shard_job_payload,
        build_remediation_run_job_payload,
    )


@dataclass
class FamilyCandidate:
    tenant_id: str
    action_type: str
    account_id: str
    region: str | None
    status: str
    total_actions: int
    action_ids: list[str]
    representative_action_id: str
    control_ids: list[str]
    not_run_yet: int
    run_not_successful: int
    needs_followup: int
    metadata_only: int
    confirmed: int
    latest_artifacts: dict[str, Any] | None
    latest_run_id: str | None


RETRIABLE_CREATE_REASONS = {
    "missing_strategy_id",
    "dependency_check_failed",
    "invalid_strategy_inputs",
    "invalid_override_strategy",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all unresolved PR-bundle families locally against one account.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--aws-profile")
    parser.add_argument("--poll-interval-sec", type=int, default=10)
    parser.add_argument("--run-timeout-sec", type=int, default=1800)
    parser.add_argument("--terraform-timeout-sec", type=int, default=1800)
    parser.add_argument("--verify-timeout-sec", type=int, default=900)
    parser.add_argument(
        "--local-sync-refresh",
        action="store_true",
        help=(
            "Run ingest, compute, and inventory reconcile directly in the local process after bundle apply. "
            "Use this when local API credentials differ from the SaaS queue credentials."
        ),
    )
    return parser.parse_args()


def load_backend_env() -> None:
    for line in Path("backend/.env").read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item or item.startswith("#") or "=" not in item:
            continue
        key, value = item.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


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


def resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser().resolve()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("docs/test-results/live-runs") / f"{ts}-unresolved-pr-bundle-sweep"


def db_engine():
    resolved = resolve_database_urls()
    return create_engine(
        resolved.sync_url,
        connect_args=build_sync_connect_args(resolved.sync_url),
    )


def fetch_candidates(account_id: str) -> list[FamilyCandidate]:
    engine = db_engine()
    rows = _family_rows(engine, account_id)
    candidates = [_row_to_candidate(engine, row) for row in rows]
    return [item for item in candidates if item.total_actions > 0]


def _family_rows(engine, account_id: str) -> list[dict[str, Any]]:
    sql = text(
        """
        select a.tenant_id::text as tenant_id,
               a.action_type,
               a.account_id,
               a.region,
               a.status,
               array_agg(a.id::text order by a.priority desc, a.updated_at desc, a.created_at desc) as action_ids,
               array_agg(distinct coalesce(f.canonical_control_id, f.control_id)) filter (
                   where coalesce(f.canonical_control_id, f.control_id) is not null
               ) as control_ids,
               count(*) as total_actions,
               count(*) filter (where exists (
                   select 1 from exceptions e
                   where e.entity_type = 'action' and e.entity_id = a.id and e.expires_at > now()
               )) as active_exception_actions,
               count(*) filter (where coalesce(s.latest_run_status_bucket::text, 'not_run_yet') = 'not_run_yet') as not_run_yet,
               count(*) filter (where s.latest_run_status_bucket::text = 'run_not_successful') as run_not_successful,
               count(*) filter (where s.latest_run_status_bucket::text = 'run_successful_needs_followup') as needs_followup,
               count(*) filter (where s.latest_run_status_bucket::text = 'run_finished_metadata_only') as metadata_only,
               count(*) filter (where s.latest_run_status_bucket::text = 'run_successful_confirmed') as confirmed
        from actions a
        left join action_group_action_state s on s.action_id = a.id
        left join action_findings af on af.action_id = a.id
        left join findings f on f.id = af.finding_id
        where a.account_id = :account_id
          and a.status in ('open', 'in_progress')
        group by a.tenant_id, a.action_type, a.account_id, a.region, a.status
        having count(*) > 0
           and count(*) filter (where exists (
               select 1 from exceptions e
               where e.entity_type = 'action' and e.entity_id = a.id and e.expires_at > now()
           )) = 0
           and count(*) filter (where s.latest_run_status_bucket::text = 'run_successful_needs_followup') = 0
           and (
               count(*) filter (where coalesce(s.latest_run_status_bucket::text, 'not_run_yet') = 'not_run_yet') > 0
               or count(*) filter (where s.latest_run_status_bucket::text = 'run_not_successful') > 0
           )
        order by coalesce(a.region, ''), a.action_type
        """
    )
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql, {"account_id": account_id})]


def _row_to_candidate(engine, row: dict[str, Any]) -> FamilyCandidate:
    action_ids = [str(item) for item in list(row.get("action_ids") or []) if item]
    latest = _latest_run_for_family(engine, row["account_id"], row["action_type"], row["region"])
    return FamilyCandidate(
        tenant_id=str(row["tenant_id"]),
        action_type=str(row["action_type"]),
        account_id=str(row["account_id"]),
        region=str(row["region"]) if row["region"] is not None else None,
        status=str(row["status"]),
        total_actions=int(row["total_actions"]),
        action_ids=action_ids,
        representative_action_id=action_ids[0],
        control_ids=sorted(str(item) for item in list(row.get("control_ids") or []) if item),
        not_run_yet=int(row["not_run_yet"]),
        run_not_successful=int(row["run_not_successful"]),
        needs_followup=int(row["needs_followup"]),
        metadata_only=int(row["metadata_only"]),
        confirmed=int(row["confirmed"]),
        latest_artifacts=latest.get("artifacts") if latest else None,
        latest_run_id=latest.get("run_id") if latest else None,
    )


def _latest_run_for_family(engine, account_id: str, action_type: str, region: str | None) -> dict[str, Any] | None:
    sql = text(
        """
        select r.id::text as run_id, r.artifacts
        from remediation_runs r
        join actions a on a.id = r.action_id
        where a.account_id = :account_id
          and a.action_type = :action_type
          and ((:region is null and a.region is null) or a.region = :region)
        order by r.created_at desc
        limit 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"account_id": account_id, "action_type": action_type, "region": region}).mappings().first()
    return dict(row) if row else None


def build_request_candidates(client: SaaSApiClient, candidate: FamilyCandidate) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    artifact_body = _request_from_artifacts(candidate)
    if artifact_body is not None:
        candidates.append(_normalize_request_body(candidate, artifact_body))
    candidates.extend(_option_request_bodies(client, candidate))
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for body in candidates:
        signature = json.dumps(body, sort_keys=True, separators=(",", ":"))
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(body)
    if not deduped:
        raise ApiError(f"No remediation options available for action {candidate.representative_action_id}", status_code=400)
    return deduped


def _normalize_request_body(candidate: FamilyCandidate, body: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(body)
    normalized["action_type"] = candidate.action_type
    normalized["account_id"] = candidate.account_id
    normalized["status"] = candidate.status
    if candidate.region is None:
        normalized["region_is_null"] = True
        normalized.pop("region", None)
    else:
        normalized["region"] = candidate.region
        normalized.pop("region_is_null", None)
    normalized["risk_acknowledged"] = bool(normalized.get("risk_acknowledged", True))
    normalized["bucket_creation_acknowledged"] = bool(
        normalized.get("bucket_creation_acknowledged", candidate.action_type == "cloudtrail_enabled")
    )
    return normalized


def _request_from_artifacts(candidate: FamilyCandidate) -> dict[str, Any] | None:
    artifacts = candidate.latest_artifacts
    if not isinstance(artifacts, dict):
        return None
    strategy_id = str(artifacts.get("selected_strategy") or "").strip()
    if not strategy_id:
        return None
    body: dict[str, Any] = {
        "strategy_id": strategy_id,
        "strategy_inputs": artifacts.get("strategy_inputs"),
        "pr_bundle_variant": artifacts.get("pr_bundle_variant"),
        "repo_target": artifacts.get("repo_target"),
        "risk_acknowledged": bool(artifacts.get("risk_acknowledged")),
        "bucket_creation_acknowledged": "cloudtrail_bucket_creation_approval" in artifacts,
        "action_overrides": [],
    }
    resolutions = _artifact_action_resolutions(artifacts)
    for item in resolutions:
        action_id = str(item.get("action_id") or "")
        if action_id not in set(candidate.action_ids):
            continue
        override = {
            "action_id": action_id,
            "strategy_id": item.get("strategy_id"),
            "profile_id": item.get("profile_id"),
            "strategy_inputs": item.get("strategy_inputs"),
        }
        if _override_has_value(override, body):
            body["action_overrides"].append(override)
    return _compact_body(body)


def _artifact_action_resolutions(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    group_bundle = artifacts.get("group_bundle") if isinstance(artifacts.get("group_bundle"), dict) else {}
    rows = group_bundle.get("action_resolutions") if isinstance(group_bundle.get("action_resolutions"), list) else []
    return [item for item in rows if isinstance(item, dict)]


def _override_has_value(override: dict[str, Any], body: dict[str, Any]) -> bool:
    if override.get("strategy_id") and override.get("strategy_id") != body.get("strategy_id"):
        return True
    if override.get("profile_id") and override.get("profile_id") != override.get("strategy_id"):
        return True
    return bool(override.get("strategy_inputs"))


def _compact_body(body: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in body.items():
        if key == "action_overrides" and not value:
            continue
        if value in (None, "", []):
            continue
        compact[key] = value
    return compact


def _option_request_bodies(client: SaaSApiClient, candidate: FamilyCandidate) -> list[dict[str, Any]]:
    payload = client.get_remediation_options(candidate.representative_action_id)
    strategies = payload.get("strategies") if isinstance(payload.get("strategies"), list) else []
    ordered = sorted(
        (item for item in strategies if isinstance(item, dict)),
        key=lambda item: (0 if item.get("recommended") else 1, str(item.get("strategy_id") or "")),
    )
    requests: list[dict[str, Any]] = []
    for selected in ordered:
        strategy_id = str(selected.get("strategy_id") or "").strip()
        if not strategy_id:
            continue
        body: dict[str, Any] = {
            "strategy_id": strategy_id,
            "risk_acknowledged": True,
            "bucket_creation_acknowledged": candidate.action_type == "cloudtrail_enabled",
        }
        input_schema = selected.get("input_schema") if isinstance(selected.get("input_schema"), dict) else {}
        strategy_inputs = _safe_default_strategy_inputs(candidate, input_schema)
        if strategy_inputs:
            body["strategy_inputs"] = strategy_inputs
        recommended_profile_id = str(selected.get("recommended_profile_id") or "").strip()
        if recommended_profile_id and recommended_profile_id != strategy_id:
            body["action_overrides"] = [
                {
                    "action_id": candidate.representative_action_id,
                    "strategy_id": strategy_id,
                    "profile_id": recommended_profile_id,
                    "strategy_inputs": dict(strategy_inputs),
                }
            ]
        requests.append(_normalize_request_body(candidate, _compact_body(body)))
    return requests


def _safe_default_strategy_inputs(candidate: FamilyCandidate, input_schema: dict[str, Any]) -> dict[str, Any]:
    fields = input_schema.get("fields") if isinstance(input_schema.get("fields"), list) else []
    resolved: dict[str, Any] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "").strip()
        if not key:
            continue
        if not field.get("required"):
            continue
        if "safe_default_value" not in field:
            continue
        rendered = _render_safe_default(candidate, field.get("safe_default_value"))
        if rendered in (None, ""):
            continue
        resolved[key] = rendered
    return resolved


def _render_safe_default(candidate: FamilyCandidate, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    rendered = value
    replacements = {
        "{{account_id}}": candidate.account_id,
        "{{region}}": candidate.region or "",
    }
    for needle, replacement in replacements.items():
        rendered = rendered.replace(needle, replacement)
    return rendered


def _extract_reason(payload: Any) -> str | None:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            reason = detail.get("reason")
            if isinstance(reason, str) and reason.strip():
                return reason.strip()
    return None


def _extract_existing_run_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            run_id = detail.get("existing_run_id")
            if isinstance(run_id, str) and run_id.strip():
                return run_id.strip()
    return None


def _group_id_for_candidate(candidate: FamilyCandidate) -> str:
    engine = db_engine()
    sql = text(
        """
        select g.id::text as group_id
        from action_group_memberships m
        join action_groups g
          on g.id = m.group_id
         and g.tenant_id = m.tenant_id
        where m.action_id = :action_id
        limit 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"action_id": candidate.representative_action_id}).mappings().first()
    group_id = str((row or {}).get("group_id") or "").strip()
    if not group_id:
        raise RuntimeError(f"No action group found for action {candidate.representative_action_id}")
    return group_id


def _action_group_request_body(body: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "strategy_id",
        "strategy_inputs",
        "action_overrides",
        "risk_acknowledged",
        "bucket_creation_acknowledged",
        "pr_bundle_variant",
        "repo_target",
    )
    compact: dict[str, Any] = {}
    for key in allowed:
        value = body.get(key)
        if key == "action_overrides" and not value:
            continue
        if value in (None, "", []):
            continue
        compact[key] = value
    return compact


def _create_or_reuse_run(
    client: SaaSApiClient,
    candidate: FamilyCandidate,
    request_bodies: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    group_id = _group_id_for_candidate(candidate)
    attempts: list[dict[str, Any]] = []
    last_error: ApiError | None = None
    for body in request_bodies:
        group_body = _action_group_request_body(body)
        try:
            created = client.create_action_group_bundle_run(group_id, group_body)
            run_id = str(created.get("remediation_run_id") or "").strip()
            if not run_id:
                raise RuntimeError("Action-group bundle response did not include remediation_run_id")
            return group_id, body, created, client.get_remediation_run(run_id), attempts
        except ApiError as exc:
            reason = _extract_reason(exc.payload)
            attempts.append(
                {
                    "request_body": body,
                    "group_request_body": group_body,
                    "status_code": exc.status_code,
                    "reason": reason,
                    "message": str(exc),
                    "payload": exc.payload,
                }
            )
            existing_run_id = _extract_existing_run_id(exc.payload)
            if reason == "grouped_bundle_already_created_no_changes" and existing_run_id:
                return group_id, body, {"reused_existing_run_id": existing_run_id, "reason": reason}, client.get_remediation_run(existing_run_id), attempts
            if reason == "duplicate_pending_group_run" and existing_run_id:
                return group_id, body, {"reused_existing_run_id": existing_run_id, "reason": reason}, client.get_remediation_run(existing_run_id), attempts
            if exc.status_code == 400 and reason in RETRIABLE_CREATE_REASONS:
                last_error = exc
                continue
            raise
    if last_error is not None:
        raise last_error
    raise ApiError("No grouped PR-bundle request body could be created", status_code=400)


def poll_run_success(client: SaaSApiClient, run_id: str, *, timeout_sec: int, poll_sec: int) -> dict[str, Any]:
    started = time.monotonic()
    while True:
        payload = client.get_remediation_run(run_id)
        status = str(payload.get("status") or "").lower()
        if status == "success":
            return payload
        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"Run {run_id} ended with status={status}")
        if (time.monotonic() - started) >= timeout_sec:
            raise RuntimeError(f"Timed out waiting for remediation run {run_id}")
        time.sleep(max(1, poll_sec))


def run_bundle(workspace: Path, *, aws_profile: str | None, region: str | None, timeout_sec: int) -> list[dict[str, Any]]:
    env = os.environ.copy()
    if aws_profile:
        env["AWS_PROFILE"] = aws_profile
    if region:
        env["AWS_REGION"] = region
        env.setdefault("AWS_DEFAULT_REGION", region)
    if (workspace / "run_all.sh").exists():
        return _run_group_bundle(workspace, env, timeout_sec)
    return _run_single_bundle(workspace, env, timeout_sec)


def _run_group_bundle(workspace: Path, env: dict[str, str], timeout_sec: int) -> list[dict[str, Any]]:
    records = [run_command(["chmod", "+x", "run_all.sh"], workspace, 30, env)]
    for name in ("run_actions.sh", "replay_group_run_reports.sh"):
        path = workspace / name
        if path.exists():
            records.append(run_command(["chmod", "+x", name], workspace, 30, env))
    records.append(run_command(["bash", "./run_all.sh"], workspace, timeout_sec, env))
    if int(records[-1]["exit_code"]) != 0:
        raise RuntimeError("Grouped bundle execution failed")
    return records


def _run_single_bundle(workspace: Path, env: dict[str, str], timeout_sec: int) -> list[dict[str, Any]]:
    try:
        return run_terraform_apply(workspace, timeout_sec, env=env)
    except TerraformError as exc:
        raise RuntimeError(str(exc)) from exc


def refresh_family(
    client: SaaSApiClient,
    candidate: FamilyCandidate,
    *,
    poll_sec: int,
    timeout_sec: int,
    local_sync_refresh: bool,
) -> dict[str, Any]:
    if local_sync_refresh:
        return _refresh_family_locally(candidate)
    ingest = client.trigger_ingest(candidate.account_id, [candidate.region] if candidate.region else [])
    compute = client.trigger_compute_actions(candidate.account_id, candidate.region or "")
    reconcile = _trigger_reconcile(client, candidate, poll_sec=poll_sec, timeout_sec=timeout_sec)
    return {"ingest": ingest, "compute": compute, "reconcile": reconcile}


def _trigger_reconcile(client: SaaSApiClient, candidate: FamilyCandidate, *, poll_sec: int, timeout_sec: int) -> dict[str, Any]:
    control_id = candidate.control_ids[0] if candidate.control_ids else ""
    services = _reconcile_services_for_control(control_id)
    if not services or candidate.region is None:
        return {"skipped": True, "reason": "no_reconcile_service"}
    response = client.trigger_reconciliation_run(
        account_id=candidate.account_id,
        regions=[candidate.region],
        services=services,
        require_preflight_pass=False,
        force=True,
        sweep_mode="global",
        max_resources=500,
    )
    run_id = str(response.get("run_id") or "")
    if not run_id:
        return {"trigger": response, "status": "missing_run_id"}
    started = time.monotonic()
    while True:
        status_payload = client.get_reconciliation_status(candidate.account_id, limit=100)
        run = _find_reconciliation_run(status_payload, run_id)
        status = str((run or {}).get("status") or "").lower()
        if status in {"succeeded", "partial_failed", "failed"}:
            return {"trigger": response, "run": run, "status": status}
        if (time.monotonic() - started) >= timeout_sec:
            return {"trigger": response, "run": run, "status": "timeout"}
        time.sleep(max(1, poll_sec))


def _refresh_family_locally(candidate: FamilyCandidate) -> dict[str, Any]:
    if candidate.region is None:
        return {"skipped": True, "reason": "region_required_for_local_refresh"}
    tenant_uuid = uuid.UUID(candidate.tenant_id)
    created_at = datetime.now(timezone.utc).isoformat()
    reconcile = _run_reconcile_jobs_locally(candidate, tenant_uuid=tenant_uuid, created_at=created_at)
    compute = _run_compute_locally(candidate, tenant_uuid=tenant_uuid)
    return {
        "mode": "local_sync_refresh",
        "ingest": {"skipped": True, "reason": "inventory_reconcile_only"},
        "reconcile": reconcile,
        "compute_after_reconcile": compute,
    }


@contextmanager
def _local_target_account_profile(profile_name: str | None):
    if not profile_name:
        yield
        return
    previous_allow = settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION
    previous_profile = settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE
    previous_env_allow = os.environ.get("ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION")
    previous_env_profile = os.environ.get("LOCAL_TARGET_ACCOUNT_AWS_PROFILE")
    settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION = True
    settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE = profile_name
    os.environ["ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION"] = "true"
    os.environ["LOCAL_TARGET_ACCOUNT_AWS_PROFILE"] = profile_name
    try:
        yield
    finally:
        settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION = previous_allow
        settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE = previous_profile
        if previous_env_allow is None:
            os.environ.pop("ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION", None)
        else:
            os.environ["ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION"] = previous_env_allow
        if previous_env_profile is None:
            os.environ.pop("LOCAL_TARGET_ACCOUNT_AWS_PROFILE", None)
        else:
            os.environ["LOCAL_TARGET_ACCOUNT_AWS_PROFILE"] = previous_env_profile


def _replay_group_reports_if_present(client: SaaSApiClient, workspace: Path) -> dict[str, Any]:
    replay_dir = workspace / ".bundle-callback-replay"
    if not replay_dir.is_dir():
        return {"skipped": True, "reason": "no_group_report_payloads"}
    payload_files = sorted(replay_dir.glob("*.json"))
    if not payload_files:
        return {"skipped": True, "reason": "no_group_report_payloads"}
    responses: list[dict[str, Any]] = []
    for payload_path in payload_files:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        response = client.report_group_run(payload)
        responses.append({"file": payload_path.name, "response": response})
        payload_path.unlink()
    return {"status": "completed", "count": len(responses), "responses": responses}


def _execute_run_locally(
    candidate: FamilyCandidate,
    run_payload: dict[str, Any],
    *,
    request_body: dict[str, Any],
) -> dict[str, Any]:
    from backend.workers.jobs.remediation_run import execute_remediation_run_job

    run_id = uuid.UUID(str(run_payload.get("id") or ""))
    action_id = uuid.UUID(str(run_payload.get("action_id") or candidate.representative_action_id))
    created_at = str(run_payload.get("created_at") or datetime.now(timezone.utc).isoformat())
    mode = str(run_payload.get("mode") or "pr_only")
    artifacts = run_payload.get("artifacts") if isinstance(run_payload.get("artifacts"), dict) else {}
    group_bundle = artifacts.get("group_bundle") if isinstance(artifacts.get("group_bundle"), dict) else {}
    group_action_ids = [
        str(action_id)
        for action_id in list(group_bundle.get("action_ids") or candidate.action_ids)
        if isinstance(action_id, str) and action_id.strip()
    ]
    job = build_remediation_run_job_payload(
        run_id=run_id,
        tenant_id=uuid.UUID(candidate.tenant_id),
        action_id=action_id,
        mode=mode,
        created_at=created_at,
        pr_bundle_variant=request_body.get("pr_bundle_variant") or artifacts.get("pr_bundle_variant"),
        strategy_id=request_body.get("strategy_id") or artifacts.get("selected_strategy"),
        strategy_inputs=request_body.get("strategy_inputs") or artifacts.get("strategy_inputs"),
        risk_acknowledged=bool(request_body.get("risk_acknowledged", artifacts.get("risk_acknowledged"))),
        group_action_ids=group_action_ids,
        repo_target=request_body.get("repo_target") or artifacts.get("repo_target"),
        action_resolutions=_artifact_action_resolutions(artifacts),
        schema_version=REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
    )
    started = time.monotonic()
    execute_remediation_run_job(job)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "status": "completed",
        "elapsed_ms": elapsed_ms,
        "job": job,
    }


def _run_reconcile_jobs_locally(candidate: FamilyCandidate, *, tenant_uuid: uuid.UUID, created_at: str) -> dict[str, Any]:
    from backend.workers.jobs.reconcile_inventory_shard import execute_reconcile_inventory_shard_job

    control_id = candidate.control_ids[0] if candidate.control_ids else ""
    services = _reconcile_services_for_control(control_id)
    if not services or candidate.region is None:
        return {"skipped": True, "reason": "no_reconcile_service"}
    jobs: list[dict[str, Any]] = []
    for service in services:
        job = build_reconcile_inventory_shard_job_payload(
            tenant_id=tenant_uuid,
            account_id=candidate.account_id,
            region=candidate.region,
            service=service,
            created_at=created_at,
            sweep_mode="global",
            max_resources=500,
        )
        execute_reconcile_inventory_shard_job(job)
        jobs.append(job)
    return {"status": "completed", "jobs": jobs}


def _run_compute_locally(candidate: FamilyCandidate, *, tenant_uuid: uuid.UUID) -> dict[str, Any]:
    from backend.services.action_engine import compute_actions_for_tenant
    from backend.workers.database import session_scope

    started = time.monotonic()
    with session_scope() as session:
        result = compute_actions_for_tenant(
            session,
            tenant_id=tenant_uuid,
            account_id=candidate.account_id,
            region=candidate.region,
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "status": "completed",
        "tenant_id": candidate.tenant_id,
        "account_id": candidate.account_id,
        "region": candidate.region,
        "elapsed_ms": elapsed_ms,
        "result": result,
    }


def snapshot_family(candidate: FamilyCandidate) -> dict[str, Any]:
    engine = db_engine()
    sql = text(
        """
        select count(*) as open_actions,
               count(*) filter (where coalesce(s.latest_run_status_bucket::text, 'not_run_yet') = 'not_run_yet') as not_run_yet,
               count(*) filter (where s.latest_run_status_bucket::text = 'run_not_successful') as run_not_successful,
               count(*) filter (where s.latest_run_status_bucket::text = 'run_successful_pending_confirmation') as pending_confirmation,
               count(*) filter (where s.latest_run_status_bucket::text = 'run_successful_confirmed') as confirmed
        from actions a
        left join action_group_action_state s on s.action_id = a.id
        where a.account_id = :account_id
          and a.action_type = :action_type
          and a.status in ('open', 'in_progress')
          and ((:region is null and a.region is null) or a.region = :region)
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"account_id": candidate.account_id, "action_type": candidate.action_type, "region": candidate.region}).mappings().first()
    return dict(row or {})


def family_converged(snapshot: dict[str, Any]) -> bool:
    return int(snapshot.get("not_run_yet") or 0) == 0 and int(snapshot.get("run_not_successful") or 0) == 0


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    load_backend_env()
    email, password = prompt_credentials()
    output_dir = resolve_output_dir(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    client = SaaSApiClient(api_base=args.api_base, timeout_sec=30, retries=3, retry_backoff_sec=1.0)
    client.login(email, password)
    write_json(output_dir / "login_context.json", client.get_me())
    candidates = fetch_candidates(args.account_id)
    write_json(output_dir / "candidates.json", [asdict(item) for item in candidates])
    results: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        family_dir = output_dir / f"{index:02d}-{candidate.region or 'global'}-{candidate.action_type}"
        result = run_candidate(client, candidate, family_dir, args)
        results.append(result)
        write_json(family_dir / "result.json", result)
    final_candidates = fetch_candidates(args.account_id)
    summary = {
        "account_id": args.account_id,
        "local_sync_refresh": bool(args.local_sync_refresh),
        "initial_candidate_count": len(candidates),
        "final_candidate_count": len(final_candidates),
        "final_candidates": [asdict(item) for item in final_candidates],
        "results": results,
    }
    write_json(output_dir / "summary.json", summary)
    return 0 if all(item.get("status") == "passed" for item in results) else 1


def run_candidate(client: SaaSApiClient, candidate: FamilyCandidate, family_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    family_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"candidate": asdict(candidate), "status": "failed"}
    result["before"] = snapshot_family(candidate)
    try:
        request_candidates = build_request_candidates(client, candidate)
        result["request_candidates"] = request_candidates
        group_id, request_body, created, run_payload, create_attempts = _create_or_reuse_run(client, candidate, request_candidates)
        result["group_id"] = group_id
        result["request_body"] = request_body
        if create_attempts:
            result["create_attempts"] = create_attempts
        result["run_create"] = created
        run_id = str(run_payload.get("id") or "")
        if not run_id:
            raise RuntimeError("Grouped PR-bundle create response did not include a run id")
        if args.local_sync_refresh:
            status = str(run_payload.get("status") or "").lower()
            result["run_before_local_execution"] = run_payload
            if status not in {"success", "failed", "cancelled"}:
                with _local_target_account_profile(args.aws_profile):
                    result["local_run_execution"] = _execute_run_locally(
                        candidate,
                        run_payload,
                        request_body=request_body,
                    )
        result["run_final"] = poll_run_success(client, run_id, timeout_sec=args.run_timeout_sec, poll_sec=args.poll_interval_sec)
        zip_bytes = client.download_pr_bundle_zip(run_id)
        zip_path = family_dir / f"pr-bundle-{run_id}.zip"
        zip_path.write_bytes(zip_bytes)
        workspace = family_dir / "bundle"
        workspace.mkdir(exist_ok=True)
        extract_zip_safe(zip_path, workspace)
        result["terraform_transcript"] = run_bundle(
            workspace,
            aws_profile=args.aws_profile or os.environ.get("AWS_PROFILE"),
            region=candidate.region,
            timeout_sec=args.terraform_timeout_sec,
        )
        result["group_report_replay"] = _replay_group_reports_if_present(client, workspace)
        with _local_target_account_profile(args.aws_profile if args.local_sync_refresh else None):
            result["refresh"] = refresh_family(
                client,
                candidate,
                poll_sec=args.poll_interval_sec,
                timeout_sec=args.verify_timeout_sec,
                local_sync_refresh=bool(args.local_sync_refresh),
            )
        result["after"] = snapshot_family(candidate)
        if not family_converged(result["after"]):
            raise RuntimeError(
                "Family remained unresolved after local apply and refresh "
                f"(not_run_yet={result['after'].get('not_run_yet')}, "
                f"run_not_successful={result['after'].get('run_not_successful')})"
            )
        result["status"] = "passed"
    except Exception as exc:
        result["error"] = str(exc)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
