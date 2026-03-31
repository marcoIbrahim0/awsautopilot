"""
Weekly digest content (Step 11.2).

Builds email subject/body (plain + HTML) and Slack Block Kit blocks from the
digest payload. Used by 11.3 (email) and 11.4 (Slack). Single source of truth
for subject line, body copy, and "View in app" link.
"""
from __future__ import annotations

from typing import Any

from backend.services.email_templates import (
    build_email_html_document,
    escape_html,
    render_html_link_box,
    render_html_paragraphs,
    render_html_rich_list,
    render_html_section,
    render_html_stat_grid,
)

# Default app name for subject and footer
DEFAULT_APP_NAME = "AWS Security Autopilot"

# Payload keys (must match worker/jobs/weekly_digest.build_digest_payload)
KEY_OPEN_ACTION_COUNT = "open_action_count"
KEY_OVERDUE_ACTION_COUNT = "overdue_action_count"
KEY_EXPIRING_ACTION_COUNT = "expiring_action_count"
KEY_ESCALATION_ACTION_COUNT = "escalation_action_count"
KEY_NEW_FINDINGS_7D = "new_findings_count_7d"
KEY_EXCEPTIONS_EXPIRING_14D = "exceptions_expiring_14d_count"
KEY_TOP_ACTIONS = "top_5_actions"
KEY_ESCALATIONS = "escalations"
KEY_EXPIRING_EXCEPTIONS = "expiring_exceptions"
KEY_GENERATED_AT = "generated_at"


def _view_in_app_base(frontend_url: str, path: str = "/top-risks") -> str:
    """Base URL for 'View in app' and action/exception links. No trailing slash."""
    base = (frontend_url or "").rstrip("/")
    return f"{base}{path}" if path.startswith("/") else f"{base}/{path}"


def get_view_in_app_url(frontend_url: str, path: str = "/top-risks") -> str:
    """Canonical 'View in app' URL (Top Risks page)."""
    return _view_in_app_base(frontend_url, path)


def get_action_url(frontend_url: str, action_id: str) -> str:
    """URL to a single action in the app."""
    return _view_in_app_base(frontend_url, f"/actions/{action_id}")


def get_exceptions_url(frontend_url: str) -> str:
    """URL to exceptions page."""
    return _view_in_app_base(frontend_url, "/exceptions")


def _base_from_view_url(view_in_app_url: str) -> str:
    """Derive app base URL from the 'View in app' URL (e.g. https://app.example.com/top-risks -> https://app.example.com)."""
    u = (view_in_app_url or "").rstrip("/")
    if "/" in u.replace("://", ""):
        return u.rsplit("/", 1)[0]
    return u


def _escalation_plain_line(view_in_app_url: str, item: dict[str, Any]) -> str:
    risk_tier = (item.get("risk_tier") or "unknown").upper()
    sla_state = item.get("sla_state") or "state_unknown"
    title = (item.get("title") or "Action").replace("\n", " ")[:80]
    owner = (item.get("owner_label") or "Unassigned").replace("\n", " ")[:60]
    due_at = item.get("due_at") or "unknown"
    action_id = item.get("action_id")
    action_url = get_action_url(_base_from_view_url(view_in_app_url), action_id) if action_id else None
    suffix = f" — {action_url}" if action_url else ""
    return f"• [{risk_tier}/{sla_state}] {title} — owner {owner} — due {due_at}{suffix}"


def _escalation_html_line(view_in_app_url: str, item: dict[str, Any]) -> str:
    title = escape_html((item.get("title") or "Action")[:80])
    risk_tier = escape_html(item.get("risk_tier") or "unknown")
    sla_state = escape_html(item.get("sla_state") or "state_unknown")
    owner = escape_html((item.get("owner_label") or "Unassigned")[:60])
    due_at = escape_html(item.get("due_at") or "unknown")
    action_id = item.get("action_id")
    if action_id:
        action_link = get_action_url(_base_from_view_url(view_in_app_url), action_id)
        title = f'<a href="{escape_html(action_link)}" style="color:#0d63c8;">{title}</a>'
    return f"{title} — {risk_tier}/{sla_state} — owner {owner} — due {due_at}"


def _escalation_slack_line(view_in_app_url: str, item: dict[str, Any]) -> str:
    title = (item.get("title") or "Action").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:80]
    risk_tier = (item.get("risk_tier") or "unknown").upper()
    sla_state = item.get("sla_state") or "state_unknown"
    owner = (item.get("owner_label") or "Unassigned").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:60]
    due_at = item.get("due_at") or "unknown"
    action_id = item.get("action_id")
    if action_id:
        action_url = get_action_url(_base_from_view_url(view_in_app_url), action_id)
        title = f"<{action_url}|{title}>"
    return f"• {title} — {risk_tier}/{sla_state} — owner {owner} — due {due_at}"


