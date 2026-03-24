from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

from backend.config import settings
from scripts import run_unresolved_pr_bundle_sweep as sweep


def _candidate(*, region: str | None = "eu-north-1") -> sweep.FamilyCandidate:
    return sweep.FamilyCandidate(
        tenant_id=str(uuid.uuid4()),
        action_type="s3_bucket_access_logging",
        account_id="696505809372",
        region=region,
        status="open",
        total_actions=1,
        action_ids=[str(uuid.uuid4())],
        representative_action_id=str(uuid.uuid4()),
        control_ids=["S3.9"],
        not_run_yet=1,
        run_not_successful=0,
        needs_followup=0,
        metadata_only=0,
        confirmed=0,
        latest_artifacts=None,
        latest_run_id=None,
    )


def test_refresh_family_locally_runs_reconcile_and_scoped_compute(monkeypatch) -> None:
    candidate = _candidate()
    reconcile_jobs: list[dict[str, object]] = []
    compute_calls: list[dict[str, object]] = []
    session_token = object()

    monkeypatch.setattr(sweep, "_reconcile_services_for_control", lambda control_id: ["s3", "ec2"])
    monkeypatch.setattr(
        sweep,
        "build_reconcile_inventory_shard_job_payload",
        lambda **kwargs: kwargs,
    )

    from backend.workers.jobs import reconcile_inventory_shard as shard_job
    from backend.services import action_engine
    from backend.workers import database as worker_db

    monkeypatch.setattr(
        shard_job,
        "execute_reconcile_inventory_shard_job",
        lambda job: reconcile_jobs.append(job),
    )

    @contextmanager
    def _session_scope():
        yield session_token

    monkeypatch.setattr(worker_db, "session_scope", _session_scope)

    def _compute_actions_for_tenant(session, *, tenant_id, account_id, region):  # noqa: ANN001
        compute_calls.append(
            {
                "session": session,
                "tenant_id": tenant_id,
                "account_id": account_id,
                "region": region,
            }
        )
        return {
            "actions_updated": 2,
            "phase_timings_ms": {"group_projection": 1200, "total": 1800},
        }

    monkeypatch.setattr(action_engine, "compute_actions_for_tenant", _compute_actions_for_tenant)

    result = sweep._refresh_family_locally(candidate)

    assert result["mode"] == "local_sync_refresh"
    assert result["reconcile"]["status"] == "completed"
    assert [job["service"] for job in reconcile_jobs] == ["s3", "ec2"]
    assert result["compute_after_reconcile"]["status"] == "completed"
    assert result["compute_after_reconcile"]["account_id"] == candidate.account_id
    assert result["compute_after_reconcile"]["region"] == candidate.region
    assert result["compute_after_reconcile"]["elapsed_ms"] >= 0
    assert result["compute_after_reconcile"]["result"]["phase_timings_ms"]["group_projection"] == 1200
    assert len(compute_calls) == 1
    assert compute_calls[0]["session"] is session_token
    assert compute_calls[0]["tenant_id"] == uuid.UUID(candidate.tenant_id)
    assert compute_calls[0]["account_id"] == candidate.account_id
    assert compute_calls[0]["region"] == candidate.region


def test_refresh_family_locally_requires_region() -> None:
    result = sweep._refresh_family_locally(_candidate(region=None))
    assert result == {"skipped": True, "reason": "region_required_for_local_refresh"}


def test_execute_run_locally_builds_worker_payload(monkeypatch) -> None:
    candidate = _candidate()
    recorded: dict[str, object] = {}

    def _build_payload(**kwargs):  # noqa: ANN003
        recorded["build_kwargs"] = kwargs
        return {"job_type": "remediation_run", "run_id": kwargs["run_id"].hex}

    def _execute(job):  # noqa: ANN001
        recorded["job"] = job

    monkeypatch.setattr(sweep, "build_remediation_run_job_payload", _build_payload)

    from backend.workers.jobs import remediation_run as remediation_run_job

    monkeypatch.setattr(remediation_run_job, "execute_remediation_run_job", _execute)

    run_payload = {
        "id": str(uuid.uuid4()),
        "action_id": candidate.representative_action_id,
        "mode": "pr_only",
        "created_at": "2026-03-24T20:00:00+00:00",
        "artifacts": {
            "selected_strategy": "config_enable_account_local_delivery",
            "strategy_inputs": {"delivery_bucket": "bucket-name"},
            "group_bundle": {
                "action_ids": candidate.action_ids,
                "action_resolutions": [
                    {
                        "action_id": candidate.action_ids[0],
                        "strategy_id": "config_enable_account_local_delivery",
                        "strategy_inputs": {"delivery_bucket": "bucket-name"},
                    }
                ],
            },
        },
    }
    request_body = {
        "strategy_id": "config_enable_account_local_delivery",
        "strategy_inputs": {"delivery_bucket": "bucket-name"},
        "risk_acknowledged": True,
    }

    result = sweep._execute_run_locally(candidate, run_payload, request_body=request_body)

    assert result["status"] == "completed"
    assert result["elapsed_ms"] >= 0
    assert recorded["job"] == {"job_type": "remediation_run", "run_id": uuid.UUID(run_payload["id"]).hex}
    build_kwargs = recorded["build_kwargs"]
    assert build_kwargs["schema_version"] == sweep.REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert build_kwargs["strategy_id"] == "config_enable_account_local_delivery"
    assert build_kwargs["strategy_inputs"] == {"delivery_bucket": "bucket-name"}
    assert build_kwargs["group_action_ids"] == candidate.action_ids
    assert build_kwargs["risk_acknowledged"] is True


