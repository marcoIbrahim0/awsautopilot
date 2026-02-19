from __future__ import annotations

import importlib


def test_legacy_worker_imports_resolve_via_shim() -> None:
    module = importlib.import_module("worker.jobs.ingest_findings")
    assert hasattr(module, "execute_ingest_job")
