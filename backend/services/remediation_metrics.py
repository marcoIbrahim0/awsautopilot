"""
Structured remediation metrics and alert-signal logging.

These helpers emit stable log records that can be converted into CloudWatch
metric filters and alarms without requiring a dedicated metrics backend.
"""
from __future__ import annotations

import json
import logging
from typing import Any


def _normalized(value: Any, fallback: str = "none") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or fallback
    return str(value)


def emit_strategy_metric(
    logger: logging.Logger,
    metric_name: str,
    *,
    action_type: str | None = None,
    strategy_id: str | None = None,
    mode: str | None = None,
) -> None:
    """Emit a one-count metric event for remediation strategy analytics."""
    payload = {
        "event": "remediation_metric",
        "metric": _normalized(metric_name),
        "value": 1,
        "action_type": _normalized(action_type),
        "strategy_id": _normalized(strategy_id),
        "mode": _normalized(mode),
    }
    logger.info("remediation_metric %s", json.dumps(payload, sort_keys=True))


def emit_validation_failure(
    logger: logging.Logger,
    *,
    reason: str,
    action_type: str | None = None,
    strategy_id: str | None = None,
    mode: str | None = None,
) -> None:
    """Emit validation-failure signal for alerting on request rejection spikes."""
    payload = {
        "event": "remediation_validation_failure",
        "reason": _normalized(reason),
        "action_type": _normalized(action_type),
        "strategy_id": _normalized(strategy_id),
        "mode": _normalized(mode),
        "value": 1,
    }
    logger.warning("remediation_validation_failure %s", json.dumps(payload, sort_keys=True))


def emit_worker_dispatch_error(
    logger: logging.Logger,
    *,
    phase: str,
    run_id: str | None = None,
    action_type: str | None = None,
    strategy_id: str | None = None,
    mode: str | None = None,
) -> None:
    """Emit worker dispatch/execution failure signal for alerting."""
    payload = {
        "event": "remediation_worker_dispatch_error",
        "phase": _normalized(phase),
        "run_id": _normalized(run_id),
        "action_type": _normalized(action_type),
        "strategy_id": _normalized(strategy_id),
        "mode": _normalized(mode),
        "value": 1,
    }
    logger.error("remediation_worker_dispatch_error %s", json.dumps(payload, sort_keys=True))

