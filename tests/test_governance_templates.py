from __future__ import annotations

import pytest

from backend.services.governance_templates import render_governance_template


def test_render_template_pre_change() -> None:
    rendered = render_governance_template(
        stage="pre_change",
        tenant_name="Tenant A",
        target_label="Run 123",
        detail="Change will start soon.",
        action_url=None,
    )
    assert "Pre-change" in rendered["subject"]
    assert "Change will start soon." in rendered["text"]
    webhook_payload = rendered["webhook"]
    assert isinstance(webhook_payload, dict)
    assert webhook_payload["stage"] == "pre_change"


def test_render_template_action_required_with_url() -> None:
    rendered = render_governance_template(
        stage="action_required",
        tenant_name="Tenant B",
        target_label="Exception X",
        detail="Owner approval is required.",
        action_url="https://app.example.com/exceptions",
    )
    assert "Action required" in rendered["subject"]
    assert "Open in app" in rendered["text"]
    assert "https://app.example.com/exceptions" in rendered["html"]


def test_render_template_invalid_stage() -> None:
    with pytest.raises(ValueError):
        render_governance_template(
            stage="not_valid",
            tenant_name="Tenant",
            target_label="Target",
        )