def test_local_target_account_profile_sets_and_restores_settings(monkeypatch) -> None:
    monkeypatch.delenv("ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION", raising=False)
    monkeypatch.delenv("LOCAL_TARGET_ACCOUNT_AWS_PROFILE", raising=False)
    original_allow = settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION
    original_profile = settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE

    with sweep._local_target_account_profile("test28-root"):
        assert settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION is True
        assert settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE == "test28-root"
        assert os.environ["ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION"] == "true"
        assert os.environ["LOCAL_TARGET_ACCOUNT_AWS_PROFILE"] == "test28-root"

    assert settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION == original_allow
    assert settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE == original_profile
    assert "ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION" not in os.environ
    assert "LOCAL_TARGET_ACCOUNT_AWS_PROFILE" not in os.environ


def test_run_candidate_applies_local_profile_for_local_execution_and_refresh(monkeypatch, tmp_path: Path) -> None:
    candidate = _candidate()
    observed: dict[str, object] = {}

    class _Client:
        def download_pr_bundle_zip(self, run_id: str) -> bytes:
            return b"zip-bytes"

    monkeypatch.setattr(sweep, "snapshot_family", lambda candidate: {"not_run_yet": 1, "run_not_successful": 0})
    monkeypatch.setattr(sweep, "build_request_candidates", lambda client, candidate: [{"strategy_id": "x", "risk_acknowledged": True}])
    monkeypatch.setattr(
        sweep,
        "_create_or_reuse_run",
        lambda client, candidate, request_bodies: (
            "group-1",
            request_bodies[0],
            {"ok": True},
            {"id": str(uuid.uuid4()), "action_id": candidate.representative_action_id, "status": "pending"},
            [],
        ),
    )

    def _execute(candidate, run_payload, *, request_body):  # noqa: ANN001
        observed["execute_allow"] = settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION
        observed["execute_profile"] = settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE
        return {"status": "completed"}

    monkeypatch.setattr(sweep, "_execute_run_locally", _execute)
    monkeypatch.setattr(sweep, "poll_run_success", lambda client, run_id, *, timeout_sec, poll_sec: {"id": run_id, "status": "success"})
    monkeypatch.setattr(sweep, "extract_zip_safe", lambda zip_path, workspace: None)
    monkeypatch.setattr(sweep, "run_bundle", lambda workspace, *, aws_profile, region, timeout_sec: [{"exit_code": 0}])
    monkeypatch.setattr(sweep, "_replay_group_reports_if_present", lambda client, workspace: {"status": "completed", "count": 0})

    def _refresh(client, candidate, *, poll_sec, timeout_sec, local_sync_refresh):  # noqa: ANN001
        observed["refresh_allow"] = settings.ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION
        observed["refresh_profile"] = settings.LOCAL_TARGET_ACCOUNT_AWS_PROFILE
        return {"mode": "local_sync_refresh"}

    monkeypatch.setattr(sweep, "refresh_family", _refresh)
    snapshots = iter(
        [
            {"not_run_yet": 1, "run_not_successful": 0},
            {"not_run_yet": 0, "run_not_successful": 0},
        ]
    )
    monkeypatch.setattr(sweep, "snapshot_family", lambda candidate: next(snapshots))

    args = type(
        "Args",
        (),
        {
            "poll_interval_sec": 1,
            "run_timeout_sec": 1,
            "terraform_timeout_sec": 1,
            "verify_timeout_sec": 1,
            "local_sync_refresh": True,
            "aws_profile": "test28-root",
        },
    )()

    result = sweep.run_candidate(_Client(), candidate, tmp_path, args)

    assert result["status"] == "passed"
    assert observed["execute_allow"] is True
    assert observed["execute_profile"] == "test28-root"
    assert observed["refresh_allow"] is True
    assert observed["refresh_profile"] == "test28-root"


def test_replay_group_reports_if_present(tmp_path: Path) -> None:
    replay_dir = tmp_path / ".bundle-callback-replay"
    replay_dir.mkdir(parents=True)
    payload_path = replay_dir / "finished.json"
    payload = {"event": "finished", "token": "abc"}
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    class _Client:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def report_group_run(self, body: dict[str, object]) -> dict[str, object]:
            self.calls.append(body)
            return {"ok": True}

    client = _Client()

    result = sweep._replay_group_reports_if_present(client, tmp_path)

    assert result["status"] == "completed"
    assert result["count"] == 1
    assert client.calls == [payload]
    assert not payload_path.exists()
