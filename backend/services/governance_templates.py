"""Template rendering for governance communication stages."""
from __future__ import annotations

from typing import Any

from backend.services.email_templates import (
    build_email_html_document,
    escape_html,
    render_html_fact_table,
    render_html_paragraphs,
    render_html_rich_list,
    render_html_section,
)

GOVERNANCE_STAGES = {
    "pre_change",
    "in_progress",
    "action_required",
    "completion",
}

_STAGE_TITLES = {
    "pre_change": "Pre-change",
    "in_progress": "In progress",
    "action_required": "Action required",
    "completion": "Completion",
}


def _normalize(value: str | None, fallback: str) -> str:
    text = (value or "").strip()
    return text or fallback


def _stage_prefix(stage: str) -> str:
    if stage not in GOVERNANCE_STAGES:
        raise ValueError(f"unsupported_stage:{stage}")
    return _STAGE_TITLES[stage]


def render_governance_template(
    *,
    stage: str,
    tenant_name: str,
    target_label: str,
    detail: str | None = None,
    action_url: str | None = None,
    escalation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render email/in-app/webhook-safe payload text for one governance stage."""
    prefix = _stage_prefix(stage)
    tenant = _normalize(tenant_name, "Tenant")
    target = _normalize(target_label, "Governance item")
    details = _normalize(detail, "No additional detail provided.")
    cta_url = (action_url or "").strip()
    escalation = escalation_context if isinstance(escalation_context, dict) else None

    subject = f"[{prefix}] {escape_html(tenant)}: {escape_html(target)}"
    text_lines = [subject, "", details]
    if escalation:
        risk_tier = _normalize(str(escalation.get("risk_tier")), "unknown")
        sla_state = _normalize(str(escalation.get("sla_state")), "unknown")
        owner_label = _normalize(str(escalation.get("owner_label")), "Unassigned")
        due_at = _normalize(str(escalation.get("due_at")), "unknown")
        escalation_reason = _normalize(str(escalation.get("escalation_reason")), "No escalation reason provided.")
        text_lines.extend(
            [
                "",
                "Escalation context",
                f"- Risk tier: {risk_tier}",
                f"- SLA state: {sla_state}",
                f"- Owner: {owner_label}",
                f"- Due at: {due_at}",
                f"- Reason: {escalation_reason}",
            ]
        )
    if cta_url:
        text_lines.extend(["", f"Open in app: {cta_url}"])

    sections_html = [
        render_html_section(
            "Governance item details",
            render_html_fact_table([("Tenant", tenant), ("Target", target)]),
        )
    ]
    if escalation:
        sections_html.append(
            render_html_section(
                "Escalation context",
                render_html_rich_list(
                    [
                        f"Risk tier: {escape_html(escalation.get('risk_tier') or 'unknown')}",
                        f"SLA state: {escape_html(escalation.get('sla_state') or 'unknown')}",
                        f"Owner: {escape_html(escalation.get('owner_label') or 'Unassigned')}",
                        f"Due at: {escape_html(escalation.get('due_at') or 'unknown')}",
                        f"Reason: {escape_html(escalation.get('escalation_reason') or 'No escalation reason provided.')}",
                    ]
                ),
            )
        )
    if cta_url:
        sections_html.append(
            render_html_section(
                "Direct link",
                f'<a href="{escape_html(cta_url)}" style="color:#0d63c8;">{escape_html(cta_url)}</a>',
            )
        )

    html_body = build_email_html_document(
        title=f"{prefix}: {target}",
        intro_html=render_html_paragraphs([details]),
        sections_html=sections_html,
        cta_label="Open in app" if cta_url else None,
        cta_url=cta_url or None,
        preheader=f"{prefix} notification for {target}.",
    )

    return {
        "subject": subject,
        "text": "\n".join(text_lines),
        "html": html_body,
        "title": f"{prefix}: {target}",
        "message": details,
        "webhook": {
            "stage": stage,
            "tenant": tenant,
            "target": target,
            "detail": details,
            "action_url": cta_url,
            "escalation": escalation,
        },
    }
