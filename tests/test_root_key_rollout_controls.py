from __future__ import annotations

import uuid

from backend.services.root_key_rollout_controls import (
    evaluate_root_key_canary,
    sanitize_operator_override_reason,
)


def test_canary_disabled_allows_all() -> None:
    decision = evaluate_root_key_canary(
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        enabled=False,
    )
    assert decision.allowed is True
    assert decision.reason == "canary_disabled"


def test_canary_percent_zero_denies_non_allowlisted() -> None:
    decision = evaluate_root_key_canary(
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        enabled=True,
        percent=0,
        tenant_allowlist=set(),
        account_allowlist=set(),
    )
    assert decision.allowed is False
    assert decision.reason == "canary_percent_excluded"
    assert isinstance(decision.bucket, int)


def test_canary_percent_full_allows() -> None:
    decision = evaluate_root_key_canary(
        tenant_id=uuid.uuid4(),
        account_id="029037611564",
        enabled=True,
        percent=100,
        tenant_allowlist=set(),
        account_allowlist=set(),
    )
    assert decision.allowed is True
    assert decision.reason == "canary_percent_selected"


def test_canary_allowlist_bypasses_percent() -> None:
    tenant_id = uuid.uuid4()
    decision = evaluate_root_key_canary(
        tenant_id=tenant_id,
        account_id="029037611564",
        enabled=True,
        percent=0,
        tenant_allowlist={str(tenant_id)},
        account_allowlist=set(),
    )
    assert decision.allowed is True
    assert decision.reason == "canary_allowlist"
    assert decision.matched_allowlist is True


def test_canary_bucket_is_deterministic_for_same_scope() -> None:
    tenant_id = uuid.uuid4()
    first = evaluate_root_key_canary(
        tenant_id=tenant_id,
        account_id="029037611564",
        enabled=True,
        percent=50,
        tenant_allowlist=set(),
        account_allowlist=set(),
    )
    second = evaluate_root_key_canary(
        tenant_id=tenant_id,
        account_id="029037611564",
        enabled=True,
        percent=50,
        tenant_allowlist=set(),
        account_allowlist=set(),
    )
    assert first.bucket == second.bucket
    assert first.allowed == second.allowed


def test_operator_override_reason_redacts_secret_like_text() -> None:
    reason = sanitize_operator_override_reason("token=AKIAABCDEFGHIJKLMNOP")
    assert reason == "<REDACTED>"


def test_operator_override_reason_normalizes_plain_text() -> None:
    reason = sanitize_operator_override_reason("  manual   approval for canary  ")
    assert reason == "manual approval for canary"
