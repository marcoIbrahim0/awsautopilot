"""
Unit tests for backend/utils/sqs.py (shared SQS utilities).

Tests cover:
- parse_queue_region: extracts region from various SQS URL formats
- build_ingest_job_payload: builds correct job dict matching worker contract
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

from backend.utils.sqs import (
    EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE,
    EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE,
    INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE,
    INGEST_ACCESS_ANALYZER_JOB_TYPE,
    INGEST_INSPECTOR_JOB_TYPE,
    INGEST_JOB_TYPE,
    RECONCILE_INVENTORY_SHARD_JOB_TYPE,
    RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE,
    WEEKLY_DIGEST_JOB_TYPE,
    build_ingest_control_plane_events_job_payload,
    build_ingest_access_analyzer_job_payload,
    build_ingest_inspector_job_payload,
    build_ingest_job_payload,
    build_pr_bundle_execution_job_payload,
    build_reconcile_inventory_shard_job_payload,
    build_reconcile_recently_touched_resources_job_payload,
    build_weekly_digest_job_payload,
    parse_queue_region,
)


# ---------------------------------------------------------------------------
# parse_queue_region
# ---------------------------------------------------------------------------
def test_parse_queue_region_standard_url() -> None:
    """Standard SQS URL format extracts region correctly."""
    url = "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"
    assert parse_queue_region(url) == "us-east-1"


def test_parse_queue_region_eu_region() -> None:
    """European region URL extracts correctly."""
    url = "https://sqs.eu-west-1.amazonaws.com/123456789012/queue-name"
    assert parse_queue_region(url) == "eu-west-1"


def test_parse_queue_region_ap_region() -> None:
    """Asia-Pacific region URL extracts correctly."""
    url = "https://sqs.ap-southeast-2.amazonaws.com/123456789012/queue"
    assert parse_queue_region(url) == "ap-southeast-2"


def test_parse_queue_region_with_whitespace() -> None:
    """URL with leading/trailing whitespace is handled."""
    url = "  https://sqs.eu-north-1.amazonaws.com/123456789012/queue  "
    assert parse_queue_region(url) == "eu-north-1"


def test_parse_queue_region_empty_string() -> None:
    """Empty string returns default region from settings."""
    with patch("backend.utils.sqs.settings") as mock_settings:
        mock_settings.AWS_REGION = "us-west-2"
        assert parse_queue_region("") == "us-west-2"


def test_parse_queue_region_none() -> None:
    """None returns default region from settings."""
    with patch("backend.utils.sqs.settings") as mock_settings:
        mock_settings.AWS_REGION = "eu-central-1"
        assert parse_queue_region(None) == "eu-central-1"  # type: ignore


def test_parse_queue_region_invalid_format() -> None:
    """Invalid URL format returns default region."""
    with patch("backend.utils.sqs.settings") as mock_settings:
        mock_settings.AWS_REGION = "us-east-1"
        assert parse_queue_region("not-a-valid-url") == "us-east-1"


def test_parse_queue_region_http_url() -> None:
    """HTTP (not HTTPS) URL still works."""
    url = "http://sqs.us-west-1.amazonaws.com/123456789012/queue"
    # The check is for "//sqs" so http:// works too
    assert parse_queue_region(url) == "us-west-1"


def test_parse_queue_region_missing_region_part() -> None:
    """URL with unusual format returns extracted part or default.
    
    Note: The parser extracts parts[1] which would be 'amazonaws' for this URL.
    This is expected behavior - the function tries its best but falls back to
    whatever is in position [1]. For truly malformed URLs, it returns default.
    """
    with patch("backend.utils.sqs.settings") as mock_settings:
        mock_settings.AWS_REGION = "ap-northeast-1"
        # This URL doesn't match the expected "//sqs" prefix pattern
        url = "https://invalid-sqs-url.com/queue"
        assert parse_queue_region(url) == "ap-northeast-1"


# ---------------------------------------------------------------------------
# build_ingest_job_payload
# ---------------------------------------------------------------------------
def test_build_ingest_job_payload_basic() -> None:
    """Builds correct payload with all required fields."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    account_id = "123456789012"
    region = "us-east-1"
    created_at = "2026-01-30T10:00:00+00:00"
    
    payload = build_ingest_job_payload(tenant_id, account_id, region, created_at)
    
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["account_id"] == account_id
    assert payload["region"] == region
    assert payload["job_type"] == INGEST_JOB_TYPE
    assert payload["job_type"] == "ingest_findings"
    assert payload["created_at"] == created_at