def build_email_subject(
    tenant_name: str,
    app_name: str = DEFAULT_APP_NAME,
) -> str:
    """Email subject line: e.g. 'AWS Security Autopilot – Weekly digest for Acme Corp'."""
    name = (tenant_name or "Your organization").strip()
    return f"{app_name} – Weekly digest for {name}"


def build_email_body_plain(
    tenant_name: str,
    payload: dict[str, Any],
    view_in_app_url: str,
    app_name: str = DEFAULT_APP_NAME,
) -> str:
    """Plain-text email body: counts, optional top actions and expiring exceptions, View in app link."""
    open_count = payload.get(KEY_OPEN_ACTION_COUNT, 0) or 0
    overdue_count = payload.get(KEY_OVERDUE_ACTION_COUNT, 0) or 0
    expiring_action_count = payload.get(KEY_EXPIRING_ACTION_COUNT, 0) or 0
    escalation_count = payload.get(KEY_ESCALATION_ACTION_COUNT, 0) or 0
    new_findings = payload.get(KEY_NEW_FINDINGS_7D, 0) or 0
    expiring_count = payload.get(KEY_EXCEPTIONS_EXPIRING_14D, 0) or 0
    top_actions = payload.get(KEY_TOP_ACTIONS) or []
    escalations = payload.get(KEY_ESCALATIONS) or []
    expiring_list = payload.get(KEY_EXPIRING_EXCEPTIONS) or []

    lines = [
        f"Hi, here’s your weekly security digest for {(tenant_name or 'your organization').strip()}.",
        "",
        "Summary",
        "-------",
        f"• Open actions: {open_count}",
        f"• Actions nearing SLA due time: {expiring_action_count}",
        f"• Overdue actions: {overdue_count}",
        f"• High-impact escalations: {escalation_count}",
        f"• New or updated findings (last 7 days): {new_findings}",
        f"• Exceptions expiring in the next 14 days: {expiring_count}",
        "",
    ]

    if top_actions:
        lines.append("Top actions by priority")
        lines.append("------------------------")
        for a in top_actions[:5]:
            title = (a.get("title") or "Action")[:60]
            priority = a.get("priority", 0)
            lines.append(f"• [{priority}] {title}")
        lines.append("")

    if expiring_list:
        lines.append("Exceptions expiring soon")
        lines.append("------------------------")
        for e in expiring_list[:10]:
            label = (e.get("label") or "Exception").replace("\n", " ")
            expiry = e.get("expires_at_iso") or e.get("expires_at", "")
            lines.append(f"• {label} (expires {expiry})")
        lines.append("")

    if escalations:
        lines.append("High-impact escalations")
        lines.append("-----------------------")
        for item in escalations[:5]:
            lines.append(_escalation_plain_line(view_in_app_url, item))
        lines.append("")

    lines.extend([
        "View full details and take action in the app:",
        view_in_app_url,
        "",
        f"— {app_name}",
    ])
    return "\n".join(lines)


