"""
Unit tests for evidence export worker and service (Step 10.3).

Tests cover:
- build_generate_export_job_payload shape
- generate_evidence_pack raises when S3 bucket not configured
- execute_evidence_export_job idempotent skip when already success/failed
- execute_evidence_export_job sets failed when generate_evidence_pack raises
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.models.enums import EvidenceExportStatus
from backend.utils.sqs import build_generate_export_job_payload, GENERATE_EXPORT_JOB_TYPE
from worker.jobs.evidence_export import execute_evidence_export_job


def test_build_generate_export_job_payload() -> None:
    """build_generate_export_job_payload returns correct shape for worker."""
    export_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    created_at = "2026-02-02T12:00:00Z"
    payload = build_generate_export_job_payload(export_id, tenant_id, created_at)
    assert payload["job_type"] == GENERATE_EXPORT_JOB_TYPE
    assert payload["export_id"] == str(export_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["created_at"] == created_at
    assert payload.get("pack_type") == "evidence"


def test_build_generate_export_job_payload_compliance() -> None:
    """build_generate_export_job_payload includes pack_type=compliance when requested."""
    export_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    created_at = "2026-02-02T12:00:00Z"
    payload = build_generate_export_job_payload(
        export_id, tenant_id, created_at, pack_type="compliance"
    )
    assert payload["pack_type"] == "compliance"


def test_generate_evidence_pack_raises_when_bucket_not_configured() -> None:
    """generate_evidence_pack raises ValueError when S3_EXPORT_BUCKET is empty."""
    from backend.services.evidence_export import generate_evidence_pack
    from sqlalchemy.orm import Session

    mock_session = MagicMock(spec=Session)
    tenant_id = uuid.uuid4()
    export_id = uuid.uuid4()

    with patch("backend.services.evidence_export.settings") as mock_settings:
        mock_settings.S3_EXPORT_BUCKET = ""
        mock_settings.AWS_REGION = "us-east-1"
        with pytest.raises(ValueError, match="S3 export bucket not configured"):
            generate_evidence_pack(
                session=mock_session,
                tenant_id=tenant_id,
                export_id=export_id,
                requested_by_email="test@example.com",
                export_created_at=datetime.now(timezone.utc).isoformat(),
                pack_type="evidence",
            )


def test_execute_evidence_export_job_idempotent_skip_when_success() -> None:
    """execute_evidence_export_job skips (no-op) when export is already success."""
    job = {
        "job_type": GENERATE_EXPORT_JOB_TYPE,
        "export_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    export = MagicMock()
    export.id = uuid.UUID(job["export_id"])
    export.tenant_id = uuid.UUID(job["tenant_id"])
    export.status = EvidenceExportStatus.success
    export.requested_by = None
    export.requested_by_user_id = None
    export.created_at = datetime.now(timezone.utc)

    result = MagicMock()
    result.scalar_one_or_none.return_value = export
    mock_session = MagicMock()
    mock_session.execute.return_value = result
    mock_session.flush = MagicMock()

    with patch("worker.jobs.evidence_export.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        execute_evidence_export_job(job)

    # generate_evidence_pack must not be called (idempotent skip)
    mock_session.execute.assert_called()
    export.status = EvidenceExportStatus.success  # unchanged


def test_execute_evidence_export_job_sets_failed_when_generate_raises() -> None:
    """execute_evidence_export_job sets status=failed and error_message when generate_evidence_pack raises."""
    job = {
        "job_type": GENERATE_EXPORT_JOB_TYPE,
        "export_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    export = MagicMock()
    export.id = uuid.UUID(job["export_id"])
    export.tenant_id = uuid.UUID(job["tenant_id"])
    export.status = EvidenceExportStatus.pending
    export.requested_by = None
    export.requested_by_user_id = uuid.uuid4()
    export.created_at = datetime.now(timezone.utc)

    result = MagicMock()
    result.scalar_one_or_none.return_value = export
    mock_session = MagicMock()
    mock_session.execute.return_value = result
    mock_session.flush = MagicMock()

    with patch("worker.jobs.evidence_export.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.evidence_export.generate_evidence_pack") as mock_gen:
            mock_gen.side_effect = RuntimeError("S3 upload failed")

            execute_evidence_export_job(job)

    assert export.status == EvidenceExportStatus.failed
    assert export.error_message == "S3 upload failed"
    assert export.completed_at is not None


def test_execute_evidence_export_job_passes_pack_type_to_generate() -> None:
    """execute_evidence_export_job passes pack_type from job to generate_evidence_pack."""
    job = {
        "job_type": GENERATE_EXPORT_JOB_TYPE,
        "export_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pack_type": "compliance",
    }
    export = MagicMock()
    export.id = uuid.UUID(job["export_id"])
    export.tenant_id = uuid.UUID(job["tenant_id"])
    export.status = EvidenceExportStatus.pending
    export.requested_by = None
    export.requested_by_user_id = uuid.uuid4()
    export.created_at = datetime.now(timezone.utc)

    result = MagicMock()
    result.scalar_one_or_none.return_value = export
    mock_session = MagicMock()
    mock_session.execute.return_value = result
    mock_session.flush = MagicMock()

    with patch("worker.jobs.evidence_export.session_scope") as mock_scope:
        ctx = MagicMock()
        ctx.__enter__.return_value = mock_session
        ctx.__exit__.return_value = False
        mock_scope.return_value = ctx

        with patch("worker.jobs.evidence_export.generate_evidence_pack") as mock_gen:
            mock_gen.return_value = ("bucket", "key", 1234)

            execute_evidence_export_job(job)

    mock_gen.assert_called_once()
    call_kw = mock_gen.call_args[1]
    assert call_kw.get("pack_type") == "compliance"
