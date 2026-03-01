from __future__ import annotations

import re
from pathlib import Path

from backend.services.control_plane_event_allowlist import SUPPORTED_CONTROL_PLANE_EVENT_NAMES
from backend.services.control_plane_intake import SUPPORTED_CONTROL_PLANE_EVENT_NAMES as INTAKE_EVENT_NAMES
from backend.workers.services.control_plane_events import SUPPORTED_EVENT_NAMES as WORKER_EVENT_NAMES


REPO_ROOT = Path(__file__).resolve().parents[1]
FORWARDER_TEMPLATE_PATH = REPO_ROOT / "infrastructure/cloudformation/control-plane-forwarder-template.yaml"


def _template_event_names() -> set[str]:
    text = FORWARDER_TEMPLATE_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"eventName:\n(?P<body>(?:\s+-\s+\"[A-Za-z0-9.]+\"\n)+)",
        text,
    )
    assert match, "Could not locate EventPattern.detail.eventName block in forwarder template."
    return set(re.findall(r"\"([A-Za-z0-9.]+)\"", match.group("body")))


def test_control_plane_allowlist_parity_across_intake_worker_and_template() -> None:
    canonical = set(SUPPORTED_CONTROL_PLANE_EVENT_NAMES)
    assert set(INTAKE_EVENT_NAMES) == canonical
    assert set(WORKER_EVENT_NAMES) == canonical
    assert _template_event_names() == canonical


def test_s3_bucket_public_access_block_event_names_are_allowlisted() -> None:
    canonical = set(SUPPORTED_CONTROL_PLANE_EVENT_NAMES)
    assert "PutBucketPublicAccessBlock" in canonical
    assert "DeleteBucketPublicAccessBlock" in canonical
