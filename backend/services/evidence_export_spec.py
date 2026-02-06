"""
Evidence pack export content specification (Step 10.2).

Single source of truth for what goes in the evidence pack zip: file names,
manifest schema, and ordered column names per entity. The export worker
(Step 10.3) uses this module to generate consistent CSV/JSON and manifest.

Format rules:
- CSV: header row; escape commas and newlines in fields; UTF-8 encoding.
- JSON: array of objects; same field names as CSV columns for consistency.
- Control IDs in findings/actions map to Security Hub / CIS (see CONTROL_SCOPE_NOTE).
"""

from __future__ import annotations

from typing import TypedDict

# ---------------------------------------------------------------------------
# File names (bundle contents)
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "manifest.json"
README_FILENAME = "README.txt"

FINDINGS_CSV_FILENAME = "findings.csv"
FINDINGS_JSON_FILENAME = "findings.json"
ACTIONS_CSV_FILENAME = "actions.csv"
ACTIONS_JSON_FILENAME = "actions.json"
REMEDIATION_RUNS_CSV_FILENAME = "remediation_runs.csv"
REMEDIATION_RUNS_JSON_FILENAME = "remediation_runs.json"
EXCEPTIONS_CSV_FILENAME = "exceptions.csv"
EXCEPTIONS_JSON_FILENAME = "exceptions.json"

# Encoding for all text files in the bundle
EXPORT_ENCODING = "utf-8"

# ---------------------------------------------------------------------------
# Manifest schema
# ---------------------------------------------------------------------------


class ManifestFileEntry(TypedDict):
    """One entry in manifest.files: name, row count, description."""

    name: str
    rows: int
    description: str


class ManifestSchema(TypedDict, total=False):
    """
    Structure of manifest.json.
    total=False so control_scope is optional.
    """

    export_id: str
    tenant_id: str
    export_created_at: str  # ISO8601
    requested_by: str  # user email or id
    files: list[ManifestFileEntry]
    control_scope: str  # optional note for auditors


# ---------------------------------------------------------------------------
# Column names (ordered) per entity — CSV header and JSON object keys
# ---------------------------------------------------------------------------
# Use these in order when writing CSV and when building JSON objects.
# Finding: "severity" is exported from model severity_label; "updated_at" from sh_updated_at.
# Action: finding_count is computed (e.g. len(action_finding_links)).
# Enum fields (mode, status, entity_type): export string value (e.g. .value or str()).

FINDINGS_COLUMNS: tuple[str, ...] = (
    "id",
    "finding_id",
    "account_id",
    "region",
    "severity",       # from Finding.severity_label
    "status",
    "control_id",
    "title",
    "resource_id",
    "resource_type",
    "first_observed_at",
    "updated_at",     # from Finding.sh_updated_at (Security Hub updated)
    "created_at",
)

ACTIONS_COLUMNS: tuple[str, ...] = (
    "id",
    "action_type",
    "target_id",
    "account_id",
    "region",
    "priority",
    "status",
    "title",
    "control_id",
    "resource_id",
    "created_at",
    "updated_at",
    "finding_count",  # computed: number of linked findings
)

REMEDIATION_RUNS_COLUMNS: tuple[str, ...] = (
    "id",
    "action_id",
    "mode",
    "status",
    "outcome",
    "approved_by_user_id",
    "started_at",
    "completed_at",
    "created_at",
)

EXCEPTIONS_COLUMNS: tuple[str, ...] = (
    "id",
    "entity_type",
    "entity_id",
    "reason",
    "approved_by_user_id",
    "expires_at",
    "ticket_link",
    "created_at",
)

# ---------------------------------------------------------------------------
# Descriptions (for manifest.files[].description and README)
# ---------------------------------------------------------------------------

FINDINGS_DESCRIPTION = "Security Hub findings for the tenant (one row per finding)."
ACTIONS_DESCRIPTION = "Deduplicated actions derived from findings (one row per action)."
REMEDIATION_RUNS_DESCRIPTION = "Remediation run history: PR bundle and direct fix runs (one row per run)."
EXCEPTIONS_DESCRIPTION = "Exceptions/suppressions for findings or actions with reason and expiry (one row per exception)."

CONTROL_SCOPE_NOTE = (
    "The control_id field in findings and actions corresponds to Security Hub control IDs "
    "(e.g. CIS AWS Foundations Benchmark, AWS Foundational Security Best Practices). "
    "Use these IDs to map evidence to your compliance framework (e.g. SOC 2, ISO 27001)."
)

README_CONTENT_TEMPLATE = """Evidence Pack — AWS Security Autopilot
Generated: {export_created_at}
Export ID: {export_id}
Tenant ID: {tenant_id}

This zip contains:
- manifest.json    — Export metadata and file list
- findings.csv     — Security Hub findings
- actions.csv      — Deduplicated actions
- remediation_runs.csv — Remediation run history
- exceptions.csv   — Exceptions/suppressions with expiry

Control IDs (findings and actions):
{control_scope_note}

All timestamps are ISO 8601 (UTC). CSV files use UTF-8 encoding.
"""

# ---------------------------------------------------------------------------
# Public API for worker (Step 10.3)
# ---------------------------------------------------------------------------

def get_manifest_file_entries(
    findings_rows: int,
    actions_rows: int,
    remediation_runs_rows: int,
    exceptions_rows: int,
) -> list[ManifestFileEntry]:
    """Build the manifest.files list from row counts."""
    return [
        {"name": FINDINGS_CSV_FILENAME, "rows": findings_rows, "description": FINDINGS_DESCRIPTION},
        {"name": ACTIONS_CSV_FILENAME, "rows": actions_rows, "description": ACTIONS_DESCRIPTION},
        {
            "name": REMEDIATION_RUNS_CSV_FILENAME,
            "rows": remediation_runs_rows,
            "description": REMEDIATION_RUNS_DESCRIPTION,
        },
        {"name": EXCEPTIONS_CSV_FILENAME, "rows": exceptions_rows, "description": EXCEPTIONS_DESCRIPTION},
    ]


def get_readme_content(export_id: str, tenant_id: str, export_created_at: str) -> str:
    """Build README.txt content for the bundle."""
    return README_CONTENT_TEMPLATE.format(
        export_id=export_id,
        tenant_id=tenant_id,
        export_created_at=export_created_at,
        control_scope_note=CONTROL_SCOPE_NOTE,
    )
