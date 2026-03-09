"""Phase 3 P0.8 regression coverage for handoff-free closure metadata."""
from __future__ import annotations

from types import SimpleNamespace

from backend.services.remediation_handoff import (
    build_action_implementation_artifacts,
    build_run_artifact_metadata,
)


def test_successful_pr_run_exposes_engineer_executable_artifacts_and_evidence() -> None:
    metadata = build_run_artifact_metadata(
        run_id="run-pr-1",
        mode="pr_only",
        status="success",
        artifacts={
            "pr_bundle": {
                "format": "terraform",
                "files": [
                    {"path": "main.tf", "content": 'terraform {}'},
                    {"path": "README.md", "content": "# Apply"},
                ],
                "steps": ["review", "apply"],
                "metadata": {
                    "generated_action_count": 1,
                    "skipped_action_count": 0,
                },
            },
            "change_summary": {
                "applied_at": "2026-03-04T10:12:00+00:00",
                "applied_by": "ops@example.com",
                "changes": [
                    {
                        "field": "allowed cidr",
                        "before": "0.0.0.0/0",
                        "after": "10.0.0.0/24",
                    }
                ],
            },
            "risk_snapshot": {
                "checks": [{"code": "owner_confirmed", "status": "pass"}],
                "recommendation": "apply",
            },
        },
        logs="generated bundle\nreviewed bundle",
        action_status="open",
    )

    assert [artifact.key for artifact in metadata.implementation_artifacts] == ["pr_bundle", "change_summary"]
    assert metadata.implementation_artifacts[0].executable is True
    assert metadata.implementation_artifacts[0].href == "/remediation-runs/run-pr-1#run-generated-files"
    assert metadata.implementation_artifacts[1].href == "/remediation-runs/run-pr-1#run-activity"

    evidence = {pointer.key: pointer for pointer in metadata.evidence_pointers}
    assert {"pr_bundle", "change_summary", "risk_snapshot", "activity_log"} <= set(evidence)
    assert evidence["risk_snapshot"].href == "/remediation-runs/run-pr-1#run-generated-files"

    checklist = {item.id: item for item in metadata.closure_checklist}
    assert checklist["artifact_recorded"].status == "complete"
    assert checklist["evidence_attached"].status == "complete"
    assert checklist["action_closure_verified"].status == "pending"


def test_successful_direct_fix_run_exposes_closure_and_evidence_links() -> None:
    metadata = build_run_artifact_metadata(
        run_id="run-direct-1",
        mode="direct_fix",
        status="success",
        artifacts={
            "direct_fix": {
                "outcome": "S3 Block Public Access enabled at account level",
                "recorded_at": "2026-03-05T09:00:00+00:00",
                "post_check_passed": True,
                "log_count": 3,
                "log_excerpt": ["Pre-check", "Apply", "Post-check"],
            }
        },
        outcome="S3 Block Public Access enabled at account level",
        logs="Pre-check\nApply\nPost-check",
        action_status="resolved",
    )

    assert [artifact.key for artifact in metadata.implementation_artifacts] == ["direct_fix"]
    assert metadata.implementation_artifacts[0].href == "/remediation-runs/run-direct-1#run-activity"
    assert metadata.implementation_artifacts[0].metadata["post_check_passed"] is True

    evidence = {pointer.key: pointer for pointer in metadata.evidence_pointers}
    assert {"direct_fix", "activity_log"} <= set(evidence)

    checklist = {item.id: item for item in metadata.closure_checklist}
    assert checklist["artifact_recorded"].status == "complete"
    assert checklist["evidence_attached"].status == "complete"
    assert checklist["action_closure_verified"].status == "complete"


def test_pending_legacy_run_without_artifacts_remains_backward_compatible() -> None:
    metadata = build_run_artifact_metadata(
        run_id="run-legacy-1",
        mode="pr_only",
        status="pending",
        artifacts=None,
        outcome=None,
        logs=None,
        action_status="open",
    )

    assert metadata.implementation_artifacts == []
    assert metadata.evidence_pointers == []
    assert metadata.closure_checklist == []


def test_action_detail_links_surface_latest_run_artifacts_for_engineering() -> None:
    runs = [
        SimpleNamespace(
            id="run-pr-2",
            mode="pr_only",
            status="success",
            artifacts={
                "pr_bundle": {
                    "format": "terraform",
                    "files": [{"path": "main.tf", "content": 'terraform {}'}],
                    "steps": ["review"],
                    "metadata": {},
                }
            },
            outcome="Bundle generated",
            logs="generated",
            completed_at="2026-03-06T10:00:00+00:00",
            created_at="2026-03-06T09:55:00+00:00",
        ),
        SimpleNamespace(
            id="run-direct-2",
            mode="direct_fix",
            status="success",
            artifacts={
                "direct_fix": {
                    "outcome": "GuardDuty enabled",
                    "recorded_at": "2026-03-06T11:00:00+00:00",
                    "post_check_passed": True,
                    "log_count": 2,
                }
            },
            outcome="GuardDuty enabled",
            logs="apply\nverify",
            completed_at="2026-03-06T11:00:00+00:00",
            created_at="2026-03-06T10:58:00+00:00",
        ),
    ]

    action_links = build_action_implementation_artifacts(runs, action_status="resolved")

    assert [item.run_id for item in action_links] == ["run-pr-2", "run-direct-2"]
    assert action_links[0].href == "/remediation-runs/run-pr-2#run-generated-files"
    assert action_links[0].executable is True
    assert action_links[1].href == "/remediation-runs/run-direct-2#run-activity"
    assert all(item.closure_status == "complete" for item in action_links)
