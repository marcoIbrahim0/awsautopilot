"""
Baseline report generation and S3 upload (Step 13.2).

Builds report data from tenant findings, renders HTML, uploads to S3.
Used by the worker job handler for generate_baseline_report.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.tenant import Tenant
from backend.services.baseline_report_builder import build_baseline_report_data
from backend.services.baseline_report_renderer import render_baseline_report_html
from backend.services.evidence_export_s3 import build_baseline_report_s3_key


def generate_baseline_report(
    session: Session,
    tenant_id: uuid.UUID,
    report_id: uuid.UUID,
    account_ids: Optional[List[str]] = None,
) -> tuple[str, str, int]:
    """
    Generate baseline report (data + HTML), upload to S3 (Step 13.2).

    Loads tenant name, builds BaselineReportData from findings, renders HTML,
    uploads to S3_EXPORT_BUCKET at baseline-reports/{tenant_id}/{report_id}/baseline-report.html.
    Returns (bucket, key, file_size_bytes).

    Raises:
        ValueError: If S3_EXPORT_BUCKET is not configured.
        Exception: On build, render, or upload failure.
    """
    bucket = (settings.S3_EXPORT_BUCKET or "").strip()
    if not bucket:
        raise ValueError("S3 export bucket not configured")

    tenant_row = session.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
    tenant_name = (tenant_row.name or "").strip() if tenant_row else None

    data = build_baseline_report_data(
        session=session,
        tenant_id=str(tenant_id),
        account_ids=account_ids,
        tenant_name=tenant_name,
    )
    html_str = render_baseline_report_html(data)
    body = html_str.encode("utf-8")
    file_size = len(body)

    key = build_baseline_report_s3_key(tenant_id, report_id)
    region = (settings.S3_EXPORT_BUCKET_REGION or "").strip() or settings.AWS_REGION
    s3 = boto3.client("s3", region_name=region)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="text/html; charset=utf-8",
        Metadata={
            "tenant_id": str(tenant_id),
            "report_id": str(report_id),
        },
    )
    return (bucket, key, file_size)
