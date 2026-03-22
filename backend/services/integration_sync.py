from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import uuid
from typing import Any

import boto3
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.action import Action
from backend.models.action_external_link import ActionExternalLink
from backend.models.integration_event_receipt import IntegrationEventReceipt
from backend.models.integration_sync_task import IntegrationSyncTask
from backend.models.tenant_integration_setting import TenantIntegrationSetting
from backend.services.integration_adapters import (
    PROVIDER_JIRA,
    PROVIDER_SERVICENOW,
    PROVIDER_SLACK,
    SUPPORTED_INTEGRATION_PROVIDERS,
)
from backend.services.action_remediation_state_machine import (
    EXTERNAL_STATUS_MAPPING_TABLE,
    PREFERRED_EXTERNAL_STATUS_TABLE,
)
from backend.services.action_remediation_sync import (
    apply_canonical_action_status,
    record_external_status_observation,
    record_reconciled_external_status,
)
from backend.utils.sqs import build_integration_sync_job_payload, parse_queue_region

logger = logging.getLogger(__name__)

ACTION_STATUS_OPEN = "open"
ACTION_STATUS_IN_PROGRESS = "in_progress"
ACTION_STATUS_RESOLVED = "resolved"
ACTION_STATUS_SUPPRESSED = "suppressed"
SYNC_STATUS_QUEUED = "queued"
SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_SUCCESS = "success"
SYNC_STATUS_FAILED = "failed"
SYNC_OPERATION_CREATE = "create"
SYNC_OPERATION_UPDATE = "update"
SYNC_OPERATION_REOPEN = "reopen"
OWNER_TYPE_USER = "user"
_SECRET_TOKENS = ("password", "secret", "token", "authorization", "webhook")


@dataclass(frozen=True)
class IntegrationSettingsView:
    provider: str
    enabled: bool
    outbound_enabled: bool
    inbound_enabled: bool
    auto_create: bool
    reopen_on_regression: bool
    config: dict[str, Any]
    secret_configured: bool
    webhook_configured: bool


@dataclass(frozen=True)
class InboundEventResult:
    provider: str
    replayed: bool
    applied: bool
    action_id: uuid.UUID | None
    action_status: str | None
    owner_key: str | None
    receipt_status: str


