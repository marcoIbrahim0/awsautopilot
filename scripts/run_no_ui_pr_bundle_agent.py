#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from zipfile import ZipFile

import boto3
import sqlalchemy as sa

try:
    from scripts.lib.no_ui_agent_client import ApiError, SaaSApiClient
    from scripts.lib.no_ui_agent_state import CheckpointManager
    from scripts.lib.no_ui_agent_stats import (
        aggregate_findings,
        compute_delta,
        select_pr_only_strategy,
        select_target_finding,
    )
    from scripts.lib.no_ui_agent_terraform import TerraformError, run_terraform_apply
except ImportError:  # pragma: no cover
    from lib.no_ui_agent_client import ApiError, SaaSApiClient
    from lib.no_ui_agent_state import CheckpointManager
    from lib.no_ui_agent_stats import (
        aggregate_findings,
        compute_delta,
        select_pr_only_strategy,
        select_target_finding,
    )
    from lib.no_ui_agent_terraform import TerraformError, run_terraform_apply


PHASES = [
    "auth",
    "readiness",
    "pre_snapshot",
    "target_select",
    "strategy_select",
    "run_create",
    "run_poll",
    "bundle_download",
    "terraform_apply",
    "refresh",
    "verification_poll",
    "post_snapshot",
    "report",
]


POLL_PHASES = {"run_poll", "verification_poll"}
RUNTIME_API_FUNCTION_NAME = "security-autopilot-dev-api"


class AgentConfigError(Exception):
    pass


