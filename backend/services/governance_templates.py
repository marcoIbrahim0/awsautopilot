"""Template rendering for governance communication stages."""
from __future__ import annotations

from html import escape
from typing import Any

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
    safe_details = escape(details)
    safe_target = escape(target)
    safe_tenant = escape(tenant)
    cta_url = (action_url or "").strip()
    escalation = escalation_context if isinstance(escalation_context, dict) else None

    subject = f"[{prefix}] {safe_tenant}: {safe_target}"
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

    html_parts = [
        f"<h2>{escape(prefix)}</h2>",
        f"<p><strong>Tenant:</strong> {safe_tenant}</p>",
        f"<p><strong>Target:</strong> {safe_target}</p>",
        f"<p>{safe_details}</p>",
    ]
    if escalation:
        html_parts.append(
            "<p><strong>Escalation context</strong><br>"
            f"Risk tier: {escape(str(escalation.get('risk_tier') or 'unknown'))}<br>"
            f"SLA state: {escape(str(escalation.get('sla_state') or 'unknown'))}<br>"
            f"Owner: {escape(str(escalation.get('owner_label') or 'Unassigned'))}<br>"
            f"Due at: {escape(str(escalation.get('due_at') or 'unknown'))}<br>"
            f"Reason: {escape(str(escalation.get('escalation_reason') or 'No escalation reason provided.'))}</p>"
        )
    if cta_url:
        safe_url = escape(cta_url)
        html_parts.append(f'<p><a href="{safe_url}">Open in app</a></p>')

    return {
        "subject": subject,
        "text": "\n".join(text_lines),
        "html": "\n".join(html_parts),
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
