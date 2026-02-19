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
from typing import Any, Callable
from zipfile import ZipFile

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
        if phase not in POLL_PHASES and elapsed > self.settings["phase_timeout_sec"]:
            raise AgentValidationError(f"Phase exceeded timeout: {phase}")
        self.state.mark_phase_complete(phase)

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
        write_json(self.output_dir / "readiness.json", {"service": service, "control_plane": control})

        if not bool(service.get("overall_ready")):
            raise AgentValidationError("Service readiness failed: required services are not fully enabled")
        if not bool(control.get("overall_ready")):
            missing = ", ".join(control.get("missing_regions") or [])
            raise AgentValidationError(f"Control-plane readiness failed (missing: {missing})")

    def phase_pre_snapshot(self) -> None:
        self._trigger_refresh()
        findings = self._fetch_all_findings(status_filter=None)
        summary = aggregate_findings(findings)
        write_json(self.output_dir / "findings_pre_raw.json", findings)
        write_json(self.output_dir / "findings_pre_summary.json", summary)

    def phase_target_select(self) -> None:
        findings = read_json(self.output_dir / "findings_pre_raw.json")
        selected = select_target_finding(findings, self.settings["control_preference"])
        if selected is None:
            raise AgentValidationError("No eligible finding with remediation_action_id in NEW/NOTIFIED state")

        context = {
            "target_finding_id": str(selected.get("id") or ""),
            "target_action_id": str(selected.get("remediation_action_id") or ""),
            "target_control_id": str(selected.get("control_id") or ""),
            "target_resource_id": str(selected.get("resource_id") or ""),
        }
        if not context["target_finding_id"] or not context["target_action_id"]:
            raise AgentValidationError("Selected finding is missing required identifiers")

        for key, value in context.items():
            self.state.set_context(key, value)
        write_json(self.output_dir / "target_context.json", context)

    def phase_strategy_select(self) -> None:
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
        self._trigger_refresh()

    def phase_verification_poll(self) -> None:
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

    def _trigger_refresh(self) -> None:
        account_id = self.settings["account_id"]
        region = self.settings["region"]
        ingest = self.client.trigger_ingest(account_id, [region])
        compute = self.client.trigger_compute_actions(account_id, region)
        write_json(self.output_dir / "refresh_last.json", {"ingest": ingest, "compute": compute})

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
