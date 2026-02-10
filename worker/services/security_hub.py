"""
Security Hub API client wrapper. Fetches findings using an assumed-role session.
"""
from __future__ import annotations

import logging
import time
import boto3
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

__all__ = ["fetch_security_hub_findings", "fetch_all_findings", "DEFAULT_FILTERS"]

# ---------------------------------------------------------------------------
# Filters: include active + archived and all workflow states so Compliance PASSED
# findings are retrievable and can drive resolved matching downstream.
# ---------------------------------------------------------------------------
DEFAULT_FILTERS = {
    "RecordState": [
        {"Comparison": "EQUALS", "Value": "ACTIVE"},
        {"Comparison": "EQUALS", "Value": "ARCHIVED"},
    ],
    "WorkflowStatus": [
        {"Comparison": "EQUALS", "Value": "NEW"},
        {"Comparison": "EQUALS", "Value": "NOTIFIED"},
        {"Comparison": "EQUALS", "Value": "RESOLVED"},
        {"Comparison": "EQUALS", "Value": "SUPPRESSED"},
    ],
}

# Throttling / transient errors → retry
TRANSIENT_CODES = {
    "Throttling",
    "ThrottlingException",
    "RequestThrottled",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    "InternalError",
    "InternalServiceError",
    "RequestTimeout",
    "RequestTimeoutException",
}

# Rate limit: ~10 TPS per account; sleep between pages (seconds)
PAGE_SLEEP_SECONDS = 0.15


def _is_transient(e: BaseException) -> bool:
    if isinstance(e, ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        return code in TRANSIENT_CODES
    return False


# ---------------------------------------------------------------------------
# Single-page fetcher (with retry)
# ---------------------------------------------------------------------------
@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def fetch_security_hub_findings(
    session: boto3.Session,
    region: str,
    account_id: str,
    max_results: int = 100,
    next_token: str | None = None,
) -> dict:
    """
    Fetch one page of Security Hub findings using the assumed-role session.

    Args:
        session: boto3.Session with assumed-role credentials.
        region: AWS region to query.
        account_id: AWS account ID (for logging).
        max_results: Max findings per page (capped at 100).
        next_token: Pagination token for the next page.

    Returns:
        dict with 'Findings' (list of raw finding dicts) and 'NextToken' (str | None).

    Raises:
        ClientError: If Security Hub access fails (not enabled, access denied, etc.).
    """
    client = session.client("securityhub", region_name=region)
    cap = min(max(1, max_results), 100)

    kwargs: dict = {
        "Filters": DEFAULT_FILTERS,
        "MaxResults": cap,
    }
    if next_token:
        kwargs["NextToken"] = next_token

    logger.info(
        "Fetching Security Hub findings account_id=%s region=%s page=%s",
        account_id,
        region,
        "next" if next_token else "first",
    )
    response = client.get_findings(**kwargs)
    findings = response.get("Findings", [])
    nxt = response.get("NextToken")

    logger.debug(
        "Fetched %d findings account_id=%s region=%s has_next=%s",
        len(findings),
        account_id,
        region,
        bool(nxt),
    )
    return {"Findings": findings, "NextToken": nxt}


# ---------------------------------------------------------------------------
# Fetch-all helper (pagination loop + rate limiting)
# ---------------------------------------------------------------------------
def fetch_all_findings(
    session: boto3.Session,
    region: str,
    account_id: str,
) -> list[dict]:
    """
    Fetch all Security Hub findings for the given account/region via pagination.

    Uses fetch_security_hub_findings in a loop, with a short sleep between pages
    to respect ~10 TPS rate limits.

    Returns:
        List of raw Security Hub finding dicts.
    """
    all_findings: list[dict] = []
    next_token: str | None = None
    page = 0

    while True:
        page += 1
        if page > 1:
            time.sleep(PAGE_SLEEP_SECONDS)
        response = fetch_security_hub_findings(
            session,
            region=region,
            account_id=account_id,
            max_results=100,
            next_token=next_token,
        )
        findings = response.get("Findings", [])
        all_findings.extend(findings)
        next_token = response.get("NextToken")
        if not next_token:
            break

    logger.info(
        "Fetched all findings account_id=%s region=%s total=%d pages=%d",
        account_id,
        region,
        len(all_findings),
        page,
    )
    return all_findings
