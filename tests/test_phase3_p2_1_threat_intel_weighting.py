"""Phase 3 P2.1 threat-intelligence weighting regression coverage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.routers.actions import _action_to_detail_response
from backend.services.action_scoring import score_action_finding

_TEST_NOW = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)


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
        owner_type="unassigned",
        owner_key="unassigned",
        owner_label="Unassigned",
        created_at=finding.created_at,
        updated_at=finding.updated_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def test_score_is_unchanged_without_trusted_threat_intel() -> None:
    score = score_action_finding(
        _finding(raw_json={"Vulnerabilities": [{"Id": "CVE-2026-0001"}]}),
        now=_TEST_NOW,
    )

    assert score.score == 0
    assert score.components["exploit_signals"]["points"] == 0
    assert score.components["exploit_signals"]["applied_threat_signals"] == []


def test_kev_signal_raises_priority_and_records_provenance() -> None:
    baseline = score_action_finding(_finding())
    scored = score_action_finding(
        _threat_finding(
            {
                "source": "cisa_kev",
                "confidence": 1.0,
                "timestamp": "2026-03-12T09:30:00Z",
            }
        ),
        now=_TEST_NOW,
    )

    signal = scored.components["exploit_signals"]["applied_threat_signals"][0]

    assert scored.score > baseline.score
    assert scored.components["exploit_signals"]["threat_intel_points_applied"] == 10
    assert signal["source"] == "cisa_kev"
    assert signal["cve_id"] == "CVE-2026-0001"
    assert signal["timestamp"] == "2026-03-12T09:30:00+00:00"
    assert signal["confidence"] == 1.0
    assert signal["applied_points"] == 10
    assert signal["capped"] is False


def test_high_confidence_exploitability_feed_adds_bounded_weight() -> None:
    scored = score_action_finding(
        _threat_finding(
            {
                "source": "epss_high_confidence",
                "confidence": 0.92,
                "active": True,
                "timestamp": "2026-03-12T10:00:00Z",
            }
        ),
        now=_TEST_NOW,
    )

    assert scored.score == 6
    assert scored.components["exploit_signals"]["threat_intel_points_applied"] == 6
    assert scored.components["exploit_signals"]["applied_threat_signals"][0]["source"] == "high_confidence_exploitability"


def test_threat_intel_respects_remaining_exploit_headroom_cap() -> None:
    finding = _threat_finding(
        {
            "source": "cisa_kev",
            "confidence": 1.0,
            "timestamp": "2026-03-12T11:00:00Z",
        },
        control_id="IAM.4",
    )

    score = score_action_finding(finding, now=_TEST_NOW)
    signal = score.components["exploit_signals"]["applied_threat_signals"][0]

    assert score.components["exploit_signals"]["heuristic_points"] == 13
    assert score.components["exploit_signals"]["points"] == 15
    assert score.components["exploit_signals"]["threat_intel_points_requested"] == 10
    assert score.components["exploit_signals"]["threat_intel_points_applied"] == 2
    assert signal["applied_points"] == 2
    assert signal["capped"] is True


def test_missing_or_untrusted_feed_data_fails_closed() -> None:
    malformed = score_action_finding(_finding(raw_json={"ThreatIntel": "not-json"}), now=_TEST_NOW)
    untrusted = score_action_finding(
        _threat_finding(
            {
                "source": "unknown_feed",
                "confidence": 1.0,
                "active": True,
                "timestamp": "2026-03-12T12:00:00Z",
            },
            {
                "source": "epss_high_confidence",
                "confidence": 0.4,
                "active": True,
                "trusted": False,
            },
        ),
        now=_TEST_NOW,
    )

    assert malformed.score == 0
    assert malformed.components["exploit_signals"]["applied_threat_signals"] == []
    assert untrusted.score == 0
    assert untrusted.components["exploit_signals"]["applied_threat_signals"] == []


def test_action_detail_exposes_applied_threat_signal_provenance() -> None:
    finding = _threat_finding(
        {
            "source": "cisa_kev",
            "confidence": 1.0,
            "timestamp": "2026-03-12T09:30:00Z",
        }
    )
    score = score_action_finding(finding, now=_TEST_NOW)
    action = _action_from_score(score, finding)

    response = _action_to_detail_response(action)
    signal = response.score_components["exploit_signals"]["applied_threat_signals"][0]

    assert signal["source"] == "cisa_kev"
    assert signal["timestamp"] == "2026-03-12T09:30:00+00:00"
    assert signal["confidence"] == 1.0
    assert signal["applied_points"] == 10
    factor = next(factor for factor in response.score_factors if factor.factor_name == "exploit_signals")

    assert "0 heuristic points plus 10 decayed threat-intel points" in factor.explanation
    assert "10 heuristic points plus 10 decayed threat-intel points" not in factor.explanation
