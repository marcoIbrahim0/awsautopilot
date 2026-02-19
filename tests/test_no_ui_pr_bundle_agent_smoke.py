from __future__ import annotations

import io
import zipfile
from pathlib import Path

from scripts.lib.no_ui_agent_client import ApiError
from scripts.run_no_ui_pr_bundle_agent import NoUiPrBundleAgent


class FakeClient:
    def __init__(self) -> None:
        self.run_polls = 0
        self.transcript = []

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

    def create_pr_bundle_run(self, action_id: str, strategy_id: str):
        del action_id, strategy_id
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

    def create_pr_bundle_run(self, action_id: str, strategy_id: str | None = None):
        del action_id
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
        "api_base": "https://api.valensjewelry.com",
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


def test_no_ui_agent_dry_run_smoke_pr_only_without_strategy(tmp_path: Path) -> None:
    settings = {
        "api_base": "https://api.valensjewelry.com",
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
        "api_base": "https://api.valensjewelry.com",
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
