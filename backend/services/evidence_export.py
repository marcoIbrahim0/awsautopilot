"""
Evidence pack generation and S3 upload (Step 10.3, 12.2).

Loads tenant data (findings, actions, remediation_runs, exceptions), builds
CSV/JSON and manifest per evidence_export_spec, zips, and uploads to S3.
When pack_type is "compliance", adds exception_attestations, control_mapping,
and auditor_summary from compliance_pack_spec (Step 12.1).
Used by the worker job handler for generate_export.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import boto3
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.config import settings
from backend.models.action import Action
from backend.models.enums import (
    ActionStatus,
    EvidenceExportStatus,
    FindingStatus,
    RemediationRunStatus,
)
from backend.models.evidence_export import EvidenceExport
from backend.models.exception import Exception as ExceptionModel
from backend.models.finding import Finding
from backend.models.remediation_run import RemediationRun
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.evidence_export_s3 import build_export_s3_key
from backend.services.evidence_export_spec import (
    ACTIONS_COLUMNS,
    ACTIONS_CSV_FILENAME,
    ACTIONS_JSON_FILENAME,
    CONTROL_SCOPE_NOTE,
    EXCEPTIONS_COLUMNS,
    EXCEPTIONS_CSV_FILENAME,
    EXCEPTIONS_JSON_FILENAME,
    EXPORT_ENCODING,
    FINDINGS_COLUMNS,
    FINDINGS_CSV_FILENAME,
    FINDINGS_JSON_FILENAME,
    MANIFEST_FILENAME,
    README_FILENAME,
    REMEDIATION_RUNS_COLUMNS,
    REMEDIATION_RUNS_CSV_FILENAME,
    REMEDIATION_RUNS_JSON_FILENAME,
    get_manifest_file_entries,
    get_readme_content,
)
from backend.services.compliance_pack_spec import (
    AUDITOR_SUMMARY_FILENAME,
    CONTROL_MAPPING_CSV_FILENAME,
    CONTROL_MAPPING_COLUMNS,
    EXCEPTION_ATTESTATIONS_CSV_FILENAME,
    EXCEPTION_ATTESTATIONS_COLUMNS,
    build_auditor_summary_content,
    build_control_mapping_rows,
    build_exception_attestation_rows,
    csv_content_from_rows,
)


def _serialize(val: Any) -> str:
    """Serialize a value for CSV/JSON export (datetime → ISO, uuid → str, enum → value)."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat() if val.tzinfo else val.replace(tzinfo=None).isoformat() + "Z"
    if isinstance(val, uuid.UUID):
        return str(val)
    if hasattr(val, "value"):  # Enum
        return str(val.value)
    return str(val)


def _row_finding(f: Finding) -> dict[str, str]:
    """Build export row for a finding (spec column names; severity from severity_label, updated_at from sh_updated_at)."""
    return {
        "id": _serialize(f.id),
        "finding_id": _serialize(f.finding_id),
        "account_id": _serialize(f.account_id),
        "region": _serialize(f.region),
        "severity": _serialize(f.severity_label),
        "status": _serialize(f.status),
        "control_id": _serialize(f.control_id),
        "title": _serialize(f.title),
        "resource_id": _serialize(f.resource_id),
        "resource_type": _serialize(f.resource_type),
        "first_observed_at": _serialize(f.first_observed_at),
        "updated_at": _serialize(f.sh_updated_at),
        "created_at": _serialize(f.created_at),
    }


def _row_action(a: Action) -> dict[str, str]:
    """Build export row for an action (finding_count = len(action_finding_links))."""
    finding_count = len(a.action_finding_links) if a.action_finding_links else 0
    return {
        "id": _serialize(a.id),
        "action_type": _serialize(a.action_type),
        "target_id": _serialize(a.target_id),
        "account_id": _serialize(a.account_id),
        "region": _serialize(a.region),
        "priority": _serialize(a.priority),
        "status": _serialize(a.status),
        "title": _serialize(a.title),
        "control_id": _serialize(a.control_id),
        "resource_id": _serialize(a.resource_id),
        "created_at": _serialize(a.created_at),
        "updated_at": _serialize(a.updated_at),
        "finding_count": _serialize(finding_count),
    }


def _row_remediation_run(r: RemediationRun) -> dict[str, str]:
    """Build export row for a remediation run (mode/status as string value)."""
    return {
        "id": _serialize(r.id),
        "action_id": _serialize(r.action_id),
        "mode": _serialize(r.mode),
        "status": _serialize(r.status),
        "outcome": _serialize(r.outcome),
        "approved_by_user_id": _serialize(r.approved_by_user_id),
        "started_at": _serialize(r.started_at),
        "completed_at": _serialize(r.completed_at),
        "created_at": _serialize(r.created_at),
    }


