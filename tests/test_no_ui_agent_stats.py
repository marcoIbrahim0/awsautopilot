from __future__ import annotations

from scripts.lib.no_ui_agent_stats import (
    aggregate_findings,
    compute_delta,
    select_pr_only_strategy,
    select_target_finding,
)


def test_aggregate_findings_counts() -> None:
    findings = [
        {
            "status": "NEW",
            "severity_label": "HIGH",
            "control_id": "EC2.53",
            "source": "security_hub",
        },
        {
            "status": "NOTIFIED",
            "severity_label": "MEDIUM",
            "control_id": "S3.2",
            "source": "security_hub",
        },
        {
            "status": "RESOLVED",
            "severity_label": "LOW",
            "control_id": "EC2.53",
            "source": "event_monitor_shadow",
        },
    ]

    summary = aggregate_findings(findings)
    assert summary["total"] == 3
    assert summary["open_count"] == 2
    assert summary["resolved_count"] == 1
    assert summary["by_status"]["NEW"] == 1
    assert summary["by_control_id"]["EC2.53"] == 2


def test_compute_delta_with_kpis() -> None:
    pre = {
        "by_status": {"NEW": 3, "NOTIFIED": 2, "RESOLVED": 1},
        "by_severity": {"HIGH": 2},
        "by_control_id": {"EC2.53": 4, "S3.2": 2},
    }
    post = {
        "by_status": {"NEW": 1, "NOTIFIED": 1, "RESOLVED": 4},
        "by_severity": {"HIGH": 1},
        "by_control_id": {"EC2.53": 1, "S3.2": 2},
    }

    delta = compute_delta(pre, post, "EC2.53")
    assert delta["status_delta"]["RESOLVED"] == 3
    assert delta["kpis"]["open_drop"] == 3
    assert delta["kpis"]["resolved_gain"] == 3
    assert delta["kpis"]["tested_control_delta"] == -3


def test_select_target_finding_prefers_control_then_severity_then_time() -> None:
    findings = [
        {
            "id": "f-a",
            "status": "NEW",
            "control_id": "S3.2",
            "severity_label": "MEDIUM",
            "updated_at_db": "2026-02-19T10:00:00Z",
            "remediation_action_id": "a-a",
        },
        {
            "id": "f-b",
            "status": "NOTIFIED",
            "control_id": "EC2.53",
            "severity_label": "HIGH",
            "updated_at_db": "2026-02-19T09:00:00Z",
            "remediation_action_id": "a-b",
        },
        {
            "id": "f-c",
            "status": "NEW",
            "control_id": "EC2.53",
            "severity_label": "CRITICAL",
            "updated_at_db": "2026-02-19T08:00:00Z",
            "remediation_action_id": "a-c",
        },
    ]

    selected = select_target_finding(findings, ["EC2.53", "S3.2"])
    assert selected is not None
    assert selected["id"] == "f-c"


def test_select_pr_only_strategy_recommended_first() -> None:
    strategies = [
        {
            "strategy_id": "fallback",
            "mode": "pr_only",
            "requires_inputs": False,
            "recommended": False,
        },
        {
            "strategy_id": "best",
            "mode": "pr_only",
            "requires_inputs": False,
            "recommended": True,
        },
    ]

    selected = select_pr_only_strategy(strategies)
    assert selected is not None
    assert selected["strategy_id"] == "best"
