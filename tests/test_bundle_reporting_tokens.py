from __future__ import annotations

import uuid

import jwt
import pytest

from backend.config import settings
from backend.services.bundle_reporting_tokens import (
    issue_group_run_reporting_token,
    verify_group_run_reporting_token,
)


def test_issue_and_verify_group_run_reporting_token_roundtrip() -> None:
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

    claims = verify_group_run_reporting_token(token)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["group_run_id"] == str(group_run_id)
    assert claims["group_id"] == str(group_id)
    assert claims["jti"] == jti
    assert sorted(claims["allowed_action_ids"]) == sorted(str(v) for v in action_ids)


def test_verify_group_run_reporting_token_requires_allowed_action_ids() -> None:
    token = jwt.encode(
        {
            "tenant_id": str(uuid.uuid4()),
            "group_run_id": str(uuid.uuid4()),
            "group_id": str(uuid.uuid4()),
            "jti": str(uuid.uuid4()),
            "exp": 9999999999,
        },
        settings.BUNDLE_REPORTING_TOKEN_SECRET or settings.JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(ValueError):
        verify_group_run_reporting_token(token)
