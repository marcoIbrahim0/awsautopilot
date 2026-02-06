"""
Unit tests for compliance pack content specification (Step 12.1).

Covers: file names, column names, exception attestation rows, control mapping rows,
auditor summary content, get_compliance_pack_only_files, csv_content_from_rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.models.enums import EntityType
from backend.services.compliance_pack_spec import (
    AUDITOR_SUMMARY_FILENAME,
    CONTROL_MAPPING_CSV_FILENAME,
    CONTROL_MAPPING_COLUMNS,
    CONTROL_MAPPING_V1,
    EXCEPTION_ATTESTATIONS_CSV_FILENAME,
    EXCEPTION_ATTESTATIONS_COLUMNS,
    build_auditor_summary_content,
    build_control_mapping_rows,
    build_exception_attestation_rows,
    csv_content_from_rows,
    get_compliance_pack_only_files,
)


def test_compliance_pack_only_files_list() -> None:
    """Compliance-pack-only files include exception_attestations, control_mapping, auditor_summary."""
    files = get_compliance_pack_only_files()
    names = [f[0] for f in files]
    assert EXCEPTION_ATTESTATIONS_CSV_FILENAME in names
    assert CONTROL_MAPPING_CSV_FILENAME in names
    assert AUDITOR_SUMMARY_FILENAME in names
    assert len(files) == 3
    assert all(len(f[1]) > 0 for f in files)


def test_exception_attestations_columns() -> None:
    """Exception attestation report has approver name/email, approval timestamp, expiry, etc."""
    assert "approver_name" in EXCEPTION_ATTESTATIONS_COLUMNS
    assert "approver_email" in EXCEPTION_ATTESTATIONS_COLUMNS
    assert "approval_timestamp" in EXCEPTION_ATTESTATIONS_COLUMNS
    assert "expires_at" in EXCEPTION_ATTESTATIONS_COLUMNS
    assert "entity_type" in EXCEPTION_ATTESTATIONS_COLUMNS
    assert "entity_id" in EXCEPTION_ATTESTATIONS_COLUMNS
    assert "reason" in EXCEPTION_ATTESTATIONS_COLUMNS
    assert "ticket_link" in EXCEPTION_ATTESTATIONS_COLUMNS


def test_control_mapping_columns() -> None:
    """Control mapping has control_id, framework_name, framework_control_code, control_title, description."""
    assert CONTROL_MAPPING_COLUMNS == (
        "control_id",
        "framework_name",
        "framework_control_code",
        "control_title",
        "description",
    )


def test_build_exception_attestation_rows_empty() -> None:
    """build_exception_attestation_rows returns empty list when no exceptions."""
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    tenant_id = uuid.uuid4()
    rows = build_exception_attestation_rows(session, tenant_id)
    assert rows == []


def test_build_exception_attestation_rows_with_approver() -> None:
    """build_exception_attestation_rows includes approver name/email and approval_timestamp."""
    session = MagicMock()
    exc = MagicMock()
    exc.id = uuid.uuid4()
    exc.entity_type = EntityType.action
    exc.entity_id = uuid.uuid4()
    exc.reason = "Approved for Q1"
    exc.ticket_link = "https://jira/123"
    exc.expires_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    exc.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    approver = MagicMock()
    approver.name = "Jane Doe"
    approver.email = "jane@example.com"
    exc.approved_by = approver
    result = MagicMock()
    result.scalars.return_value.all.return_value = [exc]
    session.execute.return_value = result
    tenant_id = uuid.uuid4()
    rows = build_exception_attestation_rows(session, tenant_id)
    assert len(rows) == 1
    assert rows[0]["approver_name"] == "Jane Doe"
    assert rows[0]["approver_email"] == "jane@example.com"
    assert "approval_timestamp" in rows[0]
    assert rows[0]["reason"] == "Approved for Q1"
    assert rows[0]["ticket_link"] == "https://jira/123"


def test_build_control_mapping_rows() -> None:
    """build_control_mapping_rows() with no session returns v1 static mapping with expected columns."""
    rows = build_control_mapping_rows()
    assert len(rows) == len(CONTROL_MAPPING_V1)
    for row in rows:
        for col in CONTROL_MAPPING_COLUMNS:
            assert col in row
            assert isinstance(row[col], str)
    control_ids = {r["control_id"] for r in rows}
    assert "S3.1" in control_ids
    assert "CloudTrail.1" in control_ids
    assert "GuardDuty.1" in control_ids
    assert "SecurityHub.1" in control_ids
    frameworks = {r["framework_name"] for r in rows}
    assert "SOC 2" in frameworks
    assert "CIS AWS Foundations Benchmark" in frameworks
    assert "ISO 27001" in frameworks


def test_build_control_mapping_rows_from_db() -> None:
    """build_control_mapping_rows(session) with DB rows returns DB-shaped rows (Step 12.3)."""
    from unittest.mock import MagicMock

    mock_row = MagicMock()
    mock_row.control_id = "S3.1"
    mock_row.framework_name = "CIS AWS"
    mock_row.framework_control_code = "3.1"
    mock_row.control_title = "S3 block public access"
    mock_row.description = "S3 account-level"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [mock_row]
    session = MagicMock()
    session.execute.return_value = result

    rows = build_control_mapping_rows(session)
    assert len(rows) == 1
    assert rows[0]["control_id"] == "S3.1"
    assert rows[0]["framework_name"] == "CIS AWS"
    assert rows[0]["framework_control_code"] == "3.1"
    assert rows[0]["control_title"] == "S3 block public access"
    assert rows[0]["description"] == "S3 account-level"


def test_build_control_mapping_rows_empty_db_fallback() -> None:
    """build_control_mapping_rows(session) with empty DB returns static v1 fallback."""
    from unittest.mock import MagicMock

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = MagicMock()
    session.execute.return_value = result

    rows = build_control_mapping_rows(session)
    assert len(rows) == len(CONTROL_MAPPING_V1)
    assert rows[0]["control_id"] == "S3.1"


def test_build_auditor_summary_content() -> None:
    """Auditor summary HTML contains tenant name, date, and all metrics."""
    html = build_auditor_summary_content(
        tenant_name="Acme Corp",
        as_of_date="2026-02-02T12:00:00Z",
        open_findings=10,
        open_actions=5,
        total_exceptions=2,
        expiring_30d=1,
        remediations_30d=3,
    )
    assert "Acme Corp" in html
    assert "2026-02-02" in html
    assert "10" in html
    assert "5" in html
    assert "2" in html
    assert "1" in html
    assert "3" in html
    assert "Open findings" in html
    assert "Open actions" in html
    assert "Exceptions expiring in 30 days" in html
    assert "Remediations in last 30 days" in html
    assert "<!DOCTYPE html>" in html
    assert "</table>" in html


def test_build_auditor_summary_escapes_tenant_name() -> None:
    """Auditor summary escapes tenant name to prevent XSS."""
    html = build_auditor_summary_content(
        tenant_name="<script>alert(1)</script>",
        as_of_date="2026-02-02",
        open_findings=0,
        open_actions=0,
        total_exceptions=0,
        expiring_30d=0,
        remediations_30d=0,
    )
    assert "&lt;script&gt;" in html
    assert "<script>" not in html or "&lt;script&gt;" in html


def test_csv_content_from_rows() -> None:
    """csv_content_from_rows produces CSV with header and rows."""
    columns = ("control_id", "framework_name")
    rows = [
        {"control_id": "S3.1", "framework_name": "CIS"},
        {"control_id": "CloudTrail.1", "framework_name": "SOC 2"},
    ]
    content = csv_content_from_rows(columns, rows)
    assert isinstance(content, bytes)
    text = content.decode("utf-8")
    assert "control_id" in text
    assert "framework_name" in text
    assert "S3.1" in text
    assert "CloudTrail.1" in text
    assert "CIS" in text
    assert "SOC 2" in text
