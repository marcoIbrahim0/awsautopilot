from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_sqs_template_has_export_report_queue_and_alarm_coverage() -> None:
    text = _read("infrastructure/cloudformation/sqs-queues.yaml")

    required_tokens = (
        "ExportReportQueue:",
        "ExportReportDLQ:",
        "ExportReportQueueURL:",
        "ExportReportDLQURL:",
        "IngestQueueDepthAlarm:",
        "IngestQueueOldestMessageAlarm:",
        "EventsQueueDepthAlarm:",
        "EventsQueueOldestMessageAlarm:",
        "InventoryQueueDepthAlarm:",
        "InventoryQueueOldestMessageAlarm:",
        "ExportReportQueueDepthAlarm:",
        "ExportReportQueueOldestMessageAlarm:",
        "IngestDLQIngressAlarm:",
        "EventsDLQIngressAlarm:",
        "InventoryReconcileDLQIngressAlarm:",
        "ExportReportDLQIngressAlarm:",
    )

    for token in required_tokens:
        assert token in text


def test_control_plane_forwarder_template_has_dlq_retry_and_alarms() -> None:
    text = _read("infrastructure/cloudformation/control-plane-forwarder-template.yaml")

    required_tokens = (
        "ControlPlaneTargetDLQ:",
        "DeadLetterConfig:",
        "RetryPolicy:",
        "MaximumEventAgeInSeconds",
        "MaximumRetryAttempts",
        "ControlPlaneRuleFailedInvocationsAlarm:",
        "ControlPlaneTargetDLQDepthAlarm:",
        '"PutAccountPublicAccessBlock"',
        '"DeleteAccountPublicAccessBlock"',
        '"PutBucketEncryption"',
        '"DeleteBucketEncryption"',
        '"EnableSecurityHub"',
        '"CreateDetector"',
        '"UpdateDetector"',
        '"CreateTrail"',
        '"UpdateTrail"',
        '"StartLogging"',
        '"StopLogging"',
        '"PutConfigurationRecorder"',
        '"PutDeliveryChannel"',
        '"StartConfigurationRecorder"',
    )

    for token in required_tokens:
        assert token in text


def test_reconcile_scheduler_template_has_dlq_retry_and_alarms() -> None:
    text = _read("infrastructure/cloudformation/reconcile-scheduler-template.yaml")

    required_tokens = (
        "ReconcileSchedulerTargetDLQ:",
        "DeadLetterConfig:",
        "RetryPolicy:",
        "MaximumEventAgeInSeconds",
        "MaximumRetryAttempts",
        "ReconcileSchedulerRuleFailedInvocationsAlarm:",
        "ReconcileSchedulerTargetDLQDepthAlarm:",
    )

    for token in required_tokens:
        assert token in text
