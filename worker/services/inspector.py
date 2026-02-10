"""
Amazon Inspector v2 API client (Step 2B.2).

Fetches vulnerability findings (CVE, package, code) using the assumed-role session.
Inspector v2 is regional; list_findings returns findings for the account in that region.
Normalizes Inspector Finding to our finding shape for storage with source='inspector'.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from worker.services.json_safe import make_json_safe

logger = logging.getLogger(__name__)

__all__ = ["fetch_all_inspector_findings", "normalize_inspector_finding"]

# Throttling / transient errors → retry
TRANSIENT_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailable",
    "InternalServerException",
    "RequestLimitExceeded",
}


def _is_transient(e: BaseException) -> bool:
    if isinstance(e, ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        return code in TRANSIENT_CODES
    return False


PAGE_SLEEP_SECONDS = 0.25
MAX_RESULTS_PER_PAGE = 100


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _trunc(s: str | None, n: int) -> str | None:
    if s is None:
        return None
    return s[:n] if len(s) > n else s


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def list_findings_page(
    session: boto3.Session,
    region: str,
    account_id: str,
    max_results: int = MAX_RESULTS_PER_PAGE,
    next_token: str | None = None,
) -> dict:
    """
    List one page of Inspector v2 findings for the account in the region.

    Uses filterCriteria.awsAccountId to scope to the member account.
    Returns dict with 'findings' (list) and 'nextToken' (str | None).
    """
    client = session.client("inspector2", region_name=region)
    kwargs: dict = {
        "filterCriteria": {
            "awsAccountId": [{"comparison": "EQUALS", "value": account_id}],
        },
        "maxResults": min(max(1, max_results), 100),
    }
    if next_token:
        kwargs["nextToken"] = next_token

    logger.debug(
        "Fetching Inspector findings account_id=%s region=%s page=%s",
        account_id,
        region,
        "next" if next_token else "first",
    )
    response = client.list_findings(**kwargs)
    return {
        "findings": response.get("findings", []),
        "nextToken": response.get("nextToken"),
    }


def fetch_all_inspector_findings(
    session: boto3.Session,
    region: str,
    account_id: str,
) -> list[dict]:
    """
    Fetch all Inspector v2 findings for the account in the given region.

    Paginates list_findings with rate limiting. Returns raw Finding dicts;
    normalize with normalize_inspector_finding() before upserting.

    Returns:
        List of raw Inspector Finding dicts.
    """
    all_findings: list[dict] = []
    next_token: str | None = None
    page = 0

    while True:
        page += 1
        if page > 1:
            time.sleep(PAGE_SLEEP_SECONDS)
        resp = list_findings_page(
            session,
            region=region,
            account_id=account_id,
            max_results=MAX_RESULTS_PER_PAGE,
            next_token=next_token,
        )
        findings = resp.get("findings", [])
        all_findings.extend(findings)
        next_token = resp.get("nextToken")
        if not next_token:
            break

    logger.info(
        "Fetched Inspector findings region=%s account_id=%s total=%d pages=%d",
        region,
        account_id,
        len(all_findings),
        page,
    )
    return all_findings


def normalize_inspector_finding(
    raw: dict,
    account_id: str,
    region: str,
    tenant_id: Any,
) -> dict[str, Any]:
    """
    Normalize Inspector v2 Finding to our Finding model shape.

    Maps: findingArn → finding_id, severity → severity_label (CRITICAL/HIGH/MEDIUM/LOW/
    INFORMATIONAL/UNTRIAGED), type → title prefix, description → title/description,
    resources[0] → resource_id/resource_type, firstObservedAt/lastObservedAt →
    first_observed_at/last_observed_at, status → status (ACTIVE→NEW, CLOSED→RESOLVED).
    """
    finding_arn = raw.get("findingArn") or ""
    finding_id = _trunc(finding_arn, 512) or "unknown"
    severity_label = (raw.get("severity") or "UNTRIAGED").upper()
    if severity_label not in (
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "INFORMATIONAL",
        "UNTRIAGED",
    ):
        severity_label = "MEDIUM"
    severity_normalized = {
        "CRITICAL": 100,
        "HIGH": 75,
        "MEDIUM": 50,
        "LOW": 25,
        "INFORMATIONAL": 0,
        "UNTRIAGED": 25,
    }.get(severity_label, 50)

    finding_type = (raw.get("type") or "FINDING").replace("_", " ")
    description = _trunc(raw.get("description"), 65535)
    title = _trunc(raw.get("description"), 512)
    if not title:
        title = f"Inspector: {finding_type} - {severity_label}"
    if len(title) > 512:
        title = title[:509] + "..."

    resources = raw.get("resources") or []
    resource_id = _trunc(resources[0].get("id"), 2048) if resources else None
    resource_type = _trunc(resources[0].get("type"), 256) if resources else None

    inspector_status = (raw.get("status") or "ACTIVE").upper()
    if inspector_status == "ACTIVE":
        status = "NEW"
    elif inspector_status == "CLOSED":
        status = "RESOLVED"
    else:
        status = "NOTIFIED"

    first_obs = _parse_ts(raw.get("firstObservedAt"))
    last_obs = _parse_ts(raw.get("lastObservedAt"))
    updated_at = last_obs or first_obs

    return {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "region": region,
        "finding_id": finding_id,
        "source": "inspector",
        "severity_label": severity_label[:32],
        "severity_normalized": severity_normalized,
        "title": title,
        "description": description,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "control_id": None,
        "standard_name": None,
        "status": status[:32],
        "first_observed_at": first_obs,
        "last_observed_at": last_obs,
        "sh_updated_at": updated_at,
        "raw_json": make_json_safe(raw),
    }
