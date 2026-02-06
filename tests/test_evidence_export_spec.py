"""
Tests for Step 10.2: Evidence pack export content specification.

Asserts file names, column lists, manifest schema helpers, and README content
are defined and consistent for the export worker (Step 10.3).
"""
from __future__ import annotations

import pytest

from backend.services.evidence_export_spec import (
    ACTIONS_COLUMNS,
    ACTIONS_CSV_FILENAME,
    CONTROL_SCOPE_NOTE,
    EXCEPTIONS_COLUMNS,
    EXCEPTIONS_CSV_FILENAME,
    EXPORT_ENCODING,
    FINDINGS_COLUMNS,
    FINDINGS_CSV_FILENAME,
    MANIFEST_FILENAME,
    README_FILENAME,
    REMEDIATION_RUNS_COLUMNS,
    REMEDIATION_RUNS_CSV_FILENAME,
    get_manifest_file_entries,
    get_readme_content,
)


def test_file_names_defined() -> None:
    """Step 10.2: All bundle file names are defined."""
    assert MANIFEST_FILENAME == "manifest.json"
    assert README_FILENAME == "README.txt"
    assert FINDINGS_CSV_FILENAME == "findings.csv"
    assert ACTIONS_CSV_FILENAME == "actions.csv"
    assert REMEDIATION_RUNS_CSV_FILENAME == "remediation_runs.csv"
    assert EXCEPTIONS_CSV_FILENAME == "exceptions.csv"


def test_encoding_is_utf8() -> None:
    """Step 10.2: Export encoding is UTF-8."""
    assert EXPORT_ENCODING == "utf-8"


def test_findings_columns_ordered_and_audit_relevant() -> None:
    """Step 10.2: Findings columns include audit-relevant fields in order."""
    assert len(FINDINGS_COLUMNS) >= 10
    assert "id" in FINDINGS_COLUMNS
    assert "finding_id" in FINDINGS_COLUMNS
    assert "severity" in FINDINGS_COLUMNS
    assert "control_id" in FINDINGS_COLUMNS
    assert "title" in FINDINGS_COLUMNS
    assert "resource_id" in FINDINGS_COLUMNS
    assert "status" in FINDINGS_COLUMNS
    assert "updated_at" in FINDINGS_COLUMNS
    assert FINDINGS_COLUMNS[0] == "id"


def test_actions_columns_include_finding_count() -> None:
    """Step 10.2: Actions columns include finding_count (computed)."""
    assert "finding_count" in ACTIONS_COLUMNS
    assert "action_type" in ACTIONS_COLUMNS
    assert "priority" in ACTIONS_COLUMNS
    assert len(ACTIONS_COLUMNS) >= 10


def test_remediation_runs_columns_include_mode_outcome_completed_at() -> None:
    """Step 10.2: Remediation runs columns include mode, status, outcome, completed_at."""
    assert "mode" in REMEDIATION_RUNS_COLUMNS
    assert "status" in REMEDIATION_RUNS_COLUMNS
    assert "outcome" in REMEDIATION_RUNS_COLUMNS
    assert "completed_at" in REMEDIATION_RUNS_COLUMNS
    assert "approved_by_user_id" in REMEDIATION_RUNS_COLUMNS


def test_exceptions_columns_include_reason_expires_at() -> None:
    """Step 10.2: Exceptions columns include reason, approved_by_user_id, expires_at."""
    assert "reason" in EXCEPTIONS_COLUMNS
    assert "approved_by_user_id" in EXCEPTIONS_COLUMNS
    assert "expires_at" in EXCEPTIONS_COLUMNS
    assert "entity_type" in EXCEPTIONS_COLUMNS


def test_control_scope_note_non_empty() -> None:
    """Step 10.2: Control scope note is present for auditors."""
    assert len(CONTROL_SCOPE_NOTE) > 20
    assert "control_id" in CONTROL_SCOPE_NOTE.lower()
    assert "Security Hub" in CONTROL_SCOPE_NOTE or "CIS" in CONTROL_SCOPE_NOTE


def test_get_manifest_file_entries_returns_four_entries() -> None:
    """Step 10.2: get_manifest_file_entries returns one entry per entity file."""
    entries = get_manifest_file_entries(
        findings_rows=10,
        actions_rows=5,
        remediation_runs_rows=3,
        exceptions_rows=2,
    )
    assert len(entries) == 4
    assert entries[0]["name"] == FINDINGS_CSV_FILENAME
    assert entries[0]["rows"] == 10
    assert entries[0]["description"]
    assert entries[1]["name"] == ACTIONS_CSV_FILENAME
    assert entries[2]["name"] == REMEDIATION_RUNS_CSV_FILENAME
    assert entries[3]["name"] == EXCEPTIONS_CSV_FILENAME


def test_get_readme_content_includes_export_id_tenant_control_note() -> None:
    """Step 10.2: README content includes export id, tenant id, and control scope note."""
    content = get_readme_content(
        export_id="test-export-uuid",
        tenant_id="test-tenant-uuid",
        export_created_at="2026-02-02T12:00:00Z",
    )
    assert "test-export-uuid" in content
    assert "test-tenant-uuid" in content
    assert "manifest.json" in content
    assert "findings.csv" in content
    assert "Evidence Pack" in content
    assert "control_id" in content.lower() or "Control ID" in content
