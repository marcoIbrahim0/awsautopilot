from __future__ import annotations

import threading
from unittest.mock import MagicMock

from worker import main as worker_main


def test_run_worker_starts_independent_queue_pollers(monkeypatch) -> None:
    started: list[str] = []
    shutdown_lock = threading.Lock()

    def fake_run_queue_poller(queue_name: str, sqs: object, queue_url: str, *, max_in_flight: int) -> None:
        started.append(queue_name)
        # Trigger shutdown once all expected pollers are started.
        with shutdown_lock:
            if len(started) >= 2:
                worker_main._handle_shutdown(15, None)

    monkeypatch.setattr(worker_main, "assert_database_revision_at_head", lambda component: None)
    monkeypatch.setattr(
        worker_main,
        "_resolve_queue_configs",
        lambda: [
            ("events", "https://sqs.us-east-1.amazonaws.com/123/events"),
            ("inventory", "https://sqs.us-east-1.amazonaws.com/123/inventory"),
        ],
    )
    monkeypatch.setattr(worker_main, "_run_queue_poller", fake_run_queue_poller)
    monkeypatch.setattr(worker_main, "_max_in_flight_per_queue", lambda: 4)
    monkeypatch.setattr(worker_main.boto3, "client", lambda *_args, **_kwargs: MagicMock())

    original_shutdown = worker_main._shutdown_requested
    worker_main._shutdown_requested = False
    try:
        worker_main.run_worker()
    finally:
        worker_main._shutdown_requested = original_shutdown

    assert set(started) == {"events", "inventory"}


def test_resolve_queue_configs_all_includes_export_queue(monkeypatch) -> None:
    monkeypatch.setattr(worker_main.settings, "WORKER_POOL", "all", raising=False)
    monkeypatch.setattr(
        worker_main.settings,
        "SQS_EVENTS_FAST_LANE_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/events",
        raising=False,
    )
    monkeypatch.setattr(
        worker_main.settings,
        "SQS_INVENTORY_RECONCILE_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/inventory",
        raising=False,
    )
    monkeypatch.setattr(
        worker_main.settings,
        "SQS_EXPORT_REPORT_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/export",
        raising=False,
    )
    monkeypatch.setattr(
        worker_main.settings,
        "SQS_INGEST_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/legacy",
        raising=False,
    )

    configs = worker_main._resolve_queue_configs()

    assert configs == [
        ("events", "https://sqs.us-east-1.amazonaws.com/123/events"),
        ("inventory", "https://sqs.us-east-1.amazonaws.com/123/inventory"),
        ("export", "https://sqs.us-east-1.amazonaws.com/123/export"),
        ("legacy", "https://sqs.us-east-1.amazonaws.com/123/legacy"),
    ]


def test_resolve_queue_configs_export_pool(monkeypatch) -> None:
    monkeypatch.setattr(worker_main.settings, "WORKER_POOL", "export", raising=False)
    monkeypatch.setattr(
        worker_main.settings,
        "SQS_EXPORT_REPORT_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123/export",
        raising=False,
    )

    configs = worker_main._resolve_queue_configs()

    assert configs == [("export", "https://sqs.us-east-1.amazonaws.com/123/export")]
