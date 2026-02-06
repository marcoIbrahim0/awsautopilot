"""
Tests for Step 10.5: S3 configuration and tenant isolation.

Asserts key pattern, presigned URL expiry, and tenant path isolation.
"""
from __future__ import annotations

import uuid

import pytest

from backend.services.evidence_export_s3 import (
    BASELINE_REPORT_FILENAME,
    BASELINE_REPORT_KEY_PREFIX,
    EVIDENCE_PACK_FILENAME,
    EXPORT_KEY_PREFIX,
    PRESIGNED_URL_EXPIRES_IN,
    build_baseline_report_s3_key,
    build_export_s3_key,
)


def test_build_export_s3_key_tenant_isolation() -> None:
    """Key pattern isolates tenants by path: exports/{tenant_id}/{export_id}/evidence-pack.zip."""
    tenant_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    export_id = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    key = build_export_s3_key(tenant_id, export_id)
    assert key.startswith(EXPORT_KEY_PREFIX + "/")
    assert str(tenant_id) in key
    assert str(export_id) in key
    assert key.endswith("/" + EVIDENCE_PACK_FILENAME)
    assert key == f"exports/{tenant_id}/{export_id}/evidence-pack.zip"


def test_build_export_s3_key_different_tenants_different_paths() -> None:
    """Different tenant_id produces different path prefix."""
    export_id = uuid.uuid4()
    key1 = build_export_s3_key(uuid.uuid4(), export_id)
    key2 = build_export_s3_key(uuid.uuid4(), export_id)
    assert key1 != key2
    parts1 = key1.split("/")
    parts2 = key2.split("/")
    assert parts1[0] == parts2[0] == EXPORT_KEY_PREFIX
    assert parts1[1] != parts2[1]  # tenant_id differs


def test_presigned_url_expiry_one_hour() -> None:
    """Presigned URL expiry is 3600 seconds (1 hour) per Step 10.5."""
    assert PRESIGNED_URL_EXPIRES_IN == 3600


def test_build_baseline_report_s3_key_pattern() -> None:
    """Baseline report key: baseline-reports/{tenant_id}/{report_id}/baseline-report.html (Step 13.2)."""
    tenant_id = uuid.uuid4()
    report_id = uuid.uuid4()
    key = build_baseline_report_s3_key(tenant_id, report_id)
    assert key.startswith(BASELINE_REPORT_KEY_PREFIX + "/")
    assert str(tenant_id) in key
    assert str(report_id) in key
    assert key.endswith("/" + BASELINE_REPORT_FILENAME)
    assert key == f"baseline-reports/{tenant_id}/{report_id}/baseline-report.html"
