from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import run_multi_account_campaign as campaign


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs

    def login(self, email: str, password: str) -> dict[str, str]:
        del email, password
        return {"access_token": "token"}


def _write_final_campaign_summary(
    output_dir: Path,
    *,
    overall_passed: bool,
    remediated_count: int,
    already_compliant_noop_count: int,
    failed_count: int,
    control_outcomes: dict[str, str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "overall_passed": overall_passed,
        "remediated_count": remediated_count,
        "already_compliant_noop_count": already_compliant_noop_count,
        "failed_count": failed_count,
        "controls": {control_id: {"outcome_type": outcome} for control_id, outcome in control_outcomes.items()},
    }
    (output_dir / "final_campaign_summary.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_campaign_summary_error(output_dir: Path, message: str) -> None:
    payload = {
        "results": [
            {
                "errors": [
                    {
                        "message": message,
                    }
                ]
            }
        ]
    }
    (output_dir / "campaign_summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_multi_account_campaign_aggregates_per_account_results(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "multi"
    monkeypatch.setattr(campaign, "SaaSApiClient", _FakeClient)
    monkeypatch.setattr(campaign, "_prompt_credentials", lambda: ("user@example.com", "secret"))
    monkeypatch.setattr(
        campaign,
        "_list_validated_accounts",
        lambda _client: [
            {"account_id": "111111111111", "status": "validated", "region": None},
            {"account_id": "222222222222", "status": "validated", "region": "us-east-1"},
        ],
    )

    def fake_run(cmd: list[str], env: dict[str, str], check: bool = False):
        del check
        assert env["SAAS_EMAIL"] == "user@example.com"
        assert env["SAAS_PASSWORD"] == "secret"
        account_id = cmd[cmd.index("--account-id") + 1]
        output_dir = Path(cmd[cmd.index("--output-dir") + 1])
        if account_id == "111111111111":
            _write_final_campaign_summary(
                output_dir,
                overall_passed=True,
                remediated_count=1,
                already_compliant_noop_count=3,
                failed_count=0,
                control_outcomes={
                    "Config.1": "remediated",
                    "SSM.7": "already_compliant_noop",
                    "EC2.7": "already_compliant_noop",
                    "EC2.182": "already_compliant_noop",
                },
            )
        else:
            _write_final_campaign_summary(
                output_dir,
                overall_passed=True,
                remediated_count=0,
                already_compliant_noop_count=4,
                failed_count=0,
                control_outcomes={
                    "Config.1": "already_compliant_noop",
                    "SSM.7": "already_compliant_noop",
                    "EC2.7": "already_compliant_noop",
                    "EC2.182": "already_compliant_noop",
                },
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(campaign.subprocess, "run", fake_run)

    exit_code = campaign.main(
        [
            "--api-base",
            "https://api.valensjewelry.com",
            "--region",
            "eu-north-1",
            "--controls",
            "Config.1,SSM.7,EC2.7,EC2.182",
            "--output-dir",
            str(run_dir),
            "--reconcile-after-apply",
        ]
    )

    assert exit_code == 0
    summary = json.loads((run_dir / "cross_account_summary.json").read_text(encoding="utf-8"))
    assert summary["accounts_total"] == 2
    assert summary["accounts_passed"] == 2
    assert summary["accounts_failed"] == 0
    assert summary["overall_passed"] is True

    by_account = {row["account_id"]: row for row in summary["accounts"]}
    assert by_account["111111111111"]["overall_passed"] is True
    assert by_account["111111111111"]["control_outcomes"]["Config.1"] == "remediated"
    assert by_account["222222222222"]["control_outcomes"]["EC2.182"] == "already_compliant_noop"


def test_multi_account_campaign_overall_passed_false_if_any_account_fails(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "multi-fail"
    monkeypatch.setattr(campaign, "SaaSApiClient", _FakeClient)
    monkeypatch.setattr(campaign, "_prompt_credentials", lambda: ("user@example.com", "secret"))
    monkeypatch.setattr(
        campaign,
        "_list_validated_accounts",
        lambda _client: [
            {"account_id": "111111111111", "status": "validated", "region": None},
            {"account_id": "222222222222", "status": "validated", "region": None},
        ],
    )

    def fake_run(cmd: list[str], env: dict[str, str], check: bool = False):
        del check, env
        account_id = cmd[cmd.index("--account-id") + 1]
        output_dir = Path(cmd[cmd.index("--output-dir") + 1])
        if account_id == "111111111111":
            _write_final_campaign_summary(
                output_dir,
                overall_passed=True,
                remediated_count=0,
                already_compliant_noop_count=4,
                failed_count=0,
                control_outcomes={"Config.1": "already_compliant_noop"},
            )
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        _write_final_campaign_summary(
            output_dir,
            overall_passed=False,
            remediated_count=0,
            already_compliant_noop_count=3,
            failed_count=1,
            control_outcomes={"EC2.182": "failed"},
        )
        _write_campaign_summary_error(output_dir, "Selected control mismatch")
        return subprocess.CompletedProcess(args=cmd, returncode=1)

    monkeypatch.setattr(campaign.subprocess, "run", fake_run)

    exit_code = campaign.main(
        [
            "--api-base",
            "https://api.valensjewelry.com",
            "--region",
            "eu-north-1",
            "--controls",
            "Config.1,SSM.7,EC2.7,EC2.182",
            "--output-dir",
            str(run_dir),
        ]
    )

    assert exit_code == 1
    summary = json.loads((run_dir / "cross_account_summary.json").read_text(encoding="utf-8"))
    assert summary["accounts_total"] == 2
    assert summary["accounts_passed"] == 1
    assert summary["accounts_failed"] == 1
    assert summary["overall_passed"] is False

    by_account = {row["account_id"]: row for row in summary["accounts"]}
    assert by_account["222222222222"]["overall_passed"] is False
    assert by_account["222222222222"]["failed_count"] == 1
    assert by_account["222222222222"]["error"] == "Selected control mismatch"
