from __future__ import annotations

import uuid

import jwt
import pytest

from backend.config import settings
from backend.services.bundle_reporting_tokens import (
    BundleReportingTokenSecretNotConfiguredError,
    issue_group_run_reporting_token,
    verify_group_run_reporting_token,
)


def _claims_payload(
    *,
    tenant_id: uuid.UUID | None = None,
    group_run_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    action_ids: list[uuid.UUID] | None = None,
) -> dict[str, object]:
    return {
        "tenant_id": str(tenant_id or uuid.uuid4()),
        "group_run_id": str(group_run_id or uuid.uuid4()),
        "group_id": str(group_id or uuid.uuid4()),
        "allowed_action_ids": [str(action_id) for action_id in (action_ids or [uuid.uuid4()])],
        "jti": str(uuid.uuid4()),
        "exp": 9999999999,
    }


def test_issue_and_verify_group_run_reporting_token_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BUNDLE_REPORTING_TOKEN_SECRET", "bundle-reporting-secret")
    monkeypatch.setattr(settings, "JWT_SECRET", "jwt-auth-secret")
    tenant_id = uuid.uuid4()
    group_run_id = uuid.uuid4()
    group_id = uuid.uuid4()
    action_ids = [uuid.uuid4(), uuid.uuid4()]

    token, jti, _ = issue_group_run_reporting_token(
        tenant_id=tenant_id,
        group_run_id=group_run_id,
        group_id=group_id,
        allowed_action_ids=action_ids,
        ttl_seconds=3600,
    )

    decoded = jwt.decode(token, "bundle-reporting-secret", algorithms=["HS256"])
    assert decoded["jti"] == jti
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(token, "jwt-auth-secret", algorithms=["HS256"])

    claims = verify_group_run_reporting_token(token)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["group_run_id"] == str(group_run_id)
    assert claims["group_id"] == str(group_id)
    assert claims["jti"] == jti
    assert sorted(claims["allowed_action_ids"]) == sorted(str(v) for v in action_ids)


def test_issue_group_run_reporting_token_requires_dedicated_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BUNDLE_REPORTING_TOKEN_SECRET", "")
    monkeypatch.setattr(settings, "JWT_SECRET", "jwt-auth-secret")

    with pytest.raises(BundleReportingTokenSecretNotConfiguredError, match="BUNDLE_REPORTING_TOKEN_SECRET"):
        issue_group_run_reporting_token(
            tenant_id=uuid.uuid4(),
            group_run_id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            allowed_action_ids=[uuid.uuid4()],
        )


def test_verify_group_run_reporting_token_requires_allowed_action_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BUNDLE_REPORTING_TOKEN_SECRET", "bundle-reporting-secret")
    token = jwt.encode(
        {
            "tenant_id": str(uuid.uuid4()),
            "group_run_id": str(uuid.uuid4()),
            "group_id": str(uuid.uuid4()),
            "jti": str(uuid.uuid4()),
            "exp": 9999999999,
        },
        "bundle-reporting-secret",
        algorithm="HS256",
    )

    with pytest.raises(ValueError):
        verify_group_run_reporting_token(token)


def test_verify_group_run_reporting_token_ignores_jwt_secret_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BUNDLE_REPORTING_TOKEN_SECRET", "bundle-reporting-secret")
    monkeypatch.setattr(settings, "JWT_SECRET", "jwt-auth-secret-v1")

    reporting_token = jwt.encode(
        _claims_payload(),
        "bundle-reporting-secret",
        algorithm="HS256",
    )

    monkeypatch.setattr(settings, "JWT_SECRET", "jwt-auth-secret-v2")
    claims = verify_group_run_reporting_token(reporting_token)
    assert "group_run_id" in claims

    jwt_signed_token = jwt.encode(
        _claims_payload(),
        "jwt-auth-secret-v2",
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        verify_group_run_reporting_token(jwt_signed_token)
