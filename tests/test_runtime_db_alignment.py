from __future__ import annotations

import importlib.util
from pathlib import Path

from backend.services.migration_guard import RevisionStatus


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_runtime_db_alignment.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_runtime_db_alignment", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runtime_db_alignment_allows_database_behind_runtime() -> None:
    module = _load_module()
    module.get_revision_status = lambda: RevisionStatus(
        expected_heads=("0048_pending", "0049_metadata"),
        current_heads=("0048_pending",),
    )

    ok, message = module.validate_revision_status(require_at_head=False)

    assert ok is True
    assert "db_behind_runtime" in message


def test_runtime_db_alignment_rejects_database_ahead_of_runtime() -> None:
    module = _load_module()
    module.get_revision_status = lambda: RevisionStatus(
        expected_heads=("0049_metadata",),
        current_heads=("0049_metadata", "0050_future"),
    )

    ok, message = module.validate_revision_status(require_at_head=False)

    assert ok is False
    assert "ahead of the runtime artifact" in message


def test_runtime_db_alignment_requires_head_when_requested() -> None:
    module = _load_module()
    module.get_revision_status = lambda: RevisionStatus(
        expected_heads=("0048_pending", "0049_metadata"),
        current_heads=("0048_pending",),
    )

    ok, message = module.validate_revision_status(require_at_head=True)

    assert ok is False
    assert "not at Alembic head" in message
