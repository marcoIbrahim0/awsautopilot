"""
Unit tests for evidence export service (Step 10.3, 12.2).

Covers: generate_evidence_pack with pack_type evidence vs compliance;
compliance pack zip includes exception_attestations.csv, control_mapping.csv, auditor_summary.html.
"""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.services.compliance_pack_spec import (
    AUDITOR_SUMMARY_FILENAME,
    CONTROL_MAPPING_CSV_FILENAME,
    EXCEPTION_ATTESTATIONS_CSV_FILENAME,
)
from backend.services.evidence_export import generate_evidence_pack


def _result_scalars_all(rows: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


def _result_scalar_one_or_none(obj: object | None) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = obj
    return r


def _result_scalar(val: int) -> MagicMock:
    r = MagicMock()
    r.scalar.return_value = val
    return r


def test_generate_evidence_pack_compliance_zip_contains_compliance_files() -> None:
    """When pack_type is compliance, zip contains exception_attestations, control_mapping, auditor_summary."""
    tenant_id = uuid.uuid4()
    export_id = uuid.uuid4()
    tenant = MagicMock()
    tenant.id = tenant_id
    tenant.name = "Test Tenant"

    # Order: Finding, Action, RemediationRun, Exception (evidence); then Tenant; then 5 counts; then Exception (attestations); then ControlMapping (12.3)
    session = MagicMock()
    empty_result = _result_scalars_all([])
    tenant_result = _result_scalar_one_or_none(tenant)
    count_result = _result_scalar(0)
    session.execute.side_effect = [
        empty_result,  # findings
        empty_result,  # actions
        empty_result,  # remediation_runs
        empty_result,  # exceptions
        tenant_result,  # Tenant for compliance
        count_result,  # open_findings
        count_result,  # open_actions
        count_result,  # total_exceptions
        count_result,  # expiring_30d
        count_result,  # remediations_30d
        empty_result,  # build_exception_attestation_rows: exceptions
        empty_result,  # build_control_mapping_rows: ControlMapping (empty → fallback to v1 static)
    ]

    put_calls = []

    def capture_put(**kwargs):
        put_calls.append(kwargs)

    with patch("backend.services.evidence_export.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = "test-bucket"
        mock_settings.S3_EXPORT_BUCKET_REGION = ""
        mock_settings.AWS_REGION = "us-east-1"
        with patch("backend.services.evidence_export.boto3") as mock_boto3:
            mock_s3 = MagicMock()
            mock_s3.put_object = capture_put
            mock_boto3.client.return_value = mock_s3

            generate_evidence_pack(
                session=session,
                tenant_id=tenant_id,
                export_id=export_id,
                requested_by_email="user@example.com",
                export_created_at=datetime.now(timezone.utc).isoformat(),
                pack_type="compliance",
            )

    assert len(put_calls) == 1
    body = put_calls[0].get("Body")
    assert body is not None
    zip_buf = io.BytesIO(body)
    with zipfile.ZipFile(zip_buf, "r") as zf:
        names = zf.namelist()
    assert EXCEPTION_ATTESTATIONS_CSV_FILENAME in names
    assert CONTROL_MAPPING_CSV_FILENAME in names
    assert AUDITOR_SUMMARY_FILENAME in names
