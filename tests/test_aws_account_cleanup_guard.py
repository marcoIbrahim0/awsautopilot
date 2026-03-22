from __future__ import annotations

from types import SimpleNamespace

import backend.services.aws_account_cleanup as cleanup_mod


class _SessionStub:
    def client(self, service_name: str):
        assert service_name == "iam"
        return object()


def _mock_account():
    return SimpleNamespace(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/SecurityAutopilotReadRole",
        role_write_arn=None,
    )


def test_cleanup_account_resources_raises_without_authorized_flag() -> None:
    try:
        cleanup_mod.cleanup_account_resources(_mock_account(), external_id="ext-123")
    except cleanup_mod.AwsCleanupError as exc:
        assert "Runtime IAM cleanup is not authorized" in str(exc)
    else:
        raise AssertionError("expected AwsCleanupError")


def test_cleanup_account_resources_proceeds_with_authorized_flag(monkeypatch) -> None:
    monkeypatch.setattr(cleanup_mod, "_assume_first_available_role", lambda **kwargs: _SessionStub())
    monkeypatch.setattr(cleanup_mod, "_candidate_role_names", lambda account: set())
    monkeypatch.setattr(cleanup_mod, "_candidate_policy_names", lambda: set())

    summary = cleanup_mod.cleanup_account_resources(
        _mock_account(),
        external_id="ext-123",
        _authorized=True,
    )

    assert summary == cleanup_mod.CleanupSummary(
        roles_deleted=set(),
        policies_deleted=set(),
        roles_missing=set(),
        policies_missing=set(),
    )
