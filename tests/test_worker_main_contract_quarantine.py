from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock

from worker import main as worker_main


def _message(body: str, *, message_id: str = "msg-1", receive_count: str = "1") -> dict:
    return {
        "MessageId": message_id,
        "ReceiptHandle": "receipt-1",
        "Body": body,
        "Attributes": {"ApproximateReceiveCount": receive_count},
    }


def test_build_quarantine_envelope_includes_required_metadata() -> None:
    body = '{"tenant_id":"t-1","job_type":"unknown"}'
    envelope = worker_main._build_quarantine_envelope(
        message_id="msg-123",
        source_queue_name="legacy",
        source_queue_url="https://sqs.us-east-1.amazonaws.com/123/ingest",
        receive_count=2,
        body_raw=body,
        reason_code=worker_main.CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE,
    )

    assert envelope["reason_code"] == worker_main.CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE
    assert envelope["original_message_id"] == "msg-123"
    assert envelope["original_queue_name"] == "legacy"
    assert envelope["original_queue_url"] == "https://sqs.us-east-1.amazonaws.com/123/ingest"
    assert envelope["payload_sha256"] == hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert envelope["approx_receive_count"] == 2
    assert envelope["original_body"] == body
    assert isinstance(envelope["seen_at"], str)


def test_process_message_invalid_json_quarantines_and_deletes_source(monkeypatch) -> None:
    quarantine_url = "https://sqs.us-east-1.amazonaws.com/123/contract-quarantine"
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", quarantine_url, raising=False)

    sqs = MagicMock()
    msg = _message("{not-json")

    worker_main._process_message(sqs, source_url, msg, queue_name="legacy")

    sqs.send_message.assert_called_once()
    send_kwargs = sqs.send_message.call_args.kwargs
    assert send_kwargs["QueueUrl"] == quarantine_url

    envelope = json.loads(send_kwargs["MessageBody"])
    assert envelope["reason_code"] == worker_main.CONTRACT_VIOLATION_INVALID_JSON
    assert envelope["original_message_id"] == "msg-1"

    sqs.delete_message.assert_called_once_with(QueueUrl=source_url, ReceiptHandle="receipt-1")


def test_process_message_missing_required_fields_quarantines_and_deletes_source(monkeypatch) -> None:
    quarantine_url = "https://sqs.us-east-1.amazonaws.com/123/contract-quarantine"
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", quarantine_url, raising=False)

    sqs = MagicMock()
    body = json.dumps(
        {
            "tenant_id": "tenant-1",
            "account_id": "123456789012",
            "job_type": "ingest_findings",
        }
    )

    worker_main._process_message(sqs, source_url, _message(body), queue_name="legacy")

    sqs.send_message.assert_called_once()
    envelope = json.loads(sqs.send_message.call_args.kwargs["MessageBody"])
    assert envelope["reason_code"] == worker_main.CONTRACT_VIOLATION_MISSING_FIELDS
    assert "missing_required_fields=region" in envelope.get("reason_detail", "")
    assert isinstance(envelope.get("parsed_job"), dict)

    sqs.delete_message.assert_called_once_with(QueueUrl=source_url, ReceiptHandle="receipt-1")


def test_process_message_unknown_job_type_quarantines_and_deletes_source(monkeypatch) -> None:
    quarantine_url = "https://sqs.us-east-1.amazonaws.com/123/contract-quarantine"
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", quarantine_url, raising=False)

    sqs = MagicMock()
    body = json.dumps(
        {
            "tenant_id": "tenant-1",
            "account_id": "123456789012",
            "region": "us-east-1",
            "job_type": "unknown_job",
        }
    )

    worker_main._process_message(sqs, source_url, _message(body), queue_name="legacy")

    sqs.send_message.assert_called_once()
    envelope = json.loads(sqs.send_message.call_args.kwargs["MessageBody"])
    assert envelope["reason_code"] == worker_main.CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE
    assert envelope.get("reason_detail") == "job_type=unknown_job"

    sqs.delete_message.assert_called_once_with(QueueUrl=source_url, ReceiptHandle="receipt-1")


