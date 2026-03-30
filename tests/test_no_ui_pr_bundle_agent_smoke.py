from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from scripts.lib.no_ui_agent_client import ApiError
from scripts.run_no_ui_pr_bundle_agent import NoUiPrBundleAgent


class FakeClient:
    def __init__(self) -> None:
        self.run_polls = 0
        self.transcript = []
        self.reconcile_run_id = "recon-1"

    def login(self, email: str, password: str):
        del email, password
        return {"access_token": "hidden", "tenant": {"id": "t-1"}, "user": {"id": "u-1"}}

    def get_me(self):
        return {"tenant": {"id": "t-1"}, "user": {"id": "u-1"}}

    def check_service_readiness(self, account_id: str):
        del account_id
        return {"overall_ready": True}

    def check_control_plane_readiness(self, account_id: str, stale_after_minutes: int = 30):
        del account_id, stale_after_minutes
        return {
            "overall_ready": True,
            "regions": [{"region": "eu-north-1", "is_recent": True}],
        }

    def trigger_ingest(self, account_id: str, regions: list[str]):
        del account_id, regions
        return {"message": "queued"}

    def trigger_compute_actions(self, account_id: str, region: str):
        del account_id, region
        return {"message": "queued"}

    def list_findings(self, account_id: str, region: str | None, limit: int, offset: int, status_filter: str | None = None):
        del account_id, region, limit, status_filter
        if offset > 0:
            return {"items": [], "total": 1}
        return {
            "items": [
                {
                    "id": "finding-1",
                    "status": "NEW",
                    "severity_label": "HIGH",
                    "control_id": "EC2.53",
                    "resource_id": "sg-1",
                    "remediation_action_id": "action-1",
                    "updated_at_db": "2026-02-19T10:00:00Z",
                    "source": "security_hub",
                }
            ],
            "total": 1,
        }

    def get_finding(self, finding_id: str):
        del finding_id
        return {
            "id": "finding-1",
            "status": "RESOLVED",
            "shadow": {"status_normalized": "RESOLVED"},
        }

    def get_remediation_options(self, action_id: str):
        del action_id
        return {
            "strategies": [
                {
                    "strategy_id": "strategy-1",
                    "mode": "pr_only",
                    "requires_inputs": False,
                    "recommended": True,
                }
            ]
        }

    def create_pr_bundle_run(
        self,
        action_id: str,
        strategy_id: str | None = None,
        *,
        profile_id: str | None = None,
        strategy_inputs: dict | None = None,
        risk_acknowledged: bool = True,
        bucket_creation_acknowledged: bool = False,
    ):
        del action_id, strategy_id, profile_id, strategy_inputs, risk_acknowledged, bucket_creation_acknowledged
        return {"id": "run-1"}

    def get_remediation_run(self, run_id: str):
        del run_id
        self.run_polls += 1
        if self.run_polls < 2:
            return {"status": "running", "created_at": "2026-02-19T10:00:00Z"}
        return {"status": "success", "created_at": "2026-02-19T10:00:00Z"}

    def resend_remediation_run(self, run_id: str):
        del run_id
        return {"message": "resent"}

    def download_pr_bundle_zip(self, run_id: str) -> bytes:
        del run_id
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("main.tf", "terraform {}")
        return buf.getvalue()

    def trigger_reconciliation_run(
        self,
        account_id: str,
        regions: list[str],
        services: list[str],
        require_preflight_pass: bool,
        force: bool,
        sweep_mode: str,
        max_resources: int,
    ):
        del account_id, regions, services, require_preflight_pass, force, sweep_mode, max_resources
        return {"run_id": self.reconcile_run_id}

    def get_reconciliation_status(self, account_id: str, limit: int = 20):
        del account_id, limit
        return {"runs": [{"id": self.reconcile_run_id, "status": "succeeded"}]}

    def get_transcript(self):
        return self.transcript


