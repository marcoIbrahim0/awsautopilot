"""
Compliance pack content specification (Step 12.1).

Defines compliance-pack-only files on top of the evidence pack (Step 10):
exception attestation report, control/framework mapping, and mandatory auditor summary.
Single source of truth for file names, column names, and content builders.
Used by export worker when pack_type is "compliance" (Step 12.2).
Control mapping rows come from DB (Step 12.3) when session is provided; else static v1 fallback.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.control_mapping import ControlMapping
from backend.models.exception import Exception as ExceptionModel
from backend.models.user import User

# ---------------------------------------------------------------------------
# Compliance-pack-only file names (Step 12.1)
# ---------------------------------------------------------------------------

EXCEPTION_ATTESTATIONS_CSV_FILENAME = "exception_attestations.csv"
CONTROL_MAPPING_CSV_FILENAME = "control_mapping.csv"
AUDITOR_SUMMARY_FILENAME = "auditor_summary.html"

# Encoding (same as evidence pack)
EXPORT_ENCODING = "utf-8"

# ---------------------------------------------------------------------------
# Exception attestation report columns
# Who approved what, until when — one row per exception
# ---------------------------------------------------------------------------

EXCEPTION_ATTESTATIONS_COLUMNS: tuple[str, ...] = (
    "id",
    "entity_type",
    "entity_id",
    "approver_name",
    "approver_email",
    "approval_timestamp",
    "expires_at",
    "reason",
    "ticket_link",
)

EXCEPTION_ATTESTATIONS_DESCRIPTION = (
    "Exception attestation report: every exception with approver name/email, "
    "approval timestamp, expiry date, reason, ticket link, entity type and id."
)

# ---------------------------------------------------------------------------
# Control/framework mapping columns
# control_id (e.g. Security Hub) → framework (SOC 2, CIS, ISO) → code and title
# ---------------------------------------------------------------------------

CONTROL_MAPPING_COLUMNS: tuple[str, ...] = (
    "control_id",
    "framework_name",
    "framework_control_code",
    "control_title",
    "description",
)

CONTROL_MAPPING_DESCRIPTION = (
    "Control/framework mapping: maps control_id (findings/actions) to audit "
    "framework controls (e.g. SOC 2 CC6.1, ISO 27001 A.12.4.1)."
)

# ---------------------------------------------------------------------------
# Minimal v1 control mapping (Step 12.1; expand in 12.3)
# Security Hub / CIS control IDs → SOC 2, CIS AWS, ISO 27001
# ---------------------------------------------------------------------------

class ControlMappingRow(TypedDict):
    control_id: str
    framework_name: str
    framework_control_code: str
    control_title: str
    description: str


CONTROL_MAPPING_V1: list[ControlMappingRow] = [
    {"control_id": "S3.1", "framework_name": "CIS AWS Foundations Benchmark", "framework_control_code": "3.1", "control_title": "Ensure S3 block public access", "description": "S3 account-level block public access"},
    {"control_id": "S3.1", "framework_name": "SOC 2", "framework_control_code": "CC6.1", "control_title": "Logical access", "description": "Logical and physical access controls"},
    {"control_id": "CloudTrail.1", "framework_name": "CIS AWS Foundations Benchmark", "framework_control_code": "3.2", "control_title": "Ensure CloudTrail in all regions", "description": "CloudTrail multi-region"},
    {"control_id": "CloudTrail.1", "framework_name": "SOC 2", "framework_control_code": "CC7.2", "control_title": "System monitoring", "description": "Monitoring of system operations"},
    {"control_id": "CloudTrail.1", "framework_name": "ISO 27001", "framework_control_code": "A.12.4.1", "control_title": "Event logging", "description": "Event logs for audit"},
    {"control_id": "GuardDuty.1", "framework_name": "CIS AWS Foundations Benchmark", "framework_control_code": "4.1", "control_title": "Ensure GuardDuty enabled", "description": "GuardDuty threat detection"},
    {"control_id": "GuardDuty.1", "framework_name": "SOC 2", "framework_control_code": "CC7.2", "control_title": "System monitoring", "description": "Threat detection and monitoring"},
    {"control_id": "SecurityHub.1", "framework_name": "CIS AWS Foundations Benchmark", "framework_control_code": "4.2", "control_title": "Ensure Security Hub enabled", "description": "Security Hub standards"},
]


# ---------------------------------------------------------------------------
# Auditor summary (mandatory one-pager)
# ---------------------------------------------------------------------------

AUDITOR_SUMMARY_DESCRIPTION = (
    "Auditor summary: as-of-date snapshot of open findings, open actions, "
    "exceptions (and expiring in 30 days), remediations in last 30 days."
)

AUDITOR_SUMMARY_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Auditor Summary — {tenant_name}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 24px; max-width: 640px; color: #1a1a1a; line-height: 1.5; }}
    h1 {{ font-size: 1.25rem; margin-bottom: 8px; }}
    .meta {{ color: #666; font-size: 0.875rem; margin-bottom: 20px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; }}
    th {{ font-weight: 600; color: #444; }}
    .footer {{ margin-top: 24px; font-size: 0.75rem; color: #888; }}
  </style>
</head>
<body>
  <h1>Auditor Summary</h1>
  <p class="meta">Tenant: {tenant_name} · As of: {as_of_date}</p>
  <table>
    <tr><th>Metric</th><th>Count</th></tr>
    <tr><td>Open findings</td><td>{open_findings}</td></tr>
    <tr><td>Open actions</td><td>{open_actions}</td></tr>
    <tr><td>Total exceptions</td><td>{total_exceptions}</td></tr>
    <tr><td>Exceptions expiring in 30 days</td><td>{expiring_30d}</td></tr>
    <tr><td>Remediations in last 30 days</td><td>{remediations_30d}</td></tr>
  </table>
  <p class="footer">AWS Security Autopilot · Compliance pack · {as_of_date}</p>
</body>
</html>
"""


