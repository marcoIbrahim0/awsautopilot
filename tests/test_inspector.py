"""
Unit tests for Step 2B.2: Amazon Inspector v2 service and normalizer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from worker.services.inspector import normalize_inspector_finding


def test_normalize_inspector_finding_package_vulnerability() -> None:
    """Normalize Inspector PACKAGE_VULNERABILITY finding to our shape."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    raw = {
        "findingArn": "arn:aws:inspector2:us-east-1:123456789012:finding/abc-123",
        "awsAccountId": "123456789012",
        "type": "PACKAGE_VULNERABILITY",
        "severity": "HIGH",
        "status": "ACTIVE",
        "description": "CVE-2024-1234 in package foo",
        "firstObservedAt": "2026-01-15T10:00:00.000Z",
        "lastObservedAt": "2026-02-01T12:00:00.000Z",
        "resources": [
            {"id": "arn:aws:ec2:us-east-1:123456789012:instance/i-abc", "type": "AWS_EC2_INSTANCE"},
        ],
    }
    out = normalize_inspector_finding(raw, "123456789012", "us-east-1", tenant_id)
    assert out["source"] == "inspector"
    assert out["finding_id"] == raw["findingArn"][:512]
    assert out["account_id"] == "123456789012"
    assert out["region"] == "us-east-1"
    assert out["tenant_id"] == tenant_id
    assert out["severity_label"] == "HIGH"
    assert out["severity_normalized"] == 75
    assert out["status"] == "NEW"
    assert out["title"] == "CVE-2024-1234 in package foo"
    assert out["description"] == "CVE-2024-1234 in package foo"
    assert out["resource_id"] == "arn:aws:ec2:us-east-1:123456789012:instance/i-abc"
    assert out["resource_type"] == "AWS_EC2_INSTANCE"
    assert out["first_observed_at"] is not None
    assert out["last_observed_at"] is not None
    assert out["raw_json"]["findingArn"] == raw["findingArn"]


def test_normalize_inspector_finding_untriaged_severity() -> None:
    """UNTRIAGED severity maps to LOW (25)."""
    tenant_id = uuid.uuid4()
    raw = {
        "findingArn": "arn:aws:inspector2:eu-west-1:999:finding/untriaged-1",
        "type": "PACKAGE_VULNERABILITY",
        "severity": "UNTRIAGED",
        "status": "ACTIVE",
        "description": "",
        "resources": [],
    }
    out = normalize_inspector_finding(raw, "999", "eu-west-1", tenant_id)
    assert out["severity_label"] == "UNTRIAGED"
    assert out["severity_normalized"] == 25
    assert out["title"].startswith("Inspector:")


def test_normalize_inspector_finding_closed_status() -> None:
    """CLOSED status maps to RESOLVED."""
    tenant_id = uuid.uuid4()
    raw = {
        "findingArn": "arn:aws:inspector2:us-west-2:123:finding/closed-1",
        "type": "CODE_VULNERABILITY",
        "severity": "MEDIUM",
        "status": "CLOSED",
        "description": "Code vuln",
        "resources": [],
    }
    out = normalize_inspector_finding(raw, "123", "us-west-2", tenant_id)
    assert out["status"] == "RESOLVED"


def test_normalize_inspector_finding_long_arn_truncated() -> None:
    """Long findingArn is truncated to 512 for finding_id."""
    tenant_id = uuid.uuid4()
    long_arn = "arn:aws:inspector2:us-east-1:123:finding/" + ("x" * 600)
    raw = {
        "findingArn": long_arn,
        "type": "NETWORK_REACHABILITY",
        "severity": "LOW",
        "status": "ACTIVE",
        "description": "Open port",
        "resources": [],
    }
    out = normalize_inspector_finding(raw, "123", "us-east-1", tenant_id)
    assert len(out["finding_id"]) <= 512


def test_normalize_inspector_finding_raw_json_is_datetime_safe() -> None:
    """raw_json is recursively converted so it can be stored in JSONB."""
    tenant_id = uuid.uuid4()
    raw = {
        "findingArn": "arn:aws:inspector2:us-east-1:123:finding/datetime-1",
        "type": "NETWORK_REACHABILITY",
        "severity": "LOW",
        "status": "ACTIVE",
        "description": "Open port",
        "firstObservedAt": datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        "nested": {
            "updatedAt": datetime(2026, 2, 2, 11, 30, tzinfo=timezone.utc),
            "list": [datetime(2026, 2, 3, 9, 15, tzinfo=timezone.utc)],
        },
        "resources": [],
    }

    out = normalize_inspector_finding(raw, "123", "us-east-1", tenant_id)

    assert out["raw_json"]["firstObservedAt"] == "2026-02-01T10:00:00+00:00"
    assert out["raw_json"]["nested"]["updatedAt"] == "2026-02-02T11:30:00+00:00"
    assert out["raw_json"]["nested"]["list"][0] == "2026-02-03T09:15:00+00:00"
