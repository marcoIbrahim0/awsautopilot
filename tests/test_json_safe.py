from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from backend.workers.services.json_safe import make_json_safe


def test_make_json_safe_converts_nested_datetime_values() -> None:
    raw = {
        "ts": datetime(2026, 2, 7, 7, 48, 35, 728000, tzinfo=timezone.utc),
        "nested": {"values": [datetime(2026, 2, 7, 7, 50, tzinfo=timezone.utc)]},
    }

    safe = make_json_safe(raw)

    assert safe["ts"] == "2026-02-07T07:48:35.728000+00:00"
    assert safe["nested"]["values"][0] == "2026-02-07T07:50:00+00:00"
    json.dumps(safe)


def test_make_json_safe_converts_decimal_values() -> None:
    raw = {"int_like": Decimal("42"), "float_like": Decimal("1.25")}

    safe = make_json_safe(raw)

    assert safe == {"int_like": 42, "float_like": 1.25}