def test_build_ingest_job_payload_different_region() -> None:
    """Payload correctly uses provided region."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    
    payload = build_ingest_job_payload(
        tenant_id,
        "999999999999",
        "eu-west-1",
        "2026-01-30T12:00:00Z",
    )
    
    assert payload["region"] == "eu-west-1"
    assert payload["account_id"] == "999999999999"


def test_build_ingest_job_payload_tenant_id_converted_to_string() -> None:
    """UUID tenant_id is converted to string in payload."""
    tenant_id = uuid.uuid4()
    
    payload = build_ingest_job_payload(
        tenant_id,
        "123456789012",
        "us-east-1",
        "2026-01-30T10:00:00Z",
    )
    
    assert isinstance(payload["tenant_id"], str)
    assert payload["tenant_id"] == str(tenant_id)


def test_build_ingest_job_payload_matches_worker_contract() -> None:
    """Payload contains all fields required by worker (REQUIRED_JOB_FIELDS)."""
    # Worker expects: tenant_id, account_id, region, job_type
    tenant_id = uuid.uuid4()
    
    payload = build_ingest_job_payload(
        tenant_id,
        "123456789012",
        "us-east-1",
        "2026-01-30T10:00:00Z",
    )
    
    required_fields = {"tenant_id", "account_id", "region", "job_type"}
    assert required_fields.issubset(payload.keys())


def test_ingest_job_type_constant() -> None:
    """INGEST_JOB_TYPE constant has expected value."""
    assert INGEST_JOB_TYPE == "ingest_findings"


# ---------------------------------------------------------------------------
# build_ingest_access_analyzer_job_payload (Step 2B.1)
# ---------------------------------------------------------------------------
def test_build_ingest_access_analyzer_job_payload() -> None:
    """Step 2B.1: Access Analyzer job payload has correct job_type and shape."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    payload = build_ingest_access_analyzer_job_payload(
        tenant_id,
        "123456789012",
        "us-east-1",
        "2026-02-02T10:00:00Z",
    )
    assert payload["job_type"] == INGEST_ACCESS_ANALYZER_JOB_TYPE
    assert payload["job_type"] == "ingest_access_analyzer"
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["account_id"] == "123456789012"
    assert payload["region"] == "us-east-1"
    assert payload["created_at"] == "2026-02-02T10:00:00Z"
    required = {"tenant_id", "account_id", "region", "job_type"}
    assert required.issubset(payload.keys())


# ---------------------------------------------------------------------------
# build_ingest_inspector_job_payload (Step 2B.2)
# ---------------------------------------------------------------------------
def test_build_ingest_inspector_job_payload() -> None:
    """Step 2B.2: Inspector job payload has correct job_type and shape."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    payload = build_ingest_inspector_job_payload(
        tenant_id,
        "123456789012",
        "us-east-1",
        "2026-02-02T10:00:00Z",
    )
    assert payload["job_type"] == INGEST_INSPECTOR_JOB_TYPE
    assert payload["job_type"] == "ingest_inspector"
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["account_id"] == "123456789012"
    assert payload["region"] == "us-east-1"
    assert payload["created_at"] == "2026-02-02T10:00:00Z"
    required = {"tenant_id", "account_id", "region", "job_type"}
    assert required.issubset(payload.keys())


# ---------------------------------------------------------------------------
# build_weekly_digest_job_payload (Step 11.1)
# ---------------------------------------------------------------------------
def test_build_weekly_digest_job_payload() -> None:
    """Step 11.1: Weekly digest job payload has correct job_type and shape."""
    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    created_at = "2026-02-02T09:00:00Z"
    payload = build_weekly_digest_job_payload(tenant_id, created_at)
    assert payload["job_type"] == WEEKLY_DIGEST_JOB_TYPE
    assert payload["job_type"] == "weekly_digest"
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["created_at"] == created_at
    required = {"job_type", "tenant_id", "created_at"}
    assert required.issubset(payload.keys())


def test_build_pr_bundle_execution_job_payload_plan() -> None:
    execution_id = uuid.uuid4()
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    payload = build_pr_bundle_execution_job_payload(
        execution_id=execution_id,
        run_id=run_id,
        tenant_id=tenant_id,
        phase="plan",
        created_at="2026-02-09T10:00:00Z",
        requested_by_user_id=user_id,
    )
    assert payload["job_type"] == EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE
    assert payload["execution_id"] == str(execution_id)
    assert payload["run_id"] == str(run_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["phase"] == "plan"
    assert payload["requested_by_user_id"] == str(user_id)


def test_build_pr_bundle_execution_job_payload_apply() -> None:
    payload = build_pr_bundle_execution_job_payload(
        execution_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        phase="apply",
        created_at="2026-02-09T10:00:00Z",
    )
    assert payload["job_type"] == EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE
    assert payload["phase"] == "apply"


def test_build_ingest_control_plane_events_job_payload() -> None:
    tenant_id = uuid.uuid4()
    payload = build_ingest_control_plane_events_job_payload(
        tenant_id=tenant_id,
        account_id="123456789012",
        region="us-east-1",
        event={"id": "evt-1", "time": "2026-02-10T10:00:00Z"},
        event_id="evt-1",
        event_time="2026-02-10T10:00:00Z",
        intake_time="2026-02-10T10:00:05Z",
        created_at="2026-02-10T10:00:06Z",
    )
    assert payload["job_type"] == INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["event_id"] == "evt-1"
    assert payload["event"]["id"] == "evt-1"


def test_build_reconcile_inventory_shard_job_payload() -> None:
    tenant_id = uuid.uuid4()
    payload = build_reconcile_inventory_shard_job_payload(
        tenant_id=tenant_id,
        account_id="123456789012",
        region="eu-west-1",
        service="ec2",
        resource_ids=["sg-123"],
        created_at="2026-02-10T10:00:00Z",
    )
    assert payload["job_type"] == RECONCILE_INVENTORY_SHARD_JOB_TYPE
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["service"] == "ec2"
    assert payload["resource_ids"] == ["sg-123"]


def test_build_reconcile_recently_touched_resources_job_payload() -> None:
    tenant_id = uuid.uuid4()
    payload = build_reconcile_recently_touched_resources_job_payload(
        tenant_id=tenant_id,
        created_at="2026-02-10T10:00:00Z",
        lookback_minutes=30,
    )
    assert payload["job_type"] == RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["lookback_minutes"] == 30
    build_pr_bundle_execution_job_payload,
    build_pr_bundle_execution_job_payload,
