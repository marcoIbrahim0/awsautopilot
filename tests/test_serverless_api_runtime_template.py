from __future__ import annotations

from pathlib import Path


def test_api_serverless_template_grants_cloudwatch_queue_lag_metric_read() -> None:
    template_text = Path(
        "/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/saas-serverless-httpapi.yaml"
    ).read_text()

    assert "ApiCloudWatchMetricsAccess:" in template_text
    assert "cloudwatch:GetMetricStatistics" in template_text


def test_api_serverless_template_raises_api_lambda_memory() -> None:
    template_text = Path(
        "/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/saas-serverless-httpapi.yaml"
    ).read_text()

    assert "ApiFunction:" in template_text
    assert "MemorySize: 1536" in template_text
