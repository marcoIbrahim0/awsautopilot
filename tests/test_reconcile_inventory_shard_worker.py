from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.utils.sqs import COMPUTE_ACTIONS_JOB_TYPE
from backend.workers.jobs import reconcile_inventory_shard as shard_job


class _AccountQuery:
    def __init__(self, account: object) -> None:
        self._account = account

    def filter(self, *args, **kwargs):  # noqa: ANN002,ANN003
        return self

    def first(self):
        return self._account


class _ActionQuery:
    def __init__(self, rows: list[tuple[object]]) -> None:
        self._rows = rows

    def join(self, *args, **kwargs):  # noqa: ANN002,ANN003
        return self

    def filter(self, *args, **kwargs):  # noqa: ANN002,ANN003
        return self

    def all(self):
        return self._rows


class _WorkerSession:
    def __init__(self, account: object, action_rows: list[tuple[object]] | None = None) -> None:
        self._account = account
        self._action_rows = action_rows or []

    def query(self, *entities):  # noqa: ANN002
        if entities and entities[0] is shard_job.AwsAccount:
            return _AccountQuery(self._account)
        return _ActionQuery(self._action_rows)


def _session_scope_for(session_obj: object):
    @contextmanager
    def _scope():
        yield session_obj

    return _scope


def test_reconcile_inventory_shard_unsupported_service_marks_succeeded(monkeypatch) -> None:
    tracking = {"running": [], "finished": []}
    run_shard_id = str(uuid.uuid4())

    monkeypatch.setattr(shard_job, "session_scope", _session_scope_for(MagicMock()))
    monkeypatch.setattr(
        shard_job,
        "mark_reconcile_shard_running",
        lambda session, shard_id: tracking["running"].append(str(shard_id)),
    )

    def _mark_finished(session, shard_id, *, status_value, error_code=None, error_message=None):  # noqa: ANN001
        tracking["finished"].append((str(shard_id), status_value, error_code, error_message))

    monkeypatch.setattr(shard_job, "mark_reconcile_shard_finished", _mark_finished)
    monkeypatch.setattr(
        shard_job,
        "collect_inventory_snapshots",
        lambda *args, **kwargs: pytest.fail("collect_inventory_snapshots should not run"),
    )

    shard_job.execute_reconcile_inventory_shard_job(
        {
            "tenant_id": str(uuid.uuid4()),
            "account_id": "123456789012",
            "region": "us-east-1",
            "service": "unsupported-service",
            "run_shard_id": run_shard_id,
        }
    )

    assert tracking["running"] == [run_shard_id]
    assert tracking["finished"] == [(run_shard_id, "succeeded", None, None)]


def test_reconcile_inventory_shard_targeted_empty_resource_ids_marks_succeeded(monkeypatch) -> None:
    tracking = {"running": [], "finished": []}
    run_shard_id = str(uuid.uuid4())

    monkeypatch.setattr(shard_job, "session_scope", _session_scope_for(MagicMock()))
    monkeypatch.setattr(
        shard_job,
        "mark_reconcile_shard_running",
        lambda session, shard_id: tracking["running"].append(str(shard_id)),
    )

    def _mark_finished(session, shard_id, *, status_value, error_code=None, error_message=None):  # noqa: ANN001
        tracking["finished"].append((str(shard_id), status_value, error_code, error_message))

    monkeypatch.setattr(shard_job, "mark_reconcile_shard_finished", _mark_finished)
    monkeypatch.setattr(
        shard_job,
        "collect_inventory_snapshots",
        lambda *args, **kwargs: pytest.fail("collect_inventory_snapshots should not run"),
    )

    shard_job.execute_reconcile_inventory_shard_job(
        {
            "tenant_id": str(uuid.uuid4()),
            "account_id": "123456789012",
            "region": "us-east-1",
            "service": "s3",
            "sweep_mode": "targeted",
            "run_shard_id": run_shard_id,
        }
    )

    assert tracking["running"] == [run_shard_id]
    assert tracking["finished"] == [(run_shard_id, "succeeded", None, None)]


