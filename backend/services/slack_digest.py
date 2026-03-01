"""
Slack weekly digest delivery (Step 11.4).

POSTs digest to Slack incoming webhook using Block Kit blocks from digest_content.
Webhook URL is secret: never log the full URL.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse
from typing import Any

from backend.services.digest_content import (
    DEFAULT_APP_NAME,
    build_slack_blocks,
    get_view_in_app_url,
)

logger = logging.getLogger(__name__)

# Redacted label for logs (security: do not log full webhook URL)
WEBHOOK_LOG_LABEL = "slack_webhook"
SLACK_WEBHOOK_HOST = "hooks.slack.com"


def is_valid_slack_webhook_url(url: str) -> bool:
    """Return True only for strict Slack incoming webhook URLs."""
    raw = (url or "").strip()
    if not raw:
        return False

    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.hostname != SLACK_WEBHOOK_HOST:
        return False
    if parsed.port not in (None, 443):
        return False
    if parsed.query or parsed.fragment:
        return False

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4:
        return False
    if parts[0] != "services":
        return False
    return all(parts[1:])


def _mask_webhook_url(url: str) -> str:
    """Return a safe string for logging (e.g. 'slack_webhook...' or '...')."""
    if not url or len(url) < 12:
        return "..."
    if "hooks.slack.com" in url:
        return "slack_webhook...hooks.slack.com"
    return WEBHOOK_LOG_LABEL + "..."


def send_slack_digest(
    webhook_url: str,
    tenant_name: str,
    payload: dict[str, Any],
    frontend_url: str | None = None,
    app_name: str = DEFAULT_APP_NAME,
) -> bool:
    """
    Post weekly digest to Slack via incoming webhook (Step 11.4).

    Builds Block Kit blocks via digest_content.build_slack_blocks and POSTs
    JSON { "blocks": [...] } to the webhook. Does not log the full webhook URL.

    Args:
        webhook_url: Slack incoming webhook URL (secret).
        tenant_name: Tenant/organization name for the message header.
        payload: Digest payload from worker (open_action_count, top_5_actions, etc.).
        frontend_url: Base URL for "View in app" link; defaults to empty (link may be relative).
        app_name: App name for context footer.

    Returns:
        True if Slack responded with 200, False otherwise.
    """
    url = (webhook_url or "").strip()
    if not url:
        logger.warning("send_slack_digest: webhook URL empty, skipping")
        return False
    if not is_valid_slack_webhook_url(url):
        logger.warning(
            "send_slack_digest: invalid webhook URL tenant=%s %s",
            (tenant_name or "?").strip()[:32],
            _mask_webhook_url(url),
        )
        return False

    view_url = get_view_in_app_url(frontend_url or "http://localhost:3000")
    blocks = build_slack_blocks(tenant_name, payload, view_url, app_name)
    body = json.dumps({"blocks": blocks}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info(
                    "Slack digest sent tenant=%s %s",
                    (tenant_name or "?").strip()[:32],
                    _mask_webhook_url(url),
                )
                return True
            logger.warning(
                "Slack digest unexpected status tenant=%s %s status=%s",
                (tenant_name or "?").strip()[:32],
                _mask_webhook_url(url),
                resp.status,
            )
            return False
    except urllib.error.HTTPError as e:
        logger.warning(
            "Slack digest failed tenant=%s %s status=%s body=%s",
            (tenant_name or "?").strip()[:32],
            _mask_webhook_url(url),
            e.code,
            (e.read().decode("utf-8", errors="replace")[:200] if e.fp else ""),
        )
        return False
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        logger.warning(
            "Slack digest error tenant=%s %s error=%s",
            (tenant_name or "?").strip()[:32],
            _mask_webhook_url(url),
            type(e).__name__,
        )
        return False
