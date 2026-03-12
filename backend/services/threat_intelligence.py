"""Threat-intelligence extraction and decay helpers for action scoring."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.config import settings

_RAW_INTEL_KEYS = (
    "threat_intel",
    "threat_intelligence",
    "ThreatIntel",
    "ThreatIntelligence",
    "threatIntel",
)
_PRODUCT_FIELD_KEYS = (
    "aws/autopilot/threat_intel",
    "aws/autopilot/threat_intelligence",
    "threat_intel",
    "threat_intelligence",
)
_OBSERVED_AT_KEYS = (
    "timestamp",
    "observed_at",
    "observedAt",
    "last_seen_at",
    "lastSeenAt",
    "last_observed_at",
    "lastObservedAt",
    "updated_at",
    "updatedAt",
    "published_at",
    "publishedAt",
)
_EXPLICIT_POINTS_KEYS = ("base_contribution", "base_points", "contribution", "points", "weight")
_TRUE_LIKE = frozenset({"1", "active", "true", "yes", "y"})
_THREAT_INTELLIGENCE_FALLBACK_HALF_LIFE_HOURS = 72.0
_TRUSTED_SIGNAL_SOURCES = {
    "cisa_kev": {
        "aliases": ("cisa_kev", "kev", "known_exploited_vulnerabilities", "known_exploited_vulnerability"),
        "label": "CISA KEV",
        "signal_type": "known_exploited_vulnerability",
        "confidence_floor": 0.95,
        "base_points": 10,
    },
    "high_confidence_exploitability": {
        "aliases": (
            "high_confidence_exploitability",
            "epss_high_confidence",
            "trusted_exploitability_feed",
            "vendor_high_confidence_exploitability",
        ),
        "label": "High-confidence exploitability feed",
        "signal_type": "high_confidence_exploitability",
        "confidence_floor": 0.75,
        "base_points": 6,
    },
}
_TRUSTED_SOURCE_BY_ALIAS = {
    alias: source
    for source, rule in _TRUSTED_SIGNAL_SOURCES.items()
    for alias in rule["aliases"]
}


@dataclass(frozen=True)
class ThreatIntelSignal:
    source: str
    source_label: str
    signal_type: str
    identifier: str
    cve_id: str | None
    timestamp: str | None
    confidence: float
    decay_applied: float
    requested_points: int
    base_points: int


def collect_threat_intel_signals(finding: Any, *, now: datetime | None = None) -> tuple[ThreatIntelSignal, ...]:
    raw = getattr(finding, "raw_json", None)
    payload = raw if isinstance(raw, dict) else {}
    resolved_now = _resolved_now(now)
    fallback = _finding_observed_at(finding)
    signals = [
        signal
        for candidate in _signal_candidates(payload)
        if (signal := _build_signal(candidate, fallback, now=resolved_now)) is not None
    ]
    return tuple(sorted(_dedupe_signals(signals), key=_signal_sort_key, reverse=True))


def _signal_candidates(raw: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in _RAW_INTEL_KEYS:
        if key in raw:
            entries.extend(_coerce_entries(raw.get(key)))
    entries.extend(_product_field_entries(raw.get("ProductFields")))
    entries.extend(_vulnerability_signal_entries(raw.get("Vulnerabilities")))
    return entries


def _product_field_entries(product_fields: Any) -> list[dict[str, Any]]:
    if not isinstance(product_fields, dict):
        return []
    entries: list[dict[str, Any]] = []
    for key in _PRODUCT_FIELD_KEYS:
        if key in product_fields:
            entries.extend(_coerce_entries(product_fields.get(key)))
    return entries


def _vulnerability_signal_entries(vulnerabilities: Any) -> list[dict[str, Any]]:
    if not isinstance(vulnerabilities, list):
        return []
    entries: list[dict[str, Any]] = []
    for vulnerability in vulnerabilities:
        entries.extend(_entries_for_vulnerability(vulnerability))
    return entries


def _entries_for_vulnerability(vulnerability: Any) -> list[dict[str, Any]]:
    if not isinstance(vulnerability, dict):
        return []
    cve_id = _signal_cve_id(vulnerability)
    entries: list[dict[str, Any]] = []
    for key in ("ThreatIntel", "ThreatIntelligence"):
        for entry in _coerce_entries(vulnerability.get(key)):
            entries.append(_entry_with_cve(entry, cve_id))
    if _signal_truthy(vulnerability.get("KnownExploited")) or _signal_truthy(vulnerability.get("known_exploited")):
        entries.append(_entry_with_cve({"source": "cisa_kev", "confidence": 1.0}, cve_id))
    return entries


def _coerce_entries(value: Any) -> list[dict[str, Any]]:
    parsed = _coerce_json(value)
    if isinstance(parsed, dict) and isinstance(parsed.get("entries"), list):
        return [item for item in parsed["entries"] if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def _coerce_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _entry_with_cve(entry: dict[str, Any], cve_id: str | None) -> dict[str, Any]:
    if not cve_id or entry.get("cve_id") or entry.get("cve"):
        return entry
    payload = dict(entry)
    payload["cve_id"] = cve_id
    return payload


def _build_signal(entry: dict[str, Any], fallback: datetime | None, *, now: datetime) -> ThreatIntelSignal | None:
    source = _canonical_source(entry)
    if source is None or not _trusted_active_signal(entry, source):
        return None
    rule = _TRUSTED_SIGNAL_SOURCES[source]
    confidence = _signal_confidence(entry)
    base_points = _entry_points(entry, source)
    requested_points, decay = _decayed_points(base_points, _entry_observed_at(entry) or fallback, now=now)
    identifier = _signal_identifier(entry, source)
    if not identifier:
        return None
    return ThreatIntelSignal(
        source=source,
        source_label=str(rule["label"]),
        signal_type=str(rule["signal_type"]),
        identifier=identifier,
        cve_id=_signal_cve_id(entry),
        timestamp=_signal_timestamp(entry, fallback),
        confidence=confidence,
        decay_applied=decay,
        requested_points=requested_points,
        base_points=base_points,
    )


def _canonical_source(entry: dict[str, Any]) -> str | None:
    for key in ("source", "feed", "provider", "kind", "signal_type"):
        value = str(entry.get(key) or "").strip().lower()
        if value in _TRUSTED_SOURCE_BY_ALIAS:
            return _TRUSTED_SOURCE_BY_ALIAS[value]
    if _signal_truthy(entry.get("KnownExploited")) or _signal_truthy(entry.get("known_exploited")):
        return "cisa_kev"
    return None


def _trusted_active_signal(entry: dict[str, Any], source: str) -> bool:
    if entry.get("trusted") is False:
        return False
    confidence = _signal_confidence(entry)
    if confidence < float(_TRUSTED_SIGNAL_SOURCES[source]["confidence_floor"]):
        return False
    if source == "cisa_kev":
        return True
    return (
        _signal_truthy(entry.get("active"))
        or _signal_truthy(entry.get("exploitable"))
        or _signal_truthy(entry.get("high_confidence"))
    )


def _entry_points(entry: dict[str, Any], source: str) -> int:
    explicit = _explicit_points(entry)
    if explicit is not None:
        return explicit
    return int(_TRUSTED_SIGNAL_SOURCES[source]["base_points"])


def _explicit_points(entry: dict[str, Any]) -> int | None:
    for key in _EXPLICIT_POINTS_KEYS:
        value = entry.get(key)
        if value in (None, ""):
            continue
        try:
            numeric = int(float(value))
        except (TypeError, ValueError):
            continue
        return max(0, min(10, numeric))
    return None


def _signal_identifier(entry: dict[str, Any], source: str) -> str:
    for key in ("signal_id", "identifier", "reference"):
        value = str(entry.get(key) or "").strip()
        if value:
            return value[:160]
    cve_id = _signal_cve_id(entry)
    return cve_id or source


def _signal_cve_id(entry: dict[str, Any]) -> str | None:
    for key in ("cve_id", "cve", "cveId", "Id", "id", "VulnerabilityId", "vulnerability_id"):
        value = str(entry.get(key) or "").strip().upper()
        if value.startswith("CVE-"):
            return value[:64]
    return None


def _signal_confidence(entry: dict[str, Any]) -> float:
    for key in ("confidence", "confidence_score", "score"):
        normalized = _normalized_float(entry.get(key))
        if normalized is not None:
            return normalized
    return 0.0


def _normalized_float(value: Any) -> float | None:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "high":
            return 0.9
        if lowered == "medium":
            return 0.6
        if lowered == "low":
            return 0.3
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric > 1:
        numeric = numeric / 100.0
    return max(0.0, min(1.0, numeric))


def _entry_observed_at(entry: dict[str, Any]) -> datetime | None:
    for key in _OBSERVED_AT_KEYS:
        parsed = _parse_dt(entry.get(key))
        if parsed is not None:
            return parsed
    return None


def _signal_timestamp(entry: dict[str, Any], fallback: datetime | None) -> str | None:
    observed_at = _entry_observed_at(entry) or fallback
    return observed_at.isoformat() if observed_at is not None else None


def _finding_observed_at(finding: Any) -> datetime | None:
    for key in ("last_observed_at", "sh_updated_at", "updated_at", "created_at"):
        parsed = _parse_dt(getattr(finding, key, None))
        if parsed is not None:
            return parsed
    return None


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _decayed_points(base_points: int, observed_at: datetime | None, *, now: datetime) -> tuple[int, float]:
    effective_observed_at = observed_at or now
    age_seconds = max(0.0, (now - effective_observed_at).total_seconds())
    age_hours = age_seconds / 3600 if age_seconds else 0.0
    decay = 0.5 ** (age_hours / _half_life_hours())
    points = int((base_points * decay) + 0.5)
    return max(0, points), round(decay, 4)


def _half_life_hours() -> float:
    raw = getattr(settings, "ACTIONS_THREAT_INTELLIGENCE_HALF_LIFE_HOURS", _THREAT_INTELLIGENCE_FALLBACK_HALF_LIFE_HOURS)
    return max(1.0, float(raw))


def _dedupe_signals(signals: list[ThreatIntelSignal]) -> list[ThreatIntelSignal]:
    seen: set[tuple[str, str, int, str]] = set()
    deduped: list[ThreatIntelSignal] = []
    for signal in signals:
        key = (signal.source, signal.timestamp or "", signal.base_points, signal.identifier)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped


def _signal_sort_key(signal: ThreatIntelSignal) -> tuple[int, float, str, str]:
    return signal.requested_points, signal.confidence, signal.timestamp or "", signal.source


def _resolved_now(now: datetime | None) -> datetime:
    return _parse_dt(now) or datetime.now(timezone.utc)


def _signal_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_LIKE
    return bool(value)
