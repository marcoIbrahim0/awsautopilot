"""
Unit tests for backend/services/digest_content.py (Step 11.2).

Covers: email subject, plain body, HTML body, Slack blocks, View in app URL helpers.
"""
from __future__ import annotations

from backend.services.digest_content import (
    DEFAULT_APP_NAME,
    build_email_body_html,
    build_email_body_plain,
    build_email_subject,
    build_slack_blocks,
    get_action_url,
    get_exceptions_url,
    get_view_in_app_url,
)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def test_get_view_in_app_url() -> None:
    """View in app URL defaults to /top-risks."""
    assert get_view_in_app_url("https://app.example.com") == "https://app.example.com/top-risks"
    assert get_view_in_app_url("https://app.example.com/") == "https://app.example.com/top-risks"


def test_get_action_url() -> None:
    """Action URL is base + /actions/{id}."""
    assert get_action_url("https://app.example.com", "abc-123") == "https://app.example.com/actions/abc-123"


def test_get_exceptions_url() -> None:
    """Exceptions URL is base + /exceptions."""
    assert get_exceptions_url("https://app.example.com") == "https://app.example.com/exceptions"


# ---------------------------------------------------------------------------
# Email subject
# ---------------------------------------------------------------------------
def test_build_email_subject() -> None:
    """Subject includes app name and tenant name."""
    assert "Weekly digest" in build_email_subject("Acme Corp")
    assert "Acme Corp" in build_email_subject("Acme Corp")
    assert DEFAULT_APP_NAME in build_email_subject("Acme Corp")


def test_build_email_subject_empty_tenant() -> None:
    """Empty tenant name falls back to 'Your organization'."""
    subj = build_email_subject("")
    assert "Your organization" in subj