def normalize_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in SUPPORTED_INTEGRATION_PROVIDERS:
        raise ValueError(f"Unsupported provider '{provider}'.")
    return normalized


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_secret_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_secret_entry(str(key), nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [sanitize_secret_payload(item) for item in value]
    return value


def _sanitize_secret_entry(key: str, value: Any) -> Any:
    lowered = key.strip().lower()
    if any(token in lowered for token in _SECRET_TOKENS):
        return "<REDACTED>"
    return sanitize_secret_payload(value)


def webhook_token_hash(token: str | None) -> str | None:
    normalized = str(token or "").strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _safe_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _non_empty_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _status_map(setting: TenantIntegrationSetting) -> dict[str, str]:
    configured = _safe_dict(_safe_dict(setting.config_json).get("status_mapping"))
    if configured:
        return {str(key): str(value) for key, value in configured.items() if _non_empty_text(value)}
    return dict(PREFERRED_EXTERNAL_STATUS_TABLE.get(setting.provider, {}))


def _inbound_status_map(setting: TenantIntegrationSetting) -> dict[str, str]:
    configured = _safe_dict(_safe_dict(setting.config_json).get("external_status_mapping"))
    if configured:
        return {
            str(key).strip().lower(): str(value)
            for key, value in configured.items()
            if _non_empty_text(value)
        }
    return dict(EXTERNAL_STATUS_MAPPING_TABLE.get(setting.provider, {}))


def _list_settings(session: Session, tenant_id: uuid.UUID) -> list[TenantIntegrationSetting]:
    result = session.execute(
        select(TenantIntegrationSetting).where(TenantIntegrationSetting.tenant_id == tenant_id)
    )
    return result.scalars().all()


def list_integration_settings(session: Session, tenant_id: uuid.UUID) -> list[IntegrationSettingsView]:
    views: list[IntegrationSettingsView] = []
    for row in _list_settings(session, tenant_id):
        secret = _safe_dict(row.secret_json)
        views.append(
            IntegrationSettingsView(
                provider=row.provider,
                enabled=bool(row.enabled),
                outbound_enabled=bool(row.outbound_enabled),
                inbound_enabled=bool(row.inbound_enabled),
                auto_create=bool(row.auto_create),
                reopen_on_regression=bool(row.reopen_on_regression),
                config=_safe_dict(row.config_json),
                secret_configured=bool(secret),
                webhook_configured=bool(_non_empty_text(secret.get("webhook_token"))),
            )
        )
    return sorted(views, key=lambda item: item.provider)


def upsert_integration_setting(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    provider: str,
    enabled: bool | None,
    outbound_enabled: bool | None,
    inbound_enabled: bool | None,
    auto_create: bool | None,
    reopen_on_regression: bool | None,
    config: dict[str, Any] | None,
    secret_config: dict[str, Any] | None,
    clear_secret_config: bool,
) -> TenantIntegrationSetting:
    setting = _get_setting(session, tenant_id=tenant_id, provider=provider)
    if setting is None:
        setting = TenantIntegrationSetting(tenant_id=tenant_id, provider=provider, config_json={})
        session.add(setting)
    _apply_setting_flags(setting, enabled, outbound_enabled, inbound_enabled, auto_create, reopen_on_regression)
    if config is not None:
        setting.config_json = _safe_dict(config)
    if clear_secret_config:
        setting.secret_json = None
        setting.webhook_token_hash = None
    elif secret_config is not None:
        sanitized = sanitize_secret_payload(secret_config)
        setting.secret_json = _safe_dict(secret_config)
        setting.webhook_token_hash = webhook_token_hash(_safe_dict(secret_config).get("webhook_token"))
        logger.info("Updated integration secret payload provider=%s secret=%s", provider, sanitized)
    session.flush()
    return setting


def _apply_setting_flags(
    setting: TenantIntegrationSetting,
    enabled: bool | None,
    outbound_enabled: bool | None,
    inbound_enabled: bool | None,
    auto_create: bool | None,
    reopen_on_regression: bool | None,
) -> None:
    if enabled is not None:
        setting.enabled = enabled
    if outbound_enabled is not None:
        setting.outbound_enabled = outbound_enabled
    if inbound_enabled is not None:
        setting.inbound_enabled = inbound_enabled
    if auto_create is not None:
        setting.auto_create = auto_create
    if reopen_on_regression is not None:
        setting.reopen_on_regression = reopen_on_regression


def _get_setting(session: Session, *, tenant_id: uuid.UUID, provider: str) -> TenantIntegrationSetting | None:
    result = session.execute(
        select(TenantIntegrationSetting).where(
            TenantIntegrationSetting.tenant_id == tenant_id,
            TenantIntegrationSetting.provider == provider,
        )
    )
    return result.scalar_one_or_none()


def _eligible_settings(session: Session, tenant_id: uuid.UUID) -> list[TenantIntegrationSetting]:
    result = session.execute(
        select(TenantIntegrationSetting).where(
            TenantIntegrationSetting.tenant_id == tenant_id,
            TenantIntegrationSetting.enabled.is_(True),
            TenantIntegrationSetting.outbound_enabled.is_(True),
        )
    )
    return result.scalars().all()


def plan_manual_action_sync(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    provider: str,
) -> list[uuid.UUID]:
    action = _require_action(session, tenant_id=tenant_id, action_id=action_id)
    setting = _require_enabled_setting(session, tenant_id=tenant_id, provider=provider)
    link = _link_for_action(session, tenant_id=tenant_id, action_id=action_id, provider=provider)
    created = _maybe_create_sync_task(
        session,
        action=action,
        setting=setting,
        link=link,
        operation=_operation_for_action(action=action, link=link, setting=setting, reopened=False, manual=True),
        trigger="api.manual_sync",
    )
    return [created.id] if created is not None else []


def plan_action_sync_tasks(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action_ids: list[uuid.UUID],
    reopened_action_ids: set[uuid.UUID] | None,
    trigger: str,
) -> list[uuid.UUID]:
    actions = _actions_by_id(session, tenant_id=tenant_id, action_ids=action_ids)
    links = _links_for_actions(session, tenant_id=tenant_id, action_ids=action_ids)
    tasks: list[uuid.UUID] = []
    for setting in _eligible_settings(session, tenant_id):
        for action_id in action_ids:
            action = actions.get(action_id)
            if action is None:
                continue
            link = links.get((action_id, setting.provider))
            reopened = action_id in (reopened_action_ids or set())
            task = _maybe_create_sync_task(
                session,
                action=action,
                setting=setting,
                link=link,
                operation=_operation_for_action(action=action, link=link, setting=setting, reopened=reopened, manual=False),
                trigger=trigger,
            )
            if task is not None:
                tasks.append(task.id)
    return tasks


def _actions_by_id(session: Session, *, tenant_id: uuid.UUID, action_ids: list[uuid.UUID]) -> dict[uuid.UUID, Action]:
    if not action_ids:
        return {}
    result = session.execute(
        select(Action).where(Action.tenant_id == tenant_id, Action.id.in_(action_ids))
    )
    return {row.id: row for row in result.scalars().all()}


def _links_for_actions(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action_ids: list[uuid.UUID],
) -> dict[tuple[uuid.UUID, str], ActionExternalLink]:
    if not action_ids:
        return {}
    result = session.execute(
        select(ActionExternalLink).where(
            ActionExternalLink.tenant_id == tenant_id,
            ActionExternalLink.action_id.in_(action_ids),
        )
    )
    return {(row.action_id, row.provider): row for row in result.scalars().all()}


def _maybe_create_sync_task(
    session: Session,
    *,
    action: Action,
    setting: TenantIntegrationSetting,
    link: ActionExternalLink | None,
    operation: str | None,
    trigger: str,
) -> IntegrationSyncTask | None:
    if not operation:
        return None
    payload = _build_sync_payload(action=action, setting=setting, link=link, operation=operation)
    signature = _request_signature(provider=setting.provider, payload=payload)
    task = _existing_sync_task(session, tenant_id=action.tenant_id, signature=signature)
    if task is not None:
        if str(task.status or "").strip().lower() == SYNC_STATUS_FAILED:
            return _requeue_failed_sync_task(
                task=task,
                link=link,
                operation=operation,
                trigger=trigger,
                payload=payload,
            )
        return None
    task = IntegrationSyncTask(
        tenant_id=action.tenant_id,
        action_id=action.id,
        link_id=link.id if link else None,
        provider=setting.provider,
        operation=operation,
        status=SYNC_STATUS_QUEUED,
        trigger=trigger,
        request_signature=signature,
        payload_json=payload,
    )
    session.add(task)
    session.flush()
    return task


def _requeue_failed_sync_task(
    *,
    task: IntegrationSyncTask,
    link: ActionExternalLink | None,
    operation: str,
    trigger: str,
    payload: dict[str, Any],
) -> IntegrationSyncTask:
    task.link_id = link.id if link else None
    task.operation = operation
    task.status = SYNC_STATUS_QUEUED
    task.trigger = trigger
    task.payload_json = payload
    task.result_json = None
    task.last_error = None
    task.started_at = None
    task.completed_at = None
    return task


def _operation_for_action(
    *,
    action: Action,
    link: ActionExternalLink | None,
    setting: TenantIntegrationSetting,
    reopened: bool,
    manual: bool,
) -> str | None:
    if link is None and not (manual or setting.auto_create):
        return None
    if link is None:
        return SYNC_OPERATION_CREATE
    if reopened and setting.reopen_on_regression:
        return SYNC_OPERATION_REOPEN
    return SYNC_OPERATION_UPDATE


def _build_sync_payload(
    *,
    action: Action,
    setting: TenantIntegrationSetting,
    link: ActionExternalLink | None,
    operation: str,
) -> dict[str, Any]:
    external_status = _status_map(setting).get(action.status, action.status)
    payload = {
        "action_id": str(action.id),
        "action_status": action.status,
        "title": action.title,
        "description": action.description or action.title,
        "external_status": external_status,
        "external_assignee_key": _owner_key(action),
        "external_assignee_label": _owner_label(action),
        "operation": operation,
    }
    if link is not None:
        payload.update(_link_payload(link))
    return payload


def _owner_key(action: Action) -> str | None:
    if _non_empty_text(getattr(action, "owner_type", None)) != OWNER_TYPE_USER:
        return None
    return _non_empty_text(getattr(action, "owner_key", None))


def _owner_label(action: Action) -> str | None:
    if _non_empty_text(getattr(action, "owner_type", None)) != OWNER_TYPE_USER:
        return None
    return _non_empty_text(getattr(action, "owner_label", None))


def _link_payload(link: ActionExternalLink) -> dict[str, Any]:
    metadata = _safe_dict(link.metadata_json)
    return {
        "external_id": link.external_id,
        "external_key": link.external_key or link.external_id,
        "external_url": link.external_url,
        "channel_id": metadata.get("channel"),
        "message_ts": metadata.get("message_ts"),
    }


def _existing_sync_task(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    signature: str,
) -> IntegrationSyncTask | None:
    result = session.execute(
        select(IntegrationSyncTask).where(
            IntegrationSyncTask.tenant_id == tenant_id,
            IntegrationSyncTask.request_signature == signature,
        )
    )
    return result.scalar_one_or_none()


def _request_signature(*, provider: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps({"provider": provider, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_action(session: Session, *, tenant_id: uuid.UUID, action_id: uuid.UUID) -> Action:
    result = session.execute(
        select(Action).where(Action.tenant_id == tenant_id, Action.id == action_id)
    )
    action = result.scalar_one_or_none()
    if action is None:
        raise ValueError(f"Action not found: {action_id}")
    return action


def _require_enabled_setting(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    provider: str,
) -> TenantIntegrationSetting:
    setting = _get_setting(session, tenant_id=tenant_id, provider=provider)
    if setting is None or not setting.enabled or not setting.outbound_enabled:
        raise ValueError(f"Integration provider '{provider}' is not enabled for outbound sync.")
    return setting


def _link_for_action(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    provider: str,
) -> ActionExternalLink | None:
    result = session.execute(
        select(ActionExternalLink).where(
            ActionExternalLink.tenant_id == tenant_id,
            ActionExternalLink.action_id == action_id,
            ActionExternalLink.provider == provider,
        )
    )
    return result.scalar_one_or_none()


def dispatch_sync_tasks(task_ids: list[uuid.UUID], *, tenant_id: uuid.UUID) -> dict[str, Any]:
    queue_url = str(settings.SQS_INGEST_QUEUE_URL or "").strip()
    if not queue_url:
        return {"requested": len(task_ids), "enqueued": 0, "failed": len(task_ids), "task_ids": task_ids}
    queue_region = parse_queue_region(queue_url)
    sqs = boto3.client("sqs", region_name=queue_region)
    enqueued = 0
    for task_id in task_ids:
        payload = build_integration_sync_job_payload(task_id=task_id, tenant_id=tenant_id, created_at=utcnow().isoformat())
        try:
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            enqueued += 1
        except Exception:
            logger.warning("Failed to enqueue integration sync task task_id=%s", task_id, exc_info=True)
    return {"requested": len(task_ids), "enqueued": enqueued, "failed": max(0, len(task_ids) - enqueued), "task_ids": task_ids}


def resolve_setting_for_webhook(
    session: Session,
    *,
    provider: str,
    webhook_token: str,
) -> TenantIntegrationSetting | None:
    token_hash = webhook_token_hash(webhook_token)
    if token_hash is None:
        return None
    result = session.execute(
        select(TenantIntegrationSetting).where(
            TenantIntegrationSetting.provider == provider,
            TenantIntegrationSetting.enabled.is_(True),
            TenantIntegrationSetting.inbound_enabled.is_(True),
            TenantIntegrationSetting.webhook_token_hash == token_hash,
        )
    )
    return result.scalar_one_or_none()


def process_inbound_event(
    session: Session,
    *,
    provider: str,
    webhook_token: str,
    event: dict[str, Any],
    event_id: str | None = None,
) -> InboundEventResult:
    setting = resolve_setting_for_webhook(session, provider=provider, webhook_token=webhook_token)
    if setting is None:
        raise ValueError("Webhook token did not match an enabled integration.")
    normalized = _normalize_inbound_event(provider=provider, event=event, event_id=event_id)
    receipt = _receipt_by_key(session, tenant_id=setting.tenant_id, provider=provider, receipt_key=normalized["receipt_key"])
    if receipt is not None:
        return _replayed_result(provider=provider, receipt=receipt)
    try:
        receipt = _create_receipt(
            session,
            tenant_id=setting.tenant_id,
            provider=provider,
            normalized=normalized,
        )
    except IntegrityError:
        session.rollback()
        replayed = _receipt_by_key(
            session,
            tenant_id=setting.tenant_id,
            provider=provider,
            receipt_key=normalized["receipt_key"],
        )
        if replayed is not None:
            return _replayed_result(provider=provider, receipt=replayed)
        raise
    link = _find_link_for_inbound(session, tenant_id=setting.tenant_id, provider=provider, external_id=normalized["external_id"])
    if link is None:
        _finalize_receipt(
            receipt,
            normalized=normalized,
            action_id=None,
            status="ignored",
            result={"reason": "link_not_found"},
        )
        return InboundEventResult(provider=provider, replayed=False, applied=False, action_id=None, action_status=None, owner_key=None, receipt_status="ignored")
    if _is_stale_inbound(link=link, occurred_at=normalized["occurred_at"]):
        _finalize_receipt(
            receipt,
            normalized=normalized,
            action_id=link.action_id,
            status="ignored",
            result={"reason": "stale_event"},
        )
        return InboundEventResult(provider=provider, replayed=False, applied=False, action_id=link.action_id, action_status=None, owner_key=None, receipt_status="ignored")
    action = _require_action(session, tenant_id=setting.tenant_id, action_id=link.action_id)
    sync_result = None
    if normalized["external_status"] is not None:
        sync_result = _record_inbound_status(
            session,
            action=action,
            provider=provider,
            normalized=normalized,
            action_status=None,
        )
    owner_key = _apply_inbound_assignee(action=action, external_key=normalized["external_assignee_key"], external_label=normalized["external_assignee_label"])
    _update_link_from_inbound(link=link, normalized=normalized)
    _finalize_receipt(
        receipt,
        normalized=normalized,
        action_id=action.id,
        status="processed",
        result={
            "action_status": action.status,
            "owner_key": owner_key,
            "sync_status": getattr(sync_result, "sync_status", None),
            "mapped_internal_status": getattr(sync_result, "mapped_internal_status", None),
            "resolution_decision": getattr(sync_result, "resolution_decision", None),
        },
    )
    return InboundEventResult(
        provider=provider,
        replayed=False,
        applied=bool(sync_result or owner_key),
        action_id=action.id,
        action_status=action.status,
        owner_key=owner_key,
        receipt_status="processed",
    )


def _normalize_inbound_event(
    *,
    provider: str,
    event: dict[str, Any],
    event_id: str | None,
) -> dict[str, Any]:
    if provider == PROVIDER_JIRA:
        return _normalize_jira_event(event=event, event_id=event_id)
    if provider == PROVIDER_SERVICENOW:
        return _normalize_servicenow_event(event=event, event_id=event_id)
    if provider == PROVIDER_SLACK:
        return _normalize_slack_event(event=event, event_id=event_id)
    raise ValueError(f"Unsupported provider '{provider}'.")


def _normalize_jira_event(*, event: dict[str, Any], event_id: str | None) -> dict[str, Any]:
    issue = _safe_dict(event.get("issue"))
    fields = _safe_dict(issue.get("fields"))
    assignee = _safe_dict(fields.get("assignee"))
    external_id = _non_empty_text(issue.get("id")) or _non_empty_text(issue.get("key")) or ""
    return _normalized_event(
        receipt_key=event_id or _non_empty_text(event.get("webhookEvent")) or external_id,
        external_id=external_id,
        external_status=_non_empty_text(_safe_dict(fields.get("status")).get("name")),
        external_assignee_key=_non_empty_text(assignee.get("accountId")) or _non_empty_text(assignee.get("name")),
        external_assignee_label=_non_empty_text(assignee.get("displayName")),
        occurred_at=_parse_datetime(_non_empty_text(fields.get("updated")) or _non_empty_text(event.get("timestamp"))),
        payload=event,
    )


def _normalize_servicenow_event(*, event: dict[str, Any], event_id: str | None) -> dict[str, Any]:
    result = _safe_dict(event.get("result"))
    assignee = result.get("assigned_to")
    external_assignee_key = _extract_servicenow_field(assignee, "value")
    external_assignee_label = _extract_servicenow_field(assignee, "display_value")
    external_id = _non_empty_text(result.get("sys_id")) or _non_empty_text(event.get("external_id")) or ""
    return _normalized_event(
        receipt_key=event_id or _non_empty_text(event.get("sys_id")) or external_id,
        external_id=external_id,
        external_status=_extract_servicenow_field(result.get("state"), "display_value") or _extract_servicenow_field(result.get("state"), "value"),
        external_assignee_key=external_assignee_key,
        external_assignee_label=external_assignee_label,
        occurred_at=_parse_datetime(_non_empty_text(result.get("sys_updated_on"))),
        payload=event,
    )


def _normalize_slack_event(*, event: dict[str, Any], event_id: str | None) -> dict[str, Any]:
    metadata = _safe_dict(_safe_dict(event.get("metadata")).get("event_payload"))
    channel = _non_empty_text(event.get("channel")) or _non_empty_text(_safe_dict(event.get("container")).get("channel_id")) or ""
    message_ts = _non_empty_text(event.get("message_ts")) or _non_empty_text(_safe_dict(event.get("message")).get("ts")) or ""
    external_id = f"{channel}:{message_ts}" if channel and message_ts else message_ts
    return _normalized_event(
        receipt_key=event_id or _non_empty_text(event.get("event_id")) or external_id,
        external_id=external_id,
        external_status=_non_empty_text(metadata.get("status")) or _non_empty_text(event.get("status")),
        external_assignee_key=_non_empty_text(metadata.get("assignee_key")) or _non_empty_text(event.get("assignee_key")),
        external_assignee_label=_non_empty_text(metadata.get("assignee_label")) or _non_empty_text(event.get("assignee_label")),
        occurred_at=_parse_datetime(_non_empty_text(event.get("event_ts"))),
        payload=event,
    )


def _normalized_event(
    *,
    receipt_key: str | None,
    external_id: str,
    external_status: str | None,
    external_assignee_key: str | None,
    external_assignee_label: str | None,
    occurred_at: datetime | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    receipt = _non_empty_text(receipt_key) or hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "receipt_key": receipt,
        "external_id": external_id,
        "external_status": external_status,
        "external_assignee_key": external_assignee_key,
        "external_assignee_label": external_assignee_label,
        "occurred_at": occurred_at,
        "payload_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest(),
        "result_payload": sanitize_secret_payload(payload),
    }


def _extract_servicenow_field(value: object, field_name: str) -> str | None:
    if isinstance(value, dict):
        return _non_empty_text(value.get(field_name))
    return _non_empty_text(value)


def _parse_datetime(value: str | None) -> datetime | None:
    normalized = _non_empty_text(value)
    if normalized is None:
        return None
    if normalized.isdigit():
        return datetime.fromtimestamp(float(normalized), tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _receipt_by_key(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    provider: str,
    receipt_key: str,
) -> IntegrationEventReceipt | None:
    result = session.execute(
        select(IntegrationEventReceipt).where(
            IntegrationEventReceipt.tenant_id == tenant_id,
            IntegrationEventReceipt.provider == provider,
            IntegrationEventReceipt.receipt_key == receipt_key,
        )
    )
    return result.scalar_one_or_none()


def _find_link_for_inbound(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    provider: str,
    external_id: str,
) -> ActionExternalLink | None:
    if not external_id:
        return None
    result = session.execute(
        select(ActionExternalLink).where(
            ActionExternalLink.tenant_id == tenant_id,
            ActionExternalLink.provider == provider,
            or_(
                ActionExternalLink.external_id == external_id,
                ActionExternalLink.external_key == external_id,
            ),
        )
    )
    return result.scalar_one_or_none()


def _is_stale_inbound(*, link: ActionExternalLink, occurred_at: datetime | None) -> bool:
    if occurred_at is None or link.last_inbound_event_at is None:
        return False
    return occurred_at <= link.last_inbound_event_at


def _apply_inbound_assignee(
    *,
    action: Action,
    external_key: str | None,
    external_label: str | None,
) -> str | None:
    owner_key = _non_empty_text(external_key)
    if owner_key is None:
        return None
    action.owner_type = OWNER_TYPE_USER
    action.owner_key = owner_key
    action.owner_label = _non_empty_text(external_label) or owner_key
    return owner_key


def _update_link_from_inbound(*, link: ActionExternalLink, normalized: dict[str, Any]) -> None:
    link.external_status = normalized["external_status"]
    link.external_assignee_key = normalized["external_assignee_key"]
    link.external_assignee_label = normalized["external_assignee_label"]
    link.last_inbound_at = utcnow()
    if normalized["occurred_at"] is not None:
        link.last_inbound_event_at = normalized["occurred_at"]


def _record_inbound_status(
    session: Session,
    *,
    action: Action,
    provider: str,
    normalized: dict[str, Any],
    action_status: str | None,
) -> Any:
    payload = {"occurred_at": normalized["occurred_at"].isoformat() if normalized["occurred_at"] else None}
    if action_status is not None:
        return record_reconciled_external_status(
            session,
            action=action,
            provider=provider,
            external_status=normalized["external_status"],
            external_ref=normalized["external_id"],
            idempotency_key=f"inbound:{provider}:{normalized['receipt_key']}:reconciled",
            payload=payload,
        )
    return record_external_status_observation(
        session,
        action=action,
        provider=provider,
        external_status=normalized["external_status"],
        external_ref=normalized["external_id"],
        idempotency_key=f"inbound:{provider}:{normalized['receipt_key']}:observed",
        payload=payload,
    )


def _create_receipt(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    provider: str,
    normalized: dict[str, Any],
) -> IntegrationEventReceipt:
    receipt = IntegrationEventReceipt(
        tenant_id=tenant_id,
        provider=provider,
        receipt_key=normalized["receipt_key"],
        external_id=normalized["external_id"],
        action_id=None,
        payload_hash=normalized["payload_hash"],
        status="processing",
        occurred_at=normalized["occurred_at"],
        result_json={"payload": normalized["result_payload"]},
    )
    session.add(receipt)
    session.flush()
    return receipt


def _finalize_receipt(
    receipt: IntegrationEventReceipt,
    *,
    normalized: dict[str, Any],
    action_id: uuid.UUID | None,
    status: str,
    result: dict[str, Any],
) -> None:
    receipt.external_id = normalized["external_id"]
    receipt.action_id = action_id
    receipt.payload_hash = normalized["payload_hash"]
    receipt.status = status
    receipt.occurred_at = normalized["occurred_at"]
    receipt.result_json = {"result": result, "payload": normalized["result_payload"]}


def _replayed_result(
    *,
    provider: str,
    receipt: IntegrationEventReceipt,
) -> InboundEventResult:
    result_payload = _safe_dict(_safe_dict(receipt.result_json).get("result"))
    return InboundEventResult(
        provider=provider,
        replayed=True,
        applied=False,
        action_id=receipt.action_id,
        action_status=_non_empty_text(result_payload.get("action_status")),
        owner_key=_non_empty_text(result_payload.get("owner_key")),
        receipt_status=receipt.status,
    )


def get_sync_task(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
) -> IntegrationSyncTask | None:
    result = session.execute(
        select(IntegrationSyncTask).where(
            IntegrationSyncTask.tenant_id == tenant_id,
            IntegrationSyncTask.id == task_id,
        )
    )
    return result.scalar_one_or_none()


def mark_sync_task_running(session: Session, task: IntegrationSyncTask) -> None:
    task.attempt_count = int(task.attempt_count or 0) + 1
    task.status = SYNC_STATUS_RUNNING
    task.started_at = utcnow()
    task.completed_at = None
    session.flush()


def complete_sync_task(
    session: Session,
    *,
    task: IntegrationSyncTask,
    result: dict[str, Any],
) -> ActionExternalLink:
    link = _upsert_external_link(session, task=task, result=result)
    action = _require_action(session, tenant_id=task.tenant_id, action_id=task.action_id)
    record_reconciled_external_status(
        session,
        action=action,
        provider=task.provider,
        external_status=link.external_status,
        external_ref=link.external_id,
        idempotency_key=f"integration_sync_task:{task.id}:success",
        payload={"task_id": str(task.id), "operation": task.operation, "result": result},
    )
    task.link_id = link.id
    task.status = SYNC_STATUS_SUCCESS
    task.result_json = result
    task.last_error = None
    task.completed_at = utcnow()
    session.flush()
    return link


def fail_sync_task(
    session: Session,
    *,
    task: IntegrationSyncTask,
    message: str,
) -> None:
    task.status = SYNC_STATUS_FAILED
    task.last_error = message[:500]
    task.completed_at = utcnow()
    session.flush()


def get_sync_runtime(
    session: Session,
    *,
    task: IntegrationSyncTask,
) -> tuple[TenantIntegrationSetting, ActionExternalLink | None]:
    setting = _require_enabled_setting(session, tenant_id=task.tenant_id, provider=task.provider)
    link = _link_for_task(session, task)
    return setting, link


def _link_for_task(session: Session, task: IntegrationSyncTask) -> ActionExternalLink | None:
    if task.link_id is not None:
        result = session.execute(
            select(ActionExternalLink).where(
                ActionExternalLink.tenant_id == task.tenant_id,
                ActionExternalLink.id == task.link_id,
            )
        )
        link = result.scalar_one_or_none()
        if link is not None:
            return link
    return _link_for_action(session, tenant_id=task.tenant_id, action_id=task.action_id, provider=task.provider)


def _upsert_external_link(
    session: Session,
    *,
    task: IntegrationSyncTask,
    result: dict[str, Any],
) -> ActionExternalLink:
    link = _link_for_task(session, task)
    if link is None:
        link = ActionExternalLink(tenant_id=task.tenant_id, action_id=task.action_id, provider=task.provider)
        session.add(link)
    metadata = _safe_dict(link.metadata_json)
    metadata.update(_safe_dict(result.get("metadata")))
    link.external_id = _non_empty_text(result.get("external_id")) or link.external_id
    link.external_key = _non_empty_text(result.get("external_key")) or link.external_key
    link.external_url = _non_empty_text(result.get("external_url")) or link.external_url
    link.external_status = _non_empty_text(result.get("external_status")) or link.external_status
    link.external_assignee_key = _non_empty_text(result.get("external_assignee_key")) or link.external_assignee_key
    link.external_assignee_label = _non_empty_text(result.get("external_assignee_label")) or link.external_assignee_label
    link.last_outbound_signature = task.request_signature
    link.last_outbound_at = utcnow()
    link.metadata_json = metadata
    session.flush()
    return link
