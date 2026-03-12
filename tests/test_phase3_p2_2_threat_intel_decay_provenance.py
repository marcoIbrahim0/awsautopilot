"""Phase 3 P2.2 threat-intel decay and provenance regression coverage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.config import settings
from backend.routers.actions import _action_to_detail_response
from backend.services.action_scoring import score_action_finding


def _finding(
    *,
    control_id: str = "TEST.1",
    severity_normalized: int = 0,
    severity_label: str = "LOW",
    title: str = "Package requires review",
    description: str = "Neutral finding text without exploit keywords.",
    raw_json: dict | None = None,
) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        finding_id=f"finding-{uuid.uuid4()}",
        control_id=control_id,
        severity_normalized=severity_normalized,
        severity_label=severity_label,
        title=title,
        description=description,
        resource_id="resource-1",
        resource_type="AwsTestResource",
        raw_json=raw_json or {},
        account_id="123456789012",
        region="us-east-1",
        owner_type="unassigned",
        owner_key="unassigned",
        owner_label="Unassigned",
        sh_updated_at=observed_at,
        last_observed_at=observed_at,
        updated_at=observed_at,
        created_at=observed_at,
    )


def _threat_finding(*entries: dict[str, object], control_id: str = "TEST.1") -> SimpleNamespace:
    return _finding(
        control_id=control_id,
        raw_json={
            "Vulnerabilities": [
                {
                    "Id": "CVE-2026-0001",
                    "ThreatIntel": list(entries),
                }
            ]
        },
    )


def _action_from_score(score: SimpleNamespace, finding: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type="pr_only",
        target_id="target-1",
        account_id=finding.account_id,
        region=finding.region,
        score=score.score,
        score_components=score.components,
        priority=score.score,
        status="open",
        title=finding.title,
        description=finding.description,
        control_id=finding.control_id,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        owner_type=finding.owner_type,
        owner_key=finding.owner_key,
        owner_label=finding.owner_label,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def test_threat_intel_decay_follows_configurable_half_life(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS", 24.0)
    finding = _threat_finding(
        {
            "source": "cisa_kev",
            "confidence": 1.0,
            "timestamp": "2026-03-11T12:00:00Z",
        }
    )

    score = score_action_finding(finding, now=datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc))
    signal = score.components["exploit_signals"]["applied_threat_signals"][0]

    assert score.components["exploit_signals"]["threat_intel_points_requested"] == 5
    assert score.components["exploit_signals"]["threat_intel_points_applied"] == 5
    assert signal["decay_applied"] == 0.5
    assert signal["applied_points"] == 5


def test_zero_point_decay_keeps_provenance_visible_in_explainability(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS", 24.0)
    finding = _threat_finding(
        {
            "source": "cisa_kev",
            "confidence": 1.0,
            "timestamp": "2026-03-01T12:00:00Z",
        }
    )

    score = score_action_finding(finding, now=datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc))
    action = _action_from_score(score, finding)
    response = _action_to_detail_response(action)
    factor = next(item for item in response.score_factors if item.factor_name == "exploit_signals")

    assert score.score == 0
    assert score.components["exploit_signals"]["threat_intel_points_applied"] == 0
    assert factor.provenance
    assert factor.provenance[0].final_contribution == 0
    assert factor.provenance[0].decay_applied < 0.01
    assert "reduced the current threat-intel contribution to 0 points" in factor.explanation


def test_explainability_payload_exposes_decay_provenance_fields(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS", 72.0)
    finding = _threat_finding(
        {
            "source": "cisa_kev",
            "confidence": 1.0,
            "timestamp": "2026-03-12T09:30:00Z",
        }
    )

    score = score_action_finding(finding, now=datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc))
    action = _action_from_score(score, finding)
    response = _action_to_detail_response(action)
    factor = next(item for item in response.score_factors if item.factor_name == "exploit_signals")
    provenance = factor.provenance[0]

    assert response.score == score.score
    assert sum(item.contribution for item in response.score_factors) == response.score
    assert provenance.source == "cisa_kev"
    assert provenance.observed_at == "2026-03-12T09:30:00+00:00"
    assert provenance.decay_applied == 0.9762
    assert provenance.base_contribution == 10
    assert provenance.final_contribution == 10


def test_multiple_threat_intel_signals_remain_bounded_and_non_negative(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS", 72.0)
    finding = _threat_finding(
        {
            "source": "cisa_kev",
            "confidence": 1.0,
            "timestamp": "2026-03-12T11:00:00Z",
        },
        {
            "source": "epss_high_confidence",
            "confidence": 0.95,
            "active": True,
            "timestamp": "2026-03-12T11:30:00Z",
        },
    )

    score = score_action_finding(finding, now=datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc))
    signals = score.components["exploit_signals"]["applied_threat_signals"]

    assert 0 <= score.score <= 100
    assert score.components["exploit_signals"]["threat_intel_points_requested"] >= 10
    assert score.components["exploit_signals"]["threat_intel_points_applied"] == 10
    assert len(signals) == 2
    assert signals[0]["applied_points"] == 10
    assert signals[1]["applied_points"] == 0
