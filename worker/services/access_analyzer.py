"""
IAM Access Analyzer API client (Step 2B.1).

Fetches findings using the assumed-role session. Supports external access analyzers
per region. Normalizes FindingSummary to our finding shape (finding_id, severity, title,
resource_id, status, etc.) for storage in the findings table with source='access_analyzer'.
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
from backend.services.canonicalization import build_resource_key

logger = logging.getLogger(__name__)

__all__ = ["fetch_all_access_analyzer_findings", "normalize_aa_finding"]

# Throttling / transient errors → retry
TRANSIENT_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailable",
    "InternalServerException",
}


def _is_transient(e: BaseException) -> bool:
    if isinstance(e, ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        return code in TRANSIENT_CODES
    return False


PAGE_SLEEP_SECONDS = 0.2


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def list_analyzers(session: boto3.Session, region: str) -> list[dict]:
    """
    List active analyzers in the region across ACCOUNT and ORGANIZATION scopes.

    Args:
        session: boto3 session with assumed-role credentials.
        region: AWS region.

    Returns:
        List of analyzer dicts with at least 'arn' and 'name'.
    """
    client = session.client("accessanalyzer", region_name=region)
    out_by_arn: dict[str, dict] = {}
    for analyzer_scope in ("ACCOUNT", "ORGANIZATION"):
        next_token = None
        while True:
            kwargs: dict = {"type": analyzer_scope}
            if next_token:
                kwargs["nextToken"] = next_token
            response = client.list_analyzers(**kwargs)
            for analyzer in response.get("analyzers", []):
                if analyzer.get("status") != "ACTIVE":
                    continue
                arn = analyzer.get("arn")
                if not arn:
                    continue
                out_by_arn[arn] = {
                    "arn": arn,
                    "name": analyzer.get("name", ""),
                }
            next_token = response.get("nextToken")
            if not next_token:
                break
            time.sleep(PAGE_SLEEP_SECONDS)
    return list(out_by_arn.values())


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
    analyzer_arn: str,
    max_results: int = 100,
    next_token: str | None = None,
) -> dict:
    """
    List one page of findings for the given analyzer.

    Returns:
        dict with 'findings' (list of FindingSummary) and 'nextToken' (str | None).
    """
    client = session.client("accessanalyzer", region_name=region)
    kwargs: dict = {"analyzerArn": analyzer_arn, "maxResults": min(max_results, 100)}
    if next_token:
        kwargs["nextToken"] = next_token
    response = client.list_findings(**kwargs)
    return {
        "findings": response.get("findings", []),
        "nextToken": response.get("nextToken"),
    }


def fetch_all_access_analyzer_findings(
    session: boto3.Session,
    region: str,
    account_id: str,
) -> list[dict]:
    """
    Fetch all IAM Access Analyzer findings for the account in the given region.

    Lists active analyzers (ACCOUNT type), then lists findings for each analyzer
    with pagination. Returns raw FindingSummary dicts; normalize with
    normalize_aa_finding() before upserting.

    Returns:
        List of raw finding dicts (FindingSummary shape).
    """
    analyzers = list_analyzers(session, region)
    if not analyzers:
        logger.info(
            "No active Access Analyzer analyzers in region=%s account_id=%s",
            region,
            account_id,
        )
        return []

    all_findings: list[dict] = []
    for analyzer in analyzers:
        arn = analyzer["arn"]
        next_token = None
        page = 0
        while True:
            page += 1
            if page > 1:
                time.sleep(PAGE_SLEEP_SECONDS)
            resp = list_findings_page(
                session,
                region=region,
                analyzer_arn=arn,
                max_results=100,
                next_token=next_token,
            )
            findings = resp.get("findings", [])
            for f in findings:
                f["_analyzerArn"] = arn
            all_findings.extend(findings)
            next_token = resp.get("nextToken")
            if not next_token:
                break

    logger.info(
        "Fetched Access Analyzer findings region=%s account_id=%s total=%d",
        region,
        account_id,
        len(all_findings),
    )
    return all_findings


def normalize_aa_finding(
    raw: dict,
    account_id: str,
    region: str,
    tenant_id: Any,
) -> dict[str, Any]:
    """
    Normalize IAM Access Analyzer FindingSummary to our Finding model shape.

    Maps: id → finding_id, resource → resource_id, resourceType → resource_type,
    status (ACTIVE/ARCHIVED/RESOLVED) → status (NEW/SUPPRESSED/RESOLVED),
    createdAt/updatedAt → first_observed_at/last_observed_at.
    Derives title and severity (external/public access → HIGH, else MEDIUM).
    """
    fid = (raw.get("id") or "")[:512]
    resource = (raw.get("resource") or "")[:2048]
    resource_type = (raw.get("resourceType") or "")[:256]
    aa_status = (raw.get("status") or "ACTIVE").upper()
    if aa_status == "ACTIVE":
        status = "NEW"
    elif aa_status == "RESOLVED":
        status = "RESOLVED"
    else:
        status = "SUPPRESSED"

    actions = raw.get("action") or []
    is_public = raw.get("isPublic") is True
    principal = raw.get("principal") or {}
    if is_public or principal:
        severity_label = "HIGH"
    else:
        severity_label = "MEDIUM"

    action_str = ", ".join(actions[:3]) if actions else "external access"
    title = f"Access Analyzer: {resource_type or 'Resource'} - {action_str}"
    if len(title) > 512:
        title = title[:509] + "..."

    created = _parse_ts(raw.get("createdAt"))
    updated = _parse_ts(raw.get("updatedAt"))
    analyzed = _parse_ts(raw.get("analyzedAt"))

    resource_key = build_resource_key(
        account_id=account_id,
        region=region,
        resource_id=resource or None,
        resource_type=resource_type or None,
    )

    return {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "region": region,
        "finding_id": fid,
        "source": "access_analyzer",
        "severity_label": severity_label[:32],
        "severity_normalized": 75 if severity_label == "HIGH" else 50,
        "title": title,
        "description": None,
        "resource_id": resource or None,
        "resource_type": resource_type or None,
        "control_id": None,
        "canonical_control_id": None,
        "resource_key": resource_key,
        "standard_name": None,
        "status": status[:32],
        "in_scope": False,
        "first_observed_at": created,
        "last_observed_at": updated or analyzed or created,
        "sh_updated_at": updated,
        "raw_json": make_json_safe(raw),
    }
