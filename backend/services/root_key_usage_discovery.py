from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.enums import (
    RootKeyDependencyStatus,
    RootKeyRemediationMode,
)
from backend.services.root_key_remediation_store import (
    get_root_key_remediation_run,
    upsert_root_key_dependency_fingerprint,
)

_TRANSIENT_CODES = {
    "InternalError",
    "InternalServiceError",
    "RequestTimeout",
    "RequestTimeoutException",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    "Throttling",
    "ThrottlingException",
}
_FINGERPRINT_TYPE = "root_key_usage_cloudtrail"
_MANAGED = "managed"
_UNKNOWN = "unknown"
_MANAGED_DEPENDENCY_REGISTRY = frozenset(
    {
        ("iam.amazonaws.com", "deleteaccesskey"),
        ("iam.amazonaws.com", "getaccesskeylastused"),
        ("iam.amazonaws.com", "getaccountsummary"),
        ("iam.amazonaws.com", "listaccesskeys"),
        ("iam.amazonaws.com", "updateaccesskey"),
        ("sts.amazonaws.com", "getcalleridentity"),
    }
)


@dataclass(frozen=True)
class RootKeyUsageFingerprint:
    service: str
    api_action: str
    source_ip: str
    user_agent: str
    event_time: str
    classification: str


@dataclass(frozen=True)
class RootKeyUsageDiscoveryResult:
    run_id: uuid.UUID
    fingerprints: list[RootKeyUsageFingerprint]
    managed_count: int
    unknown_count: int
    eligible_for_auto_flow: bool
    partial_data: bool
    retries_used: int


