"""
Unit tests for baseline report data builder (Step 13.2).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.services.baseline_report_builder import build_baseline_report_data
from backend.services.baseline_report_spec import TOP_RISKS_MAX


def test_build_baseline_report_data_empty_findings() -> None:
    """build_baseline_report_data with no findings returns zero counts and empty top_risks."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    data = build_baseline_report_data(
        session=session,
        tenant_id=tenant_id,
        account_ids=None,
        tenant_name="Acme",
    )
    assert data.summary.total_finding_count == 0
    assert data.summary.critical_count == 0
    assert data.summary.open_count == 0
    assert data.summary.resolved_count == 0
    assert data.top_risks == []
    assert data.tenant_name == "Acme"


def test_build_baseline_report_data_with_findings() -> None:
    """build_baseline_report_data with findings returns counts and top_risks."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())
    f1 = MagicMock(spec=Finding)
    f1.title = "S3 public access"
    f1.severity_label = "CRITICAL"
    f1.severity_normalized = 100
    f1.account_id = "123456789012"
    f1.region = "us-east-1"
    f1.status = "NEW"
    f1.resource_id = "arn:aws:s3:::bucket"
    f1.control_id = "S3.1"
    f1.region = "us-east-1"
    f2 = MagicMock(spec=Finding)
    f2.title = "GuardDuty off"
    f2.severity_label = "HIGH"
    f2.severity_normalized = 75
    f2.account_id = "123456789012"
    f2.region = "us-west-2"
    f2.status = "NOTIFIED"
    f2.resource_id = None
    f2.control_id = "GuardDuty.1"
    f2.region = "us-west-2"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [f1, f2]
    session.execute.return_value = result

    data = build_baseline_report_data(
        session=session,
        tenant_id=tenant_id,
        account_ids=None,
        tenant_name=None,
    )
    assert data.summary.total_finding_count == 2
    assert data.summary.critical_count == 1
    assert data.summary.high_count == 1
    assert data.summary.open_count == 2
    assert data.summary.resolved_count == 0
    assert len(data.top_risks) == 2
    assert data.top_risks[0].title == "S3 public access"
    assert data.top_risks[0].severity == "CRITICAL"
    assert data.top_risks[1].title == "GuardDuty off"
    assert data.top_risks[1].severity == "HIGH"
    assert len(data.recommendations) >= 1
    rec_texts = [r.text for r in data.recommendations]
    assert any("S3" in t for t in rec_texts) or any("GuardDuty" in t for t in rec_texts)