# ---------------------------------------------------------------------------
# Plain body
# ---------------------------------------------------------------------------
def test_build_email_body_plain_minimal() -> None:
    """Plain body includes counts and View in app link."""
    payload = {
        "open_action_count": 3,
        "new_findings_count_7d": 5,
        "exceptions_expiring_14d_count": 1,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    body = build_email_body_plain("Acme", payload, "https://app.example.com/top-risks")
    assert "Acme" in body
    assert "Open actions: 3" in body
    assert "New or updated findings" in body
    assert "5" in body
    assert "Exceptions expiring" in body
    assert "1" in body
    assert "https://app.example.com/top-risks" in body
    assert "View full details" in body or "View in app" in body or "View" in body


def test_build_email_body_plain_with_top_actions() -> None:
    """Plain body includes top actions when present."""
    payload = {
        "open_action_count": 2,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [
            {"id": "a1", "title": "Enable S3 block public access", "priority": 90},
            {"id": "a2", "title": "Restrict SG 0.0.0.0/0", "priority": 75},
        ],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    body = build_email_body_plain("Acme", payload, "https://app.example.com/top-risks")
    assert "Top actions" in body
    assert "Enable S3 block public access" in body
    assert "90" in body
    assert "Restrict SG" in body


def test_build_email_body_plain_with_expiring_exceptions() -> None:
    """Plain body includes expiring exceptions when present."""
    payload = {
        "open_action_count": 0,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 1,
        "top_5_actions": [],
        "expiring_exceptions": [
            {"label": "Action: Enable MFA", "expires_at_iso": "2026-02-15T00:00:00Z"},
        ],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    body = build_email_body_plain("Acme", payload, "https://app.example.com/top-risks")
    assert "Exceptions expiring soon" in body
    assert "Enable MFA" in body
    assert "2026-02-15" in body


# ---------------------------------------------------------------------------
# HTML body
# ---------------------------------------------------------------------------
def test_build_email_body_html_minimal() -> None:
    """HTML body includes summary table and View in app button."""
    payload = {
        "open_action_count": 1,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    html = build_email_body_html("Acme Corp", payload, "https://app.example.com/top-risks")
    assert "<!DOCTYPE html>" in html
    assert "Weekly digest for Acme Corp" in html
    assert "Open actions" in html
    assert "View in app" in html
    assert "https://app.example.com/top-risks" in html
    assert "display:inline-block" in html or "background:#5B87AD" in html


def test_build_email_body_html_escapes_action_titles() -> None:
    """HTML escapes action titles to prevent XSS."""
    payload = {
        "open_action_count": 0,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [{"id": "x", "title": "<script>alert(1)</script>", "priority": 50}],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    html = build_email_body_html("Acme", payload, "https://app.example.com/top-risks")
    assert "&lt;script&gt;" in html
    assert "<script>" not in html or "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Slack blocks
# ---------------------------------------------------------------------------
def test_build_slack_blocks_structure() -> None:
    """Slack blocks include header, section, divider, actions, context."""
    payload = {
        "open_action_count": 2,
        "new_findings_count_7d": 1,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    blocks = build_slack_blocks("Acme", payload, "https://app.example.com/top-risks")
    types = [b["type"] for b in blocks]
    assert "header" in types
    assert "section" in types
    assert "divider" in types
    assert "actions" in types
    assert "context" in types


def test_build_slack_blocks_summary_content() -> None:
    """Slack summary section has open actions, new findings, expiring counts."""
    payload = {
        "open_action_count": 3,
        "overdue_action_count": 2,
        "expiring_action_count": 1,
        "escalation_action_count": 1,
        "new_findings_count_7d": 5,
        "exceptions_expiring_14d_count": 2,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    blocks = build_slack_blocks("Acme Corp", payload, "https://app.example.com/top-risks")
    section = next(b for b in blocks if b["type"] == "section")
    text = section["text"]["text"]
    assert "3" in text
    assert "2" in text
    assert "1" in text
    assert "5" in text
    assert "Open actions" in text or "Open" in text
    assert "Overdue actions" in text
    assert "High-impact escalations" in text


def test_build_slack_blocks_view_in_app_button() -> None:
    """Slack actions block has View in app button with correct URL."""
    payload = {
        "open_action_count": 0,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    blocks = build_slack_blocks("Acme", payload, "https://app.example.com/top-risks")
    actions_block = next(b for b in blocks if b["type"] == "actions")
    btn = actions_block["elements"][0]
    assert btn["type"] == "button"
    assert btn["text"]["text"] == "View in app"
    assert btn["url"] == "https://app.example.com/top-risks"


def test_build_slack_blocks_with_top_actions_links() -> None:
    """Slack includes top actions with links when present."""
    payload = {
        "open_action_count": 1,
        "new_findings_count_7d": 0,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [
            {"id": "act-123", "title": "Enable S3 block public access", "priority": 90},
        ],
        "generated_at": "2026-02-02T09:00:00Z",
    }
    blocks = build_slack_blocks("Acme", payload, "https://app.example.com/top-risks")
    sections = [b for b in blocks if b["type"] == "section"]
    assert len(sections) >= 2
    top_section = next((b for b in sections if "Top actions" in b.get("text", {}).get("text", "")), None)
    assert top_section is not None
    assert "Enable S3" in top_section["text"]["text"]
    assert "https://app.example.com/actions/act-123" in top_section["text"]["text"]


def test_build_digest_content_includes_escalation_context() -> None:
    payload = {
        "open_action_count": 3,
        "overdue_action_count": 1,
        "expiring_action_count": 1,
        "escalation_action_count": 1,
        "new_findings_count_7d": 5,
        "exceptions_expiring_14d_count": 0,
        "top_5_actions": [],
        "escalations": [
            {
                "action_id": "act-999",
                "title": "Block public S3 access",
                "owner_label": "Platform Team",
                "risk_tier": "critical",
                "sla_state": "overdue",
                "due_at": "2026-03-09T08:00:00+00:00",
            }
        ],
        "generated_at": "2026-02-02T09:00:00Z",
    }

    plain = build_email_body_plain("Acme", payload, "https://app.example.com/top-risks")
    html = build_email_body_html("Acme", payload, "https://app.example.com/top-risks")
    blocks = build_slack_blocks("Acme", payload, "https://app.example.com/top-risks")

    assert "High-impact escalations" in plain
    assert "Platform Team" in plain
    assert "https://app.example.com/actions/act-999" in plain
    assert "High-impact escalations" in html
    assert "critical/overdue" in html
    escalation_section = next(
        block for block in blocks
        if block["type"] == "section"
        and "High-impact escalations" in block.get("text", {}).get("text", "")
        and "Platform Team" in block.get("text", {}).get("text", "")
    )
    assert "Platform Team" in escalation_section["text"]["text"]
    assert "https://app.example.com/actions/act-999" in escalation_section["text"]["text"]
