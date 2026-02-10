"""
Unit tests for worker/services/security_hub.py (Step 2.5).

Tests cover:
- fetch_security_hub_findings: single page fetch with retry
- fetch_all_findings: pagination loop
- Transient error retry behavior
- DEFAULT_FILTERS constant
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from worker.services.security_hub import (
    DEFAULT_FILTERS,
    fetch_all_findings,
    fetch_security_hub_findings,
)


# ---------------------------------------------------------------------------
# DEFAULT_FILTERS tests
# ---------------------------------------------------------------------------
def test_default_filters_structure() -> None:
    """DEFAULT_FILTERS has expected keys."""
    assert "RecordState" in DEFAULT_FILTERS
    assert "WorkflowStatus" in DEFAULT_FILTERS
    assert "SeverityLabel" not in DEFAULT_FILTERS


def test_default_filters_record_state() -> None:
    """DEFAULT_FILTERS includes ACTIVE and ARCHIVED findings."""
    record_state_values = [f["Value"] for f in DEFAULT_FILTERS["RecordState"]]
    assert "ACTIVE" in record_state_values
    assert "ARCHIVED" in record_state_values


def test_default_filters_workflow_status() -> None:
    """DEFAULT_FILTERS includes all workflow states needed for PASSED reconciliation."""
    workflow_values = [f["Value"] for f in DEFAULT_FILTERS["WorkflowStatus"]]
    assert "NEW" in workflow_values
    assert "NOTIFIED" in workflow_values
    assert "RESOLVED" in workflow_values
    assert "SUPPRESSED" in workflow_values


# ---------------------------------------------------------------------------
# fetch_security_hub_findings tests
# ---------------------------------------------------------------------------
def test_fetch_security_hub_findings_success() -> None:
    """Successful single-page fetch returns findings and NextToken."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {
        "Findings": [{"Id": "finding-1"}, {"Id": "finding-2"}],
        "NextToken": "token-123",
    }
    mock_session.client.return_value = mock_client
    
    result = fetch_security_hub_findings(
        session=mock_session,
        region="us-east-1",
        account_id="123456789012",
    )
    
    assert len(result["Findings"]) == 2
    assert result["NextToken"] == "token-123"
    mock_session.client.assert_called_with("securityhub", region_name="us-east-1")


def test_fetch_security_hub_findings_no_next_token() -> None:
    """Last page has no NextToken."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {
        "Findings": [{"Id": "finding-1"}],
    }
    mock_session.client.return_value = mock_client
    
    result = fetch_security_hub_findings(
        session=mock_session,
        region="us-east-1",
        account_id="123456789012",
    )
    
    assert result["NextToken"] is None


def test_fetch_security_hub_findings_with_next_token() -> None:
    """Pagination token is passed to API."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": []}
    mock_session.client.return_value = mock_client
    
    fetch_security_hub_findings(
        session=mock_session,
        region="us-east-1",
        account_id="123456789012",
        next_token="page-2-token",
    )
    
    call_kwargs = mock_client.get_findings.call_args[1]
    assert call_kwargs["NextToken"] == "page-2-token"


def test_fetch_security_hub_findings_max_results_capped() -> None:
    """max_results is capped at 100."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": []}
    mock_session.client.return_value = mock_client
    
    fetch_security_hub_findings(
        session=mock_session,
        region="us-east-1",
        account_id="123456789012",
        max_results=500,  # Exceeds 100
    )
    
    call_kwargs = mock_client.get_findings.call_args[1]
    assert call_kwargs["MaxResults"] == 100


def test_fetch_security_hub_findings_uses_default_filters() -> None:
    """API call uses DEFAULT_FILTERS."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": []}
    mock_session.client.return_value = mock_client
    
    fetch_security_hub_findings(
        session=mock_session,
        region="us-east-1",
        account_id="123456789012",
    )
    
    call_kwargs = mock_client.get_findings.call_args[1]
    assert call_kwargs["Filters"] == DEFAULT_FILTERS


# ---------------------------------------------------------------------------
# fetch_security_hub_findings retry tests
# ---------------------------------------------------------------------------
def test_fetch_security_hub_findings_throttling_retried() -> None:
    """Throttling error triggers retry."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.side_effect = [
        ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "GetFindings"
        ),
        {"Findings": [{"Id": "finding-1"}]},
    ]
    mock_session.client.return_value = mock_client
    
    with patch("time.sleep"):  # Skip actual sleep
        result = fetch_security_hub_findings(
            session=mock_session,
            region="us-east-1",
            account_id="123456789012",
        )
    
    assert len(result["Findings"]) == 1
    assert mock_client.get_findings.call_count == 2


def test_fetch_security_hub_findings_access_denied_not_retried() -> None:
    """AccessDenied is not retried."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Not authorized"}},
        "GetFindings"
    )
    mock_session.client.return_value = mock_client
    
    with pytest.raises(ClientError):
        fetch_security_hub_findings(
            session=mock_session,
            region="us-east-1",
            account_id="123456789012",
        )
    
    # Should only be called once (no retry for non-transient errors)
    assert mock_client.get_findings.call_count == 1


# ---------------------------------------------------------------------------
# fetch_all_findings tests
# ---------------------------------------------------------------------------
def test_fetch_all_findings_single_page() -> None:
    """Single page of findings (no pagination)."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {
        "Findings": [{"Id": "f1"}, {"Id": "f2"}, {"Id": "f3"}],
    }
    mock_session.client.return_value = mock_client
    
    result = fetch_all_findings(
        session=mock_session,
        region="us-east-1",
        account_id="123456789012",
    )
    
    assert len(result) == 3
    assert mock_client.get_findings.call_count == 1


def test_fetch_all_findings_multiple_pages() -> None:
    """Multiple pages are fetched and combined."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.side_effect = [
        {"Findings": [{"Id": "f1"}, {"Id": "f2"}], "NextToken": "page2"},
        {"Findings": [{"Id": "f3"}], "NextToken": "page3"},
        {"Findings": [{"Id": "f4"}]},  # No NextToken = last page
    ]
    mock_session.client.return_value = mock_client
    
    with patch("time.sleep"):  # Skip rate limiting sleep
        result = fetch_all_findings(
            session=mock_session,
            region="us-east-1",
            account_id="123456789012",
        )
    
    assert len(result) == 4
    assert mock_client.get_findings.call_count == 3


def test_fetch_all_findings_empty() -> None:
    """No findings returns empty list."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.return_value = {"Findings": []}
    mock_session.client.return_value = mock_client
    
    result = fetch_all_findings(
        session=mock_session,
        region="us-east-1",
        account_id="123456789012",
    )
    
    assert result == []


def test_fetch_all_findings_rate_limiting() -> None:
    """Rate limiting sleep is called between pages."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_findings.side_effect = [
        {"Findings": [{"Id": "f1"}], "NextToken": "page2"},
        {"Findings": [{"Id": "f2"}]},
    ]
    mock_session.client.return_value = mock_client
    
    with patch("time.sleep") as mock_sleep:
        fetch_all_findings(
            session=mock_session,
            region="us-east-1",
            account_id="123456789012",
        )
    
    # Sleep should be called once (between page 1 and 2)
    assert mock_sleep.call_count == 1
