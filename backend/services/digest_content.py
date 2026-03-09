"""
Weekly digest content (Step 11.2).

Builds email subject/body (plain + HTML) and Slack Block Kit blocks from the
digest payload. Used by 11.3 (email) and 11.4 (Slack). Single source of truth
for subject line, body copy, and "View in app" link.
"""
from __future__ import annotations

from typing import Any

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
    title = (item.get("title") or "Action").replace("<", "&lt;").replace(">", "&gt;")[:80]
    risk_tier = (item.get("risk_tier") or "unknown").replace("<", "&lt;").replace(">", "&gt;")
    sla_state = (item.get("sla_state") or "state_unknown").replace("<", "&lt;").replace(">", "&gt;")
    owner = (item.get("owner_label") or "Unassigned").replace("<", "&lt;").replace(">", "&gt;")[:60]
    due_at = (item.get("due_at") or "unknown").replace("<", "&lt;").replace(">", "&gt;")
    action_id = item.get("action_id")
    if action_id:
        action_link = get_action_url(_base_from_view_url(view_in_app_url), action_id)
        title = f'<a href="{action_link}" style="color:#5B87AD;">{title}</a>'
    return f'<li style="margin-bottom:6px;color:#C7D0D8;">{title} — {risk_tier}/{sla_state} — owner {owner} — due {due_at}</li>'


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
    """HTML email body: same content as plain, with minimal inline styles for email clients."""
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

    rows_html = "".join(
        f'<tr><td style="padding:6px 12px 6px 0;color:#8F9BA6;">{label}</td>'
        f'<td style="padding:6px 0;color:#C7D0D8;font-weight:600;">{val}</td></tr>'
        for label, val in summary_rows
    )

    top_actions_html = ""
    if top_actions:
        items = []
        for a in top_actions[:5]:
            title = (a.get("title") or "Action").replace("<", "&lt;").replace(">", "&gt;")[:60]
            priority = a.get("priority", 0)
            action_id = a.get("id")
            if action_id:
                action_link = f"{_base_from_view_url(view_in_app_url)}/actions/{action_id}"
                items.append(
                    f'<li style="margin-bottom:6px;">'
                    f'<a href="{action_link}" style="color:#5B87AD;">{title}</a> '
                    f'<span style="color:#8F9BA6;">(priority {priority})</span></li>'
                )
            else:
                items.append(f'<li style="margin-bottom:6px;color:#C7D0D8;">{title} (priority {priority})</li>')
        top_actions_html = (
            '<p style="color:#8F9BA6;margin:16px 0 8px;">Top actions by priority</p>'
            f'<ul style="margin:0 0 16px;padding-left:20px;color:#C7D0D8;">{"".join(items)}</ul>'
        )

    expiring_html = ""
    if expiring_list:
        items = []
        for e in expiring_list[:10]:
            label = (e.get("label") or "Exception").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")[:80]
            expiry = e.get("expires_at_iso") or e.get("expires_at", "")
            items.append(f'<li style="margin-bottom:4px;color:#C7D0D8;">{label} — expires {expiry}</li>')
        expiring_html = (
            '<p style="color:#8F9BA6;margin:16px 0 8px;">Exceptions expiring soon</p>'
            f'<ul style="margin:0 0 16px;padding-left:20px;">{"".join(items)}</ul>'
        )

    escalations_html = ""
    if escalations:
        items = [_escalation_html_line(view_in_app_url, item) for item in escalations[:5]]
        escalations_html = (
            '<p style="color:#8F9BA6;margin:16px 0 8px;">High-impact escalations</p>'
            f'<ul style="margin:0 0 16px;padding-left:20px;">{"".join(items)}</ul>'
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1419;color:#C7D0D8;margin:0;padding:24px;">
<div style="max-width:560px;margin:0 auto;background:#151b23;border-radius:12px;padding:32px;border:1px solid #1f2a35;">
  <h1 style="color:#C7D0D8;font-size:20px;margin:0 0 20px;">Weekly digest for {name}</h1>
  <p style="color:#8F9BA6;line-height:1.5;margin:0 0 20px;">Here’s your weekly security summary.</p>
  <table style="border-collapse:collapse;margin:0 0 20px;">{rows_html}</table>
  {top_actions_html}
  {expiring_html}
  {escalations_html}
  <p style="margin:24px 0 16px;"><a href="{view_in_app_url}" style="display:inline-block;background:#5B87AD;color:#0f1419;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">View in app</a></p>
  <p style="font-size:12px;color:#8F9BA6;margin:24px 0 0;padding-top:16px;border-top:1px solid #1f2a35;">— {app_name}</p>
</div>
</body>
</html>"""


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
