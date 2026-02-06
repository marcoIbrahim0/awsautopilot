"""
S3 configuration and tenant isolation for evidence pack exports (Step 10.5).

Single source of truth for:
- S3 key pattern (tenant-scoped path)
- Presigned URL expiry
- Config requirement (S3_EXPORT_BUCKET)
- IAM and ops notes

Tenant isolation: Each export is stored at
  exports/{tenant_id}/{export_id}/evidence-pack.zip
so tenant data is isolated by path. The API returns a presigned URL only when
the export belongs to the requesting tenant (loaded by export_id AND tenant_id).

Presigned URL: Generated on demand in GET /api/exports/{id} when status=success.
Expiry PRESIGNED_URL_EXPIRES_IN (1 hour). No customer AWS credentials; SaaS bucket.

IAM: Worker and API use an IAM role with s3:PutObject and s3:GetObject on the
bucket (or prefix). No customer credentials.

Ops (optional): Configure a lifecycle rule on the bucket to expire or transition
old exports (e.g. delete objects under exports/ after 90 days) to manage storage cost.
"""

from __future__ import annotations

import uuid

# Key path template: exports/{tenant_id}/{export_id}/evidence-pack.zip
# Ensures one export per tenant per id and isolates tenants by path.
EXPORT_KEY_PREFIX = "exports"
EVIDENCE_PACK_FILENAME = "evidence-pack.zip"

# Presigned URL expiry (seconds). 1 hour is typical for download links.
PRESIGNED_URL_EXPIRES_IN = 3600


def build_export_s3_key(tenant_id: uuid.UUID, export_id: uuid.UUID) -> str:
    """
    Build the S3 object key for an evidence pack (Step 10.5).

    Pattern: exports/{tenant_id}/{export_id}/evidence-pack.zip
    Ensures tenant isolation: each tenant's exports live under their tenant_id path.

    Args:
        tenant_id: Tenant UUID.
        export_id: Export job UUID.

    Returns:
        S3 key string (e.g. exports/550e8400-e29b-41d4-a716-446655440000/...).
    """
    return f"{EXPORT_KEY_PREFIX}/{tenant_id}/{export_id}/{EVIDENCE_PACK_FILENAME}"


# ---------------------------------------------------------------------------
# Baseline report (Step 13.2): key pattern and filename
# ---------------------------------------------------------------------------

BASELINE_REPORT_KEY_PREFIX = "baseline-reports"
BASELINE_REPORT_FILENAME = "baseline-report.html"


def build_baseline_report_s3_key(tenant_id: uuid.UUID, report_id: uuid.UUID) -> str:
    """
    Build the S3 object key for a baseline report (Step 13.2).

    Pattern: baseline-reports/{tenant_id}/{report_id}/baseline-report.html
    Tenant-scoped; same bucket as evidence exports (S3_EXPORT_BUCKET).

    Args:
        tenant_id: Tenant UUID.
        report_id: Baseline report UUID.

    Returns:
        S3 key string.
    """
    return f"{BASELINE_REPORT_KEY_PREFIX}/{tenant_id}/{report_id}/{BASELINE_REPORT_FILENAME}"
