from __future__ import annotations

from typing import Any

_SIGNAL_COMPONENTS = {
    "internet_exposure": ("internet_exposure", 15),
    "privilege_weakness": ("privilege_level", 12),
    "sensitive_data": ("data_sensitivity", 12),
    "exploit_signals": ("exploit_signals", 10),
}


def signals_from_score_components(components: dict[str, Any] | None) -> set[str]:
    signals: set[str] = set()
    for signal_name, (component_name, minimum_points) in _SIGNAL_COMPONENTS.items():
        if component_points(components, component_name) >= minimum_points:
            signals.add(signal_name)
    return signals


def component_points(components: dict[str, Any] | None, key: str) -> int:
    payload = components.get(key) if isinstance(components, dict) else None
    if not isinstance(payload, dict):
        return 0
    return int(payload.get("points") or 0)
