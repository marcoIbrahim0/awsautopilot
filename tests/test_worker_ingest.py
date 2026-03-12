"""
Unit tests for worker/jobs/ingest_findings.py (execute_ingest_job - Step 2.5).

Tests cover:
- Missing required job fields (tenant_id, account_id, region)
- Invalid tenant_id format
- Account not found in DB
- Successful ingestion (new + updated findings)
- Finding field extraction (_extract_finding_fields)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.workers.jobs.ingest_findings import (
    _extract_finding_fields,
    _fetch_findings_with_consistency_retry,
    _merge_finding_batches,
    _normalized_finding_status,
    _parse_ts,
    _trunc,
    execute_ingest_job,
)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------
def test_parse_ts_valid_iso() -> None:
    """Valid ISO timestamp parses correctly."""
    result = _parse_ts("2026-01-30T10:00:00Z")
    assert result is not None
    assert result.year == 2026
    assert result.month == 1
    assert result.day == 30


def test_parse_ts_with_offset() -> None:
    """ISO timestamp with offset parses correctly."""
    result = _parse_ts("2026-01-30T10:00:00+00:00")
    assert result is not None


def test_parse_ts_none() -> None:
    """None input returns None."""
    assert _parse_ts(None) is None


def test_parse_ts_empty_string() -> None:
    """Empty string returns None."""
    assert _parse_ts("") is None


def test_parse_ts_invalid() -> None:
    """Invalid timestamp returns None."""
    assert _parse_ts("not-a-timestamp") is None


def test_trunc_shorter_than_limit() -> None:
    """String shorter than limit is unchanged."""
    assert _trunc("hello", 10) == "hello"


def test_trunc_longer_than_limit() -> None:
    """String longer than limit is truncated."""
    assert _trunc("hello world", 5) == "hello"


def test_trunc_none() -> None:
    """None input returns None."""
    assert _trunc(None, 10) is None


# ---------------------------------------------------------------------------
# _extract_finding_fields tests
# ---------------------------------------------------------------------------
def test_extract_finding_fields_basic() -> None:
    """Extracts basic fields from raw Security Hub finding."""
    tenant_id = uuid.uuid4()
    raw = {
        "Id": "arn:aws:securityhub:us-east-1:123456789012:finding/12345",
        "Title": "S3 bucket should have encryption enabled",
        "Description": "This S3 bucket does not have encryption enabled.",
        "Severity": {"Label": "HIGH", "Normalized": 70},
        "Resources": [
            {"Id": "arn:aws:s3:::my-bucket", "Type": "AwsS3Bucket"}
        ],
        "Workflow": {"Status": "NEW"},
        "Compliance": {
            "SecurityControlId": "S3.4",
            "AssociatedStandards": [{"StandardsId": "aws-foundational-security-best-practices"}],
        },
        "CreatedAt": "2026-01-30T08:00:00Z",
        "UpdatedAt": "2026-01-30T09:00:00Z",
    }
    
    fields = _extract_finding_fields(raw, "123456789012", "us-east-1", tenant_id)
    
    assert fields["tenant_id"] == tenant_id
    assert fields["account_id"] == "123456789012"
    assert fields["region"] == "us-east-1"
    assert fields["finding_id"] == raw["Id"]
    assert fields["severity_label"] == "HIGH"
    assert fields["title"] == raw["Title"]
    assert fields["resource_id"] == "arn:aws:s3:::my-bucket"
    assert fields["resource_type"] == "AwsS3Bucket"
    assert fields["control_id"] == "S3.4"
    assert fields["status"] == "NEW"
    assert fields["resolved_at"] is None
    assert fields["raw_json"]["relationship_context"]["complete"] is True
    assert fields["raw_json"]["relationship_context"]["confidence"] == 1.0
    assert fields["raw_json"]["relationship_context"]["scope"] == "resource"
    assert fields["raw_json"]["relationship_context"]["resource_key"] == fields["resource_key"]


def test_extract_finding_fields_sets_resolved_at_when_compliance_passed() -> None:
    """Resolved findings carry a resolved_at timestamp from AWS observation times."""
    tenant_id = uuid.uuid4()
    raw = {
        "Id": "arn:aws:securityhub:us-east-1:123456789012:finding/99999",
        "Title": "EBS encryption default enabled",
        "Severity": {"Label": "LOW"},
        "Resources": [{"Id": "AWS::::Account:123456789012", "Type": "AwsAccount"}],
        "Compliance": {"SecurityControlId": "EC2.7", "Status": "PASSED"},
        "Workflow": {"Status": "NEW"},
        "UpdatedAt": "2026-02-21T22:00:00Z",
    }

    fields = _extract_finding_fields(raw, "123456789012", "us-east-1", tenant_id)

    assert fields["status"] == "RESOLVED"
    assert fields["resolved_at"] == datetime(2026, 2, 21, 22, 0, 0, tzinfo=timezone.utc)


def test_extract_finding_fields_prefers_security_group_resource_for_ec2_control() -> None:
    """For SG controls, pick AwsEc2SecurityGroup even when AwsAccount is first."""
    tenant_id = uuid.uuid4()
    raw = {
        "Id": "arn:aws:securityhub:us-east-1:123456789012:finding/sg-1",
        "Title": "Security group should restrict SSH access",
        "Severity": {"Label": "HIGH"},
        "Resources": [
            {"Id": "AWS::::Account:123456789012", "Type": "AwsAccount"},
            {"Id": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0123456789abcdef0", "Type": "AwsEc2SecurityGroup"},
        ],
        "Workflow": {"Status": "NEW"},
        "Compliance": {"SecurityControlId": "EC2.53"},
    }

    fields = _extract_finding_fields(raw, "123456789012", "us-east-1", tenant_id)
    assert fields["resource_type"] == "AwsEc2SecurityGroup"
    assert fields["resource_id"] == "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0123456789abcdef0"


def test_extract_finding_fields_prefers_s3_bucket_resource_for_s3_bucket_controls() -> None:
    """For S3 bucket controls, pick AwsS3Bucket even when AwsAccount is first."""
    tenant_id = uuid.uuid4()
    raw = {
        "Id": "arn:aws:securityhub:us-east-1:123456789012:finding/s3-1",
        "Title": "S3 bucket should have encryption enabled",
        "Severity": {"Label": "MEDIUM"},
        "Resources": [
            {"Id": "AWS::::Account:123456789012", "Type": "AwsAccount"},
            {"Id": "arn:aws:s3:::my-bucket", "Type": "AwsS3Bucket"},
        ],
        "Workflow": {"Status": "NEW"},
        "Compliance": {"SecurityControlId": "S3.4"},
    }

    fields = _extract_finding_fields(raw, "123456789012", "us-east-1", tenant_id)
    assert fields["resource_type"] == "AwsS3Bucket"
    assert fields["resource_id"] == "arn:aws:s3:::my-bucket"


def test_extract_finding_fields_missing_optional() -> None:
    """Handles missing optional fields gracefully."""
    tenant_id = uuid.uuid4()
    raw = {
        "Id": "finding-123",
        "Title": "Test finding",
        "Severity": {"Label": "MEDIUM"},
        "Workflow": {"Status": "NOTIFIED"},
    }
    
    fields = _extract_finding_fields(raw, "123456789012", "eu-west-1", tenant_id)
    
    assert fields["finding_id"] == "finding-123"
    assert fields["severity_label"] == "MEDIUM"
    assert fields["resource_id"] is None
    assert fields["resource_type"] is None
    assert fields["control_id"] is None
    assert fields["raw_json"]["relationship_context"]["complete"] is False
    assert fields["raw_json"]["relationship_context"]["confidence"] == 0.0
    assert fields["raw_json"]["relationship_context"]["scope"] == "unknown"


def test_extract_finding_fields_severity_normalized() -> None:
    """Severity is normalized to integer."""
    tenant_id = uuid.uuid4()
    raw = {
        "Id": "finding-123",
        "Title": "Test",
        "Severity": {"Label": "CRITICAL"},
        "Workflow": {"Status": "NEW"},
    }
    
    fields = _extract_finding_fields(raw, "123456789012", "us-east-1", tenant_id)
    
    # CRITICAL maps to 100 (per Finding.severity_to_int)
    assert fields["severity_normalized"] == 100


def test_normalized_finding_status_passed_maps_to_resolved() -> None:
    """Only Compliance PASSED is treated as resolved."""
    raw = {
        "Workflow": {"Status": "NEW"},
        "Compliance": {"Status": "PASSED"},
    }
    assert _normalized_finding_status(raw) == "RESOLVED"


def test_normalized_finding_status_resolved_workflow_without_passed_stays_open() -> None:
    """Workflow RESOLVED alone must not mark finding as resolved in SaaS."""
    raw = {
        "Workflow": {"Status": "RESOLVED"},
        "Compliance": {"Status": "FAILED"},
    }
    assert _normalized_finding_status(raw) == "NEW"


def test_merge_finding_batches_prefers_later_state_when_updated_at_matches() -> None:
    """Later fetches win when Security Hub changes state without advancing UpdatedAt."""
    initial = [
        {
            "Id": "finding-1",
            "UpdatedAt": "2026-03-12T16:30:00Z",
            "Compliance": {"Status": "FAILED"},
            "Workflow": {"Status": "RESOLVED"},
            "RecordState": "ACTIVE",
        }
    ]
    converged = [
        {
            "Id": "finding-1",
            "UpdatedAt": "2026-03-12T16:30:00Z",
            "Compliance": {"Status": "PASSED"},
            "Workflow": {"Status": "NEW"},
            "RecordState": "ARCHIVED",
        }
    ]

    merged = _merge_finding_batches(initial, converged)

    assert len(merged) == 1
    assert merged[0]["Compliance"]["Status"] == "PASSED"
    assert merged[0]["RecordState"] == "ARCHIVED"


def test_fetch_findings_with_consistency_retry_merges_fresher_security_hub_state() -> None:
    """Bounded retries keep the latest state when Security Hub converges after the first fetch."""
    initial = [
        {
            "Id": "finding-1",
            "UpdatedAt": "2026-03-12T15:27:00Z",
            "Compliance": {"Status": "FAILED"},
            "Workflow": {"Status": "NEW"},
            "RecordState": "ACTIVE",
        }
    ]
    converged = [
        {
            "Id": "finding-1",
            "UpdatedAt": "2026-03-12T16:30:00Z",
            "Compliance": {"Status": "PASSED"},
            "Workflow": {"Status": "NEW"},
            "RecordState": "ARCHIVED",
        }
    ]

    with patch("backend.workers.jobs.ingest_findings.time.sleep"):
        with patch(
            "backend.workers.jobs.ingest_findings.fetch_all_findings",
            side_effect=[initial, converged, converged],
        ) as mock_fetch:
            findings = _fetch_findings_with_consistency_retry(
                MagicMock(),
                region="us-east-1",
                account_id="123456789012",
            )

    assert findings[0]["Compliance"]["Status"] == "PASSED"
    assert findings[0]["RecordState"] == "ARCHIVED"
    assert mock_fetch.call_count == 3


# ---------------------------------------------------------------------------
# execute_ingest_job validation tests
# ---------------------------------------------------------------------------
def test_execute_ingest_job_missing_tenant_id() -> None:
    """Job without tenant_id raises ValueError."""
    job = {"account_id": "123456789012", "region": "us-east-1", "job_type": "ingest_findings"}
    
    with pytest.raises(ValueError, match="tenant_id"):
        execute_ingest_job(job)


def test_execute_ingest_job_missing_account_id() -> None:
    """Job without account_id raises ValueError."""
    job = {"tenant_id": str(uuid.uuid4()), "region": "us-east-1", "job_type": "ingest_findings"}
    
    with pytest.raises(ValueError, match="account_id"):
        execute_ingest_job(job)


def test_execute_ingest_job_missing_region() -> None:
    """Job without region raises ValueError."""
    job = {"tenant_id": str(uuid.uuid4()), "account_id": "123456789012", "job_type": "ingest_findings"}
    
    with pytest.raises(ValueError, match="region"):
        execute_ingest_job(job)


def test_execute_ingest_job_invalid_tenant_id() -> None:
    """Job with invalid tenant_id format raises ValueError."""
    job = {
        "tenant_id": "not-a-uuid",
        "account_id": "123456789012",
        "region": "us-east-1",
        "job_type": "ingest_findings",
    }
    
    with pytest.raises(ValueError, match="invalid tenant_id"):
        execute_ingest_job(job)


# ---------------------------------------------------------------------------
# execute_ingest_job database tests
# ---------------------------------------------------------------------------
def test_execute_ingest_job_account_not_found() -> None:
    """Job fails if AWS account not found in database."""
    tenant_id = uuid.uuid4()
    job = {
        "tenant_id": str(tenant_id),
        "account_id": "123456789012",
        "region": "us-east-1",
        "job_type": "ingest_findings",
    }
    
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None  # No account
    mock_session.query.return_value = mock_query
    
    with patch("backend.workers.jobs.ingest_findings.session_scope") as mock_scope:
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        
        with pytest.raises(ValueError, match="aws_account not found"):
            execute_ingest_job(job)


# ---------------------------------------------------------------------------
# execute_ingest_job success tests
# ---------------------------------------------------------------------------
def test_execute_ingest_job_success() -> None:
    """Successful ingestion fetches findings and upserts them."""
    tenant_id = uuid.uuid4()
    job = {
        "tenant_id": str(tenant_id),
        "account_id": "123456789012",
        "region": "us-east-1",
        "job_type": "ingest_findings",
    }
    
    # Mock account
    mock_account = MagicMock()
    mock_account.role_read_arn = "arn:aws:iam::123456789012:role/TestRole"
    mock_account.external_id = "ext-123"
    
    # Mock DB session
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.first.side_effect = [mock_account, None]  # Account found, no existing finding
    mock_session.query.return_value = mock_query
    mock_session.begin_nested.return_value.__enter__ = MagicMock()
    mock_session.begin_nested.return_value.__exit__ = MagicMock(return_value=False)
    
    # Mock findings
    mock_findings = [
        {
            "Id": "finding-1",
            "Title": "Test Finding 1",
            "Severity": {"Label": "HIGH"},
            "Workflow": {"Status": "NEW"},
        }
    ]
    
    with patch("backend.workers.jobs.ingest_findings.session_scope") as mock_scope:
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        
        with patch("backend.workers.jobs.ingest_findings.assume_role") as mock_assume:
            mock_boto_session = MagicMock()
            mock_assume.return_value = mock_boto_session
            
            with patch("backend.workers.jobs.ingest_findings.fetch_all_findings", return_value=mock_findings):
                execute_ingest_job(job)
        
        # Verify assume_role was called with correct args
        mock_assume.assert_called_once_with(
            role_arn=mock_account.role_read_arn,
            external_id=mock_account.external_id,
        )


def test_execute_ingest_job_empty_findings() -> None:
    """Job completes successfully even with no findings."""
    tenant_id = uuid.uuid4()
    job = {
        "tenant_id": str(tenant_id),
        "account_id": "123456789012",
        "region": "us-east-1",
        "job_type": "ingest_findings",
    }
    
    mock_account = MagicMock()
    mock_account.role_read_arn = "arn:aws:iam::123456789012:role/TestRole"
    mock_account.external_id = "ext-123"
    
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_account
    mock_session.query.return_value = mock_query
    
    with patch("backend.workers.jobs.ingest_findings.session_scope") as mock_scope:
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        
        with patch("backend.workers.jobs.ingest_findings.assume_role"):
            with patch("backend.workers.jobs.ingest_findings.fetch_all_findings", return_value=[]):
                # Should complete without error
                execute_ingest_job(job)