def _row_exception(e: ExceptionModel) -> dict[str, str]:
    """Build export row for an exception (entity_type as string value)."""
    return {
        "id": _serialize(e.id),
        "entity_type": _serialize(e.entity_type),
        "entity_id": _serialize(e.entity_id),
        "reason": _serialize(e.reason),
        "approved_by_user_id": _serialize(e.approved_by_user_id),
        "expires_at": _serialize(e.expires_at),
        "ticket_link": _serialize(e.ticket_link),
        "created_at": _serialize(e.created_at),
    }


def _csv_content(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    """Build CSV file content (header + rows), UTF-8."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(c, "") for c in columns])
    return buf.getvalue().encode(EXPORT_ENCODING)


def _json_content(rows: list[dict[str, str]]) -> bytes:
    """Build JSON array content, UTF-8."""
    return json.dumps(rows, ensure_ascii=False).encode(EXPORT_ENCODING)


def _auditor_metrics(
    session: Session,
    tenant_id: uuid.UUID,
    as_of: datetime,
) -> tuple[int, int, int, int, int]:
    """
    Compute counts for auditor summary: open_findings, open_actions,
    total_exceptions, expiring_30d, remediations_30d.
    """
    now = as_of
    in_30 = now + timedelta(days=30)

    open_findings = session.execute(
        select(func.count(Finding.id)).where(
            Finding.tenant_id == tenant_id,
            Finding.status.in_([FindingStatus.NEW.value, FindingStatus.NOTIFIED.value]),
        )
    ).scalar() or 0

    open_actions = session.execute(
        select(func.count(Action.id)).where(
            Action.tenant_id == tenant_id,
            Action.status.in_([ActionStatus.open.value, ActionStatus.in_progress.value]),
        )
    ).scalar() or 0

    total_exceptions = session.execute(
        select(func.count(ExceptionModel.id)).where(ExceptionModel.tenant_id == tenant_id)
    ).scalar() or 0

    expiring_30d = session.execute(
        select(func.count(ExceptionModel.id)).where(
            ExceptionModel.tenant_id == tenant_id,
            ExceptionModel.expires_at >= now,
            ExceptionModel.expires_at <= in_30,
        )
    ).scalar() or 0

    since_30d = now - timedelta(days=30)
    remediations_30d = session.execute(
        select(func.count(RemediationRun.id)).where(
            RemediationRun.tenant_id == tenant_id,
            RemediationRun.completed_at >= since_30d,
            RemediationRun.completed_at <= now,
            RemediationRun.status.in_([
                RemediationRunStatus.success.value,
                RemediationRunStatus.failed.value,
            ]),
        )
    ).scalar() or 0

    return (open_findings, open_actions, total_exceptions, expiring_30d, remediations_30d)


def generate_evidence_pack(
    session: Session,
    tenant_id: uuid.UUID,
    export_id: uuid.UUID,
    requested_by_email: str,
    export_created_at: str,
    pack_type: Literal["evidence", "compliance"] = "evidence",
) -> tuple[str, str, int]:
    """
    Generate evidence or compliance pack zip and upload to S3 (Step 10.3, 12.2).

    Queries findings, actions, remediation_runs, exceptions for the tenant;
    builds CSV/JSON and manifest per evidence_export_spec; when pack_type is
    "compliance", adds exception_attestations.csv, control_mapping.csv, and
    auditor_summary.html per compliance_pack_spec; zips; uploads to S3.
    Returns (s3_bucket, s3_key, file_size_bytes).

    Raises:
        ValueError: If S3_EXPORT_BUCKET is not configured.
        Exception: On S3 upload or generation failure.
    """
    bucket = (settings.S3_EXPORT_BUCKET or "").strip()
    if not bucket:
        raise ValueError("S3 export bucket not configured")

    # Load tenant data (no pagination for MVP)
    findings_result = session.execute(
        select(Finding).where(Finding.tenant_id == tenant_id).order_by(Finding.created_at)
    )
    findings = list(findings_result.scalars().all())

    actions_result = session.execute(
        select(Action)
        .where(Action.tenant_id == tenant_id)
        .options(selectinload(Action.action_finding_links))
        .order_by(Action.created_at)
    )
    actions = list(actions_result.scalars().all())

    runs_result = session.execute(
        select(RemediationRun)
        .where(RemediationRun.tenant_id == tenant_id)
        .order_by(RemediationRun.created_at)
    )
    runs = list(runs_result.scalars().all())

    exceptions_result = session.execute(
        select(ExceptionModel).where(ExceptionModel.tenant_id == tenant_id).order_by(ExceptionModel.created_at)
    )
    exceptions = list(exceptions_result.scalars().all())

    # Build row dicts
    findings_rows = [_row_finding(f) for f in findings]
    actions_rows = [_row_action(a) for a in actions]
    runs_rows = [_row_remediation_run(r) for r in runs]
    exceptions_rows = [_row_exception(e) for e in exceptions]

    # Manifest
    manifest_entries = get_manifest_file_entries(
        findings_rows=len(findings_rows),
        actions_rows=len(actions_rows),
        remediation_runs_rows=len(runs_rows),
        exceptions_rows=len(exceptions_rows),
    )
    manifest: dict[str, Any] = {
        "export_id": str(export_id),
        "tenant_id": str(tenant_id),
        "export_created_at": export_created_at,
        "requested_by": requested_by_email,
        "files": manifest_entries,
        "control_scope": CONTROL_SCOPE_NOTE,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode(EXPORT_ENCODING)

    # README
    readme_bytes = get_readme_content(
        export_id=str(export_id),
        tenant_id=str(tenant_id),
        export_created_at=export_created_at,
    ).encode(EXPORT_ENCODING)

    # CSV and JSON
    findings_csv = _csv_content(FINDINGS_COLUMNS, findings_rows)
    findings_json = _json_content(findings_rows)
    actions_csv = _csv_content(ACTIONS_COLUMNS, actions_rows)
    actions_json = _json_content(actions_rows)
    runs_csv = _csv_content(REMEDIATION_RUNS_COLUMNS, runs_rows)
    runs_json = _json_content(runs_rows)
    exceptions_csv = _csv_content(EXCEPTIONS_COLUMNS, exceptions_rows)
    exceptions_json = _json_content(exceptions_rows)

    # Zip in memory
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_FILENAME, manifest_bytes)
        zf.writestr(README_FILENAME, readme_bytes)
        zf.writestr(FINDINGS_CSV_FILENAME, findings_csv)
        zf.writestr(FINDINGS_JSON_FILENAME, findings_json)
        zf.writestr(ACTIONS_CSV_FILENAME, actions_csv)
        zf.writestr(ACTIONS_JSON_FILENAME, actions_json)
        zf.writestr(REMEDIATION_RUNS_CSV_FILENAME, runs_csv)
        zf.writestr(REMEDIATION_RUNS_JSON_FILENAME, runs_json)
        zf.writestr(EXCEPTIONS_CSV_FILENAME, exceptions_csv)
        zf.writestr(EXCEPTIONS_JSON_FILENAME, exceptions_json)

        if pack_type == "compliance":
            tenant_row = session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            ).scalar_one_or_none()
            tenant_name = (tenant_row.name or "Tenant").strip() if tenant_row else "Tenant"
            as_of = datetime.now(timezone.utc)
            as_of_str = as_of.isoformat()

            open_findings, open_actions, total_exceptions, expiring_30d, remediations_30d = _auditor_metrics(
                session, tenant_id, as_of
            )
            attestation_rows = build_exception_attestation_rows(session, tenant_id)
            control_rows = build_control_mapping_rows(session)
            auditor_html = build_auditor_summary_content(
                tenant_name=tenant_name,
                as_of_date=as_of_str,
                open_findings=int(open_findings),
                open_actions=int(open_actions),
                total_exceptions=int(total_exceptions),
                expiring_30d=int(expiring_30d),
                remediations_30d=int(remediations_30d),
            )
            zf.writestr(
                EXCEPTION_ATTESTATIONS_CSV_FILENAME,
                csv_content_from_rows(EXCEPTION_ATTESTATIONS_COLUMNS, attestation_rows),
            )
            zf.writestr(
                CONTROL_MAPPING_CSV_FILENAME,
                csv_content_from_rows(CONTROL_MAPPING_COLUMNS, control_rows),
            )
            zf.writestr(AUDITOR_SUMMARY_FILENAME, auditor_html.encode("utf-8"))

    zip_bytes = zip_buf.getvalue()
    file_size = len(zip_bytes)

    key = build_export_s3_key(tenant_id, export_id)

    # Upload (use bucket region if set, else default; must match bucket for consistency)
    region = (settings.S3_EXPORT_BUCKET_REGION or "").strip() or settings.AWS_REGION
    s3 = boto3.client("s3", region_name=region)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=zip_bytes,
        ContentType="application/zip",
    )

    return (bucket, key, file_size)
