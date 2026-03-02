from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from backend.models.enums import RootKeyDependencyStatus, RootKeyRemediationMode, RootKeyRemediationState
from backend.services.root_key_usage_discovery import RootKeyUsageDiscoveryService


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _build_run(*, tenant_id: uuid.UUID) -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        control_id="IAM.4",
        action_id=uuid.uuid4(),
        finding_id=uuid.uuid4(),
        state=RootKeyRemediationState.discovery,
        strategy_id="iam_root_key_disable",
        mode=RootKeyRemediationMode.auto,
        correlation_id="corr-root-key",
    )


def _cloudtrail_event(
    *,
    event_time: datetime,
    service: str,
    action: str,
    source_ip: str = "198.51.100.1",
    user_agent: str = "aws-cli/2.0",
) -> dict[str, Any]:
    payload = {
        "eventSource": service,
        "eventName": action,
        "sourceIPAddress": source_ip,
        "userAgent": user_agent,
        "eventTime": event_time.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
    }
    return {
        "EventSource": service,
        "EventName": action,
        "EventTime": event_time,
        "CloudTrailEvent": json.dumps(payload),
    }


class _FakeCloudTrailClient:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def lookup_events(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if not self._responses:
            return {"Events": []}
        current = self._responses.pop(0)
        if isinstance(current, Exception):
            raise current
        return current


class _FakeSession:
    def __init__(self, cloudtrail_client: _FakeCloudTrailClient) -> None:
        self._cloudtrail_client = cloudtrail_client
        self.region_name_used: str | None = None

    def client(self, service_name: str, *, region_name: str | None = None) -> _FakeCloudTrailClient:
        assert service_name == "cloudtrail"
        self.region_name_used = region_name
        return self._cloudtrail_client


def test_no_usage_case_returns_auto_eligible_and_no_writes(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(tenant_id=tenant_id)
    client = _FakeCloudTrailClient([{"Events": []}])
    session = _FakeSession(client)

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        return run

    async def fake_upsert(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no fingerprints should be persisted when no usage exists")

    module = "backend.services.root_key_usage_discovery"
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.upsert_root_key_dependency_fingerprint", fake_upsert)

    service = RootKeyUsageDiscoveryService(enabled=True, sleep_fn=lambda _: None)
    result = _run(
        service.discover_and_classify(
            db=MagicMock(),
            session_boto=session,
            tenant_id=tenant_id,
            run_id=run.id,
            lookback_minutes=60,
            now=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.fingerprints == []
    assert result.managed_count == 0
    assert result.unknown_count == 0
    assert result.eligible_for_auto_flow is True
    assert result.partial_data is False
    assert client.calls[0]["LookupAttributes"][0]["AttributeValue"] == "Root"
    assert session.region_name_used == "eu-north-1"


def test_all_managed_case_is_deterministic_and_auto_eligible(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(tenant_id=tenant_id)
    late = datetime(2026, 3, 2, 12, 5, tzinfo=timezone.utc)
    early = datetime(2026, 3, 2, 12, 1, tzinfo=timezone.utc)
    client = _FakeCloudTrailClient(
        [
            {
                "Events": [
                    _cloudtrail_event(event_time=late, service="iam.amazonaws.com", action="DeleteAccessKey"),
                ],
                "NextToken": "page-2",
            },
            {
                "Events": [
                    _cloudtrail_event(event_time=early, service="sts.amazonaws.com", action="GetCallerIdentity")
                ]
            },
        ]
    )
    session = _FakeSession(client)
    writes: list[dict[str, Any]] = []

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        return run

    async def fake_upsert(*args: Any, **kwargs: Any) -> Any:
        writes.append(kwargs)
        return MagicMock(), True

    module = "backend.services.root_key_usage_discovery"
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.upsert_root_key_dependency_fingerprint", fake_upsert)

    service = RootKeyUsageDiscoveryService(enabled=True, sleep_fn=lambda _: None)
    result = _run(
        service.discover_and_classify(
            db=MagicMock(),
            session_boto=session,
            tenant_id=tenant_id,
            run_id=run.id,
            lookback_minutes=60,
            now=datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc),
        )
    )

    assert [fp.api_action for fp in result.fingerprints] == ["GetCallerIdentity", "DeleteAccessKey"]
    assert all(fp.classification == "managed" for fp in result.fingerprints)
    assert result.managed_count == 2
    assert result.unknown_count == 0
    assert result.eligible_for_auto_flow is True
    assert all(item["status"] == RootKeyDependencyStatus.pass_ for item in writes)
    assert all(item["unknown_dependency"] is False for item in writes)
    assert len(client.calls) == 2
    assert client.calls[1]["NextToken"] == "page-2"


def test_mixed_managed_and_unknown_case_blocks_auto_flow(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(tenant_id=tenant_id)
    first = datetime(2026, 3, 2, 12, 2, tzinfo=timezone.utc)
    second = datetime(2026, 3, 2, 12, 3, tzinfo=timezone.utc)
    client = _FakeCloudTrailClient(
        [
            {
                "Events": [
                    _cloudtrail_event(event_time=first, service="iam.amazonaws.com", action="ListAccessKeys"),
                    _cloudtrail_event(event_time=second, service="ec2.amazonaws.com", action="DescribeInstances"),
                ]
            }
        ]
    )
    session = _FakeSession(client)
    writes: list[dict[str, Any]] = []

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        return run

    async def fake_upsert(*args: Any, **kwargs: Any) -> Any:
        writes.append(kwargs)
        return MagicMock(), True

    module = "backend.services.root_key_usage_discovery"
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.upsert_root_key_dependency_fingerprint", fake_upsert)

    service = RootKeyUsageDiscoveryService(enabled=True, sleep_fn=lambda _: None)
    result = _run(
        service.discover_and_classify(
            db=MagicMock(),
            session_boto=session,
            tenant_id=tenant_id,
            run_id=run.id,
            lookback_minutes=60,
            now=datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc),
        )
    )

    assert [fp.classification for fp in result.fingerprints] == ["managed", "unknown"]
    assert result.managed_count == 1
    assert result.unknown_count == 1
    assert result.eligible_for_auto_flow is False
    unknown_rows = [item for item in writes if item["unknown_dependency"] is True]
    assert len(unknown_rows) == 1
    assert unknown_rows[0]["unknown_reason"] == "unmanaged_cloudtrail_dependency"
    assert unknown_rows[0]["status"] == RootKeyDependencyStatus.unknown


def test_cloudtrail_transient_failure_retries_and_succeeds(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(tenant_id=tenant_id)
    throttle = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "too many requests"}},
        "LookupEvents",
    )
    client = _FakeCloudTrailClient(
        [
            throttle,
            {
                "Events": [
                    _cloudtrail_event(
                        event_time=datetime(2026, 3, 2, 12, 10, tzinfo=timezone.utc),
                        service="iam.amazonaws.com",
                        action="UpdateAccessKey",
                    )
                ]
            },
        ]
    )
    session = _FakeSession(client)
    writes: list[dict[str, Any]] = []

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        return run

    async def fake_upsert(*args: Any, **kwargs: Any) -> Any:
        writes.append(kwargs)
        return MagicMock(), True

    module = "backend.services.root_key_usage_discovery"
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.upsert_root_key_dependency_fingerprint", fake_upsert)

    service = RootKeyUsageDiscoveryService(enabled=True, retry_attempts=3, sleep_fn=lambda _: None)
    result = _run(
        service.discover_and_classify(
            db=MagicMock(),
            session_boto=session,
            tenant_id=tenant_id,
            run_id=run.id,
            lookback_minutes=60,
            now=datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc),
        )
    )

    assert len(client.calls) == 2
    assert result.retries_used == 1
    assert result.partial_data is False
    assert result.eligible_for_auto_flow is True
    assert len(writes) == 1
    assert writes[0]["status"] == RootKeyDependencyStatus.pass_


def test_tenant_scope_auth_path_fails_closed_when_run_missing(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    client = _FakeCloudTrailClient([{"Events": []}])
    session = _FakeSession(client)

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        return None

    async def fake_upsert(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("persistence must not run when tenant-scoped run is missing")

    module = "backend.services.root_key_usage_discovery"
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.upsert_root_key_dependency_fingerprint", fake_upsert)

    service = RootKeyUsageDiscoveryService(enabled=True, sleep_fn=lambda _: None)
    with_error = None
    try:
        _run(
            service.discover_and_classify(
                db=MagicMock(),
                session_boto=session,
                tenant_id=tenant_id,
                run_id=run_id,
                lookback_minutes=60,
                now=datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc),
            )
        )
    except ValueError as exc:
        with_error = exc

    assert with_error is not None
    assert "not found for tenant" in str(with_error)


def test_retry_safe_replay_produces_stable_fingerprint_hashes(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    run = _build_run(tenant_id=tenant_id)
    fixed_event = _cloudtrail_event(
        event_time=datetime(2026, 3, 2, 12, 20, tzinfo=timezone.utc),
        service="iam.amazonaws.com",
        action="ListAccessKeys",
    )
    client = _FakeCloudTrailClient([{"Events": [fixed_event]}, {"Events": [fixed_event]}])
    session = _FakeSession(client)
    hashes: list[str] = []

    async def fake_get_run(*args: Any, **kwargs: Any) -> Any:
        return run

    async def fake_upsert(*args: Any, **kwargs: Any) -> Any:
        hashes.append(kwargs["fingerprint_hash"])
        return MagicMock(), True

    module = "backend.services.root_key_usage_discovery"
    monkeypatch.setattr(f"{module}.get_root_key_remediation_run", fake_get_run)
    monkeypatch.setattr(f"{module}.upsert_root_key_dependency_fingerprint", fake_upsert)

    service = RootKeyUsageDiscoveryService(enabled=True, sleep_fn=lambda _: None)
    _run(
        service.discover_and_classify(
            db=MagicMock(),
            session_boto=session,
            tenant_id=tenant_id,
            run_id=run.id,
            lookback_minutes=60,
            now=datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc),
        )
    )
    _run(
        service.discover_and_classify(
            db=MagicMock(),
            session_boto=session,
            tenant_id=tenant_id,
            run_id=run.id,
            lookback_minutes=60,
            now=datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc),
        )
    )

    assert len(hashes) == 2
    assert hashes[0] == hashes[1]