def build_email_body_html(
    tenant_name: str,
    payload: dict[str, Any],
    view_in_app_url: str,
    app_name: str = DEFAULT_APP_NAME,
) -> str:
    """HTML email body: same content as plain, rendered through the shared branded shell."""
    open_count = payload.get(KEY_OPEN_ACTION_COUNT, 0) or 0
    overdue_count = payload.get(KEY_OVERDUE_ACTION_COUNT, 0) or 0
    expiring_action_count = payload.get(KEY_EXPIRING_ACTION_COUNT, 0) or 0
    escalation_count = payload.get(KEY_ESCALATION_ACTION_COUNT, 0) or 0
    new_findings = payload.get(KEY_NEW_FINDINGS_7D, 0) or 0
    expiring_count = payload.get(KEY_EXCEPTIONS_EXPIRING_14D, 0) or 0
    top_actions = payload.get(KEY_TOP_ACTIONS) or []
    escalations = payload.get(KEY_ESCALATIONS) or []
    expiring_list = payload.get(KEY_EXPIRING_EXCEPTIONS) or []

    name = (tenant_name or "your organization").strip()
    summary_rows = [
        ("Open actions", open_count),
        ("Actions nearing SLA due time", expiring_action_count),
        ("Overdue actions", overdue_count),
        ("High-impact escalations", escalation_count),
        ("New or updated findings (last 7 days)", new_findings),
        ("Exceptions expiring in the next 14 days", expiring_count),
    ]
    sections_html = [render_html_section("Summary", render_html_stat_grid(summary_rows))]
    if top_actions:
        items = []
        for a in top_actions[:5]:
            title = escape_html((a.get("title") or "Action")[:60])
            priority = a.get("priority", 0)
            action_id = a.get("id")
            if action_id:
                action_link = f"{_base_from_view_url(view_in_app_url)}/actions/{action_id}"
                items.append(
                    f'<a href="{escape_html(action_link)}" style="color:#0d63c8;">{title}</a> '
                    f'<span style="color:#6a7a8f;">(priority {escape_html(priority)})</span>'
                )
            else:
                items.append(f"{title} <span style=\"color:#6a7a8f;\">(priority {escape_html(priority)})</span>")
        sections_html.append(
            render_html_section("Top actions by priority", render_html_rich_list(items))
        )
    if expiring_list:
        items = []
        for e in expiring_list[:10]:
            label = escape_html((e.get("label") or "Exception").replace("\n", " ")[:80])
            expiry = escape_html(e.get("expires_at_iso") or e.get("expires_at", ""))
            items.append(f"{label} — expires {expiry}")
        sections_html.append(
            render_html_section("Exceptions expiring soon", render_html_rich_list(items))
        )
    if escalations:
        sections_html.append(
            render_html_section(
                "High-impact escalations",
                render_html_rich_list([_escalation_html_line(view_in_app_url, item) for item in escalations[:5]]),
            )
        )
    sections_html.append(render_html_section("Direct link", render_html_link_box(view_in_app_url)))
    return build_email_html_document(
        title=f"Weekly digest for {name}",
        intro_html=render_html_paragraphs(
            [
                f"Here’s your weekly security digest for {name}.",
                "Review prioritized actions, exceptions that need attention, and high-impact escalations in the app.",
            ]
        ),
        sections_html=sections_html,
        cta_label="View in app",
        cta_url=view_in_app_url,
        footer_html=f'<p style="margin:0;color:#6a7a8f;line-height:1.6;">{escape_html(app_name)} · Weekly digest</p>',
        preheader=f"{open_count} open actions, {overdue_count} overdue, {escalation_count} escalations.",
    )


def build_slack_blocks(
    tenant_name: str,
    payload: dict[str, Any],
    view_in_app_url: str,
    app_name: str = DEFAULT_APP_NAME,
) -> list[dict[str, Any]]:
    """
    Slack Block Kit blocks for the digest message.
    Structure: header, summary section, optional top actions, optional expiring exceptions, divider, View in app button.
    """
    open_count = payload.get(KEY_OPEN_ACTION_COUNT, 0) or 0
    overdue_count = payload.get(KEY_OVERDUE_ACTION_COUNT, 0) or 0
    expiring_action_count = payload.get(KEY_EXPIRING_ACTION_COUNT, 0) or 0
    escalation_count = payload.get(KEY_ESCALATION_ACTION_COUNT, 0) or 0
    new_findings = payload.get(KEY_NEW_FINDINGS_7D, 0) or 0
    expiring_count = payload.get(KEY_EXCEPTIONS_EXPIRING_14D, 0) or 0
    top_actions = payload.get(KEY_TOP_ACTIONS) or []
    escalations = payload.get(KEY_ESCALATIONS) or []
    expiring_list = payload.get(KEY_EXPIRING_EXCEPTIONS) or []

    name = (tenant_name or "Your organization").strip()

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Weekly digest — {name}", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"• *Open actions:* {open_count}\n"
                    f"• *Actions nearing SLA:* {expiring_action_count}\n"
                    f"• *Overdue actions:* {overdue_count}\n"
                    f"• *High-impact escalations:* {escalation_count}\n"
                    f"• *New/updated findings (7d):* {new_findings}\n"
                    f"• *Exceptions expiring (14d):* {expiring_count}"
                ),
            },
        },
    ]

    if top_actions:
        lines = []
        for a in top_actions[:5]:
            title = (a.get("title") or "Action").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:80]
            priority = a.get("priority", 0)
            action_id = a.get("id")
            if action_id:
                action_link = f"{_base_from_view_url(view_in_app_url)}/actions/{action_id}"
                lines.append(f"• <{action_link}|{title}> (priority {priority})")
            else:
                lines.append(f"• {title} (priority {priority})")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Top actions*\n" + "\n".join(lines)},
        })

    if expiring_list:
        lines = []
        for e in expiring_list[:10]:
            label = (e.get("label") or "Exception").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:80]
            expiry = e.get("expires_at_iso") or e.get("expires_at", "")
            lines.append(f"• {label} — expires {expiry}")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Exceptions expiring soon*\n" + "\n".join(lines)},
        })

    if escalations:
        lines = [_escalation_slack_line(view_in_app_url, item) for item in escalations[:5]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*High-impact escalations*\n" + "\n".join(lines)},
        })

    blocks.extend([
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View in app", "emoji": True},
                    "url": view_in_app_url,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{app_name} · Weekly digest"}],
        },
    ])
    return blocks
