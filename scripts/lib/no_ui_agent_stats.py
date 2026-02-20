from __future__ import annotations

from datetime import datetime
from typing import Any


SEVERITY_SCORE = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFORMATIONAL": 0,
}


def aggregate_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_control: dict[str, int] = {}
    by_control_open: dict[str, int] = {}
    by_source: dict[str, int] = {}

    for finding in findings:
        status_token = _effective_status_token(finding)
        control_token = _normalize_token(finding.get("control_id"), "UNSPECIFIED")
        _inc(by_status, status_token)
        _inc(by_severity, _normalize_token(finding.get("severity_label"), "UNKNOWN"))
        _inc(by_control, control_token)
        if status_token in {"NEW", "NOTIFIED"}:
            _inc(by_control_open, control_token)
        _inc(by_source, _normalize_token(finding.get("source"), "UNKNOWN"))

    open_count = int(by_status.get("NEW", 0)) + int(by_status.get("NOTIFIED", 0))
    resolved_count = int(by_status.get("RESOLVED", 0))

    return {
        "total": len(findings),
        "by_status": _sort_counts(by_status),
        "by_severity": _sort_counts(by_severity),
        "by_control_id": _sort_counts(by_control),
        "by_control_id_open": _sort_counts(by_control_open),
        "by_source": _sort_counts(by_source),
        "open_count": open_count,
        "resolved_count": resolved_count,
    }


def compute_delta(
    pre_summary: dict[str, Any],
    post_summary: dict[str, Any],
    tested_control_id: str | None,
) -> dict[str, Any]:
    pre_status = _extract_counts(pre_summary, "by_status")
    post_status = _extract_counts(post_summary, "by_status")
    pre_severity = _extract_counts(pre_summary, "by_severity")
    post_severity = _extract_counts(post_summary, "by_severity")
    pre_control = _extract_counts(pre_summary, "by_control_id")
    post_control = _extract_counts(post_summary, "by_control_id")
    pre_control_open = _extract_counts(pre_summary, "by_control_id_open")
    post_control_open = _extract_counts(post_summary, "by_control_id_open")

    open_pre = int(pre_status.get("NEW", 0)) + int(pre_status.get("NOTIFIED", 0))
    open_post = int(post_status.get("NEW", 0)) + int(post_status.get("NOTIFIED", 0))
    resolved_pre = int(pre_status.get("RESOLVED", 0))
    resolved_post = int(post_status.get("RESOLVED", 0))

    control_key = _normalize_token(tested_control_id, "UNSPECIFIED")
    control_open_pre, control_open_post = _control_open_pair(
        control_key,
        pre_control_open,
        post_control_open,
        pre_control,
        post_control,
    )

    return {
        "status_delta": _delta_map(pre_status, post_status),
        "severity_delta": _delta_map(pre_severity, post_severity),
        "control_delta": _delta_map(pre_control, post_control),
        "kpis": {
            "open_drop": open_pre - open_post,
            "resolved_gain": resolved_post - resolved_pre,
            "tested_control_delta": control_open_post - control_open_pre,
            "tested_control_id": control_key,
        },
    }


def select_target_finding(
    findings: list[dict[str, Any]],
    control_preference: list[str],
) -> dict[str, Any] | None:
    eligible = [f for f in findings if _is_eligible_target(f)]
    if not eligible:
        return None

    preferred = _pick_by_control_preference(eligible, control_preference)
    if preferred is not None:
        return preferred
    return _sort_candidates(eligible)[0]


def select_pr_only_strategy(strategies: list[dict[str, Any]]) -> dict[str, Any] | None:
    recommended = [s for s in strategies if _is_pr_only_no_inputs(s) and bool(s.get("recommended"))]
    if recommended:
        return recommended[0]

    compatible = [s for s in strategies if _is_pr_only_no_inputs(s)]
    if compatible:
        return compatible[0]

    return None


def _is_eligible_target(finding: dict[str, Any]) -> bool:
    status = _normalize_token(finding.get("status"), "")
    has_action = bool(str(finding.get("remediation_action_id") or "").strip())
    return status in {"NEW", "NOTIFIED"} and has_action


def _pick_by_control_preference(
    findings: list[dict[str, Any]],
    control_preference: list[str],
) -> dict[str, Any] | None:
    for control_id in control_preference:
        key = _normalize_token(control_id, "")
        matches = [f for f in findings if _normalize_token(f.get("control_id"), "") == key]
        if matches:
            return _sort_candidates(matches)[0]
    return None


def _sort_candidates(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(findings, key=_candidate_sort_key, reverse=True)


def _candidate_sort_key(finding: dict[str, Any]) -> tuple[int, float]:
    severity = _normalize_token(finding.get("severity_label"), "INFORMATIONAL")
    severity_score = int(SEVERITY_SCORE.get(severity, 0))
    updated = _to_timestamp(finding.get("updated_at_db") or finding.get("updated_at") or finding.get("last_observed_at"))
    return (severity_score, updated)


def _is_pr_only_no_inputs(strategy: dict[str, Any]) -> bool:
    mode = _normalize_token(strategy.get("mode"), "")
    requires_inputs = bool(strategy.get("requires_inputs"))
    return mode == "PR_ONLY" and not requires_inputs


def _to_timestamp(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0


def _extract_counts(summary: dict[str, Any], key: str) -> dict[str, int]:
    source = summary.get(key) if isinstance(summary.get(key), dict) else {}
    return {str(k): int(v) for k, v in source.items() if isinstance(v, int)}


def _control_open_pair(
    control_key: str,
    pre_open: dict[str, int],
    post_open: dict[str, int],
    pre_total: dict[str, int],
    post_total: dict[str, int],
) -> tuple[int, int]:
    if pre_open or post_open:
        return int(pre_open.get(control_key, 0)), int(post_open.get(control_key, 0))
    return int(pre_total.get(control_key, 0)), int(post_total.get(control_key, 0))


def _delta_map(pre: dict[str, int], post: dict[str, int]) -> dict[str, int]:
    keys = sorted(set(pre.keys()) | set(post.keys()))
    return {key: int(post.get(key, 0)) - int(pre.get(key, 0)) for key in keys}


def _inc(counter: dict[str, int], key: str) -> None:
    counter[key] = int(counter.get(key, 0)) + 1


def _normalize_token(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text.upper() if text else fallback


def _effective_status_token(finding: dict[str, Any]) -> str:
    shadow = finding.get("shadow") if isinstance(finding.get("shadow"), dict) else {}
    shadow_norm = _normalize_token(shadow.get("status_normalized"), "")
    if shadow_norm == "RESOLVED":
        return "RESOLVED"
    if shadow_norm == "OPEN":
        canonical = _normalize_token(finding.get("status"), "NEW")
        return canonical if canonical in {"NEW", "NOTIFIED"} else "NEW"
    return _normalize_token(finding.get("status"), "UNKNOWN")


def _sort_counts(counter: dict[str, int]) -> dict[str, int]:
    return {k: int(counter[k]) for k in sorted(counter.keys())}
