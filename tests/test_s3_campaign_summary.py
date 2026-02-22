from __future__ import annotations

import json
from pathlib import Path

from scripts.run_s3_controls_campaign import _build_final_campaign_summary, parse_args


def _write_control_artifacts(
    campaign_dir: Path,
    control_id: str,
    *,
    status: str,
    exit_code: int,
    outcome_type: str,
    gate_evaluated: bool,
    gate_skip_reason: str | None,
    resolved_gain: int,
    tested_control_delta: int,
    run_id: str | None = None,
    target_finding_id: str | None = None,
    target_action_id: str | None = None,
    has_terraform_apply: bool = True,
) -> dict[str, object]:
    control_dir = campaign_dir / control_id.replace(".", "_")
    control_dir.mkdir(parents=True, exist_ok=True)

    final_report = {
        "status": status,
        "run_id": run_id if run_id is not None else f"run-{control_id}",
        "target_finding_id": target_finding_id if target_finding_id is not None else f"finding-{control_id}",
        "target_action_id": target_action_id if target_action_id is not None else f"action-{control_id}",
        "delta": {
            "kpis": {
                "resolved_gain": resolved_gain,
                "tested_control_delta": tested_control_delta,
            }
        },
        "outcome_type": outcome_type,
        "gate_evaluated": gate_evaluated,
        "gate_skip_reason": gate_skip_reason,
    }
    (control_dir / "final_report.json").write_text(json.dumps(final_report), encoding="utf-8")

    transcript = (
        [{"command": "terraform apply", "exit_code": exit_code, "stdout": "", "stderr": ""}]
        if has_terraform_apply
        else [{"command": "noop_no_target", "exit_code": 0, "stdout": "skipped", "stderr": ""}]
    )
    (control_dir / "terraform_transcript.json").write_text(json.dumps(transcript), encoding="utf-8")

    return {
        "control_id": control_id,
        "output_dir": str(control_dir),
        "status": status,
        "exit_code": exit_code,
        "run_id": run_id if run_id is not None else f"run-{control_id}",
        "target_finding_id": target_finding_id if target_finding_id is not None else f"finding-{control_id}",
        "target_action_id": target_action_id if target_action_id is not None else f"action-{control_id}",
    }


def test_final_campaign_summary_counts_outcome_types(tmp_path: Path) -> None:
    controls = ["Config.1", "SSM.7", "EC2.182"]
    results = [
        _write_control_artifacts(
            tmp_path,
            "Config.1",
            status="success",
            exit_code=0,
            outcome_type="remediated",
            gate_evaluated=True,
            gate_skip_reason=None,
            resolved_gain=1,
            tested_control_delta=-1,
        ),
        _write_control_artifacts(
            tmp_path,
            "SSM.7",
            status="success",
            exit_code=0,
            outcome_type="already_compliant_noop",
            gate_evaluated=False,
            gate_skip_reason="pre_already_compliant",
            resolved_gain=0,
            tested_control_delta=0,
        ),
        _write_control_artifacts(
            tmp_path,
            "EC2.182",
            status="failed",
            exit_code=1,
            outcome_type="failed",
            gate_evaluated=True,
            gate_skip_reason=None,
            resolved_gain=0,
            tested_control_delta=0,
        ),
    ]

    summary = _build_final_campaign_summary(tmp_path, results, controls)

    assert summary["remediated_count"] == 1
    assert summary["already_compliant_noop_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["overall_passed"] is False
    assert summary["controls"]["Config.1"]["outcome_type"] == "remediated"
    assert summary["controls"]["SSM.7"]["outcome_type"] == "already_compliant_noop"
    assert summary["controls"]["EC2.182"]["outcome_type"] == "failed"


def test_final_campaign_summary_all_noop_is_overall_pass(tmp_path: Path) -> None:
    controls = ["Config.1", "SSM.7", "EC2.7", "EC2.182"]
    results = [
        _write_control_artifacts(
            tmp_path,
            "Config.1",
            status="success",
            exit_code=0,
            outcome_type="already_compliant_noop",
            gate_evaluated=False,
            gate_skip_reason="pre_already_compliant",
            resolved_gain=0,
            tested_control_delta=0,
            run_id="",
            target_finding_id="",
            target_action_id="",
            has_terraform_apply=False,
        ),
        _write_control_artifacts(
            tmp_path,
            "SSM.7",
            status="success",
            exit_code=0,
            outcome_type="already_compliant_noop",
            gate_evaluated=False,
            gate_skip_reason="pre_already_compliant",
            resolved_gain=0,
            tested_control_delta=0,
            run_id="",
            target_finding_id="",
            target_action_id="",
            has_terraform_apply=False,
        ),
        _write_control_artifacts(
            tmp_path,
            "EC2.7",
            status="success",
            exit_code=0,
            outcome_type="already_compliant_noop",
            gate_evaluated=False,
            gate_skip_reason="pre_already_compliant",
            resolved_gain=0,
            tested_control_delta=0,
            run_id="",
            target_finding_id="",
            target_action_id="",
            has_terraform_apply=False,
        ),
        _write_control_artifacts(
            tmp_path,
            "EC2.182",
            status="success",
            exit_code=0,
            outcome_type="already_compliant_noop",
            gate_evaluated=False,
            gate_skip_reason="pre_already_compliant",
            resolved_gain=0,
            tested_control_delta=0,
            run_id="",
            target_finding_id="",
            target_action_id="",
            has_terraform_apply=False,
        ),
    ]

    summary = _build_final_campaign_summary(tmp_path, results, controls)

    assert summary["overall_passed"] is True
    assert summary["remediated_count"] == 0
    assert summary["already_compliant_noop_count"] == 4
    assert summary["failed_count"] == 0
    for control_id in controls:
        control_row = summary["controls"][control_id]
        assert control_row["outcome_type"] == "already_compliant_noop"
        assert control_row["definition_of_done_passed"] is True


def test_parse_args_accepts_output_dir_and_reconcile_after_apply_flag() -> None:
    args = parse_args(
        [
            "--output-dir",
            "/tmp/campaign_v1_validation",
            "--reconcile-after-apply",
            "--controls",
            "Config.1,SSM.7,EC2.7,EC2.182",
        ]
    )
    assert args.output_dir == "/tmp/campaign_v1_validation"
    assert args.reconcile_after_apply is True