class FakeClientNoStrategy(FakeClient):
    def get_remediation_options(self, action_id: str):
        del action_id
        return {
            "mode_options": ["pr_only"],
            "strategies": [],
        }


class FakeClientStrategyFallback(FakeClient):
    def get_remediation_options(self, action_id: str):
        del action_id
        return {
            "mode_options": ["pr_only"],
            "strategies": [
                {
                    "strategy_id": "recommended_blocked",
                    "mode": "pr_only",
                    "requires_inputs": False,
                    "recommended": True,
                },
                {
                    "strategy_id": "fallback_ok",
                    "mode": "pr_only",
                    "requires_inputs": False,
                    "recommended": False,
                },
            ],
        }

    def create_pr_bundle_run(
        self,
        action_id: str,
        strategy_id: str | None = None,
        *,
        profile_id: str | None = None,
        strategy_inputs: dict | None = None,
        risk_acknowledged: bool = True,
        bucket_creation_acknowledged: bool = False,
    ):
        del action_id, profile_id, strategy_inputs, risk_acknowledged, bucket_creation_acknowledged
        if strategy_id == "recommended_blocked":
            raise ApiError(
                "One or more dependency checks blocked this remediation strategy.",
                status_code=400,
                transient=False,
                payload={"detail": {"error": "Dependency check failed"}},
            )
        return {"id": "run-1"}


def test_no_ui_agent_dry_run_smoke(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53", "S3.2"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClient(),
    )
    code = agent.run()

    assert code == 0
    assert (tmp_path / "final_report.json").exists()
    assert (tmp_path / "findings_pre_summary.json").exists()
    assert (tmp_path / "findings_post_summary.json").exists()
    assert (tmp_path / "findings_delta.json").exists()
    assert (tmp_path / "terraform_transcript.json").exists()
    final_report = json.loads((tmp_path / "final_report.json").read_text(encoding="utf-8"))
    delta = final_report.get("delta") if isinstance(final_report.get("delta"), dict) else {}
    kpis = delta.get("kpis") if isinstance(delta.get("kpis"), dict) else {}
    assert final_report.get("tested_control_delta") == kpis.get("tested_control_delta")
    assert final_report.get("resolved_gain") == kpis.get("resolved_gain")


def test_outcome_type_failed(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53", "S3.2"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": False,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }

    def _terraform_runner(workspace: Path, timeout_sec: int):
        del timeout_sec
        assert workspace.exists()
        return [{"command": "terraform apply", "exit_code": 0, "stdout": "ok", "stderr": ""}]

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClient(),
        terraform_runner=_terraform_runner,
    )
    code = agent.run()

    assert code == 1
    final_report = json.loads((tmp_path / "final_report.json").read_text(encoding="utf-8"))
    assert final_report["status"] == "failed"
    assert final_report["exit_code"] == 1
    assert final_report.get("resolved_gain") == 0
    assert final_report.get("tested_control_delta") == 0
    assert final_report.get("outcome_type") == "failed"
    assert final_report.get("gate_evaluated") is True
    assert final_report.get("gate_skip_reason") is None
    assert any("resolved_gain must be > 0" in str(err.get("message", "")) for err in final_report["errors"])


def test_outcome_type_remediated(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": False,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }

    def _terraform_runner(workspace: Path, timeout_sec: int):
        del timeout_sec
        assert workspace.exists()
        return [{"command": "terraform apply", "exit_code": 0, "stdout": "ok", "stderr": ""}]

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClientRemediated(),
        terraform_runner=_terraform_runner,
    )
    code = agent.run()

    assert code == 0
    final_report = json.loads((tmp_path / "final_report.json").read_text(encoding="utf-8"))
    assert final_report["status"] == "success"
    assert final_report["exit_code"] == 0
    assert final_report.get("resolved_gain") == 1
    assert final_report.get("tested_control_delta") == -1
    assert final_report.get("outcome_type") == "remediated"
    assert final_report.get("gate_evaluated") is True
    assert final_report.get("gate_skip_reason") is None