class AgentValidationError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated no-UI PR-bundle validation agent")
    parser.add_argument("--api-base")
    parser.add_argument("--account-id")
    parser.add_argument("--region")
    parser.add_argument("--config")
    parser.add_argument("--output-dir")
    parser.add_argument("--control-preference")
    parser.add_argument("--poll-interval-sec", type=int)
    parser.add_argument("--phase-timeout-sec", type=int)
    parser.add_argument("--run-timeout-sec", type=int)
    parser.add_argument("--verify-timeout-sec", type=int)
    parser.add_argument("--terraform-timeout-sec", type=int)
    parser.add_argument("--stale-resend-sec", type=int)
    parser.add_argument("--resume-from-checkpoint", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--allow-insecure-http", action="store_true")
    parser.add_argument("--client-timeout-sec", type=int)
    parser.add_argument("--client-retries", type=int)
    parser.add_argument("--client-retry-backoff-sec", type=float)
    parser.add_argument("--reconcile-timeout-sec", type=int)
    parser.add_argument("--reconcile-poll-interval-sec", type=int)
    parser.add_argument("--reconcile-after-apply", dest="reconcile_after_apply", action="store_true")
    parser.add_argument("--no-reconcile-after-apply", dest="reconcile_after_apply", action="store_false")
    parser.set_defaults(reconcile_after_apply=None)
    return parser.parse_args()


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise AgentConfigError(f"Config file not found: {config_path}")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AgentConfigError("Config file must contain a JSON object")
    return payload


def merge_settings(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    def pick(name: str, default: Any) -> Any:
        value = getattr(args, name)
        if value is not None:
            return value
        if name in config:
            return config[name]
        return default

    control_pref = pick("control_preference", "EC2.53,S3.2")
    output_dir = pick("output_dir", "")

    settings = {
        "api_base": pick("api_base", ""),
        "account_id": pick("account_id", ""),
        "region": pick("region", ""),
        "output_dir": str(output_dir).strip(),
        "control_preference": [x.strip() for x in str(control_pref).split(",") if x.strip()],
        "poll_interval_sec": int(pick("poll_interval_sec", 10)),
        "phase_timeout_sec": int(pick("phase_timeout_sec", 300)),
        "run_timeout_sec": int(pick("run_timeout_sec", 1800)),
        "verify_timeout_sec": int(pick("verify_timeout_sec", 900)),
        "terraform_timeout_sec": int(pick("terraform_timeout_sec", 900)),
        "stale_resend_sec": int(pick("stale_resend_sec", 120)),
        "reconcile_timeout_sec": int(pick("reconcile_timeout_sec", 900)),
        "reconcile_poll_interval_sec": int(pick("reconcile_poll_interval_sec", 10)),
        "reconcile_after_apply": (
            bool(pick("reconcile_after_apply", True))
            if pick("reconcile_after_apply", True) is not None
            else True
        ),
        "resume_from_checkpoint": bool(args.resume_from_checkpoint or config.get("resume_from_checkpoint", False)),
        "dry_run": bool(args.dry_run or config.get("dry_run", False)),
        "keep_workdir": bool(args.keep_workdir or config.get("keep_workdir", False)),
        "allow_insecure_http": bool(args.allow_insecure_http or config.get("allow_insecure_http", False)),
        "client_timeout_sec": int(pick("client_timeout_sec", 30)),
        "client_retries": int(pick("client_retries", 3)),
        "client_retry_backoff_sec": float(pick("client_retry_backoff_sec", 1.0)),
    }
    validate_settings(settings)
    return settings


def validate_settings(settings: dict[str, Any]) -> None:
    for key in ("api_base", "account_id", "region"):
        if not str(settings.get(key) or "").strip():
            raise AgentConfigError(f"Missing required setting: {key}")

    api_base = str(settings["api_base"]).strip().lower()
    if api_base.startswith("https://"):
        return
    if api_base.startswith("http://") and bool(settings.get("allow_insecure_http")):
        return
    raise AgentConfigError("api-base must be HTTPS (or use --allow-insecure-http)")


def resolve_output_dir(settings: dict[str, Any]) -> Path:
    if settings["output_dir"]:
        return Path(settings["output_dir"]).expanduser().resolve()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("artifacts/no-ui-agent") / ts


def prompt_credentials() -> tuple[str, str]:
    email = str(os.environ.get("SAAS_EMAIL") or "").strip()
    password = str(os.environ.get("SAAS_PASSWORD") or "").strip()
    if not email:
        email = input("SaaS email: ").strip()
    if not password:
        password = getpass.getpass("SaaS password: ").strip()
    if not email or not password:
        raise AgentConfigError("Both email and password are required")
    return email, password


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _to_sync_database_url(raw: str | None) -> str:
    text = str(raw or "").strip()
    if text.startswith("postgresql+asyncpg://"):
        return text.replace("postgresql+asyncpg://", "postgresql://", 1)
    return text


def _normalize_region_list(values: Sequence[str] | None, fallback: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        token = str(value or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out or [fallback]


def _stale_control_plane_regions(control: dict[str, Any], fallback_region: str) -> list[str]:
    missing = control.get("missing_regions")
    if isinstance(missing, list) and missing:
        return _normalize_region_list([str(v) for v in missing], fallback_region)
    regions_raw = control.get("regions")
    if isinstance(regions_raw, list):
        stale = [
            str((row or {}).get("region") or "")
            for row in regions_raw
            if isinstance(row, dict) and not bool(row.get("is_recent"))
        ]
        return _normalize_region_list(stale, fallback_region)
    return [fallback_region]


def _strategy_sort_key(strategy: dict[str, Any]) -> tuple[int, str]:
    recommended = bool(strategy.get("recommended"))
    strategy_id = str(strategy.get("strategy_id") or "")
    return (0 if recommended else 1, strategy_id)


class NoUiPrBundleAgent:
    def __init__(
        self,
        settings: dict[str, Any],
        output_dir: Path,
        email: str,
        password: str,
        client_factory: Callable[..., SaaSApiClient] = SaaSApiClient,
        terraform_runner: Callable[..., list[dict[str, Any]]] = run_terraform_apply,
    ):
        self.settings = settings
        self.output_dir = output_dir
        self.email = email
        self.password = password
        self.output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self.output_dir / "checkpoint.json"
        self.state = CheckpointManager.create_or_resume(checkpoint_path, settings["resume_from_checkpoint"])
        self.client = client_factory(
            settings["api_base"],
            timeout_sec=settings["client_timeout_sec"],
            retries=int(settings.get("client_retries", 3)),
            retry_backoff_sec=float(settings.get("client_retry_backoff_sec", 1.0)),
        )
        self.terraform_runner = terraform_runner
        self.exit_code = 0
        self.final_status = "success"

    def run(self) -> int:
        failure: Exception | None = None
        for phase in PHASES:
            if self.state.is_phase_complete(phase):
                continue
            try:
                self._execute_phase(phase)
            except Exception as exc:
                failure = exc
                break

        if failure is not None:
            self._handle_failure(failure)

        self._ensure_pre_snapshot_exists()
        self._ensure_post_snapshot_exists()
        self._ensure_terraform_transcript_exists()
        self._write_api_transcript()
        try:
            self._cleanup_workspace_if_needed()
        except Exception as exc:  # pragma: no cover
            self._handle_failure(exc)
        self._write_reports()
        self.state.finalize(self.final_status, self.exit_code)
        return self.exit_code

    def _execute_phase(self, phase: str) -> None:
        method = getattr(self, f"phase_{phase}")
        started = time.monotonic()
        method()
        elapsed = time.monotonic() - started
        timeout_sec = self._phase_timeout_limit_sec(phase)
        if phase not in POLL_PHASES and elapsed > timeout_sec:
            raise AgentValidationError(f"Phase exceeded timeout: {phase}")
        self.state.mark_phase_complete(phase)

    def _phase_timeout_limit_sec(self, phase: str) -> int:
        """
        Resolve timeout budget for a phase.

        `refresh` can include reconciliation polling, so its budget must be at
        least the configured reconciliation timeout (plus one poll interval and
        small cushion) to avoid false timeout failures.
        """
        base = int(self.settings.get("phase_timeout_sec", 300))
        if phase == "refresh" and bool(self.settings.get("reconcile_after_apply", True)):
            reconcile_timeout = int(self.settings.get("reconcile_timeout_sec", base))
            reconcile_poll = int(self.settings.get("reconcile_poll_interval_sec", 10))
            return max(base, reconcile_timeout + reconcile_poll + 30)
        return base

    def _is_target_select_noop(self) -> bool:
        return bool(self.state.checkpoint.context.get("no_target_noop"))

    def _target_select_noop_reason(self) -> str:
        token = str(self.state.checkpoint.context.get("no_target_noop_reason") or "").strip()
        return token or "no_eligible_finding_for_preferred_control"

    def phase_auth(self) -> None:
        login = self.client.login(self.email, self.password)
        me = self.client.get_me()
        tenant = me.get("tenant") if isinstance(me.get("tenant"), dict) else {}
        user = me.get("user") if isinstance(me.get("user"), dict) else {}
        self.state.set_context("tenant_id", str(tenant.get("id") or ""))
        self.state.set_context("user_id", str(user.get("id") or ""))
        self.state.set_context("login_response", _safe_subset(login, ["tenant", "user"]))

    def phase_readiness(self) -> None:
        account_id = self.settings["account_id"]
        service = self.client.check_service_readiness(account_id)
        control = self.client.check_control_plane_readiness(account_id, stale_after_minutes=30)
        self_heal: dict[str, Any] | None = None

        if bool(service.get("overall_ready")) and not bool(control.get("overall_ready")):
            regions = _stale_control_plane_regions(control, self.settings["region"])
            self_heal = self._attempt_control_plane_self_heal(account_id, regions)
            control = self.client.check_control_plane_readiness(account_id, stale_after_minutes=30)

        payload: dict[str, Any] = {"service": service, "control_plane": control}
        if self_heal is not None:
            payload["control_plane_self_heal"] = self_heal
        write_json(self.output_dir / "readiness.json", payload)

        if not bool(service.get("overall_ready")):
            raise AgentValidationError("Service readiness failed: required services are not fully enabled")
        if not bool(control.get("overall_ready")):
            missing = ", ".join(control.get("missing_regions") or [])
            raise AgentValidationError(f"Control-plane readiness failed (missing: {missing})")

    def _attempt_control_plane_self_heal(self, account_id: str, regions: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {"attempted": True, "regions": list(regions)}
        try:
            result["ingest"] = self.client.trigger_ingest(account_id, regions)
        except Exception as exc:
            result["ingest_error"] = str(exc)
        result["db_rehydrate"] = self._rehydrate_control_plane_ingest_status(account_id, regions)
        return result

    def _resolve_runtime_database_url(self) -> str:
        env_sync = _to_sync_database_url(os.environ.get("DATABASE_URL_SYNC"))
        if env_sync:
            return env_sync
        env_async = _to_sync_database_url(os.environ.get("DATABASE_URL"))
        if env_async:
            return env_async
        lambda_region = str(self.settings.get("region") or "eu-north-1")
        try:
            conf = boto3.client("lambda", region_name=lambda_region).get_function_configuration(
                FunctionName=RUNTIME_API_FUNCTION_NAME
            )
            vars_payload = (conf.get("Environment", {}).get("Variables") or {})
            remote_sync = _to_sync_database_url(vars_payload.get("DATABASE_URL_SYNC"))
            if remote_sync:
                return remote_sync
            remote_async = _to_sync_database_url(vars_payload.get("DATABASE_URL"))
            if remote_async:
                return remote_async
        except Exception:
            pass
        return ""

    def _rehydrate_control_plane_ingest_status(self, account_id: str, regions: list[str]) -> dict[str, Any]:
        tenant_id = str(self.state.checkpoint.context.get("tenant_id") or "").strip()
        if not tenant_id:
            return {"ok": False, "error": "missing_tenant_id_in_checkpoint"}
        db_url = self._resolve_runtime_database_url()
        if not db_url:
            return {"ok": False, "error": "database_url_unavailable"}

        now = datetime.now(timezone.utc)
        engine = sa.create_engine(db_url)
        try:
            with engine.begin() as conn:
                for region in regions:
                    conn.execute(
                        sa.text(
                            """
                            insert into control_plane_event_ingest_status
                                (tenant_id, account_id, region, last_event_time, last_intake_time, created_at, updated_at)
                            values
                                (cast(:tenant_id as uuid), :account_id, :region, :now_ts, :now_ts, now(), now())
                            on conflict (tenant_id, account_id, region)
                            do update set
                                last_event_time = excluded.last_event_time,
                                last_intake_time = excluded.last_intake_time,
                                updated_at = now()
                            """
                        ),
                        {
                            "tenant_id": tenant_id,
                            "account_id": account_id,
                            "region": region,
                            "now_ts": now,
                        },
                    )
            return {"ok": True, "tenant_id": tenant_id, "regions": list(regions), "at": now.isoformat()}
        except Exception as exc:
            return {"ok": False, "tenant_id": tenant_id, "regions": list(regions), "error": str(exc)}
        finally:
            engine.dispose()

    def phase_pre_snapshot(self) -> None:
        self._trigger_refresh(include_reconcile=False)
        findings = self._fetch_all_findings(status_filter=None)
        summary = aggregate_findings(findings)
        write_json(self.output_dir / "findings_pre_raw.json", findings)
        write_json(self.output_dir / "findings_pre_summary.json", summary)

    def phase_target_select(self) -> None:
        findings = read_json(self.output_dir / "findings_pre_raw.json")
        preference_raw = self.settings.get("control_preference")
        preference_items = preference_raw if isinstance(preference_raw, list) else []
        preferred_controls = [
            token for token in (_canonical_control_token(item) for item in preference_items) if token
        ]
        selected = select_target_finding(findings, self.settings["control_preference"])
        if selected is None:
            if preferred_controls:
                preferred_control = preferred_controls[0]
                context = {
                    "target_finding_id": "",
                    "target_action_id": "",
                    "target_control_id": preferred_control,
                    "target_resource_id": "",
                    "no_target_noop": True,
                    "no_target_noop_reason": "no_eligible_finding_for_preferred_control",
                }
                for key, value in context.items():
                    self.state.set_context(key, value)
                write_json(self.output_dir / "target_context.json", context)
                return
            raise AgentValidationError("No eligible finding with remediation_action_id in NEW/NOTIFIED state")

        context = {
            "target_finding_id": str(selected.get("id") or ""),
            "target_action_id": str(selected.get("remediation_action_id") or ""),
            "target_control_id": str(selected.get("control_id") or ""),
            "target_resource_id": str(selected.get("resource_id") or ""),
            "no_target_noop": False,
            "no_target_noop_reason": "",
        }
        if not context["target_finding_id"] or not context["target_action_id"]:
            raise AgentValidationError("Selected finding is missing required identifiers")
        preferred_control_set = set(preferred_controls)
        selected_control = _canonical_control_token(context["target_control_id"])
        if preferred_control_set and selected_control and selected_control not in preferred_control_set:
            expected = ", ".join(sorted(preferred_control_set))
            raise AgentValidationError(
                f"Selected control '{selected_control}' is outside requested control_preference: {expected}"
            )

        for key, value in context.items():
            self.state.set_context(key, value)
        write_json(self.output_dir / "target_context.json", context)

    def phase_strategy_select(self) -> None:
        if self._is_target_select_noop():
            payload = {
                "skipped": True,
                "reason": self._target_select_noop_reason(),
                "strategy_id": "",
                "strategy_optional": True,
                "strategy": None,
                "strategy_candidates": [""],
                "mode_options": [],
            }
            self.state.set_context("strategy_id", "")
            self.state.set_context("strategy_candidates", [""])
            write_json(self.output_dir / "strategy_selection.json", payload)
            return

        action_id = str(self.state.checkpoint.context.get("target_action_id") or "")
        options = self.client.get_remediation_options(action_id)
        strategies = options.get("strategies") if isinstance(options.get("strategies"), list) else []
        mode_options = options.get("mode_options") if isinstance(options.get("mode_options"), list) else []
        compatible = [
            s
            for s in strategies
            if isinstance(s, dict)
            and str(s.get("mode") or "") == "pr_only"
            and not bool(s.get("requires_inputs"))
        ]
        compatible_non_exception = [s for s in compatible if not bool(s.get("supports_exception_flow"))]
        candidate_strategies = compatible_non_exception if compatible_non_exception else compatible
        compatible_sorted = sorted(candidate_strategies, key=_strategy_sort_key)
        selected = select_pr_only_strategy(strategies)
        # Some action types support pr_only mode without an explicit strategy catalog.
        if selected is None and "pr_only" in [str(x) for x in mode_options] and not strategies:
            payload = {
                "strategy_id": "",
                "strategy_optional": True,
                "strategy": None,
                "strategy_candidates": [""],
                "mode_options": mode_options,
            }
            self.state.set_context("strategy_id", "")
            self.state.set_context("strategy_candidates", [""])
            write_json(self.output_dir / "strategy_selection.json", payload)
            return
        if selected is None:
            raise AgentValidationError("No compatible pr_only strategy without required inputs")
        if bool(selected.get("supports_exception_flow")) and compatible_non_exception:
            selected = compatible_sorted[0]

        strategy_id = str(selected.get("strategy_id") or "")
        if not strategy_id:
            raise AgentValidationError("Selected strategy_id is missing")

        candidate_ids = [
            str(s.get("strategy_id") or "")
            for s in compatible_sorted
            if str(s.get("strategy_id") or "")
        ]
        if strategy_id not in candidate_ids:
            candidate_ids.insert(0, strategy_id)

        payload = {"strategy_id": strategy_id, "strategy": selected, "strategy_candidates": candidate_ids}
        self.state.set_context("strategy_id", strategy_id)
        self.state.set_context("strategy_candidates", candidate_ids)
        write_json(self.output_dir / "strategy_selection.json", payload)

    def phase_run_create(self) -> None:
        if self._is_target_select_noop():
            self.state.set_context("run_id", "")
            write_json(
                self.output_dir / "run_create.json",
                {"skipped": True, "reason": self._target_select_noop_reason()},
            )
            return

        action_id = str(self.state.checkpoint.context.get("target_action_id") or "")
        strategy_id_raw = str(self.state.checkpoint.context.get("strategy_id") or "")
        candidates_ctx = self.state.checkpoint.context.get("strategy_candidates")
        candidate_ids: list[str] = []
        if isinstance(candidates_ctx, list):
            candidate_ids = [str(x or "") for x in candidates_ctx]
        if not candidate_ids:
            candidate_ids = [strategy_id_raw]

        created: dict[str, Any] | None = None
        attempted: list[str] = []
        last_error: str | None = None
        for candidate_id in candidate_ids:
            attempted.append(candidate_id)
            try:
                created = self.client.create_pr_bundle_run(action_id, candidate_id or None)
                self.state.set_context("strategy_id", candidate_id)
                break
            except ApiError as exc:
                last_error = str(exc)
                if _is_dependency_check_failed(exc) and len(attempted) < len(candidate_ids):
                    continue
                raise

        if created is None:
            raise AgentValidationError(last_error or "Failed to create remediation run")

        run_id = str(created.get("id") or "")
        if not run_id:
            raise AgentValidationError("Remediation run creation returned no run id")

        self.state.set_context("run_id", run_id)
        write_json(self.output_dir / "run_create.json", {"attempted_strategies": attempted, "result": created})

    def phase_run_poll(self) -> None:
        if self._is_target_select_noop():
            write_json(
                self.output_dir / "run_final.json",
                {"skipped": True, "reason": self._target_select_noop_reason(), "status": "noop"},
            )
            return

        run_id = str(self.state.checkpoint.context.get("run_id") or "")
        timeout = self.settings["run_timeout_sec"]
        stale_after = self.settings["stale_resend_sec"]
        poll_every = self.settings["poll_interval_sec"]
        resent = False

        started = time.monotonic()
        while True:
            run = self.client.get_remediation_run(run_id)
            status = str(run.get("status") or "").lower()
            if status == "success":
                write_json(self.output_dir / "run_final.json", run)
                return
            if status in {"failed", "cancelled"}:
                raise AgentValidationError(f"Remediation run ended with status={status}")

            age_sec = _run_age_seconds(run)
            if not resent and status in {"pending", "running"} and age_sec >= stale_after:
                self.client.resend_remediation_run(run_id)
                resent = True

            if (time.monotonic() - started) >= timeout:
                raise AgentValidationError("Timed out waiting for remediation run success")
            time.sleep(poll_every)

    def phase_bundle_download(self) -> None:
        if self._is_target_select_noop():
            return

        run_id = str(self.state.checkpoint.context.get("run_id") or "")
        zip_bytes = self.client.download_pr_bundle_zip(run_id)
        zip_path = self.output_dir / f"pr-bundle-{run_id}.zip"
        zip_path.write_bytes(zip_bytes)

        workspace = self.output_dir / "workspaces" / run_id
        workspace.mkdir(parents=True, exist_ok=True)
        extract_zip_safe(zip_path, workspace)

        self.state.set_context("bundle_zip_path", str(zip_path))
        self.state.set_context("workspace_path", str(workspace))

    def phase_terraform_apply(self) -> None:
        transcript_path = self.output_dir / "terraform_transcript.json"
        if self._is_target_select_noop():
            payload = [
                {
                    "command": "noop_no_target",
                    "exit_code": 0,
                    "stdout": f"skipped: {self._target_select_noop_reason()}",
                    "stderr": "",
                }
            ]
            write_json(transcript_path, payload)
            return

        if self.settings["dry_run"]:
            payload = [{"command": "dry_run", "exit_code": 0, "stdout": "skipped", "stderr": ""}]
            write_json(transcript_path, payload)
            return

        workspace = Path(str(self.state.checkpoint.context.get("workspace_path") or ""))
        if not workspace.exists():
            raise AgentValidationError(f"Workspace path not found: {workspace}")

        try:
            transcript = self.terraform_runner(workspace, self.settings["terraform_timeout_sec"])
            write_json(transcript_path, transcript)
        except TerraformError as exc:
            write_json(transcript_path, exc.transcript)
            raise AgentValidationError(str(exc)) from exc

    def phase_refresh(self) -> None:
        if self._is_target_select_noop():
            write_json(
                self.output_dir / "refresh_last.json",
                {"skipped": True, "reason": self._target_select_noop_reason()},
            )
            return
        self._trigger_refresh(include_reconcile=True)

    def phase_verification_poll(self) -> None:
        if self._is_target_select_noop():
            write_json(
                self.output_dir / "verification_result.json",
                {"skipped": True, "reason": self._target_select_noop_reason()},
            )
            return

        finding_id = str(self.state.checkpoint.context.get("target_finding_id") or "")
        account_id = self.settings["account_id"]
        region = self.settings["region"]
        timeout = self.settings["verify_timeout_sec"]
        poll_every = self.settings["poll_interval_sec"]

        started = time.monotonic()
        while True:
            finding = self.client.get_finding(finding_id)
            readiness = self.client.check_control_plane_readiness(account_id, stale_after_minutes=30)
            finding_ok = finding_is_resolved(finding)
            readiness_ok = control_plane_region_ready(readiness, region)

            if finding_ok and readiness_ok:
                payload = {"finding": finding, "control_plane": readiness}
                write_json(self.output_dir / "verification_result.json", payload)
                return

            if (time.monotonic() - started) >= timeout:
                raise AgentValidationError("Timed out waiting for finding resolution and control-plane freshness")
            time.sleep(poll_every)

    def phase_post_snapshot(self) -> None:
        if self._is_target_select_noop():
            pre_raw = read_json(self.output_dir / "findings_pre_raw.json")
            pre_summary = _load_summary(self.output_dir / "findings_pre_summary.json")
            write_json(self.output_dir / "findings_post_raw.json", pre_raw)
            write_json(self.output_dir / "findings_post_summary.json", pre_summary)
            return

        findings = self._fetch_all_findings(status_filter=None)
        summary = aggregate_findings(findings)
        write_json(self.output_dir / "findings_post_raw.json", findings)
        write_json(self.output_dir / "findings_post_summary.json", summary)

    def phase_report(self) -> None:
        self._write_reports()

    def _write_reports(self) -> None:
        pre_summary = _load_summary(self.output_dir / "findings_pre_summary.json")
        post_summary = _load_summary(self.output_dir / "findings_post_summary.json")
        control_id = str(self.state.checkpoint.context.get("target_control_id") or "UNSPECIFIED")
        delta = compute_delta(pre_summary, post_summary, control_id)
        kpis = delta.get("kpis") if isinstance(delta.get("kpis"), dict) else {}
        tested_control_delta = kpis.get("tested_control_delta")
        resolved_gain = kpis.get("resolved_gain")
        tested_control_id = str(kpis.get("tested_control_id") or control_id).upper()
        pre_open_counts = pre_summary.get("by_control_id_open") if isinstance(pre_summary.get("by_control_id_open"), dict) else {}
        pre_open_for_control = pre_open_counts.get(tested_control_id)
        pre_was_non_compliant = int(pre_open_for_control) > 0 if isinstance(pre_open_for_control, int) else False

        apply_phase_completed = self.state.is_phase_complete("terraform_apply")
        is_real_apply = not bool(self.settings.get("dry_run"))
        if self.final_status == "success" and apply_phase_completed and is_real_apply and pre_was_non_compliant:
            resolved_gain_value = resolved_gain if isinstance(resolved_gain, (int, float)) else None
            if resolved_gain_value is None or resolved_gain_value <= 0:
                self.final_status = "failed"
                self.exit_code = self.exit_code or 1
                self.state.add_error(
                    "report",
                    (
                        "KPI gate failed: resolved_gain must be > 0 after remediation apply "
                        f"(got {resolved_gain!r})"
                    ),
                )

        if self._is_target_select_noop():
            outcome_type = "already_compliant_noop"
            gate_evaluated = False
            gate_skip_reason: str | None = "pre_already_compliant"
        elif not apply_phase_completed or not is_real_apply:
            outcome_type = "failed"
            gate_evaluated = False
            gate_skip_reason = "apply_not_completed"
        elif not pre_was_non_compliant:
            outcome_type = "already_compliant_noop"
            gate_evaluated = False
            gate_skip_reason = "pre_already_compliant"
        elif self.final_status == "success":
            outcome_type = "remediated"
            gate_evaluated = True
            gate_skip_reason = None
        else:
            outcome_type = "failed"
            gate_evaluated = True
            gate_skip_reason = None

        write_json(self.output_dir / "findings_delta.json", delta)

        report = {
            "status": self.final_status,
            "exit_code": self.exit_code,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "account_id": self.settings["account_id"],
            "region": self.settings["region"],
            "tenant_id": str(self.state.checkpoint.context.get("tenant_id") or ""),
            "user_id": str(self.state.checkpoint.context.get("user_id") or ""),
            "target_finding_id": str(self.state.checkpoint.context.get("target_finding_id") or ""),
            "target_action_id": str(self.state.checkpoint.context.get("target_action_id") or ""),
            "target_control_id": control_id,
            "run_id": str(self.state.checkpoint.context.get("run_id") or ""),
            "pre_summary": pre_summary,
            "post_summary": post_summary,
            "delta": delta,
            "tested_control_delta": tested_control_delta,
            "resolved_gain": resolved_gain,
            "outcome_type": outcome_type,
            "gate_evaluated": gate_evaluated,
            "gate_skip_reason": gate_skip_reason,
            "completed_phases": list(self.state.checkpoint.completed_phases),
            "errors": list(self.state.checkpoint.errors),
        }
        write_json(self.output_dir / "final_report.json", report)
        (self.output_dir / "final_report.md").write_text(render_markdown_report(report), encoding="utf-8")

    def _fetch_all_findings(self, status_filter: str | None) -> list[dict[str, Any]]:
        account_id = self.settings["account_id"]
        region = self.settings["region"]
        offset = 0
        limit = 200
        all_items: list[dict[str, Any]] = []

        while True:
            page = self.client.list_findings(account_id, region, limit, offset, status_filter=status_filter)
            items = page.get("items") if isinstance(page.get("items"), list) else []
            total = int(page.get("total") or 0)
            all_items.extend([x for x in items if isinstance(x, dict)])
            if not items or len(all_items) >= total:
                break
            offset += limit

        return all_items

    def _trigger_refresh(self, include_reconcile: bool) -> None:
        account_id = self.settings["account_id"]
        region = self.settings["region"]
        ingest = self.client.trigger_ingest(account_id, [region])
        compute = self.client.trigger_compute_actions(account_id, region)
        payload: dict[str, Any] = {"ingest": ingest, "compute": compute}
        if include_reconcile and bool(self.settings.get("reconcile_after_apply", True)):
            payload["reconcile"] = self._trigger_reconcile_for_target()
        write_json(self.output_dir / "refresh_last.json", payload)

    def _trigger_reconcile_for_target(self) -> dict[str, Any]:
        control_id = str(self.state.checkpoint.context.get("target_control_id") or "").upper()
        services = _reconcile_services_for_control(control_id)
        if not services:
            return {"skipped": True, "reason": "no_reconcile_service_for_control", "control_id": control_id}

        account_id = self.settings["account_id"]
        region = self.settings["region"]
        response = self.client.trigger_reconciliation_run(
            account_id=account_id,
            regions=[region],
            services=services,
            require_preflight_pass=False,
            force=True,
            sweep_mode="global",
            max_resources=500,
        )
        run_id = str(response.get("run_id") or "")
        if not run_id:
            return {"trigger": response, "status": "unknown", "reason": "missing_run_id"}

        timeout_sec = int(self.settings.get("reconcile_timeout_sec", 900))
        poll_sec = int(self.settings.get("reconcile_poll_interval_sec", 10))
        terminal = {"succeeded", "partial_failed", "failed"}
        started = time.monotonic()

        while True:
            status_payload = self.client.get_reconciliation_status(account_id, limit=100)
            run = _find_reconciliation_run(status_payload, run_id)
            status_value = str((run or {}).get("status") or "").lower()
            if status_value in terminal:
                return {"trigger": response, "run": run, "status": status_value}
            if (time.monotonic() - started) >= timeout_sec:
                return {"trigger": response, "run": run, "status": "timeout"}
            time.sleep(max(1, poll_sec))

    def _write_api_transcript(self) -> None:
        write_json(self.output_dir / "api_transcript.json", self.client.get_transcript())

    def _handle_failure(self, failure: Exception) -> None:
        message = str(failure)
        if isinstance(failure, AgentConfigError):
            self.exit_code = 2
        elif isinstance(failure, ApiError) and failure.transient:
            self.exit_code = 3
        elif isinstance(failure, ApiError):
            self.exit_code = 1
        elif isinstance(failure, AgentValidationError):
            self.exit_code = 1
        else:
            self.exit_code = 1

        self.final_status = "failed"
        current_phase = _current_phase(self.state.checkpoint.completed_phases)
        self.state.add_error(current_phase, message)

    def _ensure_post_snapshot_exists(self) -> None:
        raw_path = self.output_dir / "findings_post_raw.json"
        summary_path = self.output_dir / "findings_post_summary.json"
        if raw_path.exists() and summary_path.exists():
            return

        if self.state.is_phase_complete("auth"):
            try:
                findings = self._fetch_all_findings(status_filter=None)
                summary = aggregate_findings(findings)
                write_json(raw_path, findings)
                write_json(summary_path, summary)
                return
            except Exception as exc:
                self.state.add_error("post_snapshot", f"fallback snapshot failed: {exc}")

        write_json(raw_path, [])
        write_json(summary_path, {"total": 0, "error": "post snapshot unavailable"})

    def _ensure_pre_snapshot_exists(self) -> None:
        raw_path = self.output_dir / "findings_pre_raw.json"
        summary_path = self.output_dir / "findings_pre_summary.json"
        if raw_path.exists() and summary_path.exists():
            return

        if self.state.is_phase_complete("auth"):
            try:
                findings = self._fetch_all_findings(status_filter=None)
                summary = aggregate_findings(findings)
                write_json(raw_path, findings)
                write_json(summary_path, summary)
                return
            except Exception as exc:
                self.state.add_error("pre_snapshot", f"fallback snapshot failed: {exc}")

        write_json(raw_path, [])
        write_json(summary_path, {"total": 0, "error": "pre snapshot unavailable"})

    def _ensure_terraform_transcript_exists(self) -> None:
        path = self.output_dir / "terraform_transcript.json"
        if path.exists():
            return
        write_json(
            path,
            [
                {
                    "command": "terraform_unavailable",
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "terraform phase not reached",
                }
            ],
        )

    def _cleanup_workspace_if_needed(self) -> None:
        if self.settings["keep_workdir"]:
            return
        workspace_raw = str(self.state.checkpoint.context.get("workspace_path") or "").strip()
        if not workspace_raw:
            return
        workspace = Path(workspace_raw).resolve()
        if not workspace.exists():
            return
        if not is_path_within_root(workspace, self.output_dir.resolve()):
            raise AgentValidationError("Refusing to delete workspace outside output root")
        shutil.rmtree(workspace)


def render_markdown_report(report: dict[str, Any]) -> str:
    delta = report.get("delta") if isinstance(report.get("delta"), dict) else {}
    kpis = delta.get("kpis") if isinstance(delta.get("kpis"), dict) else {}
    lines = [
        "# No-UI PR Bundle Validation Report",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Exit code: `{report.get('exit_code')}`",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Account: `{report.get('account_id')}`",
        f"- Region: `{report.get('region')}`",
        f"- Target finding: `{report.get('target_finding_id')}`",
        f"- Target action: `{report.get('target_action_id')}`",
        f"- Target control: `{report.get('target_control_id')}`",
        f"- Remediation run: `{report.get('run_id')}`",
        "",
        "## KPI Delta",
        "",
        f"- Open drop: `{kpis.get('open_drop')}`",
        f"- Resolved gain: `{kpis.get('resolved_gain')}`",
        f"- Tested control delta: `{kpis.get('tested_control_delta')}`",
    ]
    return "\n".join(lines) + "\n"


def finding_is_resolved(finding: dict[str, Any]) -> bool:
    status = str(finding.get("status") or "").upper()
    if status == "RESOLVED":
        return True
    shadow = finding.get("shadow") if isinstance(finding.get("shadow"), dict) else {}
    shadow_status = str(shadow.get("status_normalized") or "").upper()
    return shadow_status == "RESOLVED"


def control_plane_region_ready(readiness: dict[str, Any], region: str) -> bool:
    if not bool(readiness.get("overall_ready")):
        return False
    regions = readiness.get("regions") if isinstance(readiness.get("regions"), list) else []
    target = [r for r in regions if isinstance(r, dict) and str(r.get("region") or "") == region]
    if not target:
        return False
    return bool(target[0].get("is_recent"))


def extract_zip_safe(zip_path: Path, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    with ZipFile(zip_path, "r") as zip_file:
        for info in zip_file.infolist():
            candidate = (dest_resolved / info.filename).resolve()
            if not is_path_within_root(candidate, dest_resolved):
                raise AgentValidationError(f"Unsafe zip path: {info.filename}")
            zip_file.extract(info, dest_resolved)


def is_path_within_root(path: Path, root: Path) -> bool:
    path_text = str(path.resolve())
    root_text = str(root.resolve())
    return path_text == root_text or path_text.startswith(root_text + "/")


def _run_age_seconds(run_payload: dict[str, Any]) -> int:
    created = parse_iso(str(run_payload.get("created_at") or ""))
    if created is None:
        return 0
    now = datetime.now(timezone.utc)
    return int((now - created).total_seconds())


def _safe_subset(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: payload.get(key) for key in keys if key in payload}


def _is_dependency_check_failed(exc: ApiError) -> bool:
    payload = exc.payload
    if not isinstance(payload, dict):
        return False
    detail = payload.get("detail")
    if not isinstance(detail, dict):
        return False
    error = str(detail.get("error") or "").strip().lower()
    return error == "dependency check failed"


def _reconcile_services_for_control(control_id: str) -> list[str]:
    token = str(control_id or "").strip().upper()
    if token.startswith("S3."):
        return ["s3"]
    if token in {"EC2.7", "EC2.182"}:
        return ["ebs"]
    if token.startswith("EC2."):
        return ["ec2"]
    if token.startswith("IAM."):
        return ["iam"]
    if token.startswith("SSM."):
        return ["ssm"]
    if token.startswith("CLOUDTRAIL."):
        return ["cloudtrail"]
    if token.startswith("CONFIG."):
        return ["config"]
    if token.startswith("GUARDDUTY."):
        return ["guardduty"]
    return []


def _find_reconciliation_run(payload: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    if not run_id:
        return None
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    for row in runs:
        if not isinstance(row, dict):
            continue
        if str(row.get("id") or "") == run_id:
            return row
    return None


def _canonical_control_token(control_id: Any) -> str:
    token = str(control_id or "").strip()
    if not token:
        return ""
    try:
        from backend.services.control_scope import action_type_from_control, canonical_control_id_for_action_type

        action_type = action_type_from_control(token)
        canonical = canonical_control_id_for_action_type(action_type, token)
        if canonical:
            normalized = str(canonical).strip().upper()
            if normalized:
                return normalized
    except Exception:
        pass
    return token.upper()


def _load_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"total": 0}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {"total": 0}


def _current_phase(completed: list[str]) -> str:
    if not completed:
        return "init"
    for phase in PHASES:
        if phase not in completed:
            return phase
    return "done"


def main() -> int:
    try:
        args = parse_args()
        config = load_config(args.config)
        settings = merge_settings(args, config)
        output_dir = resolve_output_dir(settings)
        email, password = prompt_credentials()
        agent = NoUiPrBundleAgent(settings, output_dir, email, password)
        return agent.run()
    except AgentConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Unhandled error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
