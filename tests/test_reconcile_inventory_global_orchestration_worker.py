from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

from worker.jobs import reconcile_inventory_global_orchestration as orchestration


@contextmanager
def _dummy_session_scope():
    yield MagicMock()


def test_orchestration_worker_enqueues_shards_and_marks_succeeded(monkeypatch) -> None:
    payload_summary = {
        "services": ["ec2", "s3"],
        "max_resources": 250,
        "checkpoint": {"account_index": 0, "region_index": 0, "service_index": 0},
        "stats": {"enqueued": 0},
    }
    accounts = [
        SimpleNamespace(
            account_id="123456789012",
            regions=["us-east-1"],
            status="validated",
            external_id="ext-1",
            role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        )
    ]
    states: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        orchestration,
        "_load_orchestration_context",
        lambda tenant_id, orchestration_job_id, job: (payload_summary, "ext-1", accounts),
    )
    monkeypatch.setattr(
        orchestration,
        "_persist_orchestration_state",
        lambda tenant_id, orchestration_job_id, summary, *, status, error_message=None: states.append(
            (status, json.loads(json.dumps(summary)))
        ),
    )
    monkeypatch.setattr(orchestration, "collect_reconciliation_queue_snapshot", lambda: {})
    monkeypatch.setattr(orchestration, "evaluate_reconciliation_prereqs", lambda *args, **kwargs: {"ok": True, "reasons": [], "snapshot": {}})
    monkeypatch.setattr(orchestration, "session_scope", _dummy_session_scope)

    monkeypatch.setattr(orchestration.settings, "SQS_INVENTORY_RECONCILE_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/inventory", raising=False)
    monkeypatch.setattr(orchestration.settings, "AWS_REGION", "us-east-1", raising=False)
    monkeypatch.setattr(orchestration.settings, "CONTROL_PLANE_SHADOW_MODE", True, raising=False)

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-1"}
    monkeypatch.setattr(orchestration.boto3, "client", lambda *args, **kwargs: mock_sqs)

    orchestration.execute_reconcile_inventory_global_orchestration_job(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000111",
            "orchestration_job_id": "00000000-0000-0000-0000-000000000222",
            "job_type": "reconcile_inventory_global_orchestration",
            "created_at": "2026-02-12T10:00:00Z",
        }
    )

    assert mock_sqs.send_message.call_count == 2
    bodies = [json.loads(call.kwargs["MessageBody"]) for call in mock_sqs.send_message.call_args_list]
    assert sorted(body["service"] for body in bodies) == ["ec2", "s3"]

    assert states
    final_status, final_summary = states[-1]
    assert final_status == "succeeded"
    assert final_summary["checkpoint"]["account_index"] == 1
    assert int(final_summary["stats"]["enqueued"]) == 2


def test_orchestration_worker_resumes_from_service_checkpoint(monkeypatch) -> None:
    payload_summary = {
        "services": ["ec2", "s3"],
        "max_resources": 250,
        "checkpoint": {"account_index": 0, "region_index": 0, "service_index": 1},
        "stats": {"enqueued": 0},
    }
    accounts = [
        SimpleNamespace(
            account_id="123456789012",
            regions=["us-east-1"],
            status="validated",
            external_id="ext-1",
            role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        )
    ]
    states: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        orchestration,
        "_load_orchestration_context",
        lambda tenant_id, orchestration_job_id, job: (payload_summary, "ext-1", accounts),
    )
    monkeypatch.setattr(
        orchestration,
        "_persist_orchestration_state",
        lambda tenant_id, orchestration_job_id, summary, *, status, error_message=None: states.append(
            (status, json.loads(json.dumps(summary)))
        ),
    )
    monkeypatch.setattr(orchestration, "collect_reconciliation_queue_snapshot", lambda: {})
    monkeypatch.setattr(orchestration, "evaluate_reconciliation_prereqs", lambda *args, **kwargs: {"ok": True, "reasons": [], "snapshot": {}})
    monkeypatch.setattr(orchestration, "session_scope", _dummy_session_scope)

    monkeypatch.setattr(orchestration.settings, "SQS_INVENTORY_RECONCILE_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/inventory", raising=False)
    monkeypatch.setattr(orchestration.settings, "AWS_REGION", "us-east-1", raising=False)
    monkeypatch.setattr(orchestration.settings, "CONTROL_PLANE_SHADOW_MODE", True, raising=False)

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-1"}
    monkeypatch.setattr(orchestration.boto3, "client", lambda *args, **kwargs: mock_sqs)

    orchestration.execute_reconcile_inventory_global_orchestration_job(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000111",
            "orchestration_job_id": "00000000-0000-0000-0000-000000000222",
            "job_type": "reconcile_inventory_global_orchestration",
            "created_at": "2026-02-12T10:00:00Z",
        }
    )

    assert mock_sqs.send_message.call_count == 1
    body = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert body["service"] == "s3"

    final_status, final_summary = states[-1]
    assert final_status == "succeeded"
    assert int(final_summary["stats"]["enqueued"]) == 1
