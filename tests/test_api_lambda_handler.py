from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from backend import lambda_handler


def test_handler_bootstraps_runtime_and_guard_once_per_execution_environment(monkeypatch) -> None:
    guard = MagicMock()
    runtime_handler = MagicMock(return_value={"statusCode": 200})
    built_handler = MagicMock(return_value=runtime_handler)

    monkeypatch.setattr(lambda_handler, "_build_mangum_handler", built_handler)
    monkeypatch.setattr(lambda_handler, "_assert_database_revision_at_head", guard)
    monkeypatch.setattr(lambda_handler, "_DB_GUARD_READY", False)
    monkeypatch.setattr(lambda_handler, "_MANGUM_HANDLER", None)

    assert lambda_handler.handler({"request": 1}, {"ctx": 1}) == {"statusCode": 200}
    assert lambda_handler.handler({"request": 2}, {"ctx": 2}) == {"statusCode": 200}

    built_handler.assert_called_once_with()
    assert guard.call_count == 1
    runtime_handler.assert_any_call({"request": 1}, {"ctx": 1})
    runtime_handler.assert_any_call({"request": 2}, {"ctx": 2})


def test_runtime_bootstrap_imports_backend_main_lazily(monkeypatch) -> None:
    import_module = MagicMock(side_effect=[
        SimpleNamespace(app="fake-app"),
        SimpleNamespace(assert_database_revision_at_head=MagicMock()),
    ])
    mangum = MagicMock(return_value=MagicMock())

    monkeypatch.setattr(lambda_handler, "import_module", import_module)
    monkeypatch.setattr(lambda_handler, "Mangum", mangum)
    monkeypatch.setattr(lambda_handler, "_MANGUM_HANDLER", None)
    monkeypatch.setattr(lambda_handler, "_DB_GUARD_READY", False)

    lambda_handler._ensure_runtime_ready()

    assert import_module.call_args_list[0].args == ("backend.main",)
    assert import_module.call_args_list[1].args == ("backend.services.migration_guard",)
    mangum.assert_called_once_with("fake-app", lifespan="off")
