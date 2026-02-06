"""
Unit tests for Slack digest delivery (Step 11.4).

Covers: send_slack_digest POSTs blocks to webhook; no full URL in logs;
empty webhook skips; HTTP error handling.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from backend.services.slack_digest import send_slack_digest, _mask_webhook_url


def test_mask_webhook_url_hooks_slack() -> None:
    """Slack webhook URL is masked for logging."""
    url = "https://hooks.slack.com/services/T00/B00/xxx"
    assert "hooks.slack.com" in _mask_webhook_url(url)
    assert "xxx" not in _mask_webhook_url(url)


def test_mask_webhook_url_short() -> None:
    """Short or empty URL returns safe placeholder."""
    assert _mask_webhook_url("") == "..."
    assert _mask_webhook_url("x") == "..."


def test_send_slack_digest_empty_webhook_returns_false() -> None:
    """Empty webhook URL returns False without making request."""
    ok = send_slack_digest(
        webhook_url="",
        tenant_name="Acme",
        payload={"open_action_count": 0, "new_findings_count_7d": 0, "exceptions_expiring_14d_count": 0},
    )
    assert ok is False


def test_send_slack_digest_posts_blocks_and_returns_true() -> None:
    """send_slack_digest POSTs JSON with blocks and returns True on 200."""
    payload = {
        "open_action_count": 2,
        "new_findings_count_7d": 1,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    captured = {}

    class FakeResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["data"] = req.data
        captured["headers"] = dict(req.headers)
        return FakeResponse()

    with patch("backend.services.slack_digest.urllib.request.urlopen", side_effect=fake_urlopen):
        ok = send_slack_digest(
            webhook_url="https://hooks.slack.com/services/T00/B00/secret",
            tenant_name="Acme Corp",
            payload=payload,
            frontend_url="https://app.example.com",
        )

    assert ok is True
    assert "blocks" in json.loads(captured["data"].decode("utf-8"))
    ct = captured["headers"].get("Content-Type") or captured["headers"].get("Content-type")
    assert ct == "application/json"
    body = json.loads(captured["data"].decode("utf-8"))
    assert "Weekly digest" in str(body["blocks"][0].get("text", {}).get("text", ""))


def test_send_slack_digest_http_error_returns_false() -> None:
    """HTTPError from Slack returns False."""
    import urllib.error

    def raise_http_error(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://hooks.slack.com/x",
            400,
            "Bad Request",
            {},
            None,
        )

    with patch("backend.services.slack_digest.urllib.request.urlopen", side_effect=raise_http_error):
        ok = send_slack_digest(
            webhook_url="https://hooks.slack.com/services/T00/B00/x",
            tenant_name="Acme",
            payload={"open_action_count": 0, "new_findings_count_7d": 0, "exceptions_expiring_14d_count": 0},
        )
    assert ok is False