def _serialize(val: Any) -> str:
    """Serialize for CSV/export (datetime → ISO, uuid → str, enum → value)."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat() if val.tzinfo else (val.replace(tzinfo=None).isoformat() + "Z")
    if isinstance(val, uuid.UUID):
        return str(val)
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


# ---------------------------------------------------------------------------
# Content builders (Step 12.1)
# ---------------------------------------------------------------------------

def build_exception_attestation_rows(session: Session, tenant_id: uuid.UUID) -> list[dict[str, str]]:
    """
    Build exception attestation report rows: every exception with approver
    name/email, approval timestamp, expiry, reason, ticket link, entity type/id.
    """
    result = session.execute(
        select(ExceptionModel)
        .where(ExceptionModel.tenant_id == tenant_id)
        .order_by(ExceptionModel.created_at)
        .options(selectinload(ExceptionModel.approved_by))
    )
    exceptions = list(result.scalars().all())
    rows: list[dict[str, str]] = []
    for e in exceptions:
        approver_name = ""
        approver_email = ""
        if e.approved_by:
            approver_name = (e.approved_by.name or "").strip()
            approver_email = (e.approved_by.email or "").strip()
        approval_timestamp = _serialize(e.created_at)
        rows.append({
            "id": _serialize(e.id),
            "entity_type": _serialize(e.entity_type),
            "entity_id": _serialize(e.entity_id),
            "approver_name": approver_name,
            "approver_email": approver_email,
            "approval_timestamp": approval_timestamp,
            "expires_at": _serialize(e.expires_at),
            "reason": (e.reason or "").strip().replace("\r", " ").replace("\n", " "),
            "ticket_link": _serialize(e.ticket_link),
        })
    return rows


def build_control_mapping_rows(session: Session | None = None) -> list[dict[str, str]]:
    """
    Build control mapping rows for compliance pack (Step 12.1, 12.3).

    When session is provided, reads from control_mappings table (one row per
    control_id + framework_name). When session is None or table is empty,
    returns static CONTROL_MAPPING_V1 for backward compatibility.
    """
    if session is not None:
        result = session.execute(
            select(ControlMapping)
            .order_by(ControlMapping.control_id, ControlMapping.framework_name)
        )
        rows_orm = list(result.scalars().all())
        if rows_orm:
            return [
                {
                    "control_id": (m.control_id or ""),
                    "framework_name": (m.framework_name or ""),
                    "framework_control_code": (m.framework_control_code or ""),
                    "control_title": (m.control_title or ""),
                    "description": (m.description or ""),
                }
                for m in rows_orm
            ]
    return [
        {k: (v or "") for k, v in row.items()}
        for row in CONTROL_MAPPING_V1
    ]


def build_auditor_summary_content(
    tenant_name: str,
    as_of_date: str,
    open_findings: int,
    open_actions: int,
    total_exceptions: int,
    expiring_30d: int,
    remediations_30d: int,
) -> str:
    """
    Build mandatory auditor summary HTML one-pager.
    As of [date], tenant X: Y open findings, Z open actions, N exceptions
    (M expiring in 30 days), P remediations in last 30 days.
    """
    return AUDITOR_SUMMARY_HTML_TEMPLATE.format(
        tenant_name=(tenant_name or "Tenant").replace("<", "&lt;").replace(">", "&gt;"),
        as_of_date=as_of_date,
        open_findings=open_findings,
        open_actions=open_actions,
        total_exceptions=total_exceptions,
        expiring_30d=expiring_30d,
        remediations_30d=remediations_30d,
    )


def get_compliance_pack_only_files() -> list[tuple[str, str]]:
    """List of (filename, description) for compliance-pack-only files (Step 12.1)."""
    return [
        (EXCEPTION_ATTESTATIONS_CSV_FILENAME, EXCEPTION_ATTESTATIONS_DESCRIPTION),
        (CONTROL_MAPPING_CSV_FILENAME, CONTROL_MAPPING_DESCRIPTION),
        (AUDITOR_SUMMARY_FILENAME, AUDITOR_SUMMARY_DESCRIPTION),
    ]


def csv_content_from_rows(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    """Build CSV bytes from columns and row dicts (UTF-8)."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(c, "") for c in columns])
    return buf.getvalue().encode(EXPORT_ENCODING)