def test_reconcile_inventory_shard_enqueues_compute_actions_for_changed_status(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run_shard_id = str(uuid.uuid4())
    action_id = uuid.uuid4()

    account = SimpleNamespace(
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="ext-123",
    )
    worker_session = _WorkerSession(account=account, action_rows=[(action_id,), (action_id,), (None,)])
    tracking = {"running": [], "finished": []}
    collect_calls: list[dict] = []
    reevaluate_calls: list[list[uuid.UUID]] = []
    upsert_asset_calls: list[object] = []
    upsert_shadow_calls: list[object] = []
    shadow_results = iter([(True, True), (True, False), (False, False)])

    eval_open = SimpleNamespace(control_id="S3.2", resource_id="bucket-one", resource_type="AwsS3Bucket")
    eval_applied_no_lookup = SimpleNamespace(control_id=None, resource_id="bucket-two", resource_type="AwsS3Bucket")
    eval_not_applied = SimpleNamespace(control_id="S3.2", resource_id="bucket-three", resource_type="AwsS3Bucket")
    snapshots = [
        SimpleNamespace(evaluations=[eval_open, eval_applied_no_lookup]),
        SimpleNamespace(evaluations=[eval_not_applied]),
    ]

    monkeypatch.setattr(shard_job, "session_scope", _session_scope_for(worker_session))
    monkeypatch.setattr(
        shard_job,
        "mark_reconcile_shard_running",
        lambda session, shard_id: tracking["running"].append(str(shard_id)),
    )

    def _mark_finished(session, shard_id, *, status_value, error_code=None, error_message=None):  # noqa: ANN001
        tracking["finished"].append((str(shard_id), status_value, error_code, error_message))

    monkeypatch.setattr(shard_job, "mark_reconcile_shard_finished", _mark_finished)
    monkeypatch.setattr(shard_job, "assume_role", lambda role_arn, external_id: object())

    def _collect(**kwargs):
        collect_calls.append(kwargs)
        return snapshots

    monkeypatch.setattr(shard_job, "collect_inventory_snapshots", _collect)

    def _upsert_asset(**kwargs):
        upsert_asset_calls.append(kwargs["snapshot"])
        return (False, False)

    monkeypatch.setattr(shard_job, "upsert_inventory_asset", _upsert_asset)

    def _upsert_shadow(**kwargs):
        upsert_shadow_calls.append(kwargs["evaluation"])
        return next(shadow_results)

    monkeypatch.setattr(shard_job, "upsert_shadow_state", _upsert_shadow)
    monkeypatch.setattr(
        shard_job,
        "reevaluate_confirmation_for_actions",
        lambda session, action_ids: reevaluate_calls.append(action_ids),
    )
    monkeypatch.setattr(shard_job.settings, "CONTROL_PLANE_SHADOW_MODE", False, raising=False)
    monkeypatch.setattr(
        shard_job.settings,
        "SQS_INGEST_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/ingest",
        raising=False,
    )

    mock_sqs = MagicMock()
    monkeypatch.setattr(shard_job.boto3, "client", lambda *args, **kwargs: mock_sqs)

    shard_job.execute_reconcile_inventory_shard_job(
        {
            "tenant_id": str(tenant_id),
            "account_id": "123456789012",
            "region": "us-east-1",
            "service": "s3",
            "run_shard_id": run_shard_id,
            "sweep_mode": "global",
            "max_resources": "250",
        }
    )

    assert tracking["running"] == [run_shard_id]
    assert tracking["finished"] == [(run_shard_id, "succeeded", None, None)]
    assert len(collect_calls) == 1
    assert collect_calls[0]["service"] == "s3"
    assert collect_calls[0]["max_resources"] == 250
    assert len(upsert_asset_calls) == 2
    assert len(upsert_shadow_calls) == 3

    assert len(reevaluate_calls) == 1
    assert set(reevaluate_calls[0]) == {action_id}

    assert mock_sqs.send_message.call_count == 1
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["job_type"] == COMPUTE_ACTIONS_JOB_TYPE
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["account_id"] == "123456789012"
    assert payload["region"] == "us-east-1"


def test_reconcile_inventory_shard_failure_marks_failed_and_reraises(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run_shard_id = str(uuid.uuid4())
    account = SimpleNamespace(
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="ext-123",
    )
    worker_session = _WorkerSession(account=account)
    tracking = {"running": [], "finished": []}

    monkeypatch.setattr(shard_job, "session_scope", _session_scope_for(worker_session))
    monkeypatch.setattr(
        shard_job,
        "mark_reconcile_shard_running",
        lambda session, shard_id: tracking["running"].append(str(shard_id)),
    )

    def _mark_finished(session, shard_id, *, status_value, error_code=None, error_message=None):  # noqa: ANN001
        tracking["finished"].append((str(shard_id), status_value, error_code, error_message))

    monkeypatch.setattr(shard_job, "mark_reconcile_shard_finished", _mark_finished)
    monkeypatch.setattr(shard_job, "assume_role", lambda role_arn, external_id: object())
    monkeypatch.setattr(
        shard_job,
        "collect_inventory_snapshots",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("collector failure")),
    )
    monkeypatch.setattr(
        shard_job,
        "classify_reconcile_exception",
        lambda exc: ("CollectorFailure", "collector failure"),
    )

    with pytest.raises(RuntimeError, match="collector failure"):
        shard_job.execute_reconcile_inventory_shard_job(
            {
                "tenant_id": str(tenant_id),
                "account_id": "123456789012",
                "region": "us-east-1",
                "service": "s3",
                "run_shard_id": run_shard_id,
                "resource_ids": ["bucket-one"],
            }
        )

    assert tracking["running"] == [run_shard_id]
    assert tracking["finished"] == [
        (run_shard_id, "failed", "CollectorFailure", "collector failure")
    ]


def test_reconcile_inventory_shard_no_change_does_not_enqueue_compute_actions(monkeypatch) -> None:
    account = SimpleNamespace(
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="ext-123",
    )
    worker_session = _WorkerSession(account=account)

    monkeypatch.setattr(shard_job, "session_scope", _session_scope_for(worker_session))
    monkeypatch.setattr(shard_job, "mark_reconcile_shard_running", lambda *args, **kwargs: None)
    monkeypatch.setattr(shard_job, "mark_reconcile_shard_finished", lambda *args, **kwargs: None)
    monkeypatch.setattr(shard_job, "assume_role", lambda role_arn, external_id: object())
    monkeypatch.setattr(
        shard_job,
        "collect_inventory_snapshots",
        lambda **kwargs: [
            SimpleNamespace(
                evaluations=[
                    SimpleNamespace(control_id="S3.2", resource_id="bucket-one", resource_type="AwsS3Bucket")
                ]
            )
        ],
    )
    monkeypatch.setattr(shard_job, "upsert_inventory_asset", lambda **kwargs: (False, False))
    monkeypatch.setattr(shard_job, "upsert_shadow_state", lambda **kwargs: (True, False))
    monkeypatch.setattr(shard_job.settings, "CONTROL_PLANE_SHADOW_MODE", False, raising=False)
    monkeypatch.setattr(
        shard_job.settings,
        "SQS_INGEST_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/ingest",
        raising=False,
    )
    monkeypatch.setattr(
        shard_job.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("compute_actions enqueue should not run when changed_status=0"),
    )

    shard_job.execute_reconcile_inventory_shard_job(
        {
            "tenant_id": str(uuid.uuid4()),
            "account_id": "123456789012",
            "region": "us-east-1",
            "service": "s3",
            "resource_ids": ["bucket-one"],
        }
    )
