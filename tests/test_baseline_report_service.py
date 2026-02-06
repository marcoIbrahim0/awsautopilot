"""
Unit tests for baseline report service (Step 13.2).
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from backend.services.baseline_report_service import generate_baseline_report


def test_generate_baseline_report_raises_when_bucket_not_configured() -> None:
    """generate_baseline_report raises ValueError when S3_EXPORT_BUCKET is empty."""
    mock_session = MagicMock()
    tenant_id = uuid.uuid4()
    report_id = uuid.uuid4()

    with patch("backend.services.baseline_report_service.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = ""
        mock_settings.S3_EXPORT_BUCKET_REGION = ""
        mock_settings.AWS_REGION = "us-east-1"
        with pytest.raises(ValueError, match="S3 export bucket not configured"):
            generate_baseline_report(
                session=mock_session,
                tenant_id=tenant_id,
                report_id=report_id,
                account_ids=None,
            )


def test_generate_baseline_report_uploads_and_returns_bucket_key_size() -> None:
    """generate_baseline_report builds data, renders HTML, uploads to S3, returns bucket/key/size."""
    mock_session = MagicMock()
    tenant_id = uuid.uuid4()
    report_id = uuid.uuid4()

    # Tenant query returns a tenant
    tenant_row = MagicMock()
    tenant_row.name = "Acme"
    result_tenant = MagicMock()
    result_tenant.scalar_one_or_none.return_value = tenant_row
    mock_session.execute.return_value = result_tenant

    capture_put = MagicMock()
    mock_s3 = MagicMock()
    mock_s3.put_object = capture_put

    with patch("backend.services.baseline_report_service.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = "test-bucket"
        mock_settings.S3_EXPORT_BUCKET_REGION = "us-east-1"
        mock_settings.AWS_REGION = "us-east-1"
        with patch("backend.services.baseline_report_service.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_s3
            with patch(
                "backend.services.baseline_report_service.build_baseline_report_data"
            ) as mock_build:
                from backend.services.baseline_report_spec import (
                    BaselineReportData,
                    BaselineSummary,
                )
                from datetime import date, datetime, timezone
                now = datetime.now(timezone.utc)
                mock_build.return_value = BaselineReportData(
                    summary=BaselineSummary(
                        total_finding_count=0,
                        critical_count=0,
                        high_count=0,
                        medium_count=0,
                        low_count=0,
                        informational_count=0,
                        open_count=0,
                        resolved_count=0,
                        narrative="Test.",
                        report_date=date(2026, 2, 3),
                        generated_at=now,
                    ),
                    top_risks=[],
                    recommendations=[],
                    tenant_name="Acme",
                    appendix_findings=None,
                )
                bucket, key, size = generate_baseline_report(
                    session=mock_session,
                    tenant_id=tenant_id,
                    report_id=report_id,
                    account_ids=None,
                )
    assert bucket == "test-bucket"
    assert str(tenant_id) in key
    assert str(report_id) in key
    assert "baseline-report.html" in key
    assert size > 0
    capture_put.assert_called_once()
    call_kw = capture_put.call_args[1]
    assert call_kw["Bucket"] == "test-bucket"
    assert call_kw["ContentType"] == "text/html; charset=utf-8"
    assert len(call_kw["Body"]) == size