def test_no_ui_agent_dry_run_smoke_pr_only_without_strategy(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53", "S3.2"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClientNoStrategy(),
    )
    code = agent.run()

    assert code == 0
    assert (tmp_path / "strategy_selection.json").exists()


def test_no_ui_agent_dry_run_smoke_strategy_fallback(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53", "S3.2"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClientStrategyFallback(),
    )
    code = agent.run()

    assert code == 0
    run_create = (tmp_path / "run_create.json").read_text(encoding="utf-8")
    assert "fallback_ok" in run_create


def test_no_ui_agent_guided_strategy_uses_preview_resolution_inputs(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["CloudTrail.1"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }
    fake_client = FakeClientGuidedInputs()

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: fake_client,
    )
    code = agent.run()

    assert code == 0
    strategy_selection = json.loads((tmp_path / "strategy_selection.json").read_text(encoding="utf-8"))
    assert strategy_selection["strategy_id"] == "cloudtrail_enable_guided"
    assert strategy_selection["profile_id"] == "cloudtrail_enable_guided"
    assert strategy_selection["strategy_inputs"]["trail_bucket_name"] == (
        "security-autopilot-trail-logs-029037611564-eu-north-1"
    )
    assert strategy_selection["strategy_inputs"]["create_bucket_if_missing"] is True
    assert fake_client.last_create_payload is not None
    assert fake_client.last_create_payload["strategy_id"] == "cloudtrail_enable_guided"
    assert fake_client.last_create_payload["profile_id"] == "cloudtrail_enable_guided"
    assert fake_client.last_create_payload["strategy_inputs"] == strategy_selection["strategy_inputs"]
    assert fake_client.last_create_payload["bucket_creation_acknowledged"] is True


def test_no_ui_agent_uses_provided_access_token_without_login(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }
    fake_client = FakeClientAccessToken()

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="",
        password="",
        access_token="token-from-env",
        client_factory=lambda *args, **kwargs: fake_client,
    )
    code = agent.run()

    assert code == 0
    assert fake_client.login_called is False
    assert fake_client.access_token == "token-from-env"


def test_refresh_phase_timeout_budget_uses_reconcile_window(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53", "S3.2"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
        "reconcile_after_apply": True,
        "reconcile_timeout_sec": 900,
        "reconcile_poll_interval_sec": 10,
    }

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClient(),
    )

    refresh_budget = agent._phase_timeout_limit_sec("refresh")
    auth_budget = agent._phase_timeout_limit_sec("auth")

    assert refresh_budget > settings["phase_timeout_sec"]
    assert auth_budget == settings["phase_timeout_sec"]


class FakeClientControlMismatch(FakeClient):
    def list_findings(
        self,
        account_id: str,
        region: str | None,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ):
        del account_id, region, limit, status_filter
        if offset > 0:
            return {"items": [], "total": 1}
        return {
            "items": [
                {
                    "id": "finding-ssm-1",
                    "status": "NEW",
                    "severity_label": "HIGH",
                    "control_id": "SSM.7",
                    "resource_id": "account-1",
                    "remediation_action_id": "action-ssm-1",
                    "updated_at_db": "2026-02-20T10:00:00Z",
                    "source": "security_hub",
                }
            ],
            "total": 1,
        }