def test_process_message_without_quarantine_url_leaves_message_for_redrive(monkeypatch) -> None:
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", "", raising=False)

    sqs = MagicMock()

    worker_main._process_message(sqs, source_url, _message("{not-json"), queue_name="legacy")

    sqs.send_message.assert_not_called()
    sqs.delete_message.assert_not_called()


def test_process_message_keeps_source_message_when_quarantine_send_fails(monkeypatch) -> None:
    quarantine_url = "https://sqs.us-east-1.amazonaws.com/123/contract-quarantine"
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", quarantine_url, raising=False)

    sqs = MagicMock()
    sqs.send_message.side_effect = RuntimeError("send failed")

    worker_main._process_message(sqs, source_url, _message("{not-json"), queue_name="legacy")

    sqs.send_message.assert_called_once()
    sqs.delete_message.assert_not_called()


def test_process_message_unsupported_schema_version_quarantines(monkeypatch) -> None:
    quarantine_url = "https://sqs.us-east-1.amazonaws.com/123/contract-quarantine"
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", quarantine_url, raising=False)

    handler = MagicMock()
    monkeypatch.setattr(worker_main, "get_job_handler", lambda _job_type: handler)

    sqs = MagicMock()
    body = json.dumps(
        {
            "tenant_id": "tenant-1",
            "account_id": "123456789012",
            "region": "us-east-1",
            "job_type": "ingest_findings",
            "schema_version": 99,
        }
    )

    worker_main._process_message(sqs, source_url, _message(body), queue_name="legacy")

    handler.assert_not_called()
    sqs.send_message.assert_called_once()
    envelope = json.loads(sqs.send_message.call_args.kwargs["MessageBody"])
    assert envelope["reason_code"] == worker_main.CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION
    assert "schema_version=99" in envelope.get("reason_detail", "")
    sqs.delete_message.assert_called_once_with(QueueUrl=source_url, ReceiptHandle="receipt-1")


def test_process_message_invalid_schema_version_quarantines(monkeypatch) -> None:
    quarantine_url = "https://sqs.us-east-1.amazonaws.com/123/contract-quarantine"
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", quarantine_url, raising=False)

    handler = MagicMock()
    monkeypatch.setattr(worker_main, "get_job_handler", lambda _job_type: handler)

    sqs = MagicMock()
    body = json.dumps(
        {
            "tenant_id": "tenant-1",
            "account_id": "123456789012",
            "region": "us-east-1",
            "job_type": "ingest_findings",
            "schema_version": "v1",
        }
    )

    worker_main._process_message(sqs, source_url, _message(body), queue_name="legacy")

    handler.assert_not_called()
    sqs.send_message.assert_called_once()
    envelope = json.loads(sqs.send_message.call_args.kwargs["MessageBody"])
    assert envelope["reason_code"] == worker_main.CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION
    assert "invalid_schema_version='v1'" in envelope.get("reason_detail", "")
    sqs.delete_message.assert_called_once_with(QueueUrl=source_url, ReceiptHandle="receipt-1")


def test_process_message_missing_schema_version_defaults_to_legacy(monkeypatch) -> None:
    source_url = "https://sqs.us-east-1.amazonaws.com/123/ingest"
    monkeypatch.setattr(worker_main.settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", "", raising=False)

    handler = MagicMock()
    monkeypatch.setattr(worker_main, "get_job_handler", lambda _job_type: handler)

    sqs = MagicMock()
    body = json.dumps(
        {
            "tenant_id": "tenant-1",
            "account_id": "123456789012",
            "region": "us-east-1",
            "job_type": "ingest_findings",
        }
    )

    worker_main._process_message(sqs, source_url, _message(body), queue_name="legacy")

    handler.assert_called_once()
    forwarded_job = handler.call_args.args[0]
    assert forwarded_job["schema_version"] == worker_main.LEGACY_QUEUE_PAYLOAD_SCHEMA_VERSION
    sqs.send_message.assert_not_called()
    sqs.delete_message.assert_called_once_with(QueueUrl=source_url, ReceiptHandle="receipt-1")