class RootKeyUsageDiscoveryService:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        retry_attempts: int = 3,
        page_size: int = 50,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        default_enabled = (
            settings.ROOT_KEY_SAFE_REMEDIATION_ENABLED
            and settings.ROOT_KEY_SAFE_REMEDIATION_DISCOVERY_ENABLED
        )
        self._enabled = default_enabled if enabled is None else bool(enabled)
        self._retry_attempts = max(1, int(retry_attempts))
        self._page_size = max(1, min(int(page_size), 50))
        self._sleep_fn = sleep_fn

    async def discover_and_classify(
        self,
        db: AsyncSession,
        *,
        session_boto: Any,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        lookback_minutes: int,
        now: datetime | None = None,
    ) -> RootKeyUsageDiscoveryResult:
        self._ensure_enabled()
        run = await self._require_run(db=db, tenant_id=tenant_id, run_id=run_id)
        query_end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        query_start = query_end - timedelta(minutes=max(1, int(lookback_minutes)))
        events, partial_data, retries_used = self._lookup_root_events(
            session_boto=session_boto,
            region=run.region or settings.AWS_REGION,
            query_start=query_start,
            query_end=query_end,
        )
        ordered = self._sorted_fingerprints(events)
        managed_count, unknown_count = await self._persist_fingerprints(
            db=db,
            run=run,
            fingerprints=ordered,
        )
        eligible = unknown_count == 0 and not partial_data
        return RootKeyUsageDiscoveryResult(
            run_id=run.id,
            fingerprints=ordered,
            managed_count=managed_count,
            unknown_count=unknown_count,
            eligible_for_auto_flow=eligible,
            partial_data=partial_data,
            retries_used=retries_used,
        )

    async def _require_run(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> Any:
        run = await get_root_key_remediation_run(db, tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("root-key remediation run not found for tenant")
        return run

    def _lookup_root_events(
        self,
        *,
        session_boto: Any,
        region: str,
        query_start: datetime,
        query_end: datetime,
    ) -> tuple[list[dict[str, Any]], bool, int]:
        client = session_boto.client("cloudtrail", region_name=region)
        events: list[dict[str, Any]] = []
        next_token: str | None = None
        partial_data = False
        retries_used = 0
        while True:
            request = self._lookup_request(
                query_start=query_start,
                query_end=query_end,
                next_token=next_token,
            )
            page, page_retries, page_ok = self._lookup_page_with_retry(client=client, request=request)
            retries_used += page_retries
            if not page_ok:
                partial_data = True
                break
            events.extend(page.get("Events") or [])
            next_token = page.get("NextToken")
            if not next_token:
                break
        return events, partial_data, retries_used

    def _lookup_request(
        self,
        *,
        query_start: datetime,
        query_end: datetime,
        next_token: str | None,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "LookupAttributes": [{"AttributeKey": "Username", "AttributeValue": "Root"}],
            "StartTime": query_start,
            "EndTime": query_end,
            "MaxResults": self._page_size,
        }
        if next_token:
            request["NextToken"] = next_token
        return request

    def _lookup_page_with_retry(
        self,
        *,
        client: Any,
        request: dict[str, Any],
    ) -> tuple[dict[str, Any], int, bool]:
        retries = 0
        attempt = 1
        while True:
            try:
                return client.lookup_events(**request), retries, True
            except ClientError as exc:
                if not self._is_transient(exc) or attempt >= self._retry_attempts:
                    return {"Events": []}, retries, False
                retries += 1
                self._sleep_fn(0.2 * attempt)
                attempt += 1

    def _sorted_fingerprints(self, events: list[dict[str, Any]]) -> list[RootKeyUsageFingerprint]:
        normalized = [self._normalize_event(event) for event in events]
        filtered = [item for item in normalized if item is not None]
        return sorted(
            filtered,
            key=lambda item: (
                item.event_time,
                item.service,
                item.api_action,
                item.source_ip,
                item.user_agent,
            ),
        )

    def _normalize_event(self, event: dict[str, Any]) -> RootKeyUsageFingerprint | None:
        payload = self._parse_cloudtrail_payload(event.get("CloudTrailEvent"))
        service = self._normalize_text(payload.get("eventSource") or event.get("EventSource"))
        api_action = self._normalize_text(payload.get("eventName") or event.get("EventName"))
        if not service or not api_action:
            return None
        source_ip = self._normalize_text(payload.get("sourceIPAddress"), default="unknown")
        user_agent = self._normalize_text(payload.get("userAgent"), default="unknown")
        event_time = self._normalize_event_time(
            payload.get("eventTime"),
            fallback=event.get("EventTime"),
        )
        classification = self._classify(service=service, api_action=api_action)
        return RootKeyUsageFingerprint(
            service=service,
            api_action=api_action,
            source_ip=source_ip,
            user_agent=user_agent,
            event_time=event_time,
            classification=classification,
        )

    async def _persist_fingerprints(
        self,
        *,
        db: AsyncSession,
        run: Any,
        fingerprints: list[RootKeyUsageFingerprint],
    ) -> tuple[int, int]:
        managed_count = 0
        unknown_count = 0
        for fingerprint in fingerprints:
            if fingerprint.classification == _MANAGED:
                managed_count += 1
            else:
                unknown_count += 1
            payload = self._fingerprint_payload(fingerprint)
            await upsert_root_key_dependency_fingerprint(
                db,
                run_id=run.id,
                tenant_id=run.tenant_id,
                account_id=run.account_id,
                region=run.region,
                control_id=run.control_id,
                action_id=run.action_id,
                finding_id=run.finding_id,
                state=run.state,
                status=self._dependency_status(fingerprint.classification),
                strategy_id=run.strategy_id,
                mode=self._coerce_mode(run.mode),
                correlation_id=run.correlation_id,
                fingerprint_type=_FINGERPRINT_TYPE,
                fingerprint_hash=self._fingerprint_hash(payload),
                fingerprint_payload=payload,
                unknown_dependency=fingerprint.classification == _UNKNOWN,
                unknown_reason=self._unknown_reason(fingerprint.classification),
            )
        return managed_count, unknown_count

    def _ensure_enabled(self) -> None:
        if self._enabled:
            return
        raise ValueError("root-key usage discovery is disabled by feature flags")

    def _classify(self, *, service: str, api_action: str) -> str:
        key = (service.lower(), api_action.lower())
        return _MANAGED if key in _MANAGED_DEPENDENCY_REGISTRY else _UNKNOWN

    def _dependency_status(self, classification: str) -> RootKeyDependencyStatus:
        if classification == _MANAGED:
            return RootKeyDependencyStatus.pass_
        return RootKeyDependencyStatus.unknown

    def _coerce_mode(self, mode: Any) -> RootKeyRemediationMode:
        if isinstance(mode, RootKeyRemediationMode):
            return mode
        normalized = self._normalize_text(mode)
        return RootKeyRemediationMode.manual if normalized == "manual" else RootKeyRemediationMode.auto

    def _unknown_reason(self, classification: str) -> str | None:
        if classification == _UNKNOWN:
            return "unmanaged_cloudtrail_dependency"
        return None

    def _fingerprint_payload(self, fingerprint: RootKeyUsageFingerprint) -> dict[str, str]:
        return {
            "api_action": fingerprint.api_action,
            "classification": fingerprint.classification,
            "event_time": fingerprint.event_time,
            "service": fingerprint.service,
            "source_ip": fingerprint.source_ip,
            "user_agent": fingerprint.user_agent,
        }

    def _fingerprint_hash(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _parse_cloudtrail_payload(self, raw_payload: Any) -> dict[str, Any]:
        if not isinstance(raw_payload, str) or not raw_payload.strip():
            return {}
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _normalize_event_time(self, value: Any, *, fallback: Any) -> str:
        parsed = self._to_datetime(value) or self._to_datetime(fallback)
        if parsed is None:
            return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    def _to_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                return None
        return None

    def _normalize_text(self, value: Any, *, default: str = "") -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        return default

    def _is_transient(self, exc: ClientError) -> bool:
        code = (exc.response.get("Error") or {}).get("Code") or ""
        return str(code) in _TRANSIENT_CODES