class FakeClientReadinessSelfHeal(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.readiness_calls = 0
        self.ingest_calls: list[tuple[str, list[str]]] = []

    def check_control_plane_readiness(self, account_id: str, stale_after_minutes: int = 30):
        del account_id, stale_after_minutes
        self.readiness_calls += 1
        if self.readiness_calls == 1:
            return {
                "overall_ready": False,
                "missing_regions": ["eu-north-1"],
                "regions": [{"region": "eu-north-1", "is_recent": False}],
            }
        return {
            "overall_ready": True,
            "missing_regions": [],
            "regions": [{"region": "eu-north-1", "is_recent": True}],
        }

    def trigger_ingest(self, account_id: str, regions: list[str]):
        self.ingest_calls.append((account_id, list(regions)))
        return {"message": "queued", "regions": list(regions)}


class FakeClientAlreadyCompliant(FakeClient):
    def list_findings(
        self,
        account_id: str,
        region: str | None,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ):
        del account_id, region, limit, status_filter
        if offset > 0:
            return {"items": [], "total": 1}
        return {
            "items": [
                {
                    "id": "finding-1",
                    "status": "NEW",
                    "severity_label": "HIGH",
                    "control_id": "EC2.53",
                    "resource_id": "sg-1",
                    "remediation_action_id": "action-1",
                    "updated_at_db": "2026-02-19T10:00:00Z",
                    "source": "security_hub",
                    "shadow": {"status_normalized": "RESOLVED"},
                }
            ],
            "total": 1,
        }


class FakeClientRemediated(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.list_calls = 0

    def list_findings(
        self,
        account_id: str,
        region: str | None,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ):
        del account_id, region, limit, status_filter
        if offset > 0:
            return {"items": [], "total": 1}
        self.list_calls += 1
        pre_snapshot = self.list_calls == 1
        return {
            "items": [
                {
                    "id": "finding-1",
                    "status": "NEW" if pre_snapshot else "RESOLVED",
                    "severity_label": "HIGH",
                    "control_id": "EC2.53",
                    "resource_id": "sg-1",
                    "remediation_action_id": "action-1",
                    "updated_at_db": "2026-02-19T10:00:00Z",
                    "source": "security_hub",
                }
            ],
            "total": 1,
        }


class FakeClientGuidedInputs(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.last_create_payload: dict[str, object] | None = None

    def list_findings(
        self,
        account_id: str,
        region: str | None,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ):
        del account_id, region, limit, status_filter
        if offset > 0:
            return {"items": [], "total": 1}
        return {
            "items": [
                {
                    "id": "finding-cloudtrail-1",
                    "status": "NEW",
                    "severity_label": "HIGH",
                    "control_id": "CloudTrail.1",
                    "resource_id": "trail-1",
                    "remediation_action_id": "action-cloudtrail-1",
                    "updated_at_db": "2026-03-26T10:00:00Z",
                    "source": "security_hub",
                }
            ],
            "total": 1,
        }

    def get_remediation_options(self, action_id: str):
        del action_id
        return {
            "strategies": [
                {
                    "strategy_id": "cloudtrail_enable_guided",
                    "mode": "pr_only",
                    "requires_inputs": True,
                    "recommended": True,
                    "supports_exception_flow": False,
                }
            ]
        }

    def get_remediation_preview(
        self,
        action_id: str,
        *,
        strategy_id: str | None = None,
        profile_id: str | None = None,
        strategy_inputs: dict | None = None,
    ):
        del action_id, strategy_id, profile_id, strategy_inputs
        return {
            "resolution": {
                "strategy_id": "cloudtrail_enable_guided",
                "profile_id": "cloudtrail_enable_guided",
                "support_tier": "deterministic_bundle",
                "resolved_inputs": {
                    "trail_name": "security-autopilot-trail",
                    "trail_bucket_name": "security-autopilot-trail-logs-029037611564-eu-north-1",
                    "create_bucket_if_missing": True,
                    "create_bucket_policy": True,
                    "multi_region": True,
                },
                "blocked_reasons": [],
                "missing_defaults": [],
            }
        }

    def create_pr_bundle_run(
        self,
        action_id: str,
        strategy_id: str | None = None,
        *,
        profile_id: str | None = None,
        strategy_inputs: dict | None = None,
        risk_acknowledged: bool = True,
        bucket_creation_acknowledged: bool = False,
    ):
        self.last_create_payload = {
            "action_id": action_id,
            "strategy_id": strategy_id,
            "profile_id": profile_id,
            "strategy_inputs": strategy_inputs,
            "risk_acknowledged": risk_acknowledged,
            "bucket_creation_acknowledged": bucket_creation_acknowledged,
        }
        return {"id": "run-guided-1"}


class FakeClientAccessToken(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.login_called = False
        self.access_token: str | None = None

    def login(self, email: str, password: str):
        self.login_called = True
        return super().login(email, password)

    def set_access_token(self, token: str) -> None:
        self.access_token = token


def test_target_select_noops_when_preferred_control_has_no_eligible_finding(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["SecurityHub.1"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
        "reconcile_after_apply": False,
    }

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClientControlMismatch(),
    )
    code = agent.run()

    assert code == 0
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint.get("status") == "success"
    assert checkpoint.get("errors") == []

    final_report = json.loads((tmp_path / "final_report.json").read_text(encoding="utf-8"))
    assert final_report["status"] == "success"
    assert final_report["target_control_id"] == "SECURITYHUB.1"
    assert final_report.get("target_finding_id") == ""
    assert final_report.get("target_action_id") == ""
    assert final_report.get("run_id") == ""
    assert final_report.get("outcome_type") == "already_compliant_noop"
    assert final_report.get("gate_evaluated") is False
    assert final_report.get("gate_skip_reason") == "pre_already_compliant"


def test_readiness_self_heal_retries_once_before_failing(tmp_path: Path, monkeypatch) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": True,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }
    fake_client = FakeClientReadinessSelfHeal()
    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: fake_client,
    )

    called: dict[str, object] = {}

    def _fake_rehydrate(account_id: str, regions: list[str]) -> dict[str, object]:
        called["account_id"] = account_id
        called["regions"] = list(regions)
        return {"ok": True, "regions": list(regions)}

    monkeypatch.setattr(agent, "_rehydrate_control_plane_ingest_status", _fake_rehydrate)

    agent.phase_auth()
    agent.phase_readiness()

    assert fake_client.readiness_calls == 2
    assert fake_client.ingest_calls == [("029037611564", ["eu-north-1"])]
    assert called["account_id"] == "029037611564"
    assert called["regions"] == ["eu-north-1"]

    readiness_payload = json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))
    assert readiness_payload["control_plane"]["overall_ready"] is True
    assert readiness_payload["control_plane_self_heal"]["attempted"] is True


def test_outcome_type_already_compliant_noop(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.ocypheris.com",
        "account_id": "029037611564",
        "region": "eu-north-1",
        "output_dir": str(tmp_path),
        "control_preference": ["EC2.53"],
        "poll_interval_sec": 0,
        "phase_timeout_sec": 300,
        "run_timeout_sec": 5,
        "verify_timeout_sec": 5,
        "terraform_timeout_sec": 5,
        "stale_resend_sec": 120,
        "resume_from_checkpoint": False,
        "dry_run": False,
        "keep_workdir": True,
        "allow_insecure_http": False,
        "client_timeout_sec": 30,
    }

    def _terraform_runner(workspace: Path, timeout_sec: int):
        del timeout_sec
        assert workspace.exists()
        return [{"command": "terraform apply", "exit_code": 0, "stdout": "ok", "stderr": ""}]

    agent = NoUiPrBundleAgent(
        settings=settings,
        output_dir=tmp_path,
        email="user@example.com",
        password="pass",
        client_factory=lambda *args, **kwargs: FakeClientAlreadyCompliant(),
        terraform_runner=_terraform_runner,
    )
    code = agent.run()

    assert code == 0
    final_report = json.loads((tmp_path / "final_report.json").read_text(encoding="utf-8"))
    assert final_report["status"] == "success"
    assert final_report["exit_code"] == 0
    assert final_report.get("resolved_gain") == 0
    assert final_report.get("tested_control_delta") == 0
    assert final_report.get("outcome_type") == "already_compliant_noop"
    assert final_report.get("gate_evaluated") is False
    assert final_report.get("gate_skip_reason") == "pre_already_compliant"
    assert not any("resolved_gain must be > 0" in str(err.get("message", "")) for err in final_report["errors"])
