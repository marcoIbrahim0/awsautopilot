from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.utils.sqs import COMPUTE_ACTIONS_JOB_TYPE
from backend.workers.jobs import ingest_control_plane_events as worker


class _Query:
    def __init__(self, result: object) -> None:
        self._result = result

    def filter(self, *args, **kwargs):  # noqa: ANN002,ANN003
        return self

    def first(self):
        return self._result

    def join(self, *args, **kwargs):  # noqa: ANN002,ANN003
        return self

    def all(self):
        return self._result if isinstance(self._result, list) else []


class _WorkerSession:
    def __init__(
        self,
        *,
        account: object | None,
        duplicate_event: object | None = None,
        action_rows: list[tuple[object]] | None = None,
    ) -> None:
        self._account = account
        self._duplicate_event = duplicate_event
        self._action_rows = action_rows or []
        self.added: list[object] = []

    def query(self, *entities):  # noqa: ANN002
        first = entities[0] if entities else None
        if first is worker.ControlPlaneEvent:
            return _Query(self._duplicate_event)
        if first is worker.AwsAccount:
            return _Query(self._account)
        return _Query(self._action_rows)

    def add(self, value: object) -> None:
        self.added.append(value)


def _session_scope_for(session_obj: object):
    @contextmanager
    def _scope():
        yield session_obj

    return _scope


def _job_payload(*, tenant_id: uuid.UUID) -> dict[str, object]:
    return {
        "tenant_id": str(tenant_id),
        "account_id": "123456789012",
        "region": "us-east-1",
        "event_id": "evt-123",
        "event_time": "2026-03-30T10:00:00Z",
        "created_at": "2026-03-30T10:00:01Z",
        "intake_time": "2026-03-30T10:00:02Z",
        "event": {
            "source": "aws.s3",
            "detail-type": "AWS API Call via CloudTrail",
            "detail": {
                "eventName": "PutBucketLifecycleConfiguration",
                "eventCategory": "Management",
            },
        },
    }


def test_ingest_control_plane_events_enqueues_compute_actions_in_shadow_mode(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    action_id = uuid.uuid4()
    account = SimpleNamespace(
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="ext-123",
    )
    session = _WorkerSession(account=account, action_rows=[(action_id,)])
    reevaluate_calls: list[list[uuid.UUID]] = []

    monkeypatch.setattr(worker, "session_scope", _session_scope_for(session))
    monkeypatch.setattr(worker, "is_supported_management_event", lambda event: (True, None))
    monkeypatch.setattr(worker, "assume_role", lambda **kwargs: object())
    monkeypatch.setattr(
        worker,
        "derive_control_evaluations",
        lambda **kwargs: [
            SimpleNamespace(
                control_id="S3.11",
                resource_id="arn:aws:s3:::bucket-one",
                resource_type="AwsS3Bucket",
                status="OPEN",
                status_reason="inventory_confirmed_non_compliant",
            )
        ],
    )
    monkeypatch.setattr(worker, "upsert_shadow_state", lambda **kwargs: (True, True))
    monkeypatch.setattr(
        worker,
        "reevaluate_confirmation_for_actions",
        lambda _session, action_ids: reevaluate_calls.append(action_ids),
    )
    monkeypatch.setattr(worker.settings, "CONTROL_PLANE_SHADOW_MODE", True, raising=False)
    monkeypatch.setattr(
        worker.settings,
        "SQS_INGEST_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/ingest",
        raising=False,
    )

    mock_sqs = MagicMock()
    monkeypatch.setattr(worker.boto3, "client", lambda *args, **kwargs: mock_sqs)

    worker.execute_ingest_control_plane_events_job(_job_payload(tenant_id=tenant_id))

    assert reevaluate_calls == [[action_id]]
    assert mock_sqs.send_message.call_count == 1
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["job_type"] == COMPUTE_ACTIONS_JOB_TYPE
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["account_id"] == "123456789012"
    assert payload["region"] == "us-east-1"


def test_ingest_control_plane_events_noop_does_not_enqueue_compute_actions(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    account = SimpleNamespace(
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="ext-123",
    )
    session = _WorkerSession(account=account, action_rows=[(uuid.uuid4(),)])

    monkeypatch.setattr(worker, "session_scope", _session_scope_for(session))
    monkeypatch.setattr(worker, "is_supported_management_event", lambda event: (True, None))
    monkeypatch.setattr(worker, "assume_role", lambda **kwargs: object())
    monkeypatch.setattr(
        worker,
        "derive_control_evaluations",
        lambda **kwargs: [
            SimpleNamespace(
                control_id="S3.11",
                resource_id="arn:aws:s3:::bucket-one",
                resource_type="AwsS3Bucket",
                status="OPEN",
                status_reason="inventory_confirmed_non_compliant",
            )
        ],
    )
    monkeypatch.setattr(worker, "upsert_shadow_state", lambda **kwargs: (True, False))
    monkeypatch.setattr(worker, "reevaluate_confirmation_for_actions", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker.settings, "CONTROL_PLANE_SHADOW_MODE", True, raising=False)
    monkeypatch.setattr(
        worker.settings,
        "SQS_INGEST_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/ingest",
        raising=False,
    )
    monkeypatch.setattr(
        worker.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("compute_actions enqueue should not run when nothing changed"),
    )

    worker.execute_ingest_control_plane_events_job(_job_payload(tenant_id=tenant_id))


def test_ingest_control_plane_events_duplicate_does_not_enqueue_compute_actions(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    duplicate_event = SimpleNamespace(duplicate_count=0)
    session = _WorkerSession(account=None, duplicate_event=duplicate_event)

    monkeypatch.setattr(worker, "session_scope", _session_scope_for(session))
    monkeypatch.setattr(
        worker.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("compute_actions enqueue should not run for duplicate events"),
    )

    worker.execute_ingest_control_plane_events_job(_job_payload(tenant_id=tenant_id))

    assert duplicate_event.duplicate_count == 1

